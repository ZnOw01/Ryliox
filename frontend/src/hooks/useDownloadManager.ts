import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelDownload,
  getBookChapters,
  getFormats,
  getProgress,
  startDownload,
  subscribeProgress,
} from "../lib/api";
import { queryKeys } from "../lib/query-keys";
import type { ProgressResponse } from "../lib/types";
import { useBookStore } from "../store/book-store";

const ACTIVE_STATES = new Set(["queued", "running"]);
const TERMINAL_STATES = new Set(["completed", "error"]);

const RECONNECT_DELAY_MS = 2500;

export type SseStatus = "idle" | "connecting" | "connected" | "reconnecting" | "error";

function isDownloadActive(progress?: ProgressResponse) {
  const status = progress?.status;
  return Boolean(status && ACTIVE_STATES.has(status));
}

function isTerminalProgress(progress?: ProgressResponse) {
  const status = progress?.status;
  return Boolean(status && TERMINAL_STATES.has(status));
}

export function useDownloadManager() {
  const queryClient = useQueryClient();
  const selectedBook = useBookStore((state) => state.selectedBook);
  const format = useBookStore((state) => state.format);
  const setFormat = useBookStore((state) => state.setFormat);
  const skipImages = useBookStore((state) => state.skipImages);
  const setSkipImages = useBookStore((state) => state.setSkipImages);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [selectedChapters, setSelectedChapters] = useState<number[]>([]);
  const [sseStatus, setSseStatus] = useState<SseStatus>("idle");
  const [reconnectToken, setReconnectToken] = useState(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);

  const formatsQuery = useQuery({
    queryKey: queryKeys.formats,
    queryFn: getFormats,
  });

  const progressQueryKey = queryKeys.downloadProgress(activeJobId);

  const progressQuery = useQuery({
    queryKey: progressQueryKey,
    queryFn: () => getProgress(activeJobId),
    enabled: true,
    refetchInterval: ({ state }) => {
      const next = state.data as ProgressResponse | undefined;
      return next && !isTerminalProgress(next) ? 8000 : false;
    },
  });

  useEffect(() => {
    const progressJobId = progressQuery.data?.job_id ?? null;
    if (!progressJobId) {
      return;
    }
    if (activeJobId === progressJobId) {
      return;
    }
    setActiveJobId(progressJobId);
  }, [activeJobId, progressQuery.data?.job_id]);

  const chaptersQuery = useQuery({
    queryKey: queryKeys.bookChapters(selectedBook?.id ?? null),
    queryFn: () => getBookChapters(selectedBook?.id ?? ""),
    enabled: Boolean(selectedBook?.id),
  });

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const progressStatus = progressQuery.data?.status ?? "idle";
  const shouldTrackProgress = Boolean(activeJobId) && !isTerminalProgress(progressQuery.data);

  useEffect(() => {
    if (!shouldTrackProgress) {
      reconnectAttemptRef.current = 0;
      clearReconnectTimer();
      if (progressStatus === "completed") {
        setSseStatus("connected");
      } else if (progressStatus === "error") {
        setSseStatus("error");
      } else if (!progressQuery.data?.job_id) {
        setSseStatus("idle");
      }
      return;
    }

    let disposed = false;
    let closed = false;
    let unsubscribe = () => {};

    const closeConnection = () => {
      if (closed) {
        return;
      }
      closed = true;
      unsubscribe();
    };

    const scheduleReconnect = () => {
      if (disposed || reconnectTimerRef.current) {
        return;
      }
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        if (disposed) {
          return;
        }
        setReconnectToken((current) => current + 1);
      }, RECONNECT_DELAY_MS);
    };

    setSseStatus(reconnectAttemptRef.current > 0 ? "reconnecting" : "connecting");

    unsubscribe = subscribeProgress({
      onProgress: (next) => {
        const nextJobId = next.job_id ?? null;
        if (!activeJobId && nextJobId) {
          setActiveJobId(nextJobId);
        }
        queryClient.setQueryData(progressQueryKey, next);
        if (nextJobId) {
          queryClient.setQueryData(queryKeys.downloadProgress(nextJobId), next);
        }
      },
      onOpen: () => {
        reconnectAttemptRef.current = 0;
        setSseStatus("connected");
        clearReconnectTimer();
      },
      onError: () => {
        if (disposed) {
          return;
        }
        setSseStatus("error");
        closeConnection();
        scheduleReconnect();
      },
    }, activeJobId);

    return () => {
      disposed = true;
      clearReconnectTimer();
      closeConnection();
    };
  }, [
    activeJobId,
    clearReconnectTimer,
    progressQuery.data?.job_id,
    progressStatus,
    progressQueryKey,
    queryClient,
    reconnectToken,
    shouldTrackProgress,
  ]);

  const forceReconnect = useCallback(() => {
    if (!shouldTrackProgress) {
      return;
    }
    clearReconnectTimer();
    reconnectAttemptRef.current += 1;
    setSseStatus("reconnecting");
    setReconnectToken((current) => current + 1);
  }, [clearReconnectTimer, shouldTrackProgress]);

  useEffect(() => {
    setSelectedChapters([]);
  }, [selectedBook?.id]);

  useEffect(() => {
    if (!chaptersQuery.data) {
      return;
    }
    const validIndexes = new Set(chaptersQuery.data.chapters.map((chapter) => chapter.index));
    setSelectedChapters((current) => current.filter((index) => validIndexes.has(index)));
  }, [chaptersQuery.data]);

  const formats = formatsQuery.data?.formats ?? [];
  useEffect(() => {
    if (formats.length === 0) {
      if (format !== "") {
        setFormat("");
      }
      return;
    }
    if (!format || !formats.includes(format)) {
      setFormat(formats[0]);
    }
  }, [format, formats]);

  const selectedChapterIndexes = useMemo(() => {
    return [...selectedChapters].sort((a, b) => a - b);
  }, [selectedChapters]);

  const selectedChapterSet = useMemo(() => new Set(selectedChapterIndexes), [selectedChapterIndexes]);

  const bookOnlyFormats = useMemo(() => new Set(formatsQuery.data?.book_only ?? []), [formatsQuery.data?.book_only]);
  const hasChapterSelection = selectedChapterIndexes.length > 0;
  const invalidFormatWithChapterSelection = hasChapterSelection && bookOnlyFormats.has(format);
  const selectedFormatDescription = format ? formatsQuery.data?.descriptions?.[format] : undefined;

  const startMutation = useMutation({
    mutationFn: () => {
      if (!selectedBook) {
        throw new Error("Selecciona un libro primero.");
      }
      if (!format) {
        throw new Error("Los formatos aun no estan listos o no estan disponibles.");
      }
      if (invalidFormatWithChapterSelection) {
        throw new Error("El formato seleccionado requiere libro completo. Limpia la seleccion de capitulos o cambia el formato.");
      }

      return startDownload({
        book_id: selectedBook.id,
        format,
        chapters: selectedChapterIndexes.length > 0 ? selectedChapterIndexes : undefined,
        skip_images: skipImages,
      });
    },
    onSuccess: async (data) => {
      setActiveJobId(data.job_id ?? null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.downloadProgressRoot });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelDownload(activeJobId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.downloadProgressRoot });
    },
  });

  const toggleChapter = useCallback((chapterIndex: number) => {
    setSelectedChapters((current) => {
      if (current.includes(chapterIndex)) {
        return current.filter((item) => item !== chapterIndex);
      }
      return [...current, chapterIndex];
    });
  }, []);

  const selectAllChapters = useCallback(() => {
    setSelectedChapters(chaptersQuery.data?.chapters.map((chapter) => chapter.index) ?? []);
  }, [chaptersQuery.data?.chapters]);

  const clearSelectedChapters = useCallback(() => {
    setSelectedChapters([]);
  }, []);

  const clampedProgressPercent = Math.max(0, Math.min(100, Number(progressQuery.data?.percentage ?? 0)));
  const progressPercent = progressStatus === "completed"
    ? 100
    : progressStatus === "queued"
      ? 0
      : progressStatus === "running"
        ? clampedProgressPercent
        : 0;
  const active = isDownloadActive(progressQuery.data);
  const totalChapters = chaptersQuery.data?.total ?? 0;
  const currentLabel = progressStatus;
  const shouldShowStartHint = currentLabel === "idle" || active;

  const formatsDisabled = formatsQuery.isLoading || formats.length === 0;
  const chaptersLoading = Boolean(selectedBook) && !chaptersQuery.data && chaptersQuery.isLoading;
  const chaptersRefreshing = Boolean(selectedBook) && chaptersQuery.isFetching;
  const startDisabledReasonBase = !selectedBook
    ? "Selecciona un libro para comenzar."
    : formatsDisabled
      ? "Esperando formatos disponibles."
      : invalidFormatWithChapterSelection
        ? "El formato actual no acepta seleccion de capitulos."
        : active
          ? "Ya hay una descarga en curso."
          : startMutation.isPending
            ? "La descarga se esta iniciando..."
            : null;
  const startDisabledReason = shouldShowStartHint ? startDisabledReasonBase : null;

  return {
    active,
    activeJobId,
    bookOnlyFormats,
    cancelMutation,
    chaptersLoading,
    chaptersQuery,
    chaptersRefreshing,
    clearSelectedChapters,
    currentLabel,
    forceReconnect,
    format,
    formats,
    formatsDisabled,
    formatsQuery,
    hasChapterSelection,
    invalidFormatWithChapterSelection,
    progressPercent,
    progressQuery,
    selectedChapterIndexes,
    selectedChapterSet,
    selectedBook,
    selectedFormatDescription,
    selectAllChapters,
    setFormat,
    setSkipImages,
    skipImages,
    sseStatus,
    startDisabledReason,
    startMutation,
    toggleChapter,
    totalChapters,
  };
}

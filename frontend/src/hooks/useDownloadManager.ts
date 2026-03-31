import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import {
  cancelDownload,
  getBookChapters,
  getFormats,
  getProgress,
  startDownload,
  subscribeProgress,
} from '../lib/api';
import { queryKeys } from '../lib/query-keys';
import type { DownloadStartResponse, ProgressResponse } from '../lib/types';
import { useBookStore } from '../store/book-store';

const ACTIVE_STATES = new Set(['queued', 'running']);

const RECONNECT_DELAY_MS = 2500;

// Stale time configuration for TanStack Query v5
const STALE_TIMES = {
  // Formatos: datos estáticos, cachear por 5 minutos
  formats: 5 * 60 * 1000,
  // Progreso: actualizar cada 5 segundos durante descargas activas
  progressActive: 5 * 1000,
  // Progreso completado: cachear por 1 minuto
  progressCompleted: 60 * 1000,
  // Capítulos: cachear por 2 minutos (raramente cambian)
  chapters: 2 * 60 * 1000,
} as const;

export type SseStatus = 'connecting' | 'connected' | 'reconnecting' | 'error';

function isDownloadActive(progress?: ProgressResponse) {
  const status = progress?.status;
  return Boolean(status && ACTIVE_STATES.has(status));
}

export function useDownloadManager() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const selectedBook = useBookStore(state => state.selectedBook);
  const format = useBookStore(state => state.format);
  const setFormat = useBookStore(state => state.setFormat);
  const skipImages = useBookStore(state => state.skipImages);
  const setSkipImages = useBookStore(state => state.setSkipImages);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [selectedChapters, setSelectedChapters] = useState<number[]>([]);
  const [sseStatus, setSseStatus] = useState<SseStatus>('connecting');
  const [reconnectToken, setReconnectToken] = useState(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const disposedRef = useRef(false);

  // Query para formatos - datos estáticos con staleTime extendido
  const formatsQuery = useQuery({
    queryKey: queryKeys.formats.all,
    queryFn: getFormats,
    staleTime: STALE_TIMES.formats,
    // gcTime remplazó cacheTime en v5
    gcTime: 10 * 60 * 1000, // 10 minutos garbage collection
  });

  // Query key para progreso usando factory pattern
  const progressQueryKey = useMemo(() => queryKeys.progress.byJob(activeJobId), [activeJobId]);

  const activeJobIdRef = useRef(activeJobId);
  const progressQueryKeyRef = useRef(progressQueryKey);

  activeJobIdRef.current = activeJobId;
  progressQueryKeyRef.current = progressQueryKey;

  // Query para progreso con staleTime dinámico basado en estado
  const progressQuery = useQuery({
    queryKey: progressQueryKey,
    queryFn: () => getProgress(activeJobId),
    refetchInterval: query => {
      const data = query.state.data as ProgressResponse | undefined;
      // Refetch más frecuente durante descargas activas
      if (isDownloadActive(data)) {
        return 8000;
      }
      // Menos frecuente cuando está idle o completado
      return 30000;
    },
    staleTime: query => {
      const data = query.state.data as ProgressResponse | undefined;
      if (isDownloadActive(data)) {
        return STALE_TIMES.progressActive;
      }
      return STALE_TIMES.progressCompleted;
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

  // Query para capítulos con staleTime apropiado
  const chaptersQuery = useQuery({
    queryKey: queryKeys.chapters.byBook(selectedBook?.id ?? null),
    queryFn: () => getBookChapters(selectedBook?.id ?? ''),
    enabled: Boolean(selectedBook?.id),
    staleTime: STALE_TIMES.chapters,
    gcTime: 5 * 60 * 1000, // 5 minutos
  });

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
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
      if (disposedRef.current || reconnectTimerRef.current) {
        return;
      }
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        if (disposedRef.current) {
          return;
        }
        setReconnectToken(current => current + 1);
      }, RECONNECT_DELAY_MS);
    };

    setSseStatus(reconnectAttemptRef.current > 0 ? 'reconnecting' : 'connecting');

    unsubscribe = subscribeProgress(
      {
        onProgress: next => {
          if (!activeJobIdRef.current && next.job_id) {
            setActiveJobId(next.job_id);
          }
          queryClient.setQueryData(progressQueryKeyRef.current, next);
        },
        onOpen: () => {
          reconnectAttemptRef.current = 0;
          setSseStatus('connected');
          clearReconnectTimer();
        },
        onError: () => {
          if (disposedRef.current) {
            return;
          }
          setSseStatus('error');
          closeConnection();
          scheduleReconnect();
        },
      },
      activeJobIdRef.current
    );

    return () => {
      disposedRef.current = true;
      clearReconnectTimer();
      closeConnection();
    };
  }, [activeJobId, clearReconnectTimer, progressQueryKey, queryClient, reconnectToken]);

  const forceReconnect = useCallback(() => {
    clearReconnectTimer();
    reconnectAttemptRef.current += 1;
    setSseStatus('reconnecting');
    setReconnectToken(current => current + 1);
  }, [clearReconnectTimer]);

  useEffect(() => {
    setSelectedChapters([]);
  }, [selectedBook?.id]);

  useEffect(() => {
    if (!chaptersQuery.data) {
      return;
    }
    const validIndexes = new Set(chaptersQuery.data.chapters.map(chapter => chapter.index));
    setSelectedChapters(current => current.filter(index => validIndexes.has(index)));
  }, [chaptersQuery.data]);

  const formats = formatsQuery.data?.formats ?? [];
  useEffect(() => {
    if (formats.length === 0) {
      if (format !== '') {
        setFormat('');
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

  const selectedChapterSet = useMemo(
    () => new Set(selectedChapterIndexes),
    [selectedChapterIndexes]
  );

  const bookOnlyFormats = useMemo(
    () => new Set(formatsQuery.data?.book_only ?? []),
    [formatsQuery.data?.book_only]
  );
  const hasChapterSelection = selectedChapterIndexes.length > 0;
  const invalidFormatWithChapterSelection = hasChapterSelection && bookOnlyFormats.has(format);
  const selectedFormatDescription = format ? formatsQuery.data?.descriptions?.[format] : undefined;

  /**
   * Mutation para iniciar descarga con OPTIMISTIC UPDATES
   * Implementa el pattern completo de TanStack Query v5:
   * - onMutate: Cancela queries pendientes y aplica update optimista
   * - onError: Rollback al estado anterior si falla
   * - onSettled: Invalidación estratégica de queries relacionadas
   */
  const startMutation = useMutation({
    mutationFn: (): Promise<DownloadStartResponse> => {
      if (!selectedBook) {
        throw new Error(t('download.book.placeholder'));
      }
      if (!format) {
        throw new Error(t('download.format.no_formats'));
      }
      if (invalidFormatWithChapterSelection) {
        throw new Error(t('download.chapters.not_selectable', { format: format.toUpperCase() }));
      }

      return startDownload({
        book_id: selectedBook.id,
        format,
        chapters: selectedChapterIndexes.length > 0 ? selectedChapterIndexes : undefined,
        skip_images: skipImages,
      });
    },

    /**
     * onMutate - Optimistic Update
     * 1. Cancela queries pendientes para evitar sobreescritura
     * 2. Snapshot del estado anterior
     * 3. Aplica estado optimista inmediatamente
     */
    onMutate: async (): Promise<{ previousProgress: ProgressResponse | undefined }> => {
      // Cancelar queries pendientes de progreso para evitar race conditions
      await queryClient.cancelQueries({ queryKey: queryKeys.progress.root });

      // Snapshot del estado anterior para posible rollback
      const previousProgress = queryClient.getQueryData<ProgressResponse>(progressQueryKey);

      // Estado optimista: simular que la descarga está en cola
      const optimisticProgress: ProgressResponse = {
        job_id: null, // Se actualizará cuando el servidor responda
        status: 'queued',
        book_id: selectedBook?.id ?? null,
        percentage: 0,
        message: t('download.actions.starting'),
        queue_position: null,
        eta_seconds: null,
        current_chapter: null,
        total_chapters: null,
        chapter_title: null,
        title: selectedBook?.title ?? null,
        epub: null,
        pdf: null,
        error: null,
        code: null,
        details: null,
        trace_log: null,
      };

      // Aplicar estado optimista inmediatamente
      queryClient.setQueryData(progressQueryKey, optimisticProgress);

      return { previousProgress };
    },

    /**
     * onSuccess - Actualización exitosa
     * Actualizar con datos reales del servidor y establecer job_id
     */
    onSuccess: async (data: DownloadStartResponse) => {
      if (data.job_id) {
        setActiveJobId(data.job_id);

        // Actualizar query data con job_id real
        queryClient.setQueryData<ProgressResponse>(progressQueryKey, old => ({
          ...old,
          job_id: data.job_id,
          status: 'queued',
          message: t('download.progress.queued', { position: data.queue_position ?? '?' }),
          queue_position: data.queue_position ?? null,
        }));
      }
    },

    /**
     * onError - Rollback
     * Restaura el estado anterior si la mutación falla
     */
    onError: (
      err: Error,
      _variables: void,
      context: { previousProgress: ProgressResponse | undefined } | undefined
    ) => {
      console.error('Error al iniciar descarga:', err);

      // Rollback al estado anterior si existe
      if (context?.previousProgress) {
        queryClient.setQueryData(progressQueryKey, context.previousProgress);
      } else {
        // Si no hay estado anterior, limpiar el estado optimista
        queryClient.setQueryData<ProgressResponse>(progressQueryKey, {
          job_id: null,
          status: 'idle',
          book_id: null,
          percentage: null,
          message: null,
          queue_position: null,
          eta_seconds: null,
          current_chapter: null,
          total_chapters: null,
          chapter_title: null,
          title: null,
          epub: null,
          pdf: null,
          error: `${t('download.notifications.download_error')}: ${err.message}`,
          code: 'START_FAILED',
          details: null,
          trace_log: null,
        });
      }
    },

    /**
     * onSettled - Invalidación Estratégica
     * Invalidar múltiples queries relacionadas para mantener consistencia
     */
    onSettled: async () => {
      // Invalidar queries de progreso para obtener estado actualizado del servidor
      await queryClient.invalidateQueries({
        queryKey: queryKeys.progress.root,
        refetchType: 'active', // Solo refetch queries activas
      });

      // Invalidar queries de capítulos (podrían haber cambiado)
      if (selectedBook?.id) {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.chapters.byBook(selectedBook.id),
          refetchType: 'inactive', // Incluir queries inactivas para próxima visita
        });
      }
    },
  });

  /**
   * Mutation para cancelar descarga con Optimistic Update
   */
  const cancelMutation = useMutation({
    mutationFn: () => cancelDownload(activeJobId),

    onMutate: async (): Promise<{ previousProgress: ProgressResponse | undefined }> => {
      await queryClient.cancelQueries({ queryKey: queryKeys.progress.root });
      const previousProgress = queryClient.getQueryData<ProgressResponse>(progressQueryKey);

      // Estado optimista: marcar como cancelando
      queryClient.setQueryData<ProgressResponse>(progressQueryKey, old => ({
        ...old,
        status: 'cancelling',
        message: t('download.actions.cancelling'),
      }));

      return { previousProgress };
    },

    onError: (
      err: Error,
      _variables: void,
      context: { previousProgress: ProgressResponse | undefined } | undefined
    ) => {
      console.error('Error al cancelar descarga:', err);

      if (context?.previousProgress) {
        queryClient.setQueryData(progressQueryKey, context.previousProgress);
      }
    },

    onSettled: async () => {
      // Invalidar múltiples queries relacionadas
      await queryClient.invalidateQueries({
        queryKey: queryKeys.progress.root,
        refetchType: 'all',
      });

      // También invalidar formats en caso de que haya cambios
      await queryClient.invalidateQueries({
        queryKey: queryKeys.formats.root,
        refetchType: 'inactive',
      });
    },
  });

  const toggleChapter = useCallback((chapterIndex: number) => {
    setSelectedChapters(current => {
      if (current.includes(chapterIndex)) {
        return current.filter(item => item !== chapterIndex);
      }
      return [...current, chapterIndex];
    });
  }, []);

  const selectAllChapters = useCallback(() => {
    setSelectedChapters(chaptersQuery.data?.chapters.map(chapter => chapter.index) ?? []);
  }, [chaptersQuery.data?.chapters]);

  const clearSelectedChapters = useCallback(() => {
    setSelectedChapters([]);
  }, []);

  const progressStatus = progressQuery.data?.status ?? 'idle';
  const clampedProgressPercent = Math.max(
    0,
    Math.min(100, Number(progressQuery.data?.percentage ?? 0))
  );
  const progressPercent =
    progressStatus === 'completed'
      ? 100
      : progressStatus === 'queued'
        ? 0
        : progressStatus === 'running'
          ? clampedProgressPercent
          : 0;
  const active = isDownloadActive(progressQuery.data);
  const totalChapters = chaptersQuery.data?.total ?? 0;
  const currentLabel = progressStatus;
  const shouldShowStartHint = currentLabel === 'idle' || active;

  const formatsDisabled = formatsQuery.isLoading || formats.length === 0;
  const chaptersLoading = Boolean(selectedBook) && !chaptersQuery.data && chaptersQuery.isLoading;
  const chaptersRefreshing = Boolean(selectedBook) && chaptersQuery.isFetching;
  const startDisabledReasonBase = !selectedBook
    ? t('download.book.placeholder')
    : formatsDisabled
      ? t('download.format.loading')
      : invalidFormatWithChapterSelection
        ? t('download.chapters.not_selectable', { format: format.toUpperCase() })
        : active
          ? t('download.progress.status_running')
          : startMutation.isPending
            ? t('download.actions.starting')
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

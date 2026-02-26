import { ApiError } from "./api";

type ParsedApiError = {
  message: string;
  code?: string;
  details?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatDetails(details: Record<string, unknown> | undefined): string | undefined {
  if (!details) {
    return undefined;
  }

  try {
    return JSON.stringify(details, null, 2);
  } catch {
    return String(details);
  }
}

export function parseApiError(error: unknown): ParsedApiError {
  if (error instanceof ApiError) {
    return {
      message: error.message,
      code: error.code,
      details: formatDetails(error.details),
    };
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  if (isRecord(error)) {
    return {
      message: typeof error.error === "string" ? error.error : "Unexpected error",
      code: typeof error.code === "string" ? error.code : undefined,
      details: formatDetails(isRecord(error.details) ? error.details : undefined),
    };
  }

  return { message: "Unexpected error" };
}

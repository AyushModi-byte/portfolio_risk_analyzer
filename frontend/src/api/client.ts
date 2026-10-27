import type {
  AnalysisResult,
  AnalyzeRequest,
  ChatRequest,
  ChatResult,
  ColumnMapping,
  Health,
  InsightsResult,
  MappingResult,
  ParseResponse,
  SampleInfo,
} from './types';

/** An error response from the backend, or a failure to reach it (status 0). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryAfter: number | null;

  constructor(status: number, code: string, detail: string, retryAfter: number | null = null) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

export interface Api {
  health: (signal?: AbortSignal) => Promise<Health>;
  samples: () => Promise<SampleInfo[]>;
  parse: (file: File, mapping?: ColumnMapping) => Promise<ParseResponse>;
  analyze: (request: AnalyzeRequest) => Promise<AnalysisResult>;
  insights: (analysis: AnalysisResult) => Promise<InsightsResult>;
  chat: (request: ChatRequest) => Promise<ChatResult>;
  suggestMapping: (headers: string[], rows: Record<string, string>[]) => Promise<MappingResult>;
}

interface ErrorBody {
  error?: unknown;
  detail?: unknown;
}

function isErrorBody(value: unknown): value is ErrorBody {
  return typeof value === 'object' && value !== null;
}

export function createApi(baseUrl: string, fetchImpl: typeof fetch = fetch): Api {
  const root = baseUrl.replace(/\/+$/, '');

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await fetchImpl(`${root}${path}`, init);
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
      throw new ApiError(0, 'network_error', 'Could not reach the server.');
    }
    if (!response.ok) {
      let body: unknown = null;
      try {
        body = await response.json();
      } catch {
        // Not JSON (for example a proxy error page); fall through to a generic error.
      }
      const code = isErrorBody(body) && typeof body.error === 'string' ? body.error : 'error';
      const detail =
        isErrorBody(body) && typeof body.detail === 'string' ? body.detail : response.statusText;
      const retry = Number(response.headers.get('Retry-After'));
      throw new ApiError(
        response.status,
        code,
        detail,
        Number.isFinite(retry) && retry > 0 ? retry : null,
      );
    }
    return (await response.json()) as T;
  }

  const json = (body: unknown): RequestInit => ({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  return {
    health: (signal) => request<Health>('/health', { signal }),
    samples: () => request<SampleInfo[]>('/api/samples'),
    parse: (file, mapping) => {
      const form = new FormData();
      form.append('file', file);
      if (mapping) form.append('mapping', JSON.stringify(mapping));
      return request<ParseResponse>('/api/parse', { method: 'POST', body: form });
    },
    analyze: (body) => request<AnalysisResult>('/api/analyze', json(body)),
    insights: (analysis) => request<InsightsResult>('/api/insights', json(analysis)),
    chat: (body) => request<ChatResult>('/api/chat', json(body)),
    suggestMapping: (headers, sample_rows) =>
      request<MappingResult>('/api/mapping/suggest', json({ headers, sample_rows })),
  };
}

/** The backend URL from the build environment. There is deliberately no fallback. */
export function apiBaseUrl(): string | null {
  const url = import.meta.env.VITE_API_URL as string | undefined;
  return url?.trim() ? url.trim() : null;
}

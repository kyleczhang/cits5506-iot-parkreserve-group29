/**
 * HTTP client.
 *
 * Wraps `ky` with:
 *   - `Authorization: Bearer <jwt>` injection (token sourced from
 *     localStorage, fed by `AuthProvider`).
 *   - Unified `ApiError` translation of the backend's envelope:
 *     `{ "error": { "code": "...", "message": "...", "details": {...} } }`
 *     — see openapi.yaml `ErrorEnvelope`.
 *   - 401 fan-out so any request that returns 401 logs the user out and
 *     bounces them to `/login`. We dispatch a `CustomEvent` rather than
 *     reaching into React state because the client is consumed from
 *     mutations and loaders that run outside the React tree.
 */
import ky, { HTTPError, type KyInstance, type Options } from "ky";
import { BACKEND_ORIGIN } from "@/lib/env";

const JWT_STORAGE_KEY = "parkreserve.jwt";

/**
 * Custom event name dispatched on any 401 response. `AuthProvider`
 * listens for this on `window` and clears its state + redirects.
 */
export const AUTH_EXPIRED_EVENT = "parkreserve:auth-expired";

/** Read/write the JWT in localStorage. */
export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(JWT_STORAGE_KEY);
    } catch {
      return null;
    }
  },
  set(value: string): void {
    try {
      localStorage.setItem(JWT_STORAGE_KEY, value);
    } catch {
      // ignore — quota / disabled storage
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(JWT_STORAGE_KEY);
    } catch {
      // ignore
    }
  },
};

/** Shape of the backend's uniform error envelope. */
export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

/** Thrown by `api.*` calls for any non-2xx response. */
export class ApiError extends Error {
  override readonly name = "ApiError";
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message || `HTTP ${status}`);
    this.status = status;
    this.code = body.code || "unknown_error";
    this.details = body.details ?? {};
  }
}

/**
 * Construct a ky instance scoped to the backend origin (or same-origin
 * in production). The 401 hook fires the auth-expired event; the
 * generic error hook re-wraps `HTTPError` into our `ApiError` envelope.
 */
function buildClient(): KyInstance {
  return ky.create({
    prefixUrl: BACKEND_ORIGIN || undefined,
    timeout: 15_000,
    retry: { limit: 0 },
    hooks: {
      beforeRequest: [
        (request) => {
          const token = tokenStore.get();
          if (token && !request.headers.has("Authorization")) {
            request.headers.set("Authorization", `Bearer ${token}`);
          }
        },
      ],
      beforeError: [
        async (error: HTTPError) => {
          const { response } = error;
          let body: ApiErrorBody = {
            code: "unknown_error",
            message: error.message,
          };
          try {
            const parsed = (await response.clone().json()) as {
              error?: ApiErrorBody;
            };
            if (parsed.error) body = parsed.error;
          } catch {
            // non-JSON body — keep generic envelope
          }
          if (response.status === 401) {
            tokenStore.clear();
            window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
          }
          // ky's hook expects an Error return — we throw via the next line.
          throw new ApiError(response.status, body);
        },
      ],
    },
  });
}

let _client = buildClient();

/** Public ky-shaped facade used by the per-resource modules. */
export const http = {
  get: (url: string, options?: Options) => _client.get(url, options),
  post: (url: string, options?: Options) => _client.post(url, options),
  delete: (url: string, options?: Options) => _client.delete(url, options),
};

/** Replace the singleton (used in tests with an MSW-backed instance). */
export function __setClientForTests(next: KyInstance): void {
  _client = next;
}

import type { TokenOut } from "./types";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string,
              public fields?: { loc: string[]; msg: string }[]) {
    super(message);
  }
}

const BASE = "/api/v1";
let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;
let onSessionLost: (() => void) | null = null;

/** Access tokens live only in memory (never localStorage). The refresh token is an httpOnly cookie. */
export function setAccessToken(t: string | null) { accessToken = t; }
export function getAccessToken() { return accessToken; }
export function setSessionLostHandler(fn: (() => void) | null) { onSessionLost = fn; }

async function parseError(res: Response): Promise<ApiError> {
  let body: any = null;
  try { body = await res.json(); } catch { /* non-JSON error */ }
  const e = body?.error;
  const msg = e?.message ?? (res.status === 429 ? "Too many requests. Try again shortly." : `Request failed (${res.status})`);
  return new ApiError(res.status, e?.code ?? "http_error", msg, e?.request_id, e?.details?.fields);
}

export async function refreshSession(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include", headers: { "X-Requested-With": "lumina" } });
        if (!res.ok) { accessToken = null; return false; }
        const data = (await res.json()) as TokenOut;
        accessToken = data.access_token;
        return true;
      } catch { return false; } finally { setTimeout(() => { refreshPromise = null; }, 0); }
    })();
  }
  return refreshPromise;
}

interface Opts { body?: unknown; form?: FormData; query?: Record<string, string | number | undefined>; auth?: boolean }

async function request<T>(method: string, path: string, o: Opts = {}, retried = false): Promise<T> {
  const qs = o.query ? "?" + new URLSearchParams(Object.entries(o.query).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])).toString() : "";
  const headers: Record<string, string> = { "X-Requested-With": "lumina" };
  if (o.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken && o.auth !== false) headers.Authorization = `Bearer ${accessToken}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}${qs}`, { method, headers, credentials: "include",
      body: o.form ?? (o.body !== undefined ? JSON.stringify(o.body) : undefined) });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the server. Check that the backend is running.");
  }
  if (res.status === 401 && !retried && o.auth !== false && !path.startsWith("/auth/")) {
    if (await refreshSession()) return request<T>(method, path, o, true);
    onSessionLost?.();
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(p: string, query?: Opts["query"]) => request<T>("GET", p, { query }),
  post: <T>(p: string, body?: unknown) => request<T>("POST", p, { body: body ?? {} }),
  patch: <T>(p: string, body: unknown) => request<T>("PATCH", p, { body }),
  del: <T = void>(p: string) => request<T>("DELETE", p),
  upload: <T>(p: string, form: FormData) => request<T>("POST", p, { form }),
  publicGet: <T>(p: string) => request<T>("GET", p, { auth: false }),
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.fields?.length) return `${e.message}: ${e.fields.map((f) => `${f.loc.join(".")} ${f.msg}`).join("; ")}`;
    return e.message;
  }
  return e instanceof Error ? e.message : "Something went wrong";
}

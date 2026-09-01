/**
 * Typed client for the ALLBEE API.
 *
 * Every request goes through `request()`, so auth headers, error shaping and
 * the 401 sign-out path exist in exactly one place.
 */
import type {
  Dashboard,
  Event,
  Page,
  Photo,
  PublicEvent,
  SearchResult,
  SelfieErrorCode,
  TokenResponse,
  UploadResponse,
  User,
} from "@/types";

const TOKEN_KEY = "allbee.token";

/**
 * Where the API lives, as seen from the browser.
 *
 * Empty means same-origin, which is the local-development default:
 * next.config.mjs proxies /api to FastAPI so there is no CORS to think about.
 *
 * Set NEXT_PUBLIC_API_URL when the frontend and backend are on different
 * hosts -- for example the frontend on Vercel and the backend on a VPS. The
 * browser then talks to the backend directly rather than through the
 * frontend host, which matters for uploads: proxying them through Vercel
 * would cap every photo at that platform's 4.5 MB request-body limit.
 */
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");

/**
 * Turn a relative path returned by the API into one the browser can load.
 *
 * The API returns photo URLs as `/api/public/photos/{id}/thumbnail`. Those
 * resolve against the *page* origin, so on a split deployment an <img> would
 * ask the frontend host for a photo it does not have. Everything that puts a
 * server-supplied path into `src` or `href` must go through here.
 */
export function mediaUrl(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

export class ApiError extends Error {
  status: number;
  code?: SelfieErrorCode | string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

/** Pull a readable message out of whatever shape the error came back in. */
async function toApiError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  let code: string | undefined;
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object") {
      message = detail.message ?? message;
      code = detail.code;
    }
  } catch {
    /* non-JSON body: keep the status-based message */
  }
  return new ApiError(message, response.status, code);
}

async function request<T>(path: string, init: RequestInit = {}, auth = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (auth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("Can't reach the server. Check that the backend is running.", 0);
  }

  if (response.status === 401 && auth) {
    setToken(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError("Your session expired. Sign in again.", 401);
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  // -- auth ---------------------------------------------------------------
  register: (data: {
    name: string;
    email: string;
    password: string;
    confirm_password: string;
  }) =>
    request<TokenResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    request<TokenResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(data) }),

  me: () => request<User>("/api/auth/me", {}, true),

  // -- events -------------------------------------------------------------
  dashboard: () => request<Dashboard>("/api/events/dashboard", {}, true),

  listEvents: () => request<Event[]>("/api/events", {}, true),

  createEvent: (data: {
    name: string;
    event_date?: string | null;
    location?: string | null;
    description?: string | null;
  }) => request<Event>("/api/events", { method: "POST", body: JSON.stringify(data) }, true),

  getEvent: (id: string) => request<Event>(`/api/events/${id}`, {}, true),

  updateEvent: (id: string, data: Partial<Event>) =>
    request<Event>(`/api/events/${id}`, { method: "PUT", body: JSON.stringify(data) }, true),

  deleteEvent: (id: string) =>
    request<{ message: string }>(`/api/events/${id}`, { method: "DELETE" }, true),

  /**
   * Fetch the QR PNG as a blob.
   *
   * This endpoint checks event ownership, and an <img src> cannot carry an
   * Authorization header -- so loading it by URL returns 401. The caller turns
   * this blob into an object URL for both display and download.
   */
  qrBlob: async (id: string): Promise<Blob> => {
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(`${API_BASE}/api/events/${id}/qr`, { headers });
    if (!response.ok) throw await toApiError(response);
    return response.blob();
  },

  // -- photos -------------------------------------------------------------
  listPhotos: (eventId: string, limit = 60, offset = 0) =>
    request<Page<Photo>>(`/api/events/${eventId}/photos?limit=${limit}&offset=${offset}`, {}, true),

  deletePhoto: (photoId: string) =>
    request<{ message: string }>(`/api/photos/${photoId}`, { method: "DELETE" }, true),

  reprocess: (eventId: string) =>
    request<{ message: string }>(
      `/api/events/${eventId}/photos/reprocess`,
      { method: "POST" },
      true,
    ),

  // -- guest --------------------------------------------------------------
  publicEvent: (code: string) => request<PublicEvent>(`/api/public/events/${code}`),

  publicPhotos: (code: string, limit = 48, offset = 0) =>
    request<Page<Photo>>(`/api/public/events/${code}/photos?limit=${limit}&offset=${offset}`),

  search: (code: string, selfie: Blob) => {
    const form = new FormData();
    form.append("selfie", selfie, "selfie.jpg");
    return request<SearchResult>(`/api/public/events/${code}/search`, {
      method: "POST",
      body: form,
    });
  },

  getSearch: (searchId: string) => request<SearchResult>(`/api/public/searches/${searchId}`),

  streamUrl: (code: string) => `${API_BASE}/api/public/events/${code}/stream`,
};

/**
 * Upload with real byte-level progress.
 *
 * `fetch` cannot report request progress, so this uses XMLHttpRequest. The
 * photographer needs to see actual movement when pushing hundreds of files
 * over venue wifi -- a fake animated bar would hide a stalled connection.
 */
export function uploadPhotos(
  eventId: string,
  files: File[],
  onProgress: (loaded: number, total: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file, file.name));

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/events/${eventId}/photos`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded, event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as UploadResponse);
        } catch {
          reject(new ApiError("The server sent a malformed response.", xhr.status));
        }
      } else {
        let message = `Upload failed (${xhr.status})`;
        try {
          const detail = JSON.parse(xhr.responseText)?.detail;
          if (typeof detail === "string") message = detail;
        } catch {
          /* keep the status message */
        }
        reject(new ApiError(message, xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("Connection lost during upload.", 0));
    xhr.ontimeout = () => reject(new ApiError("The upload timed out.", 0));
    xhr.send(form);
  });
}

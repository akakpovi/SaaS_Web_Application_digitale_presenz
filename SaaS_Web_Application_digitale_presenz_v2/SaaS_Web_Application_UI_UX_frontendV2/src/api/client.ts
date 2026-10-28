import { endpoints } from "./endpoints"
import { authStorage } from "./authStorage"
import { ApiRequestError, toApiError } from "./errors"

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1"

/**
 * Opt-in request tracing, for diagnosing a 400/401 from the browser console.
 *
 * Enable it once per origin and reload:
 *   localStorage.setItem("presence:debug-api", "1")
 * Disable with removeItem. It also turns itself on under `vite dev`, and it
 * stays off in the built bundle by default so no personal data or token is
 * ever printed to a real visitor's console.
 */
const DEBUG_FLAG = "presence:debug-api"

/** Never print credentials or bearer tokens, even in a debug trace. */
const SENSITIVE_KEYS = new Set([
  "password",
  "new_password",
  "refresh",
  "access",
  "token",
  "id_token",
])

function debugEnabled(): boolean {
  if (import.meta.env.DEV) return true
  try {
    return window.localStorage.getItem(DEBUG_FLAG) === "1"
  } catch {
    // Storage can be blocked (private mode, third-party context).
    return false
  }
}

function redact(value: unknown, depth = 0): unknown {
  if (depth > 4) return "…"
  if (Array.isArray(value)) return value.map((entry) => redact(entry, depth + 1))
  if (typeof value !== "object" || value === null) return value

  const result: Record<string, unknown> = {}
  for (const [key, entry] of Object.entries(value)) {
    result[key] = SENSITIVE_KEYS.has(key.toLowerCase())
      ? "***"
      : redact(entry, depth + 1)
  }
  return result
}

function traceRequest(method: string, url: string, body?: BodyInit | null): void {
  if (!debugEnabled()) return

  let payload: unknown = "(empty)"
  if (typeof body === "string") {
    try {
      payload = redact(JSON.parse(body))
    } catch {
      payload = body
    }
  }

  console.groupCollapsed(`[api] → ${method} ${url}`)
  console.log("payload", payload)
  console.groupEnd()
}

function traceError(url: string, status: number, payload: unknown): void {
  if (!debugEnabled()) return
  console.groupCollapsed(`[api] ← ${status} ${url}`)
  console.log("response", payload)
  console.groupEnd()
}

/**
 * These endpoints authenticate the visitor, so a 401 is a rejected credential
 * (wrong password, duplicate email), not an expired session. Refreshing here
 * would swallow the backend message and replace it with "Session expired".
 */
const PUBLIC_AUTH_ENDPOINTS: ReadonlySet<string> = new Set([
  endpoints.auth.login,
  endpoints.auth.register,
  endpoints.auth.refresh,
  endpoints.auth.logout,
  endpoints.auth.passwordReset,
  endpoints.auth.passwordResetConfirm,
  endpoints.auth.emailVerify,
])

class ApiClient {
  private baseUrl: string
  private refreshing = false
  private refreshPromise: Promise<string> | null = null

  constructor(baseUrl: string = BASE_URL) {
    this.baseUrl = baseUrl
  }

  private getHeaders(includeAuth = true): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    }

    if (includeAuth) {
      const accessToken = authStorage.getAccessToken()
      if (accessToken) {
        ;(headers as Record<string, string>)["Authorization"] =
          `Bearer ${accessToken}`
      }
    }

    return headers
  }

  private async handleResponse<T,>(response: Response): Promise<T> {
    if (!response.ok) {
      throw await this.parseError(response)
    }

    if (response.status === 204) {
      return undefined as T
    }

    return response.json()
  }

  private async parseError(response: Response): Promise<ApiRequestError> {
    const fallback = `HTTP ${response.status}: ${response.statusText}`
    let payload: unknown

    try {
      payload = await response.json()
    } catch {
      // Not JSON (proxy error page, empty body): keep the HTTP status text.
      traceError(response.url, response.status, "(non-JSON body)")
      return new ApiRequestError(response.status, fallback)
    }

    traceError(response.url, response.status, payload)
    return toApiError(response.status, fallback, payload)
  }

  /** Only an authenticated request with a stored session may try to refresh. */
  private shouldAttemptRefresh(endpoint: string): boolean {
    if (PUBLIC_AUTH_ENDPOINTS.has(endpoint)) return false
    return Boolean(authStorage.getRefreshToken())
  }

  private async refreshAccessToken(): Promise<string> {
    if (this.refreshing && this.refreshPromise) {
      return this.refreshPromise
    }

    this.refreshing = true

    this.refreshPromise = (async () => {
      const refreshToken = authStorage.getRefreshToken()
      if (!refreshToken) {
        throw new Error("No refresh token available")
      }

      try {
        const response = await fetch(
          `${this.baseUrl}${endpoints.auth.refresh}`,
          {
            method: "POST",
            headers: this.getHeaders(false),
            body: JSON.stringify({ refresh: refreshToken }),
          },
        )

        if (!response.ok) {
          throw new Error("Refresh failed")
        }

        const data = await response.json()

        if (!data.access || !data.refresh) {
          throw new Error("Invalid refresh response")
        }

        authStorage.setTokens(data.access, data.refresh)
        return data.access
      } finally {
        this.refreshing = false
        this.refreshPromise = null
      }
    })()

    return this.refreshPromise
  }

  private async request<T,>(
    endpoint: string,
    options: RequestInit = {},
    includeAuth = true,
    isRetry = false,
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const headers = this.getHeaders(includeAuth)

    traceRequest(options.method ?? "GET", url, options.body)

    const config: RequestInit = {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    }

    let response = await fetch(url, config)

    if (
      response.status === 401 &&
      includeAuth &&
      !isRetry &&
      this.shouldAttemptRefresh(endpoint)
    ) {
      try {
        await this.refreshAccessToken()
        response = await fetch(url, {
          ...config,
          headers: this.getHeaders(true),
        })
      } catch {
        authStorage.clearAll()
        window.dispatchEvent(new Event("auth:logout"))
        throw new ApiRequestError(401, "Session expired. Please log in again.")
      }
    }

    return this.handleResponse<T>(response)
  }

  async get<T,>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { method: "GET", ...options })
  }

  async post<T,>(
    endpoint: string,
    body?: unknown,
    options?: RequestInit,
  ): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    })
  }

  async put<T,>(
    endpoint: string,
    body?: unknown,
    options?: RequestInit,
  ): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    })
  }

  async patch<T,>(
    endpoint: string,
    body?: unknown,
    options?: RequestInit,
  ): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    })
  }

  async delete<T,>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE", ...options })
  }

  /**
   * Multipart upload (review CSV import).  `Content-Type` is deliberately not
   * set: the browser must add the multipart boundary itself, otherwise DRF's
   * parsers cannot read the file.
   */
  async upload<T,>(endpoint: string, form: FormData): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const headers: Record<string, string> = {}
    const token = authStorage.getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`

    let response = await fetch(url, { method: "POST", headers, body: form })

    if (response.status === 401 && this.shouldAttemptRefresh(endpoint)) {
      try {
        await this.refreshAccessToken()
        response = await fetch(url, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${authStorage.getAccessToken() ?? ""}`,
          },
          body: form,
        })
      } catch {
        authStorage.clearAll()
        window.dispatchEvent(new Event("auth:logout"))
        throw new ApiRequestError(401, "Session expired. Please log in again.")
      }
    }

    return this.handleResponse<T>(response)
  }

  /**
   * Authenticated binary download (PDF reports).  `handleResponse` always
   * parses JSON, which would corrupt a PDF, so this path reads the blob and
   * reuses the same one-shot refresh on 401.
   */
  async download(endpoint: string): Promise<Blob> {
    const url = `${this.baseUrl}${endpoint}`
    let response = await fetch(url, { headers: this.getHeaders(true) })

    if (response.status === 401 && this.shouldAttemptRefresh(endpoint)) {
      try {
        await this.refreshAccessToken()
        response = await fetch(url, { headers: this.getHeaders(true) })
      } catch {
        authStorage.clearAll()
        window.dispatchEvent(new Event("auth:logout"))
        throw new ApiRequestError(401, "Session expired. Please log in again.")
      }
    }

    if (!response.ok) {
      throw await this.parseError(response)
    }
    return response.blob()
  }
}

export const api = new ApiClient()

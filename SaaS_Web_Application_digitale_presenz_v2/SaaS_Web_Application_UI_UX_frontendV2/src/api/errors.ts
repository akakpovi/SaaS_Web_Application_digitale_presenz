import type { ApiError } from "./types"

export type FieldErrors = Record<string, string[]>

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

/**
 * Flattens a DRF error payload into field -> messages.
 *
 * DRF answers a rejected serializer with `{"field": ["message"]}`, form-level
 * problems with `{"non_field_errors": ["message"]}` and authentication
 * failures with `{"detail": "message"}`; `detail` is kept out of the field map
 * because it is a page-level message, not an input error.
 */
export function toFieldErrors(payload: unknown): FieldErrors {
  if (!isRecord(payload)) return {}

  const errors: FieldErrors = {}
  for (const [field, value] of Object.entries(payload)) {
    if (field === "detail") continue
    if (typeof value === "string" && value.trim()) {
      errors[field] = [value]
    } else if (Array.isArray(value)) {
      const messages = value.filter(
        (entry): entry is string => typeof entry === "string" && entry.trim().length > 0,
      )
      if (messages.length > 0) errors[field] = messages
    }
  }
  return errors
}

/**
 * The error thrown by `ApiClient`. It is a real `Error`, so `err.message`
 * works everywhere, and it keeps the HTTP status, the raw payload and the
 * per-field messages so forms can point at the offending input.
 */
export class ApiRequestError extends Error implements ApiError {
  readonly status: number
  readonly details?: unknown
  readonly fieldErrors: FieldErrors

  constructor(
    status: number,
    message: string,
    details?: unknown,
    fieldErrors: FieldErrors = {},
  ) {
    super(message)
    this.name = "ApiRequestError"
    this.status = status
    this.details = details
    this.fieldErrors = fieldErrors
  }
}

/** Builds the error for a non-2xx response from its parsed JSON body. */
export function toApiError(
  status: number,
  fallback: string,
  payload: unknown,
): ApiRequestError {
  const fieldErrors = toFieldErrors(payload)
  const detail =
    isRecord(payload) && typeof payload.detail === "string"
      ? payload.detail.trim()
      : ""
  const nonField = fieldErrors.non_field_errors?.[0]
  const firstField = Object.entries(fieldErrors).find(
    ([field]) => field !== "non_field_errors",
  )?.[1][0]

  return new ApiRequestError(
    status,
    detail || nonField || firstField || fallback,
    payload,
    fieldErrors,
  )
}

export function isApiError(error: unknown): error is ApiError {
  if (error instanceof ApiRequestError) return true
  if (!isRecord(error)) return false
  return typeof error.status === "number" && typeof error.message === "string"
}

/** Message to display, preferring the backend's own wording. */
export function apiErrorMessage(
  error: unknown,
  fallback = "Unexpected error. Please try again.",
): string {
  if (isApiError(error) && error.message) return error.message
  if (error instanceof Error && error.message) return error.message
  return fallback
}

export function apiFieldErrors(error: unknown): FieldErrors {
  if (!isApiError(error)) return {}
  return isRecord(error.fieldErrors) ? (error.fieldErrors as FieldErrors) : {}
}

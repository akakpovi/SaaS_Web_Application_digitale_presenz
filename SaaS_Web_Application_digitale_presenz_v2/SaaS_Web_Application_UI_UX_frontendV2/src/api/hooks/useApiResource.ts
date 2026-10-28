import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "../client"
import { apiErrorMessage } from "../errors"
import type { Paginated } from "../types"

// Kept exported from here for the pages that already import it alongside the
// hooks; the implementation lives in `api/errors.ts` with the error class.
export { apiErrorMessage }

/**
 * Minimal data-fetching primitive for the authenticated app pages.
 *
 * The project has no data library (no react-query/SWR), so pages previously
 * shipped hardcoded demo arrays. This hook keeps the ergonomics small: one
 * endpoint, optional polling, an explicit refetch for after mutations.
 *
 * `refreshKey` is part of the request identity: changing it (a counter, a
 * filter string, a website id) refetches, which keeps dependency arrays short
 * and stable.
 */
interface ResourceState<T> {
  data: T | null
  error: string | null
  loading: boolean
}

export function useApiResource<T>(
  endpoint: string | null,
  refreshKey: string | number = 0,
  pollMs = 0,
) {
  const [state, setState] = useState<ResourceState<T>>({
    data: null,
    error: null,
    loading: endpoint !== null,
  })

  const mounted = useRef(true)
  const endpointRef = useRef(endpoint)
  endpointRef.current = endpoint

  const load = useCallback(async (silent: boolean) => {
    const target = endpointRef.current
    if (!target) {
      setState({ data: null, error: null, loading: false })
      return
    }

    if (!silent) {
      setState((prev) => ({ ...prev, loading: true }))
    }

    try {
      const payload = await api.get<T>(target)
      if (!mounted.current) return
      setState({ data: payload, error: null, loading: false })
    } catch (error) {
      if (!mounted.current) return
      setState((prev) => ({
        data: prev.data,
        error: apiErrorMessage(error),
        loading: false,
      }))
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void load(false)
    return () => {
      mounted.current = false
    }
  }, [load, endpoint, refreshKey])

  useEffect(() => {
    if (!pollMs || !endpoint) return
    const timer = setInterval(() => void load(true), pollMs)
    return () => clearInterval(timer)
  }, [endpoint, pollMs, refreshKey, load])

  const refetch = useCallback(() => load(true), [load])

  return { ...state, refetch }
}

/** DRF list endpoints are paginated — this always yields a plain array. */
export function unwrapList<T>(payload: T[] | Paginated<T> | null): T[] {
  if (!payload) return []
  return Array.isArray(payload) ? payload : payload.results
}

export function useApiList<T>(
  endpoint: string | null,
  refreshKey: string | number = 0,
  pollMs = 0,
) {
  const { data, error, loading, refetch } = useApiResource<
    T[] | Paginated<T>
  >(endpoint, refreshKey, pollMs)

  const items = unwrapList<T>(data)
  // `count` is the server-side total: page size caps `results`, so a KPI built
  // on `items.length` would silently report "50" once a user passes 50 rows.
  const count =
    data && !Array.isArray(data) ? data.count : items.length

  return { data: items, count, error, loading, refetch }
}

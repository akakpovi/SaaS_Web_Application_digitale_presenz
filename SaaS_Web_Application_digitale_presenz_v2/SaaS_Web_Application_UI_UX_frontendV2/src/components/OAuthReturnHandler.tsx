import { useEffect, useRef } from "react"
import { useLocation, useNavigate } from "react-router-dom"

import { authStorage } from "../api/authStorage"
import { useToast } from "./Toast"

/**
 * The backend redirects the browser to FRONTEND_URL with only a whitelisted
 * integration label and outcome. This component consumes that outcome once,
 * shows a toast, and removes the ephemeral parameters from the address bar
 * through the History API (React Router `replace`), without a page reload.
 */
const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  invalid_request:
    "LinkedIn did not return the authorization code. Please try again.",
  invalid_state:
    "The LinkedIn authorization expired or was already used. Please start again.",
  oauth_exchange_failed:
    "LinkedIn rejected the token exchange. Check the application credentials and redirect URI.",
  oauth_identity_failed:
    "Presence could not read the LinkedIn profile. Please try again.",
  oauth_storage_failed:
    "The LinkedIn connection could not be saved. Please retry.",
  provider_not_configured:
    "LinkedIn is not configured on the server. Contact the administrator.",
  unsupported_provider:
    "This social provider is not supported yet.",
  forbidden:
    "Your organization role does not allow connecting social accounts.",
  auth_failed: "LinkedIn connection failed. Please try again.",
}

function cleanedSearch(search: string): string {
  const params = new URLSearchParams(search)
  for (const key of ["integration", "status", "error", "error_description"]) {
    params.delete(key)
  }
  const remaining = params.toString()
  return remaining ? `?${remaining}` : ""
}

export function OAuthReturnHandler() {
  const location = useLocation()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const handledSearch = useRef<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const integration = params.get("integration")

    if (!integration) {
      // A cleaned URL must allow a later OAuth return with the same query.
      handledSearch.current = null
      return
    }

    if (handledSearch.current === location.search) return

    // Do not interpret query parameters owned by another feature.
    if (integration !== "linkedin" && integration !== "unknown") return

    const status = params.get("status")
    const error = params.get("error")

    if (status === "success") {
      showToast(
        "LinkedIn connected successfully. The account is ready for social publishing.",
        "success",
      )
    } else if (error) {
      showToast(
        OAUTH_ERROR_MESSAGES[error] ??
          "LinkedIn connection failed. Please try again.",
        "error",
      )
    } else {
      // No outcome to display; leave the parameters untouched.
      return
    }

    handledSearch.current = location.search

    // Authenticated users land back on the integration screen; visitors who
    // are not signed in simply keep their current page with a clean URL.
    if (
      authStorage.hasTokens() &&
      location.pathname !== "/app/settings/integrations"
    ) {
      navigate("/app/settings/integrations", { replace: true })
      return
    }

    navigate(
      {
        pathname: location.pathname,
        search: cleanedSearch(location.search),
        hash: location.hash,
      },
      { replace: true },
    )
  }, [
    location.hash,
    location.pathname,
    location.search,
    navigate,
    showToast,
  ])

  return null
}

export const endpoints = {
  profile: "/users/profile/",
  organizations: {
    list: "/organizations/",
  },
  auth: {
    login: "/auth/login/",
    register: "/auth/register/",
    refresh: "/auth/refresh/",
    logout: "/auth/logout/",
    me: "/auth/me/",
    passwordReset: "/auth/password/reset/",
    passwordResetConfirm: "/auth/password/reset/confirm/",
    googleOAuth: "/auth/oauth/google/",
    emailVerify: "/auth/email/verify/",
    emailVerifyResend: "/auth/email/verify/resend/",
    // GDPR — Art. 15/20 (export) and Art. 17 (account erasure)
    exportData: "/auth/export/",
    deleteAccount: "/auth/me/",
  },
  websites: {
    list: "/websites/",
    create: "/websites/",
    detail: (id: number) => `/websites/${id}/`,
    scan: (id: number) => `/websites/${id}/scan/`,
    activeScan: (id: number) => `/websites/${id}/active_scan/`,
  },
  scans: {
    list: "/scans/",
    byWebsite: (websiteId: number) => `/scans/?website=${websiteId}`,
    detail: (id: number) => `/scans/${id}/`,
    scannerRuns: (scanId: number) => `/scans/${scanId}/scanner-runs/`,
    findings: (scanId: number) => `/scans/${scanId}/findings/`,
    recommendations: (scanId: number) => `/scans/${scanId}/recommendations/`,
    results: (scanId: number) => `/scans/${scanId}/results/`,
  },
  publicScan: {
    start: "/public/scan/",
    status: (scanId: string) => `/public/scan/${scanId}/status/`,
    email: (scanId: string) => `/public/scan/${scanId}/email/`,
    convert: (scanId: string) => `/public/scan/${scanId}/convert/`,
  },
  monitoring: {
    list: "/monitoring/",
    overview: (period: string, websiteId?: number | null) =>
      `/monitoring/overview/?period=${encodeURIComponent(period)}${
        websiteId ? `&website_id=${websiteId}` : ""
      }`,
    detail: (websiteId: number) => `/monitoring/websites/${websiteId}/`,
    triggerScan: (websiteId: number) =>
      `/monitoring/websites/${websiteId}/scan/`,
  },
  reviews: {
    list: "/reviews/",
    summary: "/reviews/summary/",
    discover: "/reviews/discover/",
    sources: "/reviews/sources/",
    sourceDetail: (id: number) => `/reviews/sources/${id}/`,
    syncSource: (id: number) => `/reviews/sources/${id}/sync/`,
    draftResponse: (id: string) => `/reviews/${id}/draft-response/`,
    approve: (id: string) => `/reviews/${id}/approve/`,
    analyzeSentiment: (id: string) => `/reviews/${id}/analyze-sentiment/`,
    draft: (id: number) => `/reviews/responses/${id}/`,
    import: "/reviews/import/",
    importJob: (id: string) => `/reviews/import/${id}/`,
  },
  alerts: {
    list: "/alerts/",
    preferences: "/alerts/preferences/",
    rules: "/alerts/rules/",
    ruleDetail: (id: number) => `/alerts/rules/${id}/`,
    muteWindows: "/alerts/mute-windows/",
    muteWindowDetail: (id: number) => `/alerts/mute-windows/${id}/`,
    detail: (id: string) => `/alerts/${id}/`,
    acknowledge: (id: string) => `/alerts/${id}/acknowledge/`,
    resolve: (id: string) => `/alerts/${id}/resolve/`,
  },
  reports: {
    list: "/reports/",
    refresh: "/reports/?refresh=1",
    generate: "/reports/generate/",
    detail: (id: string) => `/reports/${id}/`,
    pdf: (scanId: number) => `/reports/pdf/${scanId}/`,
  },
  billing: {
    plans: "/subscriptions/plans/",
    me: "/subscriptions/me/",
    checkout: "/subscriptions/checkout/",
    portal: "/subscriptions/portal/",
    cancel: "/subscriptions/cancel/",
  },
  apiKeys: {
    list: "/api-keys/",
    revoke: (id: string) => `/api-keys/${id}/`,
  },
  // Advanced suites — one route family per website (backend: seo, social,
  // advanced_security). They were served by the API but had no UI at all.
  seo: {
    audits: (websiteId: number) => `/websites/${websiteId}/seo/audits/`,
    runAudit: (websiteId: number) => `/websites/${websiteId}/seo/audits/run/`,
    keywords: (websiteId: number) => `/websites/${websiteId}/seo/keywords/`,
    backlinks: (websiteId: number) => `/websites/${websiteId}/seo/backlinks/`,
  },
  social: {
    profiles: (websiteId: number) => `/websites/${websiteId}/social/profiles/`,
    sync: (websiteId: number) => `/websites/${websiteId}/social/sync/`,
    mentions: (websiteId: number) => `/websites/${websiteId}/social/mentions/`,
    connections: (organizationId: string) =>
      `/organizations/${organizationId}/social/connections/`,
    connection: (organizationId: string, connectionId: string) =>
      `/organizations/${organizationId}/social/connections/${connectionId}/`,
    authorize: (organizationId: string, provider: string) =>
      `/organizations/${organizationId}/social/connections/${provider}/authorize/`,
    // Read-only audit trail (owner/admin only). DRF paginates server-side, so
    // the page number is the only pagination input the client sends.
    audit: (
      organizationId: string,
      params: { page?: number; provider?: string; action?: string } = {},
    ) => {
      const query = new URLSearchParams()
      if (params.page && params.page > 1) query.set("page", String(params.page))
      if (params.provider) query.set("provider", params.provider)
      if (params.action) query.set("action", params.action)
      const suffix = query.toString()
      return `/organizations/${organizationId}/social/audit/${
        suffix ? `?${suffix}` : ""
      }`
    },
  },
  security: {
    incidents: (websiteId: number) =>
      `/websites/${websiteId}/security/incidents/`,
    scan: (websiteId: number) => `/websites/${websiteId}/security/scan/`,
  },
  // AI security advisor: explains the organization's open findings. Never
  // sends a tenant id other than the one selected by the signed-in user.
  advisory: {
    chat: (organizationId: string) =>
      `/organizations/${organizationId}/ai-advisor/chat/`,
    // Long-lived findings of one asset (ZAP/Nuclei, then manual imports).
    // Metadata only: evidence stays server-side.
    assetFindings: (
      organizationId: string,
      assetId: number,
      params: { status?: "open" | "resolved" | "all"; severity?: string } = {},
    ) => {
      const query = new URLSearchParams()
      if (params.status) query.set("status", params.status)
      if (params.severity) query.set("severity", params.severity)
      const suffix = query.toString()
      return `/organizations/${organizationId}/assets/${assetId}/security/findings/${
        suffix ? `?${suffix}` : ""
      }`
    },
    recommendations: (scanId: number) =>
      `/advisory/recommendations/?scan_id=${scanId}`,
  },
  notifications: {
    channels: "/notifications/channels/",
    channel: (id: number) => `/notifications/channels/${id}/`,
    testChannel: (id: number) => `/notifications/channels/${id}/test/`,
    pushPublicKey: "/notifications/push/public-key/",
    pushSubscribe: "/notifications/push/subscribe/",
    pushTest: "/notifications/push/test/",
  },
  analytics: {
    adminOverview: "/analytics/admin/overview/",
    track: "/analytics/events/track/",
  },
} as const

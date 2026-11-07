export interface User {
  id: number
  email: string
  full_name: string
  is_email_verified: boolean
  date_joined: string
  updated_at: string
}

export type OrganizationRole = "owner" | "admin" | "analyst" | "viewer"

/** Tenant available to the signed-in user (`GET /organizations/`). */
export interface Organization {
  id: string
  name: string
  is_personal: boolean
  role: OrganizationRole | null
  member_count: number
  pending_invitations: number
  created_at: string
}

/** Response from `GET /organizations/{id}/social/connections/{provider}/authorize/`. */
export interface OAuthAuthorizeResponse {
  provider: string
  authorization_url: string
  expires_at: string
}

/** Server-side status of a stored social connection. */
export type OAuthConnectionStatus = "active" | "expired" | "revoked" | "error"

/**
 * Metadata returned by `GET /organizations/{id}/social/connections/`.
 * Token ciphertext is deliberately absent from this contract.
 */
export interface OAuthConnection {
  id: string
  organization: string
  provider: string
  external_account_id: string
  status: OAuthConnectionStatus
  expires_at: string | null
  created_at: string
  updated_at: string
}

export type SocialAuditAction = "connected" | "disconnected"

/**
 * Immutable audit row from `GET /organizations/{id}/social/audit/`.
 * The backend projects explicit metadata fields: no token, no ciphertext.
 */
export interface SocialAuditEvent {
  id: string
  organization: string
  actor: number | null
  actor_email: string
  action: SocialAuditAction
  provider: string
  external_account_id: string
  connection_id: string | null
  ip_address: string | null
  created_at: string
}

/** One row of `GET /organizations/{id}/assets/{asset}/security/findings/`. */
export interface AssetSecurityFinding {
  id: string
  asset_id: number
  scanner_source: string
  vulnerability_name: string
  severity: "critical" | "high" | "medium" | "low" | "info"
  status: "open" | "resolved"
  description: string
  detected_at: string
  resolved_at: string | null
  /** Evidence exists but is never returned by the API. */
  has_proof: boolean
}

/** Scan policy of one website (`/monitoring/websites/{id}/`). */
export interface MonitoringPolicy {
  id: number
  website_id: number
  website_domain: string
  enabled: boolean
  interval: "5m" | "15m" | "30m" | "1h" | "6h" | "24h"
  scan_type: "health" | "security" | "full"
  last_scan_at: string | null
  next_scan_at: string | null
  consecutive_failures: number
  escalation_level: number
}

/** Recommendation produced by the AI advisor (`/advisory/recommendations/`). */
export interface AdvisorRecommendation {
  id: string
  title: string
  summary: string
  action: string
  effort: "low" | "medium" | "high"
  priority: "critical" | "high" | "medium" | "low"
  confidence: number
  check_code: string
  category: string
  status: "proposed" | "accepted" | "dismissed"
  created_at: string
}

export interface AdvisorRecommendationRun {
  id: string
  status: "pending" | "running" | "succeeded" | "failed"
  model_used: string
  attempts: number
  error_code: string
  completed_at: string | null
}

/**
 * Answer of `GET /advisory/recommendations/?scan_id=`.
 * `source` tells whether the rows come from the model or the deterministic
 * fallback — the asset page must not present a fallback as AI output.
 */
export interface AdvisorRecommendationsResponse {
  scan_id: number
  run: AdvisorRecommendationRun | null
  source: "ai" | "deterministic" | "none"
  persisted: boolean
  recommendations: AdvisorRecommendation[]
}

/**
 * Answer from `POST /organizations/{id}/ai-advisor/chat/`.
 * The reply is untrusted Markdown text; it is rendered through the sanitiser.
 */
export interface AdvisorChatResponse {
  reply: string
  model: string
  findings_included: number
  context_truncated: boolean
  request_id: string | null
}

/** Editable preferences from `/api/v1/users/profile/`. */
export interface UserProfile {
  language: "en" | "fr" | "de"
  business_name: string
  business_industry: "restaurant" | "retail" | "hotel" | "auto_repair" | "beauty" | "agency" | "other" | ""
  business_country: "DE" | "FR" | "AT" | "CH" | "OTHER" | ""
  timezone: "Europe/Berlin" | "Europe/Paris" | "Europe/Vienna" | "UTC"
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  full_name?: string
  password: string
  /** UI language of the sign-up, so account emails arrive translated. */
  language?: "de" | "en" | "fr"
}

export interface AuthResponse {
  access: string
  refresh: string
  user: User
}

export interface RegisterResponse {
  user: User
  detail: string
}

export interface RefreshResponse {
  access: string
  refresh: string
}

export interface LogoutRequest {
  refresh: string
}

export interface ApiError {
  status: number
  message: string
  details?: unknown
  /** DRF validation errors keyed by serializer field (e.g. `email`, `password`). */
  fieldErrors: Record<string, string[]>
}

// Password reset types
export interface PasswordResetRequest {
  email: string
}

export interface PasswordResetResponse {
  detail: string
}

export interface PasswordResetConfirmRequest {
  uidb64: string
  token: string
  new_password: string
}

export interface PasswordResetConfirmResponse {
  detail: string
}

// Password reset
export interface PasswordResetRequest {
  email: string
}

export interface PasswordResetResponse {
  detail: string
}

export interface PasswordResetConfirmRequest {
  uidb64: string
  token: string
  new_password: string
}

export interface PasswordResetConfirmResponse {
  detail: string
}

export interface RefreshResponse {
  access: string
  refresh: string
}

export interface LogoutRequest {
  refresh: string
}

export interface Website {
  id: number
  domain: string
  display_name: string
  is_active: boolean
  is_guest: boolean
  /** Owning organization; null only for legacy organization-less websites. */
  organization_id: string | null
  created_at: string
  updated_at: string
  health_score: number | null
  health_status: "healthy" | "warning" | "critical" | "neutral" | null
  last_scan_at: string | null
  last_scan_id: number | null
  /** Present on the detail endpoint only (WebsiteDetailSerializer). */
  checks?: CheckResult[]
}

export interface ScanStep {
  key: string
  label: string
  scanner: string
  weight: number
  /** False when a deployment policy explicitly excluded this step. */
  required?: boolean
  /** Set by the orchestrator after the scanner result was persisted. */
  result_usable?: boolean
  status: string
  progress: number
  duration_ms: number | null
  error: string | null
}

export interface Scan {
  id: number
  domain: string
  website_id: number
  status:
    | "pending"
    | "queued"
    | "running"
    | "completed"
    | "partial"
    | "failed"
    | "cancelled"
  trigger: "manual" | "onboarding" | "monitoring" | "public"
  health_score: number | null
  health_status: "healthy" | "warning" | "critical" | "neutral"
  failure_message: string
  scan_type: "health" | "security" | "full"
  progress: number
  current_step: string
  steps: ScanStep[]
  queued_at: string | null
  started_at: string | null
  completed_at: string | null
  failed_at: string | null
  created_at: string
  updated_at: string
  duration_seconds: number | null
  is_active: boolean
  /**
   * Only the detail endpoint (GET /scans/{id}/) embeds check results: the list
   * endpoint uses a lightweight serializer, so treat this as optional.
   */
  check_results?: CheckResult[]
}

export interface CheckResult {
  id: number
  category: "website" | "ssl" | "dns" | "email_security" | "security_headers" | "performance" | "uptime"
  status: "healthy" | "warning" | "critical" | "neutral"
  score: number | null
  max_score: number
  summary: string
  recommendation: string
  technical_details: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ScannerRun {
  id: number
  scanner: string
  status:
    | "pending"
    | "running"
    | "completed"
    | "partial"
    | "failed"
    | "timeout"
    | "cancelled"
    | "unavailable"
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  exit_code: number | null
  error_message: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface Finding {
  id: number
  scanner: string
  category: string
  check_code: string
  title: string
  description: string
  severity: "info" | "low" | "medium" | "high" | "critical"
  status: "pass" | "fail" | "warning" | "not_applicable" | "unknown"
  evidence: Record<string, unknown>
  detected_value: unknown
  expected_value: unknown
  recommendation: string
  reference_url: string
  duration_ms: number | null
  created_at: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type HealthStatus = "healthy" | "warning" | "critical" | "neutral"

export interface Alert {
  id: string
  website_id: number
  website_domain: string
  scan_id: number | null
  alert_type: string
  severity: "info" | "warning" | "critical"
  status: "firing" | "acknowledged" | "resolved"
  title: string
  message: string
  metadata: Record<string, unknown>
  notification_channels_sent: string[]
  acknowledged_at: string | null
  acknowledged_by_id: number | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}

/** Payload returned by GET /api/v1/auth/export/ (GDPR Art. 15/20). */
export interface AccountExport {
  export_metadata: {
    schema_version: number
    format: string
    generated_at: string
    subject_user_id: number
    subject_email: string
    legal_basis: string
  }
  account: User
  record_counts: Record<string, number>
  [collection: string]: unknown
}

export interface AccountDeletionResult {
  detail: string
  deleted: Record<string, number>
  leftovers_removed: Record<string, number>
}

export interface PublicCheckResult {
  category: string
  score: number | null
  status: "healthy" | "warning" | "critical" | "neutral"
  message: string
  details: Record<string, unknown>
  recommendation: string
}

export type PlanTier = "free" | "pro" | "business" | "agency"
export type BillingCycle = "monthly" | "yearly"

export interface Plan {
  id: number
  tier: PlanTier
  name: string
  description: string
  price_monthly: string
  price_yearly: string
  max_websites: number
  max_scans_per_month: number
  min_scan_interval: string
  can_export_reports: boolean
  can_use_api: boolean
  can_add_team_members: boolean
  max_team_members: number
  max_alert_channels: number
  features: string[]
  is_active: boolean
}

export interface PlanLimits {
  max_websites: number
  max_scans_per_month: number
  max_alert_channels: number
  max_team_members: number
  can_export_reports: boolean
  can_use_api: boolean
  can_add_team_members: boolean
  min_scan_interval: string
}

export interface PlanUsage {
  websites: number
  scans_this_month: number
  alert_channels: number
}

export interface SubscriptionMe {
  id: string
  plan: Plan
  plan_tier: PlanTier
  status: "active" | "cancelled" | "past_due" | "trialing" | "expired"
  billing_cycle: BillingCycle
  started_at: string
  current_period_start: string | null
  current_period_end: string | null
  cancelled_at: string | null
  trial_end: string | null
  is_active: boolean
  is_free: boolean
  created_at: string
  updated_at: string
  limits: PlanLimits | null
  usage: PlanUsage
  billing: {
    enabled: boolean
    provider: string
    customer_id: string | null
    cancel_at_period_end: boolean
  }
}

export interface CheckoutResponse {
  checkout_url: string
  transaction_id: string | null
  price_id: string
}

export interface PortalResponse {
  portal_url: string
}

export interface MonitoringSummary {
  monitored_websites: number
  enabled_websites: number
  healthy_websites: number
  warning_websites: number
  critical_websites: number
  uptime_percent: number | null
  uptime_checks: number
  failed_checks: number
  last_check_at: string | null
  interval: string | null
}

export interface MonitoringSeriesPoint {
  bucket_start: string
  uptime_percent: number
  checks: number
  downtime_checks: number
}

export interface MonitoringConfig {
  id: number
  website_id: number
  website_domain: string
  enabled: boolean
  interval: string
  scan_type: "health" | "security" | "full"
  last_scan_at: string | null
  next_scan_at: string | null
  consecutive_failures: number
  escalation_level: number
  created_at: string
  updated_at: string
}

export interface MonitoringWebsite {
  id: number
  domain: string
  enabled: boolean
  interval: string
  last_scan_at: string | null
  next_scan_at: string | null
  consecutive_failures: number
  escalation_level: number
  health_score: number | null
  health_status: HealthStatus
  last_check_at: string | null
}

export interface MonitoringEvent {
  id: string
  kind: "alert" | "scan"
  severity: "critical" | "warning" | "info" | "healthy" | "neutral" | string
  status: string
  title: string
  detail: string
  occurred_at: string
}

export interface MonitoringOverview {
  period: "24H" | "7D" | "30D" | "90D"
  from: string
  to: string
  website_id: number | null
  summary: MonitoringSummary
  series: MonitoringSeriesPoint[]
  websites: MonitoringWebsite[]
  events: MonitoringEvent[]
}

export interface Review {
  id: string
  source_id: number
  source_provider: string
  source_name: string
  external_id: string
  author_name: string
  author_photo: string
  rating: string | null
  text: string
  sentiment: "positive" | "neutral" | "negative"
  language: string
  is_approved: boolean
  review_date: string | null
  created_at: string
  updated_at: string
  response_status: "draft" | "approved" | "sent" | null
  response_draft_id: number | null
  response_draft_content: string
  has_response: boolean
  needs_response: boolean
}

export interface ReviewSummary {
  total: number
  average_rating: number | null
  new_this_month: number
  needs_response: number
  by_platform: Record<string, number>
  sources: number
  enabled_sources: number
  last_synced_at: string | null
  latest_review_at: string | null
}

export interface ResponseDraft {
  id: number
  review: string
  content: string
  status: "draft" | "approved" | "sent"
  sent_at: string | null
  created_at: string
  updated_at: string
}

export interface ReportCheckCategory {
  avg_score: number | null
  max_score: number | null
  critical_count: number
  warning_count: number
  healthy_count: number
}

export interface ReportScorePoint {
  date: string
  score: number | null
  status: string
}

export interface Report {
  id: string
  website_id: number
  website_domain: string
  period: "weekly" | "monthly"
  period_start: string
  period_end: string
  status: "pending" | "generated" | "failed"
  current_score: number | null
  previous_score: number | null
  score_change: number | null
  score_trend: "up" | "down" | "stable" | "neutral"
  check_breakdown: Record<string, ReportCheckCategory>
  improvements: string[]
  problems: string[]
  recommendations: string[]
  score_history: ReportScorePoint[]
  total_scans: number
  generated_at: string | null
  created_at: string
  updated_at: string
  latest_scan_id: number | null
}

// ─── Advanced suites (SEO, reputation, advanced security) ───────────────────

export interface SEOAudit {
  id: string
  website: number
  overall_score: number
  technical_score: number
  content_score: number
  mobile_score: number
  meta_tags: Record<string, unknown>
  robots_txt: string
  sitemap: string
  issues: string[]
  created_at: string
}

export interface Keyword {
  id: number
  website: number
  term: string
  country: string
  search_volume: number | null
  difficulty: number | null
  current_rank: number | null
  previous_rank: number | null
  tracked: boolean
  last_checked_at: string | null
}

export interface Backlink {
  id: number
  website: number
  source_url: string
  target_url: string
  anchor_text: string
  domain_authority: number
  is_dofollow: boolean
  first_seen: string
  last_seen: string
}

export type SocialProvider = "facebook" | "instagram" | "twitter" | "linkedin"

export interface SocialProfile {
  id: number
  website: number
  provider: SocialProvider
  handle: string
  profile_url: string
  followers: number
  engagement_rate: number
  last_synced_at: string | null
  created_at: string
}

export interface SocialMention {
  id: number
  website: number
  platform: string
  author: string
  content: string
  url: string
  sentiment: "positive" | "neutral" | "negative"
  mentioned_at: string
  detected_at: string
}

export interface SecurityIncident {
  id: string
  website: number
  incident_type: "malware" | "open_port" | "waf_missing" | "vulnerability"
  severity: "low" | "medium" | "high" | "critical"
  title: string
  description: string
  evidence: Record<string, unknown>
  is_resolved: boolean
  detected_at: string
}

export interface AlertRule {
  id: number
  website: number | null
  name: string
  metric: "health_score" | "ssl_days_remaining" | "load_time_ms" | "page_size_kb"
  operator: "gt" | "lt" | "gte" | "lte" | "eq"
  threshold: number
  severity: "warning" | "critical"
  enabled: boolean
  cooldown_minutes: number
  last_triggered_at: string | null
  created_at: string
}

export interface MuteWindow {
  id: number
  website_ids: number[]
  start_at: string
  end_at: string
  reason: "maintenance" | "deployment" | "migration" | "other"
  note: string
  is_active: boolean
  created_at: string
}

export interface ApiKey {
  id: string
  name: string
  prefix: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
  /** Returned once, only in the creation response. */
  api_key?: string
}

export type NotificationChannelType = "email" | "slack" | "discord" | "webhook" | "sms"

export interface NotificationChannel {
  id: number
  channel_type: NotificationChannelType
  name: string
  enabled: boolean
  config: Record<string, unknown>
  severities: string[]
  alert_types: string[]
  created_at: string
  updated_at: string
}

export interface AlertPreferences {
  ssl_expiring_enabled: boolean
  ssl_invalid_enabled: boolean
  website_offline_enabled: boolean
  dns_problem_enabled: boolean
  email_security_enabled: boolean
  security_headers_enabled: boolean
  performance_enabled: boolean
  score_drop_enabled: boolean
  scan_failed_enabled: boolean
  ssl_expiry_warning_days: number
  ssl_expiry_critical_days: number
  score_drop_threshold: number
  consecutive_failures_critical: number
  digest_frequency: "immediate" | "hourly" | "daily"
  quiet_hours_start: string | null
  quiet_hours_end: string | null
}

export interface ReviewSource {
  id: number
  website: number
  provider: "google" | "trustpilot" | "tripadvisor" | "manual"
  name: string
  config: Record<string, unknown>
  enabled: boolean
  last_synced_at: string | null
  created_at: string
  updated_at: string
}

export interface ReviewImportJob {
  id: string
  source: number
  file_type: "csv" | "json"
  total_rows: number
  imported_count: number
  failed_count: number
  errors: string[]
  status: "pending" | "processing" | "completed" | "failed"
  created_at: string
  completed_at: string | null
}

export interface AdminAnalytics {
  overview: {
    total_users: number
    total_websites: number
    total_scans: number
    total_visitors: number
    monetization_index: number
  }
  traffic_14d: { day: string; views: number; uniques: number }[]
  funnel: {
    signups: number
    added_websites: number
    scans_triggered: number
  }
  cookies: { accepted_all: number; essential_only: number }
  subscriptions: {
    mrr_eur: number
    arr_eur: number
    paying_users: number
    trialing_users: number
    by_plan: { tier: string; name: string; count: number; mrr_eur: number }[]
  }
  estimated_revenue: {
    ads_eur: number
    affiliate_eur: number
    total_eur: number
  }
  latest_users: {
    id: number
    email: string
    created_at: string | null
    websites_count: number
  }[]
}

/** Accepted response from `POST /public/scan/`. */
export interface PublicScanCreated {
  id: string
  scan_id: string
  domain: string
  status: "queued" | "running" | "completed" | "failed"
  progress: number
  steps: ScanStep[]
  poll_url: string
}

/** One health dimension, as serialised by the public scan report. */
export interface PublicScanCheck {
  status: "healthy" | "warning" | "critical" | "neutral" | string
  score: number | null
  message: string
  remediation: {
    code?: string
    server_type?: string
    nginx?: string
    apache?: string
    htaccess?: string
  }
  days_until_expiry?: number
  is_monitored?: boolean
  is_up?: boolean
}

/** Full report from `GET /public/scan/{id}/status/`. */
export interface PublicScanReport {
  id: string
  scan_id: string
  domain: string
  url: string
  status:
    | "pending"
    | "queued"
    | "running"
    | "completed"
    | "partial"
    | "failed"
    | "cancelled"
  /** Guest reports are public and shareable; account scans are private. */
  is_guest: boolean
  score: number
  progress: number
  current_step: string
  steps: ScanStep[]
  created_at: string
  scanned_at: string
  summary: { critical: number; warnings: number; passed: number }
  /** Keyed by category: website, ssl, dns, email_security, … */
  checks: Record<string, PublicScanCheck>
  preview_limitations: string[]
  cta: {
    convert_url: string
    email_report_url: string
    register_url: string
  }
}

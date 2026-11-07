// frontend/src/types/publicScan.ts
// Typage strict de la réponse API GET /api/v1/public/scan/{id}/status/

export interface CheckRemediation {
  code?: string;
  server_type?: 'nginx' | 'apache' | 'htaccess' | 'generic';
  nginx?: string;
  apache?: string;
  htaccess?: string;
}

export interface CheckItem {
  status: 'critical' | 'warning' | 'passed' | 'healthy' | 'good' | 'online' | 'unknown';
  score: number | null;
  // The public endpoint currently omits max_score; render score-only when absent.
  max_score?: number | null;
  message: string;
  // TODO BACKEND: Le champ remediation n'est pas encore retourné par l'API.
  // Fallback actuel : afficher le message brut comme correction.
  remediation?: CheckRemediation;
  // TODO BACKEND: Le champ is_monitored n'est pas encore retourné pour uptime.
  // Fallback actuel : déduire depuis le score (0 = non pondéré).
  is_monitored?: boolean;
  // TODO BACKEND: Le champ is_up n'est pas encore retourné pour uptime.
  // Fallback actuel : déduire depuis le status.
  is_up?: boolean;
  // TODO BACKEND: Le champ days_until_expiry n'est pas encore retourné pour ssl.
  // Fallback actuel : ne pas afficher la ligne d'expiration.
  days_until_expiry?: number;
}

export interface ScanSummary {
  critical: number;
  warnings: number;
  passed: number;
}

// TODO BACKEND: Le champ meta n'est pas encore retourné par l'API.
// Fallback actuel : ne pas afficher la section social proof.
export interface ScanMeta {
  total_monitored_sites?: number;
  average_rating?: number;
}

export interface PublicScanResponse {
  scan_id: string;
  // TODO BACKEND: Le champ url n'est pas systématiquement retourné.
  // Fallback actuel : utiliser le champ domain.
  url?: string;
  domain: string;
  score: number;
  status: 'completed' | 'pending' | 'processing' | 'queued' | 'failed';
  summary: ScanSummary;
  checks: Record<string, CheckItem>;
  // TODO BACKEND: Le champ created_at n'est pas encore retourné.
  // Fallback actuel : afficher "Date inconnue".
  created_at?: string;
  scanned_at?: string;
  meta?: ScanMeta;
}

export type CheckStatusNormalized = 'critical' | 'warning' | 'passed';

export function normalizeStatus(raw: string): CheckStatusNormalized {
  const s = raw.toLowerCase();
  if (['critical', 'failed', 'down'].includes(s)) return 'critical';
  if (['warning', 'degraded'].includes(s)) return 'warning';
  return 'passed';
}

export const CHECK_ORDER: Record<CheckStatusNormalized, number> = {
  critical: 0,
  warning: 1,
  passed: 2,
};

export const CHECK_LABELS: Record<string, string> = {
  website: 'Accessibilité du site',
  ssl: 'Certificat SSL / HTTPS',
  dns: 'Résolution DNS',
  email_security: 'Sécurité email (SPF / DMARC)',
  security_headers: 'En-têtes de sécurité HTTP',
  performance: 'Performance & Vitesse',
  uptime: 'Disponibilité (Uptime)',
  accessibility: 'Accessibilité (a11y)',
};

export const CHECK_ICONS: Record<string, string> = {
  website: '🌐',
  ssl: '🔒',
  dns: '📡',
  email_security: '📧',
  security_headers: '🛡️',
  performance: '⚡',
  uptime: '🟢',
  accessibility: '♿',
};

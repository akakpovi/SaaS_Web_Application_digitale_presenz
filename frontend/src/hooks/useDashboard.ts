import { useState, useEffect } from 'react';
import { websiteService, scanService, Website, Scan } from '../services/websiteService';
import { alertService, Alert } from '../services/alertService';
import { useAuth } from '../context/AuthContext';

export interface DashboardWebsite {
  id: string;
  domain: string;
  status: 'healthy' | 'warning' | 'critical' | 'neutral';
  statusLabel: string;
  score: number;
  uptime: string;
  ssl: string;
  lastCheck: string;
  issues: number;
  lastScan?: Scan;
}

export interface DashboardData {
  websites: DashboardWebsite[];
  kpis: {
    avgScore: number;
    totalWebsites: number;
    healthyCount: number;
    openIssues: number;
    lastCheck: string;
  };
  recentAlerts: Alert[];
  scoreBreakdown: { label: string; score: number; max: number }[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

function formatLastCheck(dateStr: string | null): string {
  if (!dateStr) return 'Never';
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'healthy': return 'Online';
    case 'warning': return 'Needs attention';
    case 'critical': return 'Offline';
    default: return 'Unknown';
  }
}

function getSslStatus(scan?: Scan): string {
  if (!scan?.results) return 'Unknown';
  const sslResult = scan.results.find(r => r.category === 'ssl');
  if (!sslResult) return 'Unknown';
  if (sslResult.status === 'healthy') return 'Valid';
  if (sslResult.status === 'warning') return 'Expires soon';
  return 'Invalid';
}

function getScoreBreakdown(scans: Scan[]): { label: string; score: number; max: number }[] {
  const categories = [
    { key: 'website', label: 'Website', max: 20 },
    { key: 'ssl', label: 'SSL', max: 20 },
    { key: 'dns', label: 'DNS', max: 15 },
    { key: 'email_security', label: 'Email', max: 15 },
    { key: 'security_headers', label: 'Security', max: 15 },
    { key: 'performance', label: 'Performance', max: 15 },
  ];

  // Prendre le dernier scan avec résultats
  const scanWithResults = scans.find(s => s.results && s.results.length > 0);

  return categories.map(({ key, label, max }) => {
    if (scanWithResults?.results) {
      const result = scanWithResults.results.find(r => r.category === key);
      return { label, score: result?.score ?? 0, max };
    }
    return { label, score: 0, max };
  });
}

export function useDashboard(): DashboardData {
  const { user } = useAuth();
  const [websites, setWebsites] = useState<DashboardWebsite[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [scoreBreakdown, setScoreBreakdown] = useState<{ label: string; score: number; max: number }[]>([]);
  const [kpis, setKpis] = useState({
    avgScore: 0,
    totalWebsites: 0,
    healthyCount: 0,
    openIssues: 0,
    lastCheck: 'Never',
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = () => setTick(t => t + 1);

  useEffect(() => {
    if (!user) return;

    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // Charger en parallèle
        const [rawWebsites, alerts] = await Promise.all([
          websiteService.list(),
          alertService.list({ status: 'firing' }),
        ]);

        // Pour chaque site, charger le dernier scan
        const websitesWithScans = await Promise.all(
          rawWebsites.map(async (site) => {
            try {
              const scans = await scanService.list(site.id);
              const lastScan = scans[0]; // Le plus récent

              // Charger les résultats du dernier scan si disponible
              if (lastScan && lastScan.status === 'completed') {
                try {
                  const results = await scanService.getResults(lastScan.id);
                  lastScan.results = results;
                } catch {
                  // Pas de résultats = pas grave
                }
              }

              return { site, lastScan };
            } catch {
              return { site, lastScan: undefined };
            }
          })
        );

        // Construire les données dashboard
        const dashWebsites: DashboardWebsite[] = websitesWithScans.map(({ site, lastScan }) => {
          const score = lastScan?.health_score ?? 0;
          const status = (lastScan?.health_status ?? 'neutral') as 'healthy' | 'warning' | 'critical' | 'neutral';
          const siteAlerts = alerts.filter(a => a.website === site.id);

          return {
            id: String(site.id),
            domain: site.domain,
            status,
            statusLabel: getStatusLabel(status),
            score,
            uptime: '—',
            ssl: getSslStatus(lastScan),
            lastCheck: formatLastCheck(lastScan?.completed_at ?? null),
            issues: siteAlerts.length,
            lastScan,
          };
        });

        // KPIs
        const scores = dashWebsites.map(w => w.score).filter(s => s > 0);
        const avgScore = scores.length > 0
          ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
          : 0;
        const healthyCount = dashWebsites.filter(w => w.status === 'healthy').length;
        const lastChecks = websitesWithScans
          .map(({ lastScan }) => lastScan?.completed_at)
          .filter(Boolean) as string[];
        const mostRecent = lastChecks.sort().reverse()[0];

        // Score breakdown depuis le premier site avec scan
        const allScans = websitesWithScans
          .map(({ lastScan }) => lastScan)
          .filter(Boolean) as Scan[];
        const breakdown = getScoreBreakdown(allScans);

        setWebsites(dashWebsites);
        setRecentAlerts(alerts.slice(0, 3));
        setScoreBreakdown(breakdown);
        setKpis({
          avgScore,
          totalWebsites: rawWebsites.length,
          healthyCount,
          openIssues: alerts.length,
          lastCheck: formatLastCheck(mostRecent ?? null),
        });
      } catch (err: any) {
        setError(err?.message ?? 'Failed to load dashboard');
      } finally {
        setIsLoading(false);
      }
    };

    load();
  }, [user, tick]);

  return { websites, kpis, recentAlerts, scoreBreakdown, isLoading, error, refetch };
}

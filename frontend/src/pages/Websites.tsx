import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Globe, Plus, X, RefreshCw, Trash2 } from "lucide-react";
import { Card, StatusBadge, ScoreRing, Button } from "../components/ui";
import { useTranslation } from "react-i18next";
import { websiteService, scanService, Website, Scan } from "../services/websiteService";
import { alertService } from "../services/alertService";

interface WebsiteCard {
  id: string;
  domain: string;
  display_name: string;
  status: 'healthy' | 'warning' | 'critical' | 'neutral';
  statusLabel: string;
  score: number;
  ssl: string;
  sslStatus: 'healthy' | 'warning' | 'critical' | 'neutral';
  lastCheck: string;
  issues: number;
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
    default: return 'No data';
  }
}

function getSslInfo(scan?: Scan): { label: string; status: 'healthy' | 'warning' | 'critical' | 'neutral' } {
  if (!scan?.results) return { label: 'Unknown', status: 'neutral' };
  const sslResult = scan.results.find(r => r.category === 'ssl');
  if (!sslResult) return { label: 'Unknown', status: 'neutral' };
  if (sslResult.status === 'healthy') return { label: 'Valid', status: 'healthy' };
  if (sslResult.status === 'warning') return { label: 'Expires soon', status: 'warning' };
  return { label: 'Invalid', status: 'critical' };
}

// Modal ajout de site
function AddWebsiteModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [domain, setDomain] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const site = await websiteService.create(domain.trim());
      // Lancer un scan automatiquement
      try {
        await websiteService.scan(site.id);
      } catch {
        // Scan echoue = pas grave, le site est cree
      }
      onAdded();
      onClose();
    } catch (err: any) {
      const data = err?.response?.data;
      if (data?.domain) setError(data.domain[0]);
      else if (data?.detail) setError(data.detail);
      else if (data?.non_field_errors) setError(data.non_field_errors[0]);
      else setError('Failed to add website. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-slate-900">Add a website</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
            <X size={18} className="text-slate-500" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && (
            <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-slate-700">Domain</label>
            <input
              type="text"
              placeholder="example.com"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              autoFocus
              required
            />
            <p className="text-xs text-slate-400">Enter the domain without http:// or www.</p>
          </div>

          <div className="flex gap-3 mt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 text-sm font-medium text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <Button type="submit" className="flex-1" disabled={isLoading || !domain.trim()}>
              {isLoading ? 'Adding...' : 'Add & scan'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Websites() {
  const [sites, setSites] = useState<WebsiteCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [scanningId, setScanningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadWebsites = async () => {
    setIsLoading(true);
    setError('');
    try {
      const [rawSites, alerts] = await Promise.all([
        websiteService.list(),
        alertService.list({ status: 'firing' }),
      ]);

      const cards = await Promise.all(
        rawSites.map(async (site) => {
          try {
            const scans = await scanService.list(site.id);
            const lastScan = scans[0];

            if (lastScan?.status === 'completed') {
              try {
                const results = await scanService.getResults(lastScan.id);
                lastScan.results = results;
              } catch { /* pas de résultats */ }
            }

            const siteAlerts = alerts.filter(a => a.website_id === site.id);
            const ssl = getSslInfo(lastScan);
            const status = (lastScan?.health_status ?? 'neutral') as 'healthy' | 'warning' | 'critical' | 'neutral';

            return {
              id: String(site.id),
              domain: site.domain,
              display_name: site.display_name,
              status,
              statusLabel: getStatusLabel(status),
              score: lastScan?.health_score ?? 0,
              ssl: ssl.label,
              sslStatus: ssl.status,
              lastCheck: formatLastCheck(lastScan?.completed_at ?? null),
              issues: siteAlerts.length,
            } as WebsiteCard;
          } catch {
            return {
              id: String(site.id),
              domain: site.domain,
              display_name: site.display_name,
              status: 'neutral' as const,
              statusLabel: 'No data',
              score: 0,
              ssl: 'Unknown',
              sslStatus: 'neutral' as const,
              lastCheck: 'Never',
              issues: 0,
            };
          }
        })
      );

      setSites(cards);
    } catch (err: any) {
      setError('Failed to load websites. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadWebsites();
  }, []);

  const handleScan = async (e: React.MouseEvent, siteId: string) => {
    e.preventDefault();
    e.stopPropagation();
    setScanningId(siteId);
    try {
      await websiteService.scan(Number(siteId));
      // Recharger apres 3 secondes (le scan est async)
      setTimeout(loadWebsites, 3000);
    } catch {
      // Ignore
    } finally {
      setTimeout(() => setScanningId(null), 3000);
    }
  };

  const handleDelete = async (e: React.MouseEvent, siteId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Delete this website and all its data?')) return;
    setDeletingId(siteId);
    try {
      await websiteService.delete(Number(siteId));
      setSites(prev => prev.filter(s => s.id !== siteId));
    } catch {
      setError('Failed to delete website.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      {showModal && (
        <AddWebsiteModal
          onClose={() => setShowModal(false)}
          onAdded={loadWebsites}
        />
      )}

      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Websites</h1>
          <p className="text-slate-500 mt-1">Manage and monitor all your websites from one place.</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={16} /> Add website
        </Button>
      </div>

      {error && (
        <div className="mb-6 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {sites.map((site) => (
            <Link to={`/app/websites/${site.id}`} key={site.id}>
              <Card className="p-5 h-full hover:shadow-md transition-shadow">
                <div className="flex items-start gap-3 mb-4">
                  <div className="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0">
                    <Globe size={18} className="text-indigo-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-slate-900 truncate">{site.domain}</p>
                    <StatusBadge status={site.status} label={site.statusLabel} />
                  </div>
                  {/* Actions */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={(e) => handleScan(e, site.id)}
                      disabled={scanningId === site.id}
                      className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                      title="Run scan"
                    >
                      <RefreshCw size={14} className={`text-slate-400 ${scanningId === site.id ? 'animate-spin' : ''}`} />
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, site.id)}
                      disabled={deletingId === site.id}
                      className="p-1.5 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete website"
                    >
                      <Trash2 size={14} className="text-slate-400 hover:text-red-500" />
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between mb-4">
                  <ScoreRing score={site.score} size={72} label="Health score" />
                  <div className="flex flex-col gap-2 text-right">
                    <div>
                      <p className="text-xs text-slate-500">SSL</p>
                      <StatusBadge status={site.sslStatus} label={site.ssl} />
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                  <p className="text-xs text-slate-400">Last check: {site.lastCheck}</p>
                  {site.issues > 0 ? (
                    <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full border border-amber-200 font-medium">
                      {site.issues} issue{site.issues > 1 ? "s" : ""}
                    </span>
                  ) : (
                    <span className="text-xs text-emerald-600 font-medium">✓ All good</span>
                  )}
                </div>
              </Card>
            </Link>
          ))}

          {/* Add website card */}
          <div
            onClick={() => setShowModal(true)}
            className="border-2 border-dashed border-slate-200 rounded-2xl p-5 flex flex-col items-center justify-center text-center min-h-48 hover:border-indigo-300 hover:bg-indigo-50/50 transition-all cursor-pointer group"
          >
            <div className="w-12 h-12 bg-slate-100 group-hover:bg-indigo-100 rounded-xl flex items-center justify-center mb-3 transition-colors">
              <Plus size={20} className="text-slate-400 group-hover:text-indigo-600 transition-colors" />
            </div>
            <p className="font-medium text-slate-600 group-hover:text-indigo-700 transition-colors">Add website</p>
            <p className="text-sm text-slate-400 mt-1">Monitor a new domain</p>
          </div>
        </div>
      )}
    </div>
  );
}

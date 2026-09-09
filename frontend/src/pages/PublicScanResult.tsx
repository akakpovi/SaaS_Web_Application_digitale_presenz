import React, { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import { usePublicScanStatus } from '../hooks/usePublicScanStatus';
import PWAPromptModal from '../components/PWAPromptModal';
import { RemediationBlock } from '../components/RemediationBlock';
import { REMEDIATION_GUIDES } from '../types/remediation';
import {
  normalizeStatus,
  CHECK_ORDER,
  CHECK_LABELS,
  CHECK_ICONS,
} from '../types/publicScan';

function useCookieConsentResolved(): boolean {
  try {
    return localStorage.getItem('cookie_consent') !== null;
  } catch {
    return true;
  }
}

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function PublicScanResult() {
  const { scanId, lang } = useParams<{ scanId: string; lang?: string }>();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { scan, loading, error, retryMinutes, rescan, sendEmail } = usePublicScanStatus(scanId);

  const currentLang = lang || i18n.language?.split('-')[0] || 'fr';

  const [copiedCheck, setCopiedCheck] = useState<string | null>(null);
  const [emailInput, setEmailInput] = useState('');
  const [emailError, setEmailError] = useState('');
  const [emailSent, setEmailSent] = useState(false);
  const [emailSending, setEmailSending] = useState(false);
  const [rescanning, setRescanning] = useState(false);
  const [activeServerTab, setActiveServerTab] = useState<Record<string, string>>({});

  // 1. Logique de défilement pour la Sticky Bottom Bar
  const [scrollY, setScrollY] = useState(0);
  const [isScrollingUp, setIsScrollingUp] = useState(false);
  const lastScrollY = useRef(0);

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      setIsScrollingUp(currentScrollY < lastScrollY.current);
      setScrollY(currentScrollY);
      lastScrollY.current = currentScrollY;
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Fermeture manuelle de la Sticky Bar stockée en session
  const [stickyDismissed, setStickyDismissed] = useState(
    () => sessionStorage.getItem('sticky_bar_dismissed') === 'true'
  );

  const cookieConsentResolved = useCookieConsentResolved();

  // 2. Gestion de la priorité absolue des bannières/toasts du bas (z-index)
  // Règle d'or : Cookie Banner (z-50) > Sticky Bar (z-40) > PWA Toast (z-30)
  const showStickyBar =
    scrollY > 300 &&
    !isScrollingUp &&
    cookieConsentResolved &&
    !stickyDismissed;

  // Le Toast PWA est géré par PWAPromptModal (qui s'affiche si CookieConsent est résolu et !cooldown)

  const sortedChecks = useMemo(() => {
    if (!scan?.checks) return [];
    return Object.entries(scan.checks)
      .map(([key, check]) => ({
        key,
        ...check,
        normalizedStatus: normalizeStatus(check.status),
      }))
      .sort((a, b) => {
        const diff = CHECK_ORDER[a.normalizedStatus] - CHECK_ORDER[b.normalizedStatus];
        if (diff !== 0) return diff;
        return a.key.localeCompare(b.key);
      });
  }, [scan?.checks]);

  const scoreLabel = useMemo(() => {
    if (!scan) return '';
    const s = scan.score;
    const c = scan.summary.critical;
    if (s >= 80 && c === 0) {
      return currentLang === 'fr' ? 'Excellent' : currentLang === 'de' ? 'Hervorragend' : 'Excellent';
    }
    if (s >= 80 && c > 0) {
      return currentLang === 'fr'
        ? `Bon état — ${c} correction urgente`
        : currentLang === 'de'
          ? `Guter Zustand — ${c} dringende Korrektur`
          : `Good — ${c} urgent fix`;
    }
    if (s >= 50) {
      return currentLang === 'fr' ? 'À améliorer' : currentLang === 'de' ? 'Verbesserungsfähig' : 'Needs improvement';
    }
    return currentLang === 'fr' ? 'Critique' : currentLang === 'de' ? 'Kritisch' : 'Critical';
  }, [scan, currentLang]);

  const handleCopy = useCallback(async (checkKey: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    setCopiedCheck(checkKey);
    setTimeout(() => setCopiedCheck(null), 2500);
  }, []);

  const handleRescan = useCallback(async () => {
    if (!scan) return;
    setRescanning(true);
    const newId = await rescan(scan.url || `https://${scan.domain}`);
    if (newId) navigate(`/${currentLang}/scan/${newId}`);
    setRescanning(false);
  }, [scan, rescan, navigate, currentLang]);

  const handleSendEmail = useCallback(async () => {
    if (!scan || !emailInput) return;
    setEmailError('');
    if (!isValidEmail(emailInput)) {
      setEmailError(
        currentLang === 'fr'
          ? 'Adresse email invalide.'
          : currentLang === 'de'
            ? 'Ungültige E-Mail-Adresse.'
            : 'Invalid email address.'
      );
      return;
    }
    setEmailSending(true);
    const ok = await sendEmail(scan.scan_id, emailInput);
    if (ok) setEmailSent(true);
    setEmailSending(false);
  }, [scan, emailInput, sendEmail, currentLang]);

  const handleDismissStickyBar = () => {
    sessionStorage.setItem('sticky_bar_dismissed', 'true');
    setStickyDismissed(true);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-3xl px-4 py-12">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-64 rounded bg-slate-200" />
            <div className="h-4 w-48 rounded bg-slate-200" />
            <div className="mx-auto h-32 w-32 rounded-full bg-slate-200" />
            <div className="grid grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 rounded-xl bg-slate-200" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error === 'not_found' || !scan) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="text-center">
          <p className="text-lg font-semibold text-slate-700">
            {currentLang === 'fr'
              ? "Ce scan n'existe pas ou a expiré."
              : currentLang === 'de'
                ? "Dieser Scan existiert nicht oder ist abgelaufen."
                : "This scan doesn't exist or has expired."}
          </p>
          <Link
            to={`/${currentLang}/`}
            className="mt-4 inline-block rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            {currentLang === 'fr'
              ? 'Lancer un nouveau scan'
              : currentLang === 'de'
                ? 'Neuen Scan starten'
                : 'Run a new scan'}
          </Link>
        </div>
      </div>
    );
  }

  const displayUrl = scan.url || scan.domain;
  const scanDate =
    scan.created_at || scan.scanned_at
      ? new Date(scan.created_at || scan.scanned_at!).toLocaleDateString(
        currentLang === 'fr' ? 'fr-FR' : currentLang === 'de' ? 'de-DE' : 'en-US',
        { day: 'numeric', month: 'long', year: 'numeric' }
      )
      : 'Date inconnue';

  const scoreColor = scan.score >= 80 ? 'text-emerald-600' : scan.score >= 50 ? 'text-amber-600' : 'text-red-600';
  const ringColor = scan.score >= 80 ? 'ring-emerald-500' : scan.score >= 50 ? 'ring-amber-500' : 'ring-red-500';
  const scoreBg = scan.score >= 80 ? 'bg-emerald-50' : scan.score >= 50 ? 'bg-amber-50' : 'bg-red-50';

  const showSocialProof = scan.meta?.total_monitored_sites && scan.meta?.average_rating;

  // Composant d'email dupliqué (partage la logique et l'état)
  const EmailCaptureSection = () => (
    <section className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
      <h3 className="text-md font-bold text-slate-900">
        {currentLang === 'fr'
          ? '📬 Recevez ce rapport par email'
          : currentLang === 'de'
            ? '📬 Erhalten Sie diesen Bericht per E-Mail'
            : '📬 Receive this report by email'}
      </h3>
      <p className="mt-1 text-sm text-slate-500">
        {currentLang === 'fr'
          ? 'Partagez-le avec votre développeur ou votre équipe technique.'
          : currentLang === 'de'
            ? 'Teilen Sie diesen Bericht mit Ihrem Entwickler oder Ihrem Technik-Team.'
            : 'Share it with your developer or technical team.'}
      </p>
      {emailSent ? (
        <div className="mt-4 rounded-lg bg-emerald-100 p-4 text-center">
          <p className="text-sm font-semibold text-emerald-700">
            {currentLang === 'fr'
              ? `✅ Rapport envoyé à ${emailInput} !`
              : currentLang === 'de'
                ? `✅ Bericht an ${emailInput} gesendet!`
                : `✅ Report sent to ${emailInput}!`}
          </p>
        </div>
      ) : (
        <div className="mt-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="email"
              value={emailInput}
              onChange={(e) => {
                setEmailInput(e.target.value);
                setEmailError('');
              }}
              placeholder="votre@email.com"
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <button
              onClick={handleSendEmail}
              disabled={emailSending || !emailInput}
              className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {emailSending ? '...' : currentLang === 'fr' ? 'Envoyer' : currentLang === 'de' ? 'Senden' : 'Send'}
            </button>
          </div>
          {emailError && <p className="mt-2 text-xs text-red-600">{emailError}</p>}
        </div>
      )}
    </section>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white pb-24">
      <Helmet>
        <title>{`${currentLang === 'fr' ? 'Rapport' : currentLang === 'de' ? 'Bericht' : 'Report'} ${scan.domain} — ${scan.score}/100 | Presence`}</title>
      </Helmet>

      {/* HEADER AVEC TRILINGUE RÉACTIVÉ (FR, EN, DE) */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to={`/${currentLang}/`} className="flex items-center gap-2 text-sm font-bold text-slate-900">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600">
              <span className="text-xs text-white">P</span>
            </div>
            Presence
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex gap-1 text-xs font-semibold">
              <Link
                to={`/fr/scan/${scan.scan_id}`}
                className={`px-2 py-1 rounded ${currentLang === 'fr' ? 'bg-indigo-50 text-indigo-600 font-bold' : 'text-slate-400 hover:text-slate-600'}`}
              >
                FR
              </Link>
              <Link
                to={`/en/scan/${scan.scan_id}`}
                className={`px-2 py-1 rounded ${currentLang === 'en' ? 'bg-indigo-50 text-indigo-600 font-bold' : 'text-slate-400 hover:text-slate-600'}`}
              >
                EN
              </Link>
              <Link
                to={`/de/scan/${scan.scan_id}`}
                className={`px-2 py-1 rounded ${currentLang === 'de' ? 'bg-indigo-50 text-indigo-600 font-bold' : 'text-slate-400 hover:text-slate-600'}`}
              >
                DE
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8 space-y-8">
        {/* 1. Titre & Meta */}
        <section>
          <h1 className="text-2xl font-bold text-slate-900">
            {currentLang === 'fr'
              ? `Rapport de santé — ${displayUrl}`
              : currentLang === 'de'
                ? `Gesundheitsbericht — ${displayUrl}`
                : `Health Report — ${displayUrl}`}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {currentLang === 'fr'
              ? `Analyse réalisée le ${scanDate} • ${sortedChecks.length} vérifications`
              : currentLang === 'de'
                ? `Analyse durchgeführt am ${scanDate} • ${sortedChecks.length} Überprüfungen`
                : `Scan performed on ${scanDate} • ${sortedChecks.length} checks`}
          </p>
        </section>

        {/* 2. Score Global */}
        <section className="text-center">
          <div className="inline-flex flex-col items-center">
            <div className={`flex h-32 w-32 items-center justify-center rounded-full bg-white shadow-lg ring-4 ${ringColor}`}>
              <div className="text-center">
                <span className={`text-4xl font-black ${scoreColor}`}>{scan.score}</span>
                <span className="text-sm font-semibold text-slate-400">/100</span>
              </div>
            </div>
            <span className={`mt-2 rounded-full px-3 py-0.5 text-xs font-bold ${scoreBg} ${scoreColor}`}>
              {scoreLabel}
            </span>
          </div>
          {showSocialProof && (
            <p className="mt-3 text-xs text-slate-400">
              ⭐ Rejoignez les <strong className="text-slate-600">{scan.meta!.total_monitored_sites}</strong> sites • Note : <strong className="text-slate-600">{scan.meta!.average_rating}/5</strong>
            </p>
          )}
        </section>

        {/* 3. Compteurs */}
        <section className="grid grid-cols-3 gap-3">
          <div className="rounded-xl bg-red-50 p-3 text-center">
            <span className="text-2xl font-bold text-red-600">{scan.summary.critical}</span>
            <p className="text-xs text-red-500">{currentLang === 'fr' ? 'Critiques' : 'Critical'}</p>
          </div>
          <div className="rounded-xl bg-amber-50 p-3 text-center">
            <span className="text-2xl font-bold text-amber-600">{scan.summary.warnings}</span>
            <p className="text-xs text-amber-500">{currentLang === 'fr' ? 'Avertissements' : 'Warnings'}</p>
          </div>
          <div className="rounded-xl bg-emerald-50 p-3 text-center">
            <span className="text-2xl font-bold text-emerald-600">{scan.summary.passed}</span>
            <p className="text-xs text-emerald-500">{currentLang === 'fr' ? 'Conformes' : 'Passed'}</p>
          </div>
        </section>

        {/* 4. 📧 Email CTA #1 (Nouvelle position stratégique haute) */}
        <EmailCaptureSection />

        {/* 5. Liste des checks */}
        <section className="space-y-4">
          <h2 className="text-lg font-bold text-slate-900">
            {currentLang === 'fr' ? '🔍 Diagnostic complet — Toutes les corrections' : '🔍 Full Diagnostic — All Fixes'}
          </h2>
          <p className="text-sm text-slate-500">
            {currentLang === 'fr'
              ? 'Résultats détaillés et corrections à appliquer. Tout est gratuit.'
              : 'Detailed results and fixes. Everything is free.'}
          </p>

          <div className="space-y-4">
            {sortedChecks.map(({ key, normalizedStatus, ...check }) => {
              const isPassed = normalizedStatus === 'passed';
              const isUptime = key === 'uptime';
              const statusColor =
                normalizedStatus === 'critical'
                  ? 'border-red-200 bg-red-50'
                  : normalizedStatus === 'warning'
                    ? 'border-amber-200 bg-amber-50'
                    : 'border-emerald-200 bg-emerald-50';
              const statusDot =
                normalizedStatus === 'critical'
                  ? 'bg-red-500'
                  : normalizedStatus === 'warning'
                    ? 'bg-amber-500'
                    : 'bg-emerald-500';
              const statusLabel =
                normalizedStatus === 'critical'
                  ? (currentLang === 'fr' ? 'Critique' : 'Critical')
                  : normalizedStatus === 'warning'
                    ? (currentLang === 'fr' ? 'Attention' : 'Warning')
                    : (currentLang === 'fr' ? 'Conforme' : 'Passed');

              const correctionCode = check.remediation?.code || (isPassed ? null : check.message);
              const guideKey =
                key === 'email_security'
                  ? 'spf_missing'
                  : key === 'ssl'
                    ? 'ssl_expiring_soon'
                    : key === 'security_headers'
                      ? 'security_headers_missing'
                      : '';
              const guide = REMEDIATION_GUIDES[guideKey];

              const serverTabs = check.remediation
                ? Object.entries(check.remediation)
                  .filter(([k]) => ['nginx', 'apache', 'htaccess'].includes(k))
                  .map(([k]) => k)
                : [];
              const activeTab = activeServerTab[key] || serverTabs[0] || 'generic';

              return (
                <div key={key} className={`rounded-xl border-2 p-5 ${statusColor}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-xl">{CHECK_ICONS[key] || '🔍'}</span>
                      <div>
                        <h3 className="font-bold text-slate-900">{CHECK_LABELS[key] || key.replace(/_/g, ' ')}</h3>
                        <p className="text-xs text-slate-500">
                          {statusLabel} •{' '}
                          {isUptime
                            ? check.is_up !== false
                              ? '🟢 Online'
                              : '🔴 Offline'
                            : check.score !== null
                              ? `${check.score}/20 pts`
                              : 'Non pondéré'}
                        </p>
                      </div>
                    </div>
                    <span className={`h-3 w-3 rounded-full ${statusDot}`} />
                  </div>

                  <p className="mt-3 text-sm leading-relaxed text-slate-700">{check.message}</p>

                  {correctionCode && !isPassed && (
                    <div className="mt-4 space-y-3">
                      <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        {currentLang === 'fr' ? 'Correction à appliquer' : 'Fix to apply'}
                      </p>
                      <div className="overflow-hidden rounded-lg border border-slate-200 bg-slate-900">
                        <div className="flex items-center justify-between border-b border-slate-700 px-3 py-1.5">
                          <span className="text-xs text-slate-400">Configuration</span>
                          <button
                            onClick={() => handleCopy(key, correctionCode)}
                            className="text-xs text-indigo-400 hover:text-indigo-300"
                          >
                            {copiedCheck === key ? '✅' : '📋'}
                          </button>
                        </div>
                        <pre className="overflow-x-auto px-3 py-2 text-xs leading-relaxed text-emerald-300">
                          <code>{correctionCode}</code>
                        </pre>
                      </div>

                      {/* 🚀 MICRO-CTA DE SURVEILLANCE INTEGRÉ DANS LES ERREURS */}
                      <div className="mt-3 rounded-lg bg-indigo-50 border border-indigo-100 p-3">
                        <p className="text-xs text-indigo-700 leading-relaxed">
                          💡 Presence can monitor this automatically and alert you before it breaks again.{' '}
                          <a
                            href={`/${currentLang}/register?scan_id=${scan.scan_id}&check=${key}&intent=monitor_${key}`}
                            className="font-bold underline hover:text-indigo-900"
                          >
                            Enable monitoring →
                          </a>
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={handleRescan}
                          disabled={rescanning}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
                        >
                          {rescanning ? '⏳' : currentLang === 'fr' ? '🔄 Vérifier' : '🔄 Verify'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* 6. 📧 Email CTA #2 (Position originale basse) */}
        <EmailCaptureSection />

        {/* 7. CTA Inscription */}
        <section className="rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-white p-8 text-center">
          <div className="mx-auto max-w-md">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-indigo-100">
              <span className="text-2xl">🔔</span>
            </div>
            <h3 className="text-xl font-bold text-slate-900">
              {currentLang === 'fr' ? 'Ce site est à vous ?' : 'Is this your website?'}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {currentLang === 'fr'
                ? 'Surveillez-le automatiquement et soyez alerté avant la prochaine panne. Historique complet et alertes push.'
                : 'Monitor it automatically and get alerted before the next outage. Full history and push alerts.'}
            </p>
            <Link
              to={`/${currentLang}/register?scan_id=${scan.scan_id}&url=${encodeURIComponent(scan.url || `https://${scan.domain}`)}`}
              className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-200 hover:bg-indigo-700 active:scale-95"
            >
              🚀 {currentLang === 'fr' ? 'Créer un compte gratuit' : 'Create a free account'}
            </Link>
          </div>
        </section>
      </main>

      {/* 🚀 STICKY BOTTOM BAR (AFFECTATION COHABITATION STRICTE) */}
      {showStickyBar && (
        <div
          className="fixed bottom-0 left-0 right-0 z-40 h-[72px] sm:h-16 bg-white border-t border-slate-200 shadow-[0_-4px_10px_-1px_rgba(0,0,0,0.08)] flex items-center px-4 animate-in slide-in-from-bottom duration-300"
          role="complementary"
        >
          <div className="max-w-3xl mx-auto w-full flex items-center justify-between gap-4">
            <p className="text-sm font-semibold text-slate-800 truncate">
              🔔 Monitor <strong className="text-indigo-600">{displayUrl}</strong> automatically?
            </p>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={handleDismissStickyBar}
                className="text-xs font-semibold text-slate-500 hover:text-slate-800 px-2 py-1"
              >
                Later
              </button>
              <Link
                to={`/${currentLang}/register?scan_id=${scan.scan_id}&url=${encodeURIComponent(scan.url || `https://${scan.domain}`)}`}
                className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-4 py-2 rounded-lg shadow-md active:scale-95 transition"
              >
                Create free account
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* 📱 TOAST PWA CONTEXTUALISÉ */}
      {!showStickyBar && <PWAPromptModal domain={scan.domain} score={scan.score} />}
    </div>
  );
}

export default PublicScanResult;

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { SeoTags } from './components/SeoTags';
import { ModalQueueProvider } from './context/ModalQueueContext';
import { PWAInstallToast } from './components/PWAInstallToast';
import { CookieBanner } from './components/CookieBanner';
import { AppShell } from './components/AppShell';

import AdminDashboard from './pages/AdminDashboard';
import Alerts from './pages/Alerts';
import Auth from './pages/Auth';
import BlogPage from './pages/BlogPage';
import Dashboard from './pages/Dashboard';
import FAQPage from './pages/FAQPage';
import FeaturePage from './pages/FeaturePage';
import Landing from './pages/Landing';
import Monitoring from './pages/Monitoring';
import Onboarding from './pages/Onboarding';
import Pricing from './pages/Pricing';
import PublicScanResult from './pages/PublicScanResult';
import Reports from './pages/Reports';
import Reviews from './pages/Reviews';
import SEOPage from './pages/SEOPage';
import SecurityPage from './pages/SecurityPage';
import Settings from './pages/Settings';
import ToolPage from './pages/ToolPage';
import WebsiteDetails from './pages/WebsiteDetails';
import Websites from './pages/Websites';

const SUPPORTED_LANGS = ['fr', 'en', 'de'];
const DEFAULT_LANG = 'en';

function RootRedirect() {
  const browserLang = (navigator.language || 'en').split('-')[0].toLowerCase();
  const targetLang = SUPPORTED_LANGS.includes(browserLang) ? browserLang : DEFAULT_LANG;
  return <Navigate to={`/${targetLang}/`} replace />;
}

function LangRouteWrapper({ children }: { children: React.ReactNode }) {
  const { lang } = useParams<{ lang: string }>();
  if (lang && !SUPPORTED_LANGS.includes(lang)) {
    return <Navigate to={`/${DEFAULT_LANG}/`} replace />;
  }
  return <React.Fragment key={lang}>{children}</React.Fragment>;
}

export function App() {
  return (
    <HelmetProvider>
      <BrowserRouter>
        <ModalQueueProvider>
          <SeoTags />
          <Routes>
            {/* 1. Redirection de la racine */}
            <Route path="/" element={<RootRedirect />} />

            {/* 2. Routes directes publiques */}
            <Route path="/scan/:scanId" element={<PublicScanResult />} />
            <Route path="/pricing" element={<Pricing />} />

            {/* 3. Routes multilingues (/fr/, /en/, /de/) */}
            <Route path="/:lang" element={<LangRouteWrapper><Landing /></LangRouteWrapper>} />
            <Route path="/:lang/" element={<LangRouteWrapper><Landing /></LangRouteWrapper>} />
            <Route path="/:lang/scan/:scanId" element={<LangRouteWrapper><PublicScanResult /></LangRouteWrapper>} />
            <Route path="/:lang/pricing" element={<LangRouteWrapper><Pricing /></LangRouteWrapper>} />

            {/* 4. Espace Connecté Privé (/app/*) */}
            <Route path="/app" element={<AppShell />}>
              <Route index element={<Navigate to="/app/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="websites" element={<Websites />} />
              <Route path="websites/:id" element={<WebsiteDetails />} />
              <Route path="monitoring" element={<Monitoring />} />
              <Route path="seo" element={<SEOPage />} />
              <Route path="security" element={<SecurityPage />} />
              <Route path="reports" element={<Reports />} />
              <Route path="alerts" element={<Alerts />} />
              <Route path="admin" element={<AdminDashboard />} />
              <Route path="settings" element={<Settings />} />
            </Route>

            {/* 5. Fallback */}
            <Route path="*" element={<Navigate to={`/${DEFAULT_LANG}/`} replace />} />
          </Routes>

          {/* Overlays globaux */}
          <CookieBanner />
          <PWAInstallToast />
        </ModalQueueProvider>
      </BrowserRouter>
    </HelmetProvider>
  );
}

export default App;

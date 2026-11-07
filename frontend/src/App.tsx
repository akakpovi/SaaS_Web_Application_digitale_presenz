import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { AppShell } from './components/AppShell';
import { AuthProvider } from './context/AuthContext';
import i18n, { detectBrowserLocale, detectLocale, detectLocaleFromPath } from './i18n';
import { ProtectedRoute } from './components/ProtectedRoute';
import CookieConsent from './components/CookieConsent';
import Dashboard from './pages/Dashboard';
import Websites from './pages/Websites';
import WebsiteDetails from './pages/WebsiteDetails';
import SecurityPage from './pages/SecurityPage';
import SEOPage from './pages/SEOPage';
import Alerts from './pages/Alerts';
import Monitoring from './pages/Monitoring';
import Reports from './pages/Reports';
import AdminDashboard from './pages/AdminDashboard';
import Settings from './pages/Settings';
import Reviews from './pages/Reviews';
import Social from './pages/Social';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Pricing from './pages/Pricing';
import PublicScanResult from './pages/PublicScanResult';
import { ForgotPassword } from './pages/ForgotPassword';
import { ResetPassword } from './pages/ResetPassword';
import { VerifyEmail } from './pages/VerifyEmail';
import { BlogPage } from './pages/BlogPage';

function LocaleSync() {
  const location = useLocation();
  const routeLocale = detectLocaleFromPath(location.pathname);

  useEffect(() => {
    if (routeLocale && i18n.resolvedLanguage !== routeLocale) {
      void i18n.changeLanguage(routeLocale);
    }
  }, [routeLocale]);

  return null;
}

function App() {
  return (
    <HelmetProvider>
      <Router>
        <LocaleSync />
        <AuthProvider>
          <CookieConsent />
          <Routes>
            <Route path="/" element={<Navigate to={`/${detectBrowserLocale()}/`} replace />} />
            {/* Public routes */}
            <Route path="/:lang/" element={<Landing />} />
            <Route path="/:lang/login" element={<Login />} />
            <Route path="/:lang/register" element={<Register />} />
            <Route path="/:lang/pricing" element={<Pricing />} />
            <Route path="/:lang/blog" element={<BlogPage />} />
            <Route path="/:lang/blog/:slug" element={<BlogPage />} />
            <Route path="/:lang/scan/:scanId" element={<PublicScanResult />} />
            <Route path="/:lang/forgot-password" element={<ForgotPassword />} />
            <Route path="/:lang/reset-password/:uidb64/:token" element={<ResetPassword />} />
            <Route path="/:lang/verify-email/:uidb64/:token" element={<VerifyEmail />} />

            {/* Protected app routes */}
            <Route path="/:lang/app" element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="websites" element={<Websites />} />
              <Route path="websites/:id" element={<WebsiteDetails />} />
              <Route path="monitoring" element={<Monitoring />} />
              <Route path="seo" element={<SEOPage />} />
              <Route path="security" element={<SecurityPage />} />
              <Route path="reports" element={<Reports />} />
              <Route path="alerts" element={<Alerts />} />
              <Route path="reviews" element={<Reviews />} />
              <Route path="social" element={<Social />} />
              <Route path="admin" element={<AdminDashboard />} />
              <Route path="settings" element={<Settings />} />
            </Route>

            <Route path="*" element={<Navigate to={`/${detectLocale()}/`} replace />} />
          </Routes>
        </AuthProvider>
      </Router>
    </HelmetProvider>
  );
}

export default App;

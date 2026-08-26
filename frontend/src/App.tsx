import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import Landing from "./pages/Landing";
import { Login, Register, ForgotPassword } from "./pages/Auth";
import Onboarding from "./pages/Onboarding";
import Dashboard from "./pages/Dashboard";
import Websites from "./pages/Websites";
import WebsiteDetails from "./pages/WebsiteDetails";
import Monitoring from "./pages/Monitoring";
import Alerts from "./pages/Alerts";
import Reports from "./pages/Reports";
import Reviews from "./pages/Reviews";
import Settings from "./pages/Settings";
import Pricing from "./pages/Pricing";
import FeaturePage from "./pages/FeaturePage";
import ToolPage from "./pages/ToolPage";
import FAQPage from "./pages/FAQPage";
import BlogPage from "./pages/BlogPage";
import { useAuth } from "./context/AuthContext";

function Spinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-slate-500">Loading...</span>
      </div>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <Spinner />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicOnlyRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  if (isAuthenticated) return <Navigate to="/app/dashboard" replace />;
  return <>{children}</>;
}

function AppLayout() {
  return (
    <ProtectedRoute>
      <AppShell>
        <Routes>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="websites" element={<Websites />} />
          <Route path="websites/:id" element={<WebsiteDetails />} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="reports" element={<Reports />} />
          <Route path="reviews" element={<Reviews />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Routes>
      </AppShell>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/faq" element={<FAQPage />} />
        <Route path="/blog" element={<BlogPage />} />
        <Route path="/blog/:slug" element={<BlogPage />} />
        <Route path="/features/website-monitoring" element={<FeaturePage feature="website-monitoring" />} />
        <Route path="/features/ssl-monitoring" element={<FeaturePage feature="ssl-monitoring" />} />
        <Route path="/features/dns-monitoring" element={<FeaturePage feature="dns-monitoring" />} />
        <Route path="/features/email-security" element={<FeaturePage feature="email-security" />} />
        <Route path="/features/uptime-monitoring" element={<FeaturePage feature="uptime-monitoring" />} />
        <Route path="/features/website-performance" element={<FeaturePage feature="website-performance" />} />
        <Route path="/features/security-headers" element={<FeaturePage feature="security-headers" />} />
        <Route path="/features/review-monitoring" element={<FeaturePage feature="review-monitoring" />} />
        <Route path="/tools/website-checker" element={<ToolPage tool="website-checker" />} />
        <Route path="/tools/ssl-checker" element={<ToolPage tool="ssl-checker" />} />
        <Route path="/tools/dns-checker" element={<ToolPage tool="dns-checker" />} />
        <Route path="/tools/email-security-checker" element={<ToolPage tool="email-security-checker" />} />
        <Route path="/login" element={<PublicOnlyRoute><Login /></PublicOnlyRoute>} />
        <Route path="/register" element={<PublicOnlyRoute><Register /></PublicOnlyRoute>} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
        <Route path="/app/*" element={<AppLayout />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

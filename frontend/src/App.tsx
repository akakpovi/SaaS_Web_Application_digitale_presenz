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

function AppLayout() {
  return (
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
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public marketing pages — indexable */}
        <Route path="/" element={<Landing />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/faq" element={<FAQPage />} />
        <Route path="/blog" element={<BlogPage />} />
        <Route path="/blog/:slug" element={<BlogPage />} />

        {/* Feature landing pages */}
        <Route path="/features/website-monitoring" element={<FeaturePage feature="website-monitoring" />} />
        <Route path="/features/ssl-monitoring" element={<FeaturePage feature="ssl-monitoring" />} />
        <Route path="/features/dns-monitoring" element={<FeaturePage feature="dns-monitoring" />} />
        <Route path="/features/email-security" element={<FeaturePage feature="email-security" />} />
        <Route path="/features/uptime-monitoring" element={<FeaturePage feature="uptime-monitoring" />} />
        <Route path="/features/website-performance" element={<FeaturePage feature="website-performance" />} />
        <Route path="/features/security-headers" element={<FeaturePage feature="security-headers" />} />
        <Route path="/features/review-monitoring" element={<FeaturePage feature="review-monitoring" />} />

        {/* Free tools */}
        <Route path="/tools/website-checker" element={<ToolPage tool="website-checker" />} />
        <Route path="/tools/ssl-checker" element={<ToolPage tool="ssl-checker" />} />
        <Route path="/tools/dns-checker" element={<ToolPage tool="dns-checker" />} />
        <Route path="/tools/email-security-checker" element={<ToolPage tool="email-security-checker" />} />

        {/* Auth — private, noindex */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />

        {/* Onboarding — private, noindex */}
        <Route path="/onboarding" element={<Onboarding />} />

        {/* Private app shell — noindex applied inside AppShell */}
        <Route path="/app/*" element={<AppLayout />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

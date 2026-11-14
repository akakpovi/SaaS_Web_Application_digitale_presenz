import { lazy, Suspense, useState, useEffect, type ReactNode } from "react"
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  useParams,
} from "react-router-dom"
import { AppShell, ThemeProvider } from "./components/AppShell"
import CommandMenu from "./components/CommandMenu"
import { AuthGuard } from "./components/AuthGuard"
import { OAuthReturnHandler } from "./components/OAuthReturnHandler"
import { PlanProvider } from "./contexts/PlanContext"
import { UpgradeProvider } from "./components/UpgradePrompt"
import RouteLocaleSync from "./components/RouteLocaleSync"
import AnalyticsPageviews from "./components/AnalyticsPageviews"
import { LOCALES, localizedPath, type Locale } from "./i18n"
import { PUBLIC_PATHS, type PublicPath } from "./seo/publicPaths"

// Lazy-loaded page chunks
const Landing = lazy(() => import("./pages/Landing"))
const Login = lazy(() =>
  import("./pages/Auth").then((m) => ({ default: m.Login })),
)
const Register = lazy(() =>
  import("./pages/Auth").then((m) => ({ default: m.Register })),
)
const ForgotPassword = lazy(() =>
  import("./pages/Auth").then((m) => ({ default: m.ForgotPassword })),
)
const ResetPassword = lazy(() =>
  import("./pages/Auth").then((m) => ({ default: m.ResetPassword })),
)
const VerifyEmail = lazy(() => import("./pages/VerifyEmail"))
const Onboarding = lazy(() => import("./pages/Onboarding"))
const Dashboard = lazy(() => import("./pages/Dashboard"))
const Websites = lazy(() => import("./pages/Websites"))
const WebsiteDetails = lazy(() => import("./pages/WebsiteDetails"))
const Monitoring = lazy(() => import("./pages/Monitoring"))
const Alerts = lazy(() => import("./pages/Alerts"))
const Reports = lazy(() => import("./pages/Reports"))
const Reviews = lazy(() => import("./pages/Reviews"))
const Settings = lazy(() => import("./pages/Settings"))
const Integrations = lazy(() => import("./pages/Integrations"))
const Billing = lazy(() => import("./pages/Billing"))
const Pricing = lazy(() => import("./pages/Pricing"))
const FeaturePage = lazy(() => import("./pages/FeaturePage"))
const ToolPage = lazy(() => import("./pages/ToolPage"))
const FAQPage = lazy(() => import("./pages/FAQPage"))
const BlogPage = lazy(() => import("./pages/BlogPage"))
const BlogArticle = lazy(() => import("./pages/BlogArticle"))
const Scans = lazy(() => import("./pages/Scans"))
const Growth = lazy(() => import("./pages/Growth"))
const SecurityAdvisor = lazy(() => import("./pages/SecurityAdvisor"))
const AboutPage = lazy(() => import("./pages/AboutPage"))
const ContactPage = lazy(() => import("./pages/ContactPage"))
const PrivacyPage = lazy(() => import("./pages/PrivacyPage"))
const TermsPage = lazy(() => import("./pages/TermsPage"))
const ImpressumPage = lazy(() => import("./pages/ImpressumPage"))
const CookiesPage = lazy(() => import("./pages/CookiesPage"))
const WithdrawalPage = lazy(() => import("./pages/WithdrawalPage"))
const SolutionPage = lazy(() => import("./pages/SolutionPage"))
const PublicScanResult = lazy(() => import("./pages/PublicScanResult"))
const AdminDashboard = lazy(() => import("./pages/AdminDashboard"))
const NotFound = lazy(() => import("./pages/NotFound"))

/**
 * Legacy share links (`/report/:publicId`) used to render a hard-coded demo.
 * The real public report is `/scan/:id` — guest scans are already readable by
 * anyone, while an account scan stays private and resolves to its 404 state.
 */
function LegacyReportRedirect() {
  const { publicId } = useParams<{ publicId: string }>()
  return (
    <Navigate
      to={publicId ? `/scan/${encodeURIComponent(publicId)}` : "/tools/website-checker"}
      replace
    />
  )
}

type LocaleEntry = { locale: Locale }

/**
 * Localized private entry points (`/fr/app/...`, `/fr/login`, `/de/login`).
 * They carry the locale in `?lang=` and redirect to the canonical bare URL, so
 * every existing in-app link and AuthGuard redirect keeps working unchanged.
 */
function LocaleEntryRedirect({ locale }: LocaleEntry) {
  const { pathname, search, hash } = useLocation()
  const target = pathname.replace(new RegExp(`^/${locale}(?=/|$)`), "") || "/"
  const params = new URLSearchParams(search)
  params.set("lang", locale)
  const query = params.toString()
  return <Navigate to={`${target}${query ? `?${query}` : ""}${hash}`} replace />
}

/** Keep the requested /settings/integrations URL working inside the app. */
function SettingsIntegrationsRedirect() {
  const location = useLocation()
  return (
    <Navigate
      to={`/app/settings/integrations${location.search}`}
      replace
    />
  )
}

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function AppLayout() {
  const [cmdOpen, setCmdOpen] = useState(false)

  // Global ⌘K / Ctrl+K listener
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setCmdOpen((o) => !o)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  return (
    <PlanProvider>
      <UpgradeProvider>
        <CommandMenu open={cmdOpen} onClose={() => setCmdOpen(false)} />
        <AppShell onOpenCommand={() => setCmdOpen(true)}>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="websites" element={<Websites />} />
              <Route path="websites/:id" element={<WebsiteDetails />} />
              <Route path="scans" element={<Scans />} />
              <Route path="monitoring" element={<Monitoring />} />
              <Route path="alerts" element={<Alerts />} />
              <Route path="reports" element={<Reports />} />
              <Route path="reviews" element={<Reviews />} />
              <Route path="growth" element={<Growth />} />
              <Route path="advisor" element={<SecurityAdvisor />} />
              <Route path="settings" element={<Settings />} />
              <Route path="settings/integrations" element={<Integrations />} />
              <Route path="billing" element={<Billing />} />
              <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Routes>
          </Suspense>
        </AppShell>
      </UpgradeProvider>
    </PlanProvider>
  )
}

/**
 * Public, indexable routes, declared once.
 *
 * The same table is mounted once per locale below: bare (German, the default
 * locale), under `/en` (English) and under `/fr` (French), so a page can never
 * exist in one language and be missing from another. Private and
 * authentication screens stay out of it: they are noindex entry points that
 * redirect to their canonical bare URL while carrying the requested language.
 */
const PUBLIC_ELEMENTS: Record<PublicPath, ReactNode> = {
  "/": <Landing />,
  "/pricing": <Pricing />,
  "/faq": <FAQPage />,
  "/blog": <BlogPage />,
  "/about": <AboutPage />,
  "/contact": <ContactPage />,
  "/privacy": <PrivacyPage />,
  "/terms": <TermsPage />,
  // German launch requirements: provider information and a statement about
  // browser storage.
  "/impressum": <ImpressumPage />,
  "/cookies": <CookiesPage />,
  "/widerruf": <WithdrawalPage />,

  // Solution landing pages
  "/solutions/small-business": <SolutionPage solution="small-business" />,
  "/solutions/freelancers": <SolutionPage solution="freelancers" />,
  "/solutions/agencies": <SolutionPage solution="agencies" />,
  "/solutions/restaurants": <SolutionPage solution="restaurants" />,
  "/solutions/ecommerce": <SolutionPage solution="ecommerce" />,
  "/solutions/local-business": <SolutionPage solution="local-business" />,

  // Feature landing pages
  "/features/website-monitoring": <FeaturePage feature="website-monitoring" />,
  "/features/ssl-monitoring": <FeaturePage feature="ssl-monitoring" />,
  "/features/dns-monitoring": <FeaturePage feature="dns-monitoring" />,
  "/features/email-security": <FeaturePage feature="email-security" />,
  "/features/uptime-monitoring": <FeaturePage feature="uptime-monitoring" />,
  "/features/website-performance": <FeaturePage feature="website-performance" />,
  "/features/security-headers": <FeaturePage feature="security-headers" />,
  "/features/review-monitoring": <FeaturePage feature="review-monitoring" />,

  // Free tools
  "/tools/website-checker": <ToolPage tool="website-checker" />,
  "/tools/ssl-checker": <ToolPage tool="ssl-checker" />,
  "/tools/dns-checker": <ToolPage tool="dns-checker" />,
  "/tools/email-security-checker": <ToolPage tool="email-security-checker" />,
}

/** Mounted once per locale (`de` bare, `en` `/en`, `fr` `/fr`) below. */
const PUBLIC_ROUTES = PUBLIC_PATHS.map((path) => ({
  path,
  element: PUBLIC_ELEMENTS[path],
}))

/** Private entry points that also accept a localized prefix. */
const PRIVATE_ENTRY_PATHS = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/onboarding",
  "/settings/integrations",
  "/admin",
  "/report/*",
  "/scan/*",
] as const

/**
 * Route tree without a router.
 *
 * The browser wraps it in `BrowserRouter`; the build wraps it in
 * `StaticRouter` to render the same components into HTML. Keeping the tree
 * here (rather than in the SSG entry) means a route can never exist in one
 * and be missing from the other.
 */
export function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
            {/* Public pages, mounted once per locale: bare German, /en and
                /fr, each with its own canonical URL. */}
            {LOCALES.map((locale) =>
              PUBLIC_ROUTES.map(({ path, element }) => (
                <Route
                  key={`${locale}:${path}`}
                  path={localizedPath(path, locale)}
                  element={element}
                />
              )),
            )}

            {/* Localized private entry points. The redirect keeps the locale
                in ?lang=..., while in-app links remain on the canonical bare
                /app/... URLs they already use. */}
            {LOCALES.flatMap((locale) =>
              PRIVATE_ENTRY_PATHS.map((path) => (
                <Route
                  key={`${locale}:${path}`}
                  path={`/${locale}${path}`}
                  element={<LocaleEntryRedirect locale={locale} />}
                />
              )),
            )}

            {/* The authenticated app keeps the locale in the path
                (`/fr/app/dashboard`) instead of downgrading it to `?lang=fr`.
                The same AppLayout serves both the canonical `/app/...` tree and
                every localized tree. */}
            {LOCALES.map((locale) => (
              <Route
                key={`${locale}:app`}
                path={`/${locale}/app/*`}
                element={
                  <AuthGuard>
                    <AppLayout />
                  </AuthGuard>
                }
              />
            ))}

            {/* A CMS article exists in one language under its own slug; its
                translation is another slug, never `/en/blog/<slug>`. */}
            <Route path="/blog/:slug" element={<BlogArticle />} />

            <Route path="/report/:publicId" element={<LegacyReportRedirect />} />
            <Route path="/scan/:scanId" element={<PublicScanResult />} />
            <Route path="/admin" element={<AdminDashboard />} />

            {/* Auth — private, noindex */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/verify-email" element={<VerifyEmail />} />

            {/* Short settings URL used by the OAuth documentation and links */}
            <Route
              path="/settings/integrations"
              element={<SettingsIntegrationsRedirect />}
            />

            {/* Onboarding — private, noindex */}
            <Route path="/onboarding" element={<Onboarding />} />

            {/* Private app shell — noindex applied inside AppShell */}
            <Route
              path="/app/*"
              element={
                <AuthGuard>
                  <AppLayout />
                </AuthGuard>
              }
            />

            <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <OAuthReturnHandler />
        <RouteLocaleSync />
        <AnalyticsPageviews />
        <AppRoutes />
      </BrowserRouter>
    </ThemeProvider>
  )
}

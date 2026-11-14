import React, { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import Link from "../components/LocaleLink"
import {
  CheckCircle,
  ChevronDown,
  Menu,
  X,
  Globe,
  Shield,
  Mail,
  Zap,
  Bell,
  Star,
  FileText,
  ArrowRight,
  Play,
  Activity,
} from "lucide-react"
import AuroraBackground from "../components/AuroraBackground"
import { Button } from "../components/ui"
import LanguageSwitcher from "../components/LanguageSwitcher"
import { useI18n } from "../i18n"
import { usePlanCopy, usePricingPlans } from "../lib/usePricingPlans"
import { priceLabel } from "../lib/pricing"
import SEO, {
  organizationSchema,
  websiteSchema,
  softwareAppSchema,
  faqSchema,
} from "../components/SEO"

const FAQ_IDS = [
  "q1",
  "q2",
  "q3",
  "q4",
  "q5",
  "q6",
  "q7",
  "q8",
] as const

/** Score breakdown of the hero mock — labels live in the catalogue. */
const SCORE_ITEMS = [
  { key: "website", score: 20, max: 20 },
  { key: "ssl", score: 20, max: 20 },
  { key: "dns", score: 15, max: 15 },
  { key: "email", score: 10, max: 15 },
  { key: "headers", score: 9, max: 15 },
  { key: "performance", score: 8, max: 15 },
] as const

/** Feature cards: catalogue key + route. Order drives the visible grid. */
const FEATURE_CARDS = [
  {
    id: "websiteMonitoring",
    icon: Globe,
    color: "bg-indigo-50 text-indigo-600",
    href: "/features/website-monitoring",
  },
  {
    id: "sslMonitoring",
    icon: Shield,
    color: "bg-emerald-50 text-emerald-600",
    href: "/features/ssl-monitoring",
  },
  {
    id: "dnsMonitoring",
    icon: Zap,
    color: "bg-amber-50 text-amber-600",
    href: "/features/dns-monitoring",
  },
  {
    id: "emailSecurity",
    icon: Mail,
    color: "bg-blue-50 text-blue-600",
    href: "/features/email-security",
  },
  {
    id: "performanceMonitoring",
    icon: Activity,
    color: "bg-purple-50 text-purple-600",
    href: "/features/website-performance",
  },
  {
    id: "securityHeaders",
    icon: Shield,
    color: "bg-rose-50 text-rose-600",
    href: "/features/security-headers",
  },
  {
    id: "uptimeMonitoring",
    icon: Bell,
    color: "bg-cyan-50 text-cyan-600",
    href: "/features/uptime-monitoring",
  },
  {
    id: "onlineReviews",
    icon: Star,
    color: "bg-yellow-50 text-yellow-600",
    href: "/features/review-monitoring",
  },
  {
    id: "automaticReports",
    icon: FileText,
    color: "bg-slate-50 text-slate-600",
    href: "/blog/what-is-website-monitoring",
  },
] as const

function useFaqs() {
  const { t } = useI18n()
  return FAQ_IDS.map((id) => ({
    q: t(`faq.items.${id}.q`),
    a: t(`faq.items.${id}.a`),
  }))
}

function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { t } = useI18n()
  const menuRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!menuOpen) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault()
        setMenuOpen(false)
        triggerRef.current?.focus()
        return
      }
      if (event.key !== "Tab" || !menuRef.current) return
      const focusable = Array.from(
        menuRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener("keydown", onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const focusTimer = window.setTimeout(() => {
      menuRef.current?.querySelector<HTMLElement>("a[href], button")?.focus()
    }, 50)

    return () => {
      document.removeEventListener("keydown", onKeyDown)
      document.body.style.overflow = previousOverflow
      window.clearTimeout(focusTimer)
    }
  }, [menuOpen])

  const closeMenu = () => {
    setMenuOpen(false)
    triggerRef.current?.focus()
  }

  return (
    <>
      <header className="sticky top-0 z-50 bg-slate-950/70 backdrop-blur-md border-b border-white/10">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center gap-8">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 flex-shrink-0">
          <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle
                cx="8"
                cy="8"
                r="6"
                stroke="white"
                strokeWidth="1.5"
                opacity="0.5"
              />
              <circle cx="8" cy="8" r="3" fill="white" />
              <path
                d="M8 2v2M8 12v2M2 8h2M12 8h2"
                stroke="white"
                strokeWidth="1.5"
                strokeLinecap="round"
                opacity="0.7"
              />
            </svg>
          </div>
          <span className="font-bold text-white text-base">Presence</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6 flex-1">
          <a
            href="#features"
            className="text-sm text-slate-300 hover:text-white transition-colors"
          >
            {t("nav.features")}
          </a>
          <a
            href="#how"
            className="text-sm text-slate-300 hover:text-white transition-colors"
          >
            {t("nav.howItWorks")}
          </a>
          <a
            href="#pricing"
            className="text-sm text-slate-300 hover:text-white transition-colors"
          >
            {t("nav.pricing")}
          </a>
          <a
            href="#faq"
            className="text-sm text-slate-300 hover:text-white transition-colors"
          >
            {t("nav.faq")}
          </a>
        </nav>

        <div className="hidden md:flex items-center gap-3 ml-auto">
          <LanguageSwitcher tone="dark" />
          <Link
            to="/login"
            className="text-sm font-medium text-slate-300 hover:text-white px-3 py-2 transition-colors"
          >
            {t("common.login")}
          </Link>
          <Link to="/register">
            <Button size="sm">{t("common.signup")}</Button>
          </Link>
        </div>

        <button
          ref={triggerRef}
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          className="md:hidden ml-auto w-10 h-10 flex items-center justify-center rounded-xl text-slate-300 hover:bg-white/10 transition-colors"
          aria-label={t("app.openNavigation")}
          aria-expanded={menuOpen}
          aria-controls="public-mobile-menu"
        >
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        </div>
      </header>

      {/* Mobile drawer: fixed, animated and keyboard-safe. Kept outside the
          blurred header, whose backdrop-filter would otherwise constrain a
          fixed descendant to the header box. */}
      <div
        className={`md:hidden fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm transition-opacity duration-300 ${
          menuOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={closeMenu}
        aria-hidden="true"
      />
      <div
        id="public-mobile-menu"
        ref={menuRef}
        role="dialog"
        aria-modal="true"
        aria-label={t("app.openNavigation")}
        aria-hidden={!menuOpen}
        {...(!menuOpen ? { inert: true } : {})}
        className={`md:hidden fixed inset-y-0 right-0 z-50 w-80 max-w-[85vw] bg-slate-950 border-l border-white/10 shadow-2xl flex flex-col p-6 transition-transform duration-300 ease-out ${
          menuOpen ? "translate-x-0" : "translate-x-full pointer-events-none"
        }`}
      >
        <div className="flex items-center justify-between pb-6 border-b border-white/10">
          <span className="font-bold text-white">Presence</span>
          <button
            type="button"
            onClick={closeMenu}
            className="w-10 h-10 flex items-center justify-center rounded-xl text-slate-300 hover:bg-white/10"
            aria-label={t("common.close")}
          >
            <X size={20} />
          </button>
        </div>

        <nav className="flex flex-col gap-1 py-6" aria-label={t("app.openNavigation")}>
          {[
            { href: "#features", label: t("nav.features") },
            { href: "#how", label: t("nav.howItWorks") },
            { href: "#pricing", label: t("nav.pricing") },
            { href: "#faq", label: t("nav.faq") },
          ].map((item) => (
            <a
              key={item.href}
              href={item.href}
              onClick={() => setMenuOpen(false)}
              className="text-base text-slate-200 py-3 border-b border-white/5 hover:text-white transition-colors"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="mt-auto space-y-4 pt-6 border-t border-white/10">
          <LanguageSwitcher tone="dark" className="w-fit" />
          <Link to="/login" className="block" onClick={() => setMenuOpen(false)}>
            <Button
              variant="outline"
              className="w-full border-white/20 text-white hover:bg-white/10"
            >
              {t("common.login")}
            </Button>
          </Link>
          <Link to="/register" className="block" onClick={() => setMenuOpen(false)}>
            <Button className="w-full">{t("common.signup")}</Button>
          </Link>
        </div>
      </div>
    </>
  )
}

function HeroDashboard() {
  const { t } = useI18n()
  const mockSites = [
    {
      domain: "example.de",
      status: `🟢 ${t("landing.mockOnline")}`,
      score: 92,
      uptime: "99.99%",
      ssl: `✅ ${t("landing.mockValid")}`,
    },
    {
      domain: "example.com",
      status: `🟢 ${t("landing.mockOnline")}`,
      score: 82,
      uptime: "99.98%",
      ssl: `✅ ${t("landing.mockValid")}`,
    },
    {
      domain: "example-shop.de",
      status: `🟠 ${t("landing.mockAttention")}`,
      score: 64,
      uptime: "98.91%",
      ssl: `⚠️ ${t("landing.mockExpiresSoon")}`,
    },
  ]

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-400" />
          <span className="w-3 h-3 rounded-full bg-amber-400" />
          <span className="w-3 h-3 rounded-full bg-emerald-400" />
        </div>
        <div className="flex-1 mx-4 bg-white border border-slate-200 rounded-lg px-3 py-1 text-xs text-slate-400">
          app.presence.io/dashboard
        </div>
      </div>

      <div className="p-5 bg-slate-50">
        {/* Score row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-white rounded-xl p-4 border border-slate-200 text-center col-span-1">
            <p className="text-xs text-slate-500 mb-1">{t("landing.mockScore")}</p>
            <p className="text-3xl font-bold text-emerald-600">82</p>
            <p className="text-xs text-slate-400">
              / 100 · {t("landing.mockGood")}
            </p>
          </div>
          <div className="bg-white rounded-xl p-4 border border-slate-200 text-center">
            <p className="text-xs text-slate-500 mb-1">{t("landing.mockUptime")}</p>
            <p className="text-2xl font-bold text-slate-900">99.98%</p>
            <p className="text-xs text-emerald-600">
              🟢 {t("landing.mockHealthy")}
            </p>
          </div>
          <div className="bg-white rounded-xl p-4 border border-slate-200 text-center">
            <p className="text-xs text-slate-500 mb-1">
              {t("landing.mockWebsites")}
            </p>
            <p className="text-2xl font-bold text-slate-900">3</p>
            <p className="text-xs text-slate-400">{t("landing.mockMonitored")}</p>
          </div>
          <div className="bg-white rounded-xl p-4 border border-slate-200 text-center">
            <p className="text-xs text-slate-500 mb-1">
              {t("landing.mockOpenIssues")}
            </p>
            <p className="text-2xl font-bold text-amber-600">2</p>
            <p className="text-xs text-amber-600">
              🟠 {t("landing.mockAttention")}
            </p>
          </div>
        </div>

        {/* Website list */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              {t("landing.mockYourWebsites")}
            </p>
          </div>
          {mockSites.map((site) => (
            <div
              key={site.domain}
              className="flex items-center gap-4 px-4 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors"
            >
              <div className="w-7 h-7 bg-indigo-50 rounded-lg flex items-center justify-center flex-shrink-0">
                <Globe size={14} className="text-indigo-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900">
                  {site.domain}
                </p>
                <p className="text-xs text-slate-500">{site.status}</p>
              </div>
              <div className="hidden md:flex items-center gap-4 text-xs text-slate-500">
                <span>
                  {t("landing.mockScore")}{" "}
                  <span className="font-semibold text-slate-800">
                    {site.score}
                  </span>
                </span>
                <span>
                  {t("landing.mockUptime")} {site.uptime}
                </span>
                <span>{site.ssl}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function FeatureCard({
  icon: Icon,
  title,
  description,
  color,
}: {
  icon: React.FC<{ size?: number; className?: string }>
  title: string
  description: string
  color: string
  href?: string
}) {
  return (
    <div className="group bg-white border border-slate-200 rounded-2xl p-6 hover:border-indigo-200 hover:shadow-md transition-all duration-200">
      <div
        className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${color}`}
      >
        <Icon size={18} className="text-current" />
      </div>
      <h3 className="font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-sm text-slate-500 leading-relaxed">{description}</p>
    </div>
  )
}

/**
 * Footer navigation. Every entry points at a page that really exists: the
 * previous list contained `href="#"` placeholders (Changelog, Roadmap,
 * Careers, GDPR) which are dead links on a launch-ready site.
 */
const FOOTER_COLUMNS = [
  {
    titleKey: "footer.product",
    links: [
      { labelKey: "nav.features", to: "/features/website-monitoring" },
      { labelKey: "nav.pricing", to: "/pricing" },
      { labelKey: "nav.faq", to: "/faq" },
      { labelKey: "nav.blog", to: "/blog" },
    ],
  },
  {
    titleKey: "footer.company",
    links: [
      { labelKey: "nav.about", to: "/about" },
      { labelKey: "nav.contact", to: "/contact" },
    ],
  },
  {
    titleKey: "footer.legal",
    links: [
      { labelKey: "footer.privacy", to: "/privacy" },
      { labelKey: "footer.terms", to: "/terms" },
      { labelKey: "footer.impressum", to: "/impressum" },
      { labelKey: "footer.withdrawal", to: "/widerruf" },
      { labelKey: "footer.cookies", to: "/cookies" },
    ],
  },
] as const

export default function Landing() {
  const navigate = useNavigate()
  const { t, tList } = useI18n()
  // Prices and limits come from the live catalogue — never from this file.
  const plans = usePricingPlans().map(usePlanCopy())
  const faqs = useFaqs()
  const [domain, setDomain] = useState("")

  // The hero scanner is the top of the public lead funnel: hand the domain to
  // the real checker, which starts the scan and shows its live report.
  const startCheck = () => {
    const target = domain.trim()
    navigate(
      target
        ? `/tools/website-checker?domain=${encodeURIComponent(target)}`
        : "/tools/website-checker",
    )
  }
  const [activeFaq, setActiveFaq] = useState<number | null>(null)

  return (
    <div className="min-h-full bg-white">
      <SEO
        title={t("meta.home.title")}
        description={t("meta.home.description")}
        path="/"
        structuredData={[
          organizationSchema(),
          websiteSchema(),
          softwareAppSchema(),
          faqSchema(faqs.map((f) => ({ q: f.q, a: f.a }))),
        ]}
      />
      <NavBar />

      {/* Hero */}
      <section className="relative pt-20 pb-24 px-4 overflow-hidden bg-slate-950">
        {/* Animated aurora background */}
        <AuroraBackground
          orbCount={7}
          hues={[220, 255, 195, 270, 205, 240, 185]}
          blur={72}
        />
        {/* Dark vignette to ground the content */}
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/60 via-slate-950/20 to-slate-950/80 pointer-events-none" />
        <div className="relative max-w-6xl mx-auto">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 text-indigo-200 rounded-full text-sm font-medium mb-8 border border-white/20 backdrop-blur-sm">
              <span className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
              {t("landing.badge")}
            </div>
            <h1 className="text-5xl md:text-6xl font-bold text-white leading-tight mb-6">
              {t("landing.titleLead")}{" "}
              <span className="text-indigo-300">{t("landing.titleAccent")}</span>
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed mb-10">
              {t("landing.subtitle")}
            </p>

            {/* Domain scanner */}
            <div className="flex flex-col sm:flex-row gap-3 max-w-lg mx-auto mb-5">
              <div className="flex-1 flex items-center border border-white/20 rounded-xl overflow-hidden bg-white/10 backdrop-blur-sm focus-within:ring-2 focus-within:ring-indigo-400 focus-within:border-transparent">
                <div className="pl-4 text-slate-300">
                  <Globe size={16} />
                </div>
                <input
                  type="text"
                  placeholder={t("landing.domainPlaceholder")}
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") startCheck()
                  }}
                  className="flex-1 px-3 py-3 text-sm bg-transparent text-white placeholder:text-slate-400 focus:outline-none"
                />
              </div>
              <Button
                size="lg"
                className="sm:w-auto w-full whitespace-nowrap"
                onClick={startCheck}
              >
                {t("landing.checkCta")}
                <ArrowRight size={16} />
              </Button>
            </div>
            <p className="text-xs text-slate-400">{t("landing.noCard")}</p>
          </div>

          {/* Dashboard preview */}
          <div className="max-w-4xl mx-auto">
            <HeroDashboard />
          </div>
        </div>
      </section>

      {/* Trust */}
      <section className="py-16 border-y border-slate-100 bg-slate-50">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <p className="text-sm font-medium text-slate-400 mb-8 uppercase tracking-widest">
            {t("landing.trustTitle")}
          </p>
          <div className="flex flex-wrap justify-center gap-4 text-sm text-slate-400 font-medium">
            {tList("landing.trustTags").map((tag) => (
              <span
                key={tag}
                className="px-4 py-2 bg-white border border-slate-200 rounded-full"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">
              {t("landing.howTitle")}
            </h2>
            <p className="text-lg text-slate-500">{t("landing.howSubtitle")}</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                id: "add",
                step: "01",
                title: t("landing.howSteps.add.title"),
                desc: t("landing.howSteps.add.desc"),
                icon: Globe,
              },
              {
                id: "score",
                step: "02",
                title: t("landing.howSteps.score.title"),
                desc: t("landing.howSteps.score.desc"),
                icon: CheckCircle,
              },
              {
                id: "notify",
                step: "03",
                title: t("landing.howSteps.notify.title"),
                desc: t("landing.howSteps.notify.desc"),
                icon: Bell,
              },
            ].map(({ id, step, title, desc, icon: Icon }) => (
              <div key={id} className="relative">
                <div className="flex items-start gap-5">
                  <div className="flex-shrink-0">
                    <span className="text-5xl font-black text-indigo-100 leading-none">
                      {step}
                    </span>
                  </div>
                  <div className="pt-2">
                    <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center mb-4">
                      <Icon size={18} className="text-white" />
                    </div>
                    <h3 className="font-bold text-slate-900 text-lg mb-2">
                      {title}
                    </h3>
                    <p className="text-slate-500">{desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Health Score */}
      <section className="py-24 px-4 bg-indigo-600">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="text-white">
              <h2 className="text-4xl font-bold mb-4">
                {t("landing.scoreTitle")}
              </h2>
              <p className="text-indigo-200 text-lg mb-8">
                {t("landing.scoreSubtitle")}
              </p>
              <div className="space-y-3">
                {SCORE_ITEMS.map(({ key, score, max }) => (
                  // German labels run longer than the English ones, so the
                  // label column gets a little more room.
                  <div key={key} className="flex items-center gap-4">
                    <span className="text-sm text-indigo-200 w-36 flex-shrink-0">
                      {t(`landing.scoreItems.${key}`)}
                    </span>
                    <div className="flex-1 h-1.5 bg-indigo-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          score === max ? "bg-emerald-400" : "bg-amber-400"
                        }`}
                        style={{ width: `${(score / max) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-white w-10 text-right">
                      {score}/{max}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex justify-center">
              <div className="bg-white/10 backdrop-blur rounded-3xl p-8 text-center border border-white/20">
                <p className="text-indigo-200 text-sm mb-4">
                  {t("landing.scoreLabel")}
                </p>
                <div className="relative inline-block mb-4">
                  <svg width="160" height="160" viewBox="0 0 160 160">
                    <circle
                      cx="80"
                      cy="80"
                      r="64"
                      fill="none"
                      stroke="rgba(255,255,255,0.15)"
                      strokeWidth="10"
                    />
                    <circle
                      cx="80"
                      cy="80"
                      r="64"
                      fill="none"
                      stroke="#34d399"
                      strokeWidth="10"
                      strokeDasharray={2 * Math.PI * 64}
                      strokeDashoffset={2 * Math.PI * 64 * (1 - 0.82)}
                      strokeLinecap="round"
                      transform="rotate(-90 80 80)"
                    />
                    <text
                      x="80"
                      y="72"
                      textAnchor="middle"
                      fill="white"
                      fontSize="36"
                      fontWeight="800"
                      fontFamily="Inter"
                    >
                      82
                    </text>
                    <text
                      x="80"
                      y="95"
                      textAnchor="middle"
                      fill="rgba(255,255,255,0.6)"
                      fontSize="14"
                      fontFamily="Inter"
                    >
                      / 100
                    </text>
                  </svg>
                </div>
                <p className="text-emerald-400 font-semibold">
                  {t("landing.scoreGood")}
                </p>
                <p className="text-indigo-200 text-sm mt-2 max-w-xs">
                  {t("landing.scoreNote")}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">
              {t("landing.featuresTitle")}
            </h2>
            <p className="text-lg text-slate-500">
              {t("landing.featuresSubtitle")}
            </p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURE_CARDS.map(({ id, icon, color, href }) => (
              <Link key={id} to={href}>
                <FeatureCard
                  icon={icon}
                  color={color}
                  title={t(`landing.features.${id}.title`)}
                  description={t(`landing.features.${id}.description`)}
                />
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* PWA section */}
      <section className="py-24 px-4 bg-slate-900">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="text-white">
              <h2 className="text-4xl font-bold mb-4">{t("landing.pwaTitle")}</h2>
              <p className="text-slate-400 text-lg mb-8">
                {t("landing.pwaSubtitle")}
              </p>
              <ul className="space-y-3 mb-8">
                {tList("landing.pwaBullets").map((bullet) => (
                  <li
                    key={bullet}
                    className="flex items-center gap-3 text-slate-300"
                  >
                    <CheckCircle
                      size={16}
                      className="text-emerald-400 flex-shrink-0"
                    />
                    {bullet}
                  </li>
                ))}
              </ul>
              <div className="flex gap-3">
                <Button>{t("landing.pwaInstall")}</Button>
                <Button
                  variant="ghost"
                  className="text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  <Play size={16} /> {t("landing.pwaLearn")}
                </Button>
              </div>
            </div>
            <div className="flex justify-center">
              {/* Phone mockup */}
              <div className="relative">
                <div className="w-56 bg-slate-800 rounded-3xl border-2 border-slate-700 overflow-hidden shadow-2xl">
                  <div className="h-6 bg-slate-800 flex items-center justify-center">
                    <div className="w-16 h-1 bg-slate-600 rounded-full" />
                  </div>
                  <div className="bg-slate-50 p-4 min-h-80">
                    <div className="bg-white rounded-xl p-3 mb-3 border border-slate-200">
                      <p className="text-xs font-semibold text-slate-900 mb-1">
                        {t("landing.mockScore")}
                      </p>
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-black text-emerald-600">
                          82
                        </span>
                        <span className="text-xs text-slate-500">
                          / 100 · {t("landing.mockGood")}
                        </span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {[
                        "example.de 🟢",
                        "example.com 🟢",
                        "example-shop.de 🟠",
                      ].map((s) => (
                        <div
                          key={s}
                          className="bg-white rounded-lg p-2.5 border border-slate-200 text-xs font-medium text-slate-700"
                        >
                          {s}
                        </div>
                      ))}
                    </div>
                    {/* Push notification */}
                    <div className="mt-3 bg-slate-900 text-white rounded-xl p-3 text-xs">
                      <p className="font-semibold mb-0.5">
                        {t("landing.mockSslAlert")}
                      </p>
                      <p className="text-slate-400">example-shop.de</p>
                    </div>
                  </div>
                  <div className="h-8 bg-slate-800 flex items-center justify-center">
                    <div className="w-10 h-1 bg-slate-600 rounded-full" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">
              {t("landing.pricingTitle")}
            </h2>
            <p className="text-slate-500">{t("landing.pricingSubtitle")}</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto">
            {plans.map((plan) => {
              const highlight = plan.tier === "pro"
              return (
                <div
                  key={plan.tier}
                  className={`relative rounded-2xl p-6 border flex flex-col ${
                    highlight
                      ? "border-indigo-500 shadow-xl shadow-indigo-100"
                      : "border-slate-200 bg-white"
                  } ${highlight ? "bg-indigo-600" : ""}`}
                >
                  {highlight && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="bg-amber-400 text-amber-900 text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap">
                        {t("landing.mostPopular")}
                      </span>
                    </div>
                  )}
                  <div
                    className={`mb-4 ${highlight ? "text-white" : "text-slate-900"}`}
                  >
                    <p
                      className={`text-sm font-medium mb-1 ${
                        highlight ? "text-indigo-200" : "text-slate-500"
                      }`}
                    >
                      {plan.name}
                    </p>
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-black tabular-nums">
                        {priceLabel(plan.monthly)}
                      </span>
                      <span
                        className={`text-sm ${
                          highlight ? "text-indigo-300" : "text-slate-400"
                        }`}
                      >
                        {t("pricing.perMonth")}
                      </span>
                    </div>
                    <p
                      className={`text-sm mt-1 ${
                        highlight ? "text-indigo-200" : "text-slate-500"
                      }`}
                    >
                      {plan.description}
                    </p>
                  </div>
                  <ul className="space-y-2 mb-6 flex-1">
                    {plan.features.map((feature) => (
                      <li
                        key={feature}
                        className="flex items-center gap-2 text-sm"
                      >
                        <CheckCircle
                          size={14}
                          className={
                            highlight ? "text-emerald-400" : "text-emerald-500"
                          }
                        />
                        <span
                          className={
                            highlight ? "text-indigo-100" : "text-slate-600"
                          }
                        >
                          {feature}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <Link to="/register">
                    <button
                      className={`w-full py-2.5 rounded-xl font-semibold text-sm transition-all ${
                        highlight
                          ? "bg-white text-indigo-700 hover:bg-indigo-50"
                          : "bg-indigo-600 text-white hover:bg-indigo-700"
                      }`}
                    >
                      {plan.cta}
                    </button>
                  </Link>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-24 px-4 bg-slate-50">
        <div className="max-w-2xl mx-auto">                  <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">
              {t("landing.faqTitle")}
            </h2>
          </div>
          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <div
                key={i}
                className="bg-white border border-slate-200 rounded-xl overflow-hidden"
              >
                <button
                  className="w-full flex items-center justify-between px-5 py-4 text-left"
                  onClick={() => setActiveFaq(activeFaq === i ? null : i)}
                >
                  <span className="font-medium text-slate-900">{faq.q}</span>
                  <ChevronDown
                    size={18}
                    className={`text-slate-400 flex-shrink-0 transition-transform ${
                      activeFaq === i ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {/* Kept in the HTML so the SSG output carries the answer;
                    `hidden` reproduces the collapsed accordion state. */}
                <div
                  hidden={activeFaq !== i}
                  className="px-5 pb-4 text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3"
                >
                  {faq.a}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-slate-900 mb-4">
            {t("landing.ctaTitle")}
          </h2>
          <p className="text-lg text-slate-500 mb-8">{t("landing.ctaSubtitle")}</p>
          <div className="flex justify-center gap-4">
            <Link to="/register">
              <Button size="lg">
                {t("common.startFree")} <ArrowRight size={16} />
              </Button>
            </Link>
            <Link to="/login">
              <Button variant="outline" size="lg">
                {t("common.login")}
              </Button>
            </Link>
          </div>
          <p className="text-sm text-slate-400 mt-4">
            {t("landing.ctaNoCard")}
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-12 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="3" fill="white" />
                  </svg>
                </div>
                <span className="font-bold text-slate-900">Presence</span>
              </div>
              <p className="text-sm text-slate-500">{t("footer.tagline")}</p>
          </div>
            {FOOTER_COLUMNS.map((col) => (
              <div key={col.titleKey}>
                <p className="text-sm font-semibold text-slate-700 mb-3">
                  {t(col.titleKey)}
                </p>
                <ul className="space-y-2">
                  {col.links.map((link) => (
                    <li key={link.labelKey}>
                      <Link
                        to={link.to}
                        className="text-sm text-slate-500 hover:text-slate-900"
                      >
                        {t(link.labelKey)}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="border-t border-slate-200 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="text-xs text-slate-400">{t("footer.rights")}</p>
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <span>{t("footer.madeInEurope")}</span>
              <span>{t("footer.gdprCompliant")}</span>
              <LanguageSwitcher />
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

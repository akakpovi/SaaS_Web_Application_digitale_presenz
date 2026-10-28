import React, { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { CheckCircle, Loader } from "lucide-react"
import { Button, Input, ScoreRing } from "../components/ui"
import SEO from "../components/SEO"
import { useI18n, type MessageKey } from "../i18n"

/** Step titles, in order; the index doubles as the wizard state. */
const STEP_KEYS = [
  "onboarding.stepBusiness",
  "onboarding.stepWebsite",
  "onboarding.stepScanning",
  "onboarding.stepResults",
] as const satisfies readonly MessageKey[]

/** Progress lines of the simulated first scan. */
const CHECK_KEYS = [
  "onboarding.checkWebsite",
  "onboarding.checkSsl",
  "onboarding.checkDns",
  "onboarding.checkEmail",
  "onboarding.checkHeaders",
  "onboarding.checkPerformance",
  "onboarding.checkScore",
] as const satisfies readonly MessageKey[]

/** Industry options: value sent to the API → catalogue key. */
const INDUSTRY_OPTIONS: { value: string; key: MessageKey }[] = [
  { value: "Restaurant / Café", key: "onboarding.industryRestaurant" },
  { value: "Retail", key: "onboarding.industryRetail" },
  { value: "Hotel / Hospitality", key: "onboarding.industryHotel" },
  { value: "Auto Repair", key: "onboarding.industryAuto" },
  { value: "Beauty / Hair Salon", key: "onboarding.industryBeauty" },
  { value: "Freelancer", key: "onboarding.industryFreelance" },
  { value: "Agency", key: "onboarding.industryAgency" },
  { value: "Real Estate", key: "onboarding.industryRealEstate" },
  { value: "Professional Services", key: "onboarding.industryServices" },
  { value: "Other", key: "onboarding.industryOther" },
]

/** Country options: the API expects the English name. */
const COUNTRY_OPTIONS: { value: string; key: MessageKey }[] = [
  { value: "Germany", key: "onboarding.countryGermany" },
  { value: "France", key: "onboarding.countryFrance" },
  { value: "Austria", key: "onboarding.countryAustria" },
  { value: "Switzerland", key: "onboarding.countrySwitzerland" },
  { value: "Netherlands", key: "onboarding.countryNetherlands" },
  { value: "Belgium", key: "onboarding.countryBelgium" },
  { value: "Other", key: "onboarding.countryOther" },
]

/** Preview rows of the first report (illustrative values). */
const RESULT_ROWS: { key: MessageKey; statusKey: MessageKey; score: string }[] = [
  { key: "checks.website", statusKey: "status.healthy", score: "20/20" },
  { key: "checks.ssl", statusKey: "status.healthy", score: "20/20" },
  { key: "checks.dns", statusKey: "status.healthy", score: "15/15" },
  { key: "checks.email", statusKey: "status.needsAttention", score: "10/15" },
  { key: "checks.headers", statusKey: "status.needsAttention", score: "9/15" },
  { key: "checks.performance", statusKey: "status.needsAttention", score: "8/15" },
]

export default function Onboarding() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [business, setBusiness] = useState({
    name: "",
    industry: "",
    country: "Germany",
  })
  const [domain, setDomain] = useState("example.de")
  const [checkIdx, setCheckIdx] = useState(0)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (step === 2) {
      const timer = setInterval(() => {
        setCheckIdx((prev) => {
          if (prev < CHECK_KEYS.length - 1) return prev + 1
          clearInterval(timer)
          setTimeout(() => setDone(true), 600)
          setTimeout(() => setStep(3), 1200)
          return prev
        })
      }, 700)
      return () => clearInterval(timer)
    }
  }, [step])

  return (
    <div className="min-h-full bg-slate-50 flex flex-col">
      <SEO
        title={t("onboarding.metaTitle")}
        description={t("onboarding.metaDescription")}
        noIndex
        path="/onboarding"
      />
      {/* Progress header */}
      <header className="py-6 px-4">
        <div className="max-w-lg mx-auto">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" fill="white" />
              </svg>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </div>
          <div className="flex items-center gap-2">
            {STEP_KEYS.map((stepKey, i) => (
              <React.Fragment key={stepKey}>
                <div
                  className={`flex items-center gap-2 ${
                    i <= step ? "text-indigo-600" : "text-slate-400"
                  }`}
                >
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${
                      i < step
                        ? "bg-indigo-600 border-indigo-600 text-white"
                        : i === step
                          ? "border-indigo-600 text-indigo-600 bg-white"
                          : "border-slate-300 text-slate-400"
                    }`}
                  >
                    {i < step ? <CheckCircle size={12} /> : i + 1}
                  </div>
                  <span className="text-xs font-medium hidden sm:block">
                    {t(stepKey)}
                  </span>
                </div>
                {i < STEP_KEYS.length - 1 && (
                  <div
                    className={`flex-1 h-px ${
                      i < step ? "bg-indigo-600" : "bg-slate-200"
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-lg">
          {/* Step 0 */}
          {step === 0 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
              <h1 className="text-2xl font-bold text-slate-900 mb-2">
                {t("onboarding.businessTitle")}
              </h1>
              <p className="text-sm text-slate-500 mb-6">
                {t("onboarding.businessSubtitle")}
              </p>
              <div className="flex flex-col gap-4">
                <Input
                  label={t("onboarding.businessName")}
                  placeholder={t("onboarding.businessNamePlaceholder")}
                  value={business.name}
                  onChange={(v) => setBusiness({ ...business, name: v })}
                />
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-slate-700">
                    {t("onboarding.industryLabel")}
                  </label>
                  <select
                    value={business.industry}
                    onChange={(e) =>
                      setBusiness({ ...business, industry: e.target.value })
                    }
                    className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="">
                      {t("onboarding.selectIndustry")}
                    </option>
                    {INDUSTRY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t(option.key)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-slate-700">
                    {t("onboarding.countryLabel")}
                  </label>
                  <select
                    value={business.country}
                    onChange={(e) =>
                      setBusiness({ ...business, country: e.target.value })
                    }
                    className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    {COUNTRY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t(option.key)}
                      </option>
                    ))}
                  </select>
                </div>
                <Button className="w-full mt-2" onClick={() => setStep(1)}>
                  {t("onboarding.continue")}
                </Button>
              </div>
            </div>
          )}

          {/* Step 1 */}
          {step === 1 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
              <h1 className="text-2xl font-bold text-slate-900 mb-2">
                {t("onboarding.websiteTitle")}
              </h1>
              <p className="text-sm text-slate-500 mb-6">
                {t("onboarding.websiteSubtitle")}
              </p>
              <div className="flex flex-col gap-4">
                <Input
                  label={t("onboarding.domainLabel")}
                  placeholder="example.com"
                  value={domain}
                  onChange={setDomain}
                  prefix="https://"
                  helper={t("onboarding.domainHelper")}
                />
                <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 text-sm text-indigo-700">
                  <p className="font-medium mb-1">
                    {t("onboarding.whatWeCheck")}
                  </p>
                  <ul className="space-y-1 text-indigo-600">
                    {[
                      "checks.website",
                      "checks.ssl",
                      "checks.dns",
                      "checks.email",
                      "checks.headers",
                      "checks.performance",
                    ].map((key) => (
                      <li key={key} className="flex items-center gap-2">
                        <CheckCircle size={12} /> {t(key as MessageKey)}
                      </li>
                    ))}
                  </ul>
                </div>
                <Button
                  className="w-full"
                  onClick={() => {
                    setStep(2)
                    setCheckIdx(0)
                    setDone(false)
                  }}
                >
                  {t("onboarding.checkCta")}
                </Button>
                <button
                  onClick={() => setStep(0)}
                  className="text-sm text-slate-400 hover:text-slate-600 text-center"
                >
                  ← {t("onboarding.back")}
                </button>
              </div>
            </div>
          )}

          {/* Step 2 - Scanning */}
          {step === 2 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm text-center">
              <div className="w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mx-auto mb-6">
                <Loader size={24} className="text-indigo-600 animate-spin" />
              </div>
              <h1 className="text-2xl font-bold text-slate-900 mb-2">
                {t("onboarding.scanningTitle")}
              </h1>
              <p className="text-slate-500 text-sm mb-8">
                {t("onboarding.scanningSubtitle")}
              </p>
              <div className="flex flex-col gap-2 text-left">
                {CHECK_KEYS.map((checkKey, i) => (
                  <div
                    key={checkKey}
                    className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all ${
                      i < checkIdx
                        ? "bg-emerald-50"
                        : i === checkIdx
                          ? "bg-indigo-50"
                          : "opacity-40"
                    }`}
                  >
                    {i < checkIdx ? (
                      <CheckCircle
                        size={16}
                        className="text-emerald-500 flex-shrink-0"
                      />
                    ) : i === checkIdx ? (
                      <Loader
                        size={16}
                        className="text-indigo-600 animate-spin flex-shrink-0"
                      />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-slate-300 flex-shrink-0" />
                    )}
                    <span
                      className={`text-sm ${
                        i < checkIdx
                          ? "text-emerald-700"
                          : i === checkIdx
                            ? "text-indigo-700 font-medium"
                            : "text-slate-400"
                      }`}
                    >
                      {t(checkKey)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Step 3 - Results */}
          {step === 3 && (
            <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
              <div className="text-center mb-6">
                <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircle size={24} className="text-emerald-600" />
                </div>
                <h1 className="text-2xl font-bold text-slate-900 mb-1">
                  {t("onboarding.resultTitle")}
                </h1>
                <p className="text-sm text-slate-500">
                  {t("onboarding.resultSubtitle", { domain })}
                </p>
              </div>

              <div className="flex justify-center mb-6">
                <ScoreRing
                  score={82}
                  size={140}
                  label={t("onboarding.resultScoreLabel")}
                />
              </div>

              <div className="space-y-2 mb-6">
                {RESULT_ROWS.map(({ key, statusKey, score }) => (
                  <div
                    key={key}
                    className="flex items-center justify-between px-4 py-2.5 bg-slate-50 rounded-xl"
                  >
                    <span className="text-sm font-medium text-slate-700">
                      {t(key)}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-slate-500">
                        {statusKey === "status.healthy" ? "🟢" : "🟠"}{" "}
                        {t(statusKey)}
                      </span>
                      <span className="text-sm font-semibold text-slate-800 tabular-nums">
                        {score}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <Button
                className="w-full"
                onClick={() => navigate("/app/dashboard")}
              >
                {t("onboarding.openDashboard")}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

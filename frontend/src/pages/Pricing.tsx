import React, { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle, ArrowLeft } from "lucide-react";
import SEO from "../components/SEO";

const plans = [
  {
    name: "Free",
    price: { monthly: "€0", yearly: "€0" },
    period: "/month",
    description: "Get started with basic monitoring",
    features: [
      { text: "1 website", included: true },
      { text: "Manual checks", included: true },
      { text: "Basic report", included: true },
      { text: "Email alerts", included: true },
      { text: "Automatic monitoring", included: false },
      { text: "PDF reports", included: false },
      { text: "Push notifications", included: false },
      { text: "Review monitoring", included: false },
    ],
    cta: "Start free",
    path: "/register",
    highlight: false,
  },
  {
    name: "Pro",
    price: { monthly: "€5.99", yearly: "€4.99" },
    period: "/month",
    description: "Everything you need for professional monitoring",
    features: [
      { text: "10 websites", included: true },
      { text: "Automatic hourly monitoring", included: true },
      { text: "Email & push alerts", included: true },
      { text: "PDF reports", included: true },
      { text: "Score history", included: true },
      { text: "Advanced checks", included: true },
      { text: "Review monitoring", included: false },
      { text: "Multiple users", included: false },
    ],
    cta: "Start 14-day trial",
    path: "/register",
    highlight: true,
  },
  {
    name: "Business",
    price: { monthly: "€14.99", yearly: "€11.99" },
    period: "/month",
    description: "For agencies and multi-location businesses",
    features: [
      { text: "50 websites", included: true },
      { text: "Automatic hourly monitoring", included: true },
      { text: "All alert channels", included: true },
      { text: "PDF reports", included: true },
      { text: "Advanced analytics", included: true },
      { text: "Review monitoring", included: true },
      { text: "Multiple users", included: true },
      { text: "Priority support", included: true },
    ],
    cta: "Start 14-day trial",
    path: "/register",
    highlight: false,
  },
];

export default function Pricing() {
  const [yearly, setYearly] = useState(false);

  return (
    <div className="min-h-full bg-white">
      <SEO
        title="Simple Website Monitoring Pricing | Presence"
        description="Free, Pro (€5.99/month) and Business (€14.99/month) plans. Automatic website monitoring, SSL alerts, DNS monitoring and more. Cancel anytime."
        path="/pricing"
        structuredData={{
          "@context": "https://schema.org",
          "@type": "Product",
          name: "Presence Website Monitoring",
          description: "Website monitoring for restaurants, shops and small businesses. Monitor uptime, SSL, DNS, email security and reviews from one simple dashboard.",
          offers: [
            { "@type": "Offer", name: "Free", price: "0", priceCurrency: "EUR", availability: "https://schema.org/InStock" },
            { "@type": "Offer", name: "Pro", price: "5.99", priceCurrency: "EUR", availability: "https://schema.org/InStock" },
            { "@type": "Offer", name: "Business", price: "14.99", priceCurrency: "EUR", availability: "https://schema.org/InStock" },
          ],
        }}
      />
      <div className="max-w-5xl mx-auto px-4 py-16">
        {/* Back */}
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 mb-12">
          <ArrowLeft size={14} /> Back to Presence
        </Link>

        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-slate-900 mb-4">Simple, transparent pricing</h1>
          <p className="text-lg text-slate-500 mb-8">No hidden fees. Cancel anytime.</p>

          {/* Billing toggle */}
          <div className="inline-flex items-center gap-3 p-1.5 bg-slate-100 rounded-xl">
            <button
              onClick={() => setYearly(false)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${!yearly ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
            >
              Monthly
            </button>
            <button
              onClick={() => setYearly(true)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${yearly ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
            >
              Yearly
              <span className="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded-full font-semibold">Save 20%</span>
            </button>
          </div>
        </div>

        {/* Plans */}
        <div className="grid md:grid-cols-3 gap-6 mb-16">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-2xl p-7 border ${
                plan.highlight
                  ? "border-indigo-500 shadow-2xl shadow-indigo-100/60 scale-105"
                  : "border-slate-200 bg-white"
              } ${plan.highlight ? "bg-indigo-600" : "bg-white"}`}
            >
              {plan.highlight && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                  <span className="bg-amber-400 text-amber-900 text-xs font-bold px-4 py-1.5 rounded-full shadow">Most popular</span>
                </div>
              )}

              <div className={`mb-5 ${plan.highlight ? "text-white" : "text-slate-900"}`}>
                <p className={`text-sm font-semibold mb-2 ${plan.highlight ? "text-indigo-200" : "text-slate-500"}`}>{plan.name}</p>
                <div className="flex items-baseline gap-1 mb-1">
                  <span className="text-4xl font-black">
                    {yearly ? plan.price.yearly : plan.price.monthly}
                  </span>
                  <span className={`text-sm ${plan.highlight ? "text-indigo-300" : "text-slate-400"}`}>/month</span>
                </div>
                {yearly && plan.name !== "Free" && (
                  <p className={`text-xs ${plan.highlight ? "text-indigo-300" : "text-slate-400"}`}>Billed annually</p>
                )}
                <p className={`text-sm mt-2 ${plan.highlight ? "text-indigo-200" : "text-slate-500"}`}>{plan.description}</p>
              </div>

              <ul className="space-y-2.5 mb-7">
                {plan.features.map((f) => (
                  <li key={f.text} className="flex items-center gap-2.5">
                    {f.included ? (
                      <CheckCircle size={15} className={plan.highlight ? "text-emerald-400" : "text-emerald-500"} />
                    ) : (
                      <span className={`w-4 h-4 flex items-center justify-center text-xs ${plan.highlight ? "text-indigo-400" : "text-slate-300"}`}>—</span>
                    )}
                    <span className={`text-sm ${f.included ? (plan.highlight ? "text-indigo-100" : "text-slate-700") : (plan.highlight ? "text-indigo-400" : "text-slate-400")}`}>
                      {f.text}
                    </span>
                  </li>
                ))}
              </ul>

              <Link to={plan.path}>
                <button className={`w-full py-3 rounded-xl font-semibold text-sm transition-all ${
                  plan.highlight
                    ? "bg-white text-indigo-700 hover:bg-indigo-50"
                    : "bg-indigo-600 text-white hover:bg-indigo-700"
                }`}>
                  {plan.cta}
                </button>
              </Link>
            </div>
          ))}
        </div>

        {/* Footnotes */}
        <div className="text-center text-sm text-slate-500 space-y-1">
          <p>All paid plans include a 14-day free trial. No credit card required to start.</p>
          <p>Cancel anytime from your account settings.</p>
        </div>

        {/* FAQ mini */}
        <div className="mt-16 border-t border-slate-100 pt-12">
          <h2 className="text-2xl font-bold text-slate-900 text-center mb-8">Frequently asked</h2>
          <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
            {[
              { q: "Can I change my plan later?", a: "Yes, you can upgrade or downgrade your plan at any time from your account settings." },
              { q: "What happens when I cancel?", a: "Your account remains active until the end of your billing period, then switches to the Free plan." },
              { q: "Is there a free trial?", a: "Yes. All paid plans include a 14-day free trial with no credit card required." },
              { q: "Do you offer discounts?", a: "We offer a 20% discount when you choose annual billing." },
            ].map(({ q, a }) => (
              <div key={q} className="p-5 bg-slate-50 rounded-xl">
                <p className="font-semibold text-slate-900 mb-2">{q}</p>
                <p className="text-sm text-slate-500">{a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

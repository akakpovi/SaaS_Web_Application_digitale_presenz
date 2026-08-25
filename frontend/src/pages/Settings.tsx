import React, { useState } from "react";
import { Card, Button, Toggle, Tabs } from "../components/ui";

const sections = ["Account", "Business", "Websites", "Notifications", "PWA", "Security", "Subscription", "Language"];

export default function Settings() {
  const [section, setSection] = useState("Account");
  const [notifs, setNotifs] = useState({
    websiteDown: true, sslExpiry: true, dnsChanges: true,
    emailSecurity: false, weeklyReport: true, reviews: true,
  });
  const [channels, setChannels] = useState({ email: true, push: true, discord: false, slack: false });
  const [pwa, setPwa] = useState({ installed: true, push: true, offline: true });
  const [lang, setLang] = useState("English");

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-500 mt-1">Manage your account and preferences.</p>
      </div>

      <div className="grid lg:grid-cols-4 gap-6">
        {/* Sidebar nav */}
        <nav className="lg:col-span-1">
          <Card className="overflow-hidden">
            {sections.map((s) => (
              <button
                key={s}
                onClick={() => setSection(s)}
                className={`w-full text-left px-4 py-3 text-sm border-b border-slate-100 last:border-0 transition-colors ${
                  section === s ? "bg-indigo-50 text-indigo-700 font-medium" : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {s}
              </button>
            ))}
          </Card>
        </nav>

        {/* Content */}
        <div className="lg:col-span-3">
          {section === "Account" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-6">Account details</h2>
              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-xl">
                  <div className="w-14 h-14 bg-indigo-100 rounded-full flex items-center justify-center text-xl font-bold text-indigo-600">M</div>
                  <div>
                    <p className="font-semibold text-slate-900">Maria Schmidt</p>
                    <p className="text-sm text-slate-500">maria@schmidt-bakery.de</p>
                  </div>
                  <Button size="sm" variant="outline" className="ml-auto">Change photo</Button>
                </div>
                <div className="grid gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-sm font-medium text-slate-700">Full name</label>
                    <input defaultValue="Maria Schmidt" className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-sm font-medium text-slate-700">Email address</label>
                    <input defaultValue="maria@schmidt-bakery.de" type="email" className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                </div>
                <Button className="self-start">Save changes</Button>
              </div>
            </Card>
          )}

          {section === "Business" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-6">Business information</h2>
              <div className="flex flex-col gap-4">
                {[
                  { label: "Business name", value: "Schmidt's Bakery" },
                  { label: "Industry", value: "Restaurant / Café", type: "select", options: ["Restaurant / Café", "Retail", "Hotel", "Auto Repair", "Beauty", "Agency"] },
                  { label: "Country", value: "Germany", type: "select", options: ["Germany", "France", "Austria", "Switzerland"] },
                  { label: "Timezone", value: "Europe/Berlin", type: "select", options: ["Europe/Berlin", "Europe/Paris", "Europe/Vienna", "UTC"] },
                ].map(({ label, value, type, options }) => (
                  <div key={label} className="flex flex-col gap-1.5">
                    <label className="text-sm font-medium text-slate-700">{label}</label>
                    {type === "select" ? (
                      <select defaultValue={value} className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white">
                        {options?.map(o => <option key={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input defaultValue={value} className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                    )}
                  </div>
                ))}
                <Button className="self-start">Save changes</Button>
              </div>
            </Card>
          )}

          {section === "Notifications" && (
            <div className="flex flex-col gap-4">
              <Card className="p-6">
                <h2 className="font-bold text-slate-900 mb-4">Alert types</h2>
                <div className="flex flex-col gap-4">
                  {[
                    { key: "websiteDown", label: "Website unavailable", desc: "Notify when your website goes offline" },
                    { key: "sslExpiry", label: "SSL certificate expiry", desc: "Notify 30 days before expiration" },
                    { key: "dnsChanges", label: "DNS configuration changes", desc: "Notify when DNS records change" },
                    { key: "emailSecurity", label: "Email security issues", desc: "Notify when email configuration has issues" },
                    { key: "weeklyReport", label: "Weekly report", desc: "Receive your digital health summary" },
                    { key: "reviews", label: "New reviews", desc: "Notify when new reviews are received" },
                  ].map(({ key, label, desc }) => (
                    <div key={key} className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-slate-800">{label}</p>
                        <p className="text-xs text-slate-500">{desc}</p>
                      </div>
                      <Toggle
                        checked={notifs[key as keyof typeof notifs]}
                        onChange={(v) => setNotifs(prev => ({ ...prev, [key]: v }))}
                      />
                    </div>
                  ))}
                </div>
              </Card>

              <Card className="p-6">
                <h2 className="font-bold text-slate-900 mb-4">Notification channels</h2>
                <div className="flex flex-col gap-4">
                  {[
                    { key: "email", label: "Email", desc: "Receive alerts by email" },
                    { key: "push", label: "Push notifications", desc: "Browser and PWA notifications" },
                    { key: "discord", label: "Discord", desc: "Webhook integration" },
                    { key: "slack", label: "Slack", desc: "Webhook integration" },
                  ].map(({ key, label, desc }) => (
                    <div key={key} className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-slate-800">{label}</p>
                        <p className="text-xs text-slate-500">{desc}</p>
                      </div>
                      <Toggle
                        checked={channels[key as keyof typeof channels]}
                        onChange={(v) => setChannels(prev => ({ ...prev, [key]: v }))}
                      />
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {section === "PWA" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-2">Progressive Web App</h2>
              <p className="text-sm text-slate-500 mb-6">Install Presence on your device for faster access and push notifications.</p>

              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-3 mb-6">
                <span className="text-emerald-600 text-xl">✅</span>
                <div>
                  <p className="text-sm font-semibold text-emerald-800">Presence is installed</p>
                  <p className="text-xs text-emerald-600">Last synchronized: today at 10:42</p>
                </div>
              </div>

              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-800">Push notifications</p>
                    <p className="text-xs text-slate-500">Enabled on this device</p>
                  </div>
                  <Toggle checked={pwa.push} onChange={(v) => setPwa(p => ({ ...p, push: v }))} />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-800">Offline data</p>
                    <p className="text-xs text-slate-500">Cache data for offline access</p>
                  </div>
                  <Toggle checked={pwa.offline} onChange={(v) => setPwa(p => ({ ...p, offline: v }))} />
                </div>
              </div>
            </Card>
          )}

          {section === "Language" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-6">Language & region</h2>
              <div className="flex flex-col gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">Display language</p>
                  <div className="grid grid-cols-3 gap-2">
                    {["English", "Français", "Deutsch"].map((l) => (
                      <button
                        key={l}
                        onClick={() => setLang(l)}
                        className={`py-2.5 px-4 rounded-xl border text-sm font-medium transition-all ${lang === l ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
                <Button className="self-start">Save preference</Button>
              </div>
            </Card>
          )}

          {section === "Subscription" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-2">Your subscription</h2>
              <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl mb-6 flex items-center justify-between">
                <div>
                  <p className="font-semibold text-indigo-900">Pro Plan</p>
                  <p className="text-sm text-indigo-600">€5.99/month · Renews 1 September 2026</p>
                </div>
                <span className="px-3 py-1 bg-indigo-600 text-white text-xs font-bold rounded-full">Active</span>
              </div>
              <div className="space-y-2 mb-6">
                <p className="text-sm font-medium text-slate-700">Included in your plan:</p>
                {["10 websites", "Automatic hourly monitoring", "Email & push alerts", "PDF reports", "Score history", "Advanced checks"].map(f => (
                  <div key={f} className="flex items-center gap-2 text-sm text-slate-600">
                    <span className="text-emerald-500">✓</span> {f}
                  </div>
                ))}
              </div>
              <div className="flex gap-3 flex-wrap">
                <Button variant="outline" size="sm">Upgrade to Business</Button>
                <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700 hover:bg-red-50">Cancel subscription</Button>
              </div>
            </Card>
          )}

          {!["Account", "Business", "Notifications", "PWA", "Language", "Subscription"].includes(section) && (
            <Card className="p-12 text-center">
              <p className="text-4xl mb-3">🔧</p>
              <p className="font-semibold text-slate-900 mb-1">{section} settings</p>
              <p className="text-sm text-slate-500">This section is available in the full application.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

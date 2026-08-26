import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";
import { Check, Loader2, LogOut, Shield, Bell, Globe, CreditCard, User } from "lucide-react";

interface NotifPrefs {
  ssl_expiring_enabled: boolean;
  ssl_invalid_enabled: boolean;
  website_offline_enabled: boolean;
  dns_problem_enabled: boolean;
  email_security_enabled: boolean;
  security_headers_enabled: boolean;
  performance_enabled: boolean;
  score_drop_enabled: boolean;
  scan_failed_enabled: boolean;
  digest_frequency: string;
}

interface Plan {
  id: number;
  tier: string;
  name: string;
  price_monthly: string;
}

interface Subscription {
  id: string;
  status: string;
  billing_cycle: string;
  plan: Plan;
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative w-11 h-6 rounded-full transition-colors duration-200 flex-shrink-0 ${checked ? "bg-indigo-600" : "bg-slate-200"}`}
    >
      <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${checked ? "translate-x-6" : "translate-x-1"}`} />
    </button>
  );
}

function Section({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden mb-4">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-100">
        <Icon size={18} className="text-indigo-600" />
        <h2 className="font-bold text-slate-900">{title}</h2>
      </div>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

function AccountSection() {
  const { user, logout } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const dirty = fullName !== (user?.full_name ?? "");

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.patch("/auth/me/", { full_name: fullName });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("Failed to save.");
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    try { await logout(); } catch { /* finally dans AuthContext */ }
  };

  return (
    <Section icon={User} title="Account">
      <form onSubmit={handleSave} className="flex flex-col gap-4 max-w-sm">
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-1.5">Full name</label>
          <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-1.5">Email address</label>
          <input type="email" value={user?.email ?? ""} disabled
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-slate-50 text-slate-400" />
          <p className="text-xs text-slate-400 mt-1">Email cannot be changed.</p>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={saving || !dirty}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg self-start transition-colors ${dirty ? "bg-indigo-600 text-white hover:bg-indigo-700" : "bg-slate-100 text-slate-400 cursor-not-allowed"}`}>
          {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <Check size={14} /> : null}
          {saving ? "Saving…" : saved ? "Saved" : "Save changes"}
        </button>
      </form>
      <div className="mt-6 pt-6 border-t border-slate-100 max-w-sm">
        <p className="text-sm font-medium text-slate-700 mb-1">Sign out</p>
        <p className="text-xs text-slate-400 mb-3">You will be redirected to the login page.</p>
        <button onClick={handleLogout}
          className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors">
          <LogOut size={14} /> Sign out
        </button>
      </div>
    </Section>
  );
}

function NotificationsSection() {
  const [prefs, setPrefs] = useState<NotifPrefs | null>(null);
  const [original, setOriginal] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<NotifPrefs>("/alerts/preferences/").then(({ data }) => {
      setPrefs(data);
      setOriginal(JSON.stringify(data));
    }).catch(() => {});
  }, []);

  const dirty = prefs ? JSON.stringify(prefs) !== original : false;

  const handleSave = async () => {
    if (!prefs) return;
    setSaving(true);
    try {
      await api.patch("/alerts/preferences/", prefs);
      setOriginal(JSON.stringify(prefs));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally { setSaving(false); }
  };

  const TOGGLES: [keyof NotifPrefs, string][] = [
    ["ssl_expiring_enabled",     "SSL expiring soon"],
    ["ssl_invalid_enabled",      "SSL invalid or expired"],
    ["website_offline_enabled",  "Website offline"],
    ["dns_problem_enabled",      "DNS problems"],
    ["email_security_enabled",   "Email security issues"],
    ["security_headers_enabled", "Missing security headers"],
    ["performance_enabled",      "Performance degradation"],
    ["score_drop_enabled",       "Health score drop"],
    ["scan_failed_enabled",      "Scan failed"],
  ];

  return (
    <Section icon={Bell} title="Alert preferences">
      {!prefs ? (
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {TOGGLES.map(([key, label]) => (
            <div key={key} className="flex items-center justify-between py-3 border-b border-slate-50 last:border-0">
              <span className="text-sm text-slate-700">{label}</span>
              <Toggle checked={prefs[key] as boolean} onChange={(v) => setPrefs({ ...prefs, [key]: v })} />
            </div>
          ))}
          <div className="pt-4">
            <label className="text-sm font-medium text-slate-700 block mb-2">Digest frequency</label>
            <select value={prefs.digest_frequency} onChange={(e) => setPrefs({ ...prefs, digest_frequency: e.target.value })}
              className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
              <option value="immediate">Immediate</option>
              <option value="hourly">Hourly digest</option>
              <option value="daily">Daily digest</option>
            </select>
          </div>
          <div className="pt-4">
            <button onClick={handleSave} disabled={saving || !dirty}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${dirty ? "bg-indigo-600 text-white hover:bg-indigo-700" : "bg-slate-100 text-slate-400 cursor-not-allowed"}`}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <Check size={14} /> : null}
              {saving ? "Saving…" : saved ? "Saved" : "Save preferences"}
            </button>
          </div>
        </div>
      )}
    </Section>
  );
}

function LanguageSection({ lang, setLang }: { lang: string; setLang: (l: string) => void }) {
  const [saved, setSaved] = useState(false);
  const LANGUAGES = [
    { code: "en", label: "English" },
    { code: "fr", label: "Français" },
    { code: "de", label: "Deutsch" },
    { code: "es", label: "Español" },
  ];
  const handleSave = () => {
    localStorage.setItem("presence_lang", lang);
    window.dispatchEvent(new Event("presence_lang_change"));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };
  return (
    <Section icon={Globe} title="Language & region">
      <div className="max-w-sm flex flex-col gap-4">
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-2">Display language</label>
          <select value={lang} onChange={(e) => setLang(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
            {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
          <p className="text-xs text-slate-400 mt-2">Language is saved locally. Full translations coming soon.</p>
        </div>
        <button onClick={handleSave}
          className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors self-start">
          {saved ? <><Check size={14} /> Saved</> : "Save language"}
        </button>
      </div>
    </Section>
  );
}

function SubscriptionSection() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<Subscription>("/subscriptions/me/"),
      api.get<{ results: Plan[] }>("/subscriptions/plans/"),
    ]).then(([s, p]) => {
      setSub(s.data);
      setPlans(p.data.results ?? []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleUpgrade = async (tier: string) => {
    setUpgrading(tier);
    try {
      await api.post("/subscriptions/upgrade/", { plan_tier: tier, billing_cycle: "monthly" });
      const { data } = await api.get<Subscription>("/subscriptions/me/");
      setSub(data);
    } finally { setUpgrading(null); }
  };

  const handleCancel = async () => {
    if (!confirm("Cancel your subscription?")) return;
    setCancelling(true);
    try {
      await api.post("/subscriptions/cancel/");
      const { data } = await api.get<Subscription>("/subscriptions/me/");
      setSub(data);
    } finally { setCancelling(false); }
  };

  return (
    <Section icon={CreditCard} title="Subscription">
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : sub ? (
        <div className="flex flex-col gap-5">
          <div className="p-4 bg-indigo-50 rounded-xl border border-indigo-100">
            <p className="text-sm font-bold text-indigo-900">Current plan: {sub.plan.name}</p>
            <p className="text-sm text-indigo-700 mt-0.5">
              Status: <span className="font-medium capitalize">{sub.status}</span> · {sub.billing_cycle} billing
            </p>
          </div>
          <div className="grid sm:grid-cols-3 gap-3">
            {plans.map((plan) => {
              const isCurrent = plan.tier === sub.plan.tier;
              return (
                <div key={plan.id} className={`p-4 border rounded-xl ${isCurrent ? "border-indigo-300 bg-indigo-50" : "border-slate-200"}`}>
                  <p className="font-bold text-slate-900">{plan.name}</p>
                  <p className="text-xl font-black text-slate-900 my-1">
                    €{plan.price_monthly}<span className="text-xs font-normal text-slate-500">/mo</span>
                  </p>
                  {isCurrent ? (
                    <span className="text-xs text-indigo-600 font-semibold">✓ Current</span>
                  ) : (
                    <button onClick={() => handleUpgrade(plan.tier)} disabled={upgrading === plan.tier}
                      className="mt-2 w-full flex items-center justify-center gap-1 px-3 py-1.5 text-xs font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50">
                      {upgrading === plan.tier ? <Loader2 size={12} className="animate-spin" /> : "Switch plan"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
          {sub.plan.tier !== "free" && sub.status === "active" && (
            <div className="pt-2 border-t border-slate-100">
              <button onClick={handleCancel} disabled={cancelling}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors">
                {cancelling ? <Loader2 size={14} className="animate-spin" /> : "Cancel subscription"}
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-slate-500">Unable to load subscription.</p>
      )}
    </Section>
  );
}

function SecuritySection() {
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw.length < 12) { setError("New password must be at least 12 characters."); return; }
    setSaving(true); setError("");
    try {
      await api.post("/auth/password/change/", { current_password: current, new_password: newPw });
      setSaved(true); setCurrent(""); setNewPw("");
      setTimeout(() => setSaved(false), 2500);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to change password.");
    } finally { setSaving(false); }
  };

  return (
    <Section icon={Shield} title="Security">
      <form onSubmit={handleSave} className="flex flex-col gap-4 max-w-sm">
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-1.5">Current password</label>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        <div>
          <label className="text-sm font-medium text-slate-700 block mb-1.5">New password</label>
          <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} placeholder="Min. 12 characters" required
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {saved && <p className="text-sm text-emerald-600 flex items-center gap-1"><Check size={14} /> Password updated.</p>}
        <button type="submit" disabled={saving || !current || !newPw}
          className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors self-start disabled:opacity-50">
          {saving ? <Loader2 size={14} className="animate-spin" /> : "Change password"}
        </button>
      </form>
    </Section>
  );
}

const SECTIONS = [
  { id: "account",       label: "Account",       icon: User },
  { id: "notifications", label: "Notifications",  icon: Bell },
  { id: "subscription",  label: "Subscription",   icon: CreditCard },
  { id: "language",      label: "Language",       icon: Globe },
  { id: "security",      label: "Security",       icon: Shield },
];

export default function Settings() {
  const [section, setSection] = useState("account");
  const [lang, setLang] = useState(() => localStorage.getItem("presence_lang") ?? "en");

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-500 mt-1">Manage your account and preferences.</p>
      </div>
      <div className="flex flex-col lg:flex-row gap-6">
        <nav className="lg:w-48 flex-shrink-0">
          <div className="flex flex-row lg:flex-col gap-1 flex-wrap">
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <button key={id} onClick={() => setSection(id)}
                className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium text-left transition-colors ${section === id ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-50"}`}>
                <Icon size={16} />{label}
              </button>
            ))}
          </div>
        </nav>
        <div className="flex-1 min-w-0">
          {section === "account"       && <AccountSection />}
          {section === "notifications" && <NotificationsSection />}
          {section === "subscription"  && <SubscriptionSection />}
          {section === "language"      && <LanguageSection lang={lang} setLang={setLang} />}
          {section === "security"      && <SecuritySection />}
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from "react";
import { Card, Button, Toggle, Tabs } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import api from "../services/api";

const sections = ["Account", "Business", "Websites", "Notifications", "PWA", "Security", "Subscription", "Language"];

export default function Settings() {
  const { user, logout } = useAuth();
  const [section, setSection] = useState("Account");
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [notifs, setNotifs] = useState({
    websiteDown: true, sslExpiry: true, dnsChanges: true,
    emailSecurity: false, weeklyReport: true, reviews: true,
  });
  const [channels, setChannels] = useState({ email: true, push: true, discord: false, slack: false });
  const [pwa, setPwa] = useState({ installed: true, push: true, offline: true });
  const [lang, setLang] = useState("English");

  useEffect(() => {
    if (user) {
      setFullName(user.full_name);
      setEmail(user.email);
    }
  }, [user]);

  const handleSaveAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveMsg('');
    try {
      await api.patch('/auth/me/', { full_name: fullName });
      setSaveMsg('Saved successfully!');
      setTimeout(() => setSaveMsg(''), 3000);
    } catch {
      setSaveMsg('Failed to save. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const initials = user?.full_name
    ?.split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) ?? '?';

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-500 mt-1">Manage your account and preferences.</p>
      </div>

      <div className="grid lg:grid-cols-4 gap-6">
        <nav className="lg:col-span-1">
          <Card className="overflow-hidden">
            {sections.map((s) => (
              <button key={s} onClick={() => setSection(s)}
                className={`w-full text-left px-4 py-3 text-sm border-b border-slate-100 last:border-0 transition-colors ${
                  section === s ? "bg-indigo-50 text-indigo-700 font-medium" : "text-slate-600 hover:bg-slate-50"
                }`}>
                {s}
              </button>
            ))}
          </Card>
        </nav>

        <div className="lg:col-span-3">
          {section === "Account" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-6">Account details</h2>
              <form onSubmit={handleSaveAccount} className="flex flex-col gap-4">
                <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-xl">
                  <div className="w-14 h-14 bg-indigo-100 rounded-full flex items-center justify-center text-xl font-bold text-indigo-600">
                    {initials}
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">{user?.full_name}</p>
                    <p className="text-sm text-slate-500">{user?.email}</p>
                    {user?.is_email_verified === false && (
                      <span className="text-xs text-amber-600">⚠ Email not verified</span>
                    )}
                  </div>
                </div>
                <div className="grid gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-sm font-medium text-slate-700">Full name</label>
                    <input
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className="text-sm font-medium text-slate-700">Email address</label>
                    <input
                      value={email}
                      disabled
                      className="px-3 py-2 text-sm border border-slate-200 rounded-lg bg-slate-50 text-slate-400 cursor-not-allowed"
                    />
                    <p className="text-xs text-slate-400">Email cannot be changed.</p>
                  </div>
                </div>
                {saveMsg && (
                  <p className={`text-sm ${saveMsg.includes('Failed') ? 'text-red-600' : 'text-emerald-600'}`}>
                    {saveMsg}
                  </p>
                )}
                <div className="flex items-center gap-3">
                  <Button type="submit" disabled={isSaving}>
                    {isSaving ? 'Saving...' : 'Save changes'}
                  </Button>
                  <Button type="button" variant="ghost" className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    onClick={logout}>
                    Sign out
                  </Button>
                </div>
              </form>
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
                      <Toggle checked={notifs[key as keyof typeof notifs]}
                        onChange={(v) => setNotifs(prev => ({ ...prev, [key]: v }))} />
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
                      <Toggle checked={channels[key as keyof typeof channels]}
                        onChange={(v) => setChannels(prev => ({ ...prev, [key]: v }))} />
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {section === "Subscription" && (
            <SubscriptionSection />
          )}

          {section === "Language" && (
            <Card className="p-6">
              <h2 className="font-bold text-slate-900 mb-6">Language & region</h2>
              <div className="flex flex-col gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">Display language</p>
                  <div className="grid grid-cols-3 gap-2">
                    {["English", "Français", "Deutsch"].map((l) => (
                      <button key={l} onClick={() => setLang(l)}
                        className={`py-2.5 px-4 rounded-xl border text-sm font-medium transition-all ${lang === l ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
                <Button className="self-start">Save preference</Button>
              </div>
            </Card>
          )}

          {!["Account", "Notifications", "Subscription", "Language"].includes(section) && (
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

function SubscriptionSection() {
  const [sub, setSub] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [subRes, plansRes] = await Promise.all([
          api.get('/subscriptions/me/'),
          api.get('/subscriptions/plans/'),
        ]);
        setSub(subRes.data);
        setPlans(plansRes.data.results ?? plansRes.data);
      } catch { /* ignore */ }
      finally { setIsLoading(false); }
    };
    load();
  }, []);

  if (isLoading) return <div className="flex justify-center py-8"><div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <Card className="p-6">
      <h2 className="font-bold text-slate-900 mb-2">Your subscription</h2>
      {sub && (
        <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl mb-6 flex items-center justify-between">
          <div>
            <p className="font-semibold text-indigo-900">{sub.plan?.name ?? 'Free'} Plan</p>
            <p className="text-sm text-indigo-600">
              {sub.plan?.price_monthly === '0.00' ? 'Free forever' : `€${sub.plan?.price_monthly}/month`}
            </p>
          </div>
          <span className={`px-3 py-1 text-xs font-bold rounded-full ${sub.status === 'active' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
            {sub.status}
          </span>
        </div>
      )}
      <div className="space-y-2 mb-6">
        <p className="text-sm font-medium text-slate-700">Available plans:</p>
        {plans.map((p: any) => (
          <div key={p.id} className={`flex items-center justify-between p-3 rounded-xl border ${sub?.plan?.tier === p.tier ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200'}`}>
            <div>
              <p className="text-sm font-semibold text-slate-800">{p.name}</p>
              <p className="text-xs text-slate-500">{p.max_websites} sites · {p.max_scans_per_month} scans/mo</p>
            </div>
            <span className="text-sm font-bold text-slate-800">
              {p.price_monthly === '0.00' ? 'Free' : `€${p.price_monthly}/mo`}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

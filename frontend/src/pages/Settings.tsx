import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { 
  UserCircle, 
  BellRing, 
  CreditCard, 
  CheckCircle,
  AlertTriangle
} from 'lucide-react';

// Interfaces for data types
interface AlertPreferences {
  ssl_expiring_enabled: boolean;
  ssl_invalid_enabled: boolean;
  website_offline_enabled: boolean;
  dns_problem_enabled: boolean;
  email_security_enabled: boolean;
  security_headers_enabled: boolean;
  performance_enabled: boolean;
  score_drop_enabled: boolean;
  scan_failed_enabled: boolean;
  digest_frequency: 'immediate' | 'hourly' | 'daily';
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
}

interface SubscriptionInfo {
  tier: string;
  name: string;
  status: string;
  billing_cycle: string;
  current_period_end: string;
}

export const Settings: React.FC = () => {
  const { t } = useTranslation();
  const { lang } = useParams<{ lang: string }>();
  const { user } = useAuth();
  
  const [activeTab, setActiveTab] = useState<'profile' | 'notifications' | 'subscription'>('profile');
  
  // Profile State
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);

  // Notification State
  const [alertPrefs, setAlertPrefs] = useState<AlertPreferences | null>(null);
  const [prefsLoading, setPrefsLoading] = useState(false);
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [prefsMessage, setPrefsMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);

  // Subscription State
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [subLoading, setSubLoading] = useState(false);

  // Load preferences
  const fetchPreferences = useCallback(async () => {
    try {
      setPrefsLoading(true);
      const response = await api.get('/alerts/preferences/');
      setAlertPrefs(response.data);
    } catch (error) {
      console.error('Failed to load alert preferences', error);
    } finally {
      setPrefsLoading(false);
    }
  }, []);

  // Load subscription
  const fetchSubscription = useCallback(async () => {
    try {
      setSubLoading(true);
      const response = await api.get('/subscriptions/me/');
      setSubscription(response.data);
    } catch (error) {
      console.error('Failed to load subscription info', error);
    } finally {
      setSubLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'notifications' && !alertPrefs) {
      fetchPreferences();
    } else if (activeTab === 'subscription' && !subscription) {
      fetchSubscription();
    }
  }, [activeTab, alertPrefs, subscription, fetchPreferences, fetchSubscription]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setProfileSaving(true);
      setProfileMessage(null);
      await api.patch('/auth/me/', { full_name: fullName });
      setProfileMessage({ type: 'success', text: t('settings.profileSaved', 'Profile saved successfully') });
      setTimeout(() => setProfileMessage(null), 3000);
    } catch (error) {
      setProfileMessage({ type: 'error', text: t('settings.profileError', 'Failed to save profile') });
    } finally {
      setProfileSaving(false);
    }
  };

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!alertPrefs) return;
    try {
      setPrefsSaving(true);
      setPrefsMessage(null);
      await api.put('/alerts/preferences/', alertPrefs);
      setPrefsMessage({ type: 'success', text: t('settings.prefsSaved', 'Preferences saved successfully') });
      setTimeout(() => setPrefsMessage(null), 3000);
    } catch (error) {
      setPrefsMessage({ type: 'error', text: t('settings.prefsError', 'Failed to save preferences') });
    } finally {
      setPrefsSaving(false);
    }
  };

  const handlePrefChange = (field: keyof AlertPreferences, value: any) => {
    setAlertPrefs(prev => prev ? { ...prev, [field]: value } : null);
  };

  const renderMessage = (msg: {type: 'success' | 'error', text: string} | null) => {
    if (!msg) return null;
    return (
      <div className={`p-4 rounded-xl mb-6 flex items-center gap-3 ${
        msg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-red-50 text-red-800 border border-red-200'
      }`}>
        {msg.type === 'success' ? (
          <CheckCircle className="w-5 h-5 text-emerald-600" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-red-600" />
        )}
        <p className="font-medium text-sm">{msg.text}</p>
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">{t('settings.title', 'Settings')}</h1>
        <p className="text-sm text-slate-500 mt-1">{t('settings.subtitle', 'Manage your account, notifications, and billing.')}</p>
      </div>

      <div className="flex flex-col md:flex-row gap-8">
        {/* Sidebar Tabs */}
        <div className="w-full md:w-64 shrink-0">
          <nav className="flex flex-col space-y-1">
            <button
              onClick={() => setActiveTab('profile')}
              className={`flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-xl transition-colors ${
                activeTab === 'profile' 
                  ? 'bg-indigo-50 text-indigo-700' 
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <UserCircle className={`w-5 h-5 ${activeTab === 'profile' ? 'text-indigo-600' : 'text-slate-400'}`} />
              {t('settings.profileTab', 'Profile')}
            </button>
            <button
              onClick={() => setActiveTab('notifications')}
              className={`flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-xl transition-colors ${
                activeTab === 'notifications' 
                  ? 'bg-indigo-50 text-indigo-700' 
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <BellRing className={`w-5 h-5 ${activeTab === 'notifications' ? 'text-indigo-600' : 'text-slate-400'}`} />
              {t('settings.notificationsTab', 'Notifications')}
            </button>
            <button
              onClick={() => setActiveTab('subscription')}
              className={`flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-xl transition-colors ${
                activeTab === 'subscription' 
                  ? 'bg-indigo-50 text-indigo-700' 
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <CreditCard className={`w-5 h-5 ${activeTab === 'subscription' ? 'text-indigo-600' : 'text-slate-400'}`} />
              {t('settings.subscriptionTab', 'Subscription')}
            </button>
          </nav>
        </div>

        {/* Content Area */}
        <div className="flex-1">
          {activeTab === 'profile' && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
              <h2 className="text-xl font-bold text-slate-900 mb-6">{t('settings.profileInfo', 'Profile Information')}</h2>
              
              {renderMessage(profileMessage)}
              
              <form onSubmit={handleSaveProfile} className="max-w-md space-y-6">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    {t('settings.email', 'Email Address')}
                  </label>
                  <input
                    type="email"
                    disabled
                    value={user?.email || ''}
                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-slate-500 cursor-not-allowed sm:text-sm"
                  />
                  <p className="mt-2 text-xs text-slate-500">{t('settings.emailDesc', 'Your email address is used for sign-in and cannot be changed here.')}</p>
                </div>
                
                <div>
                  <label htmlFor="fullName" className="block text-sm font-medium text-slate-700 mb-2">
                    {t('settings.fullName', 'Full Name')}
                  </label>
                  <input
                    id="fullName"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full px-4 py-2 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 sm:text-sm transition-shadow"
                  />
                </div>
                
                <div className="pt-4">
                  <button
                    type="submit"
                    disabled={profileSaving}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-xl font-bold text-sm transition-colors disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center min-w-[120px]"
                  >
                    {profileSaving ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : (
                      t('settings.saveChanges', 'Save Changes')
                    )}
                  </button>
                </div>
              </form>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
              <h2 className="text-xl font-bold text-slate-900 mb-6">{t('settings.alertPreferences', 'Alert Preferences')}</h2>
              
              {renderMessage(prefsMessage)}
              
              {prefsLoading ? (
                <div className="flex justify-center py-12">
                  <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
                </div>
              ) : alertPrefs ? (
                <form onSubmit={handleSavePreferences} className="space-y-8">
                  {/* Delivery Settings */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">{t('settings.deliverySettings', 'Delivery Settings')}</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 bg-slate-50 p-5 rounded-xl border border-slate-100">
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          {t('settings.digestFreq', 'Digest Frequency')}
                        </label>
                        <select
                          value={alertPrefs.digest_frequency}
                          onChange={(e) => handlePrefChange('digest_frequency', e.target.value)}
                          className="w-full px-4 py-2 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 sm:text-sm"
                        >
                          <option value="immediate">{t('settings.freqImmediate', 'Immediate')}</option>
                          <option value="hourly">{t('settings.freqHourly', 'Hourly')}</option>
                          <option value="daily">{t('settings.freqDaily', 'Daily')}</option>
                        </select>
                      </div>
                      <div className="flex gap-4">
                        <div className="flex-1">
                          <label className="block text-sm font-medium text-slate-700 mb-2">
                            {t('settings.quietStart', 'Quiet Hours Start')}
                          </label>
                          <input
                            type="time"
                            value={alertPrefs.quiet_hours_start || ''}
                            onChange={(e) => handlePrefChange('quiet_hours_start', e.target.value || null)}
                            className="w-full px-4 py-2 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 sm:text-sm"
                          />
                        </div>
                        <div className="flex-1">
                          <label className="block text-sm font-medium text-slate-700 mb-2">
                            {t('settings.quietEnd', 'Quiet Hours End')}
                          </label>
                          <input
                            type="time"
                            value={alertPrefs.quiet_hours_end || ''}
                            onChange={(e) => handlePrefChange('quiet_hours_end', e.target.value || null)}
                            className="w-full px-4 py-2 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 sm:text-sm"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Alert Types */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">{t('settings.alertTypes', 'Alert Types')}</h3>
                    <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
                      {[
                        { key: 'ssl_expiring_enabled', label: t('settings.sslExpiring', 'SSL Certificate Expiring'), desc: t('settings.sslExpiringDesc', 'Get notified before your SSL certificate expires.') },
                        { key: 'ssl_invalid_enabled', label: t('settings.sslInvalid', 'SSL Certificate Invalid'), desc: t('settings.sslInvalidDesc', 'Immediate alert if SSL becomes invalid or untrusted.') },
                        { key: 'website_offline_enabled', label: t('settings.siteOffline', 'Website Offline'), desc: t('settings.siteOfflineDesc', 'Immediate alert if your website stops responding.') },
                        { key: 'dns_problem_enabled', label: t('settings.dnsProblem', 'DNS Resolution Problem'), desc: t('settings.dnsProblemDesc', 'Alerts about DNS propagation or resolution errors.') },
                        { key: 'email_security_enabled', label: t('settings.emailSec', 'Email Security Issues'), desc: t('settings.emailSecDesc', 'Alerts for SPF, DKIM, or DMARC misconfigurations.') },
                        { key: 'security_headers_enabled', label: t('settings.secHeaders', 'Security Headers Missing'), desc: t('settings.secHeadersDesc', 'Notifies you if critical security headers are missing.') },
                        { key: 'performance_enabled', label: t('settings.perfDrop', 'Performance Drop'), desc: t('settings.perfDropDesc', 'Alerts when page load time increases significantly.') },
                        { key: 'score_drop_enabled', label: t('settings.scoreDrop', 'Overall Score Drop'), desc: t('settings.scoreDropDesc', 'Notifies you when your website health score drops.') },
                        { key: 'scan_failed_enabled', label: t('settings.scanFailed', 'Scan Failed'), desc: t('settings.scanFailedDesc', 'Alerts if we are unable to complete a scan of your site.') },
                      ].map((item) => (
                        <div key={item.key} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                          <div className="pr-4">
                            <h4 className="text-sm font-bold text-slate-900">{item.label}</h4>
                            <p className="text-xs text-slate-500 mt-1">{item.desc}</p>
                          </div>
                          <label className="relative inline-flex items-center cursor-pointer shrink-0">
                            <input
                              type="checkbox"
                              className="sr-only peer"
                              checked={!!alertPrefs[item.key as keyof AlertPreferences]}
                              onChange={(e) => handlePrefChange(item.key as keyof AlertPreferences, e.target.checked)}
                            />
                            <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div className="pt-4 border-t border-slate-100 flex justify-end">
                    <button
                      type="submit"
                      disabled={prefsSaving}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-xl font-bold text-sm transition-colors disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center min-w-[120px]"
                    >
                      {prefsSaving ? (
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      ) : (
                        t('settings.savePreferences', 'Save Preferences')
                      )}
                    </button>
                  </div>
                </form>
              ) : (
                <div className="text-center py-8 text-slate-500">
                  {t('settings.loadPrefsError', 'Could not load preferences.')}
                </div>
              )}
            </div>
          )}

          {activeTab === 'subscription' && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
              <h2 className="text-xl font-bold text-slate-900 mb-6">{t('settings.subscriptionPlan', 'Subscription Plan')}</h2>
              
              {subLoading ? (
                <div className="flex justify-center py-12">
                  <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
                </div>
              ) : subscription ? (
                <div className="space-y-6 max-w-2xl">
                  <div className="flex items-center justify-between p-6 rounded-2xl border-2 border-indigo-100 bg-indigo-50/50">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-black text-slate-900">{subscription.name}</h3>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                          subscription.status === 'active' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-800'
                        }`}>
                          {subscription.status.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600">
                        {subscription.billing_cycle === 'monthly' ? t('settings.billedMonthly', 'Billed monthly') : t('settings.billedYearly', 'Billed yearly')}
                        {subscription.current_period_end && ` • ${t('settings.renewsOn', 'Renews on')} ${new Date(subscription.current_period_end).toLocaleDateString()}`}
                      </p>
                    </div>
                    {subscription.tier === 'free' ? (
                      <Link 
                        to={`/${lang}/app/pricing`}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-bold text-sm transition-colors"
                      >
                        {t('settings.upgradePlan', 'Upgrade Plan')}
                      </Link>
                    ) : (
                      <button
                        onClick={async () => {
                          if (window.confirm('Voulez-vous vraiment annuler votre abonnement ?')) {
                            try {
                              const token = localStorage.getItem('access_token');
                              await api.post('/subscriptions/cancel/', {}, {
                                headers: token ? { Authorization: `Bearer ${token}` } : {}
                              });
                              alert('Votre demande a été prise en compte.');
                              window.location.reload();
                            } catch (e) {
                              console.error(e);
                              alert('Erreur lors de l\'annulation.');
                            }
                          }
                        }}
                        className="bg-white border border-red-200 text-red-600 hover:bg-red-50 px-5 py-2.5 rounded-xl font-bold text-sm transition-colors"
                      >
                        Gérer mon abonnement (Annuler)
                      </button>
                    )}
                  </div>

                  <div className="pt-6">
                    <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">{t('settings.planFeatures', 'Plan Features')}</h4>
                    <ul className="space-y-3">
                      <li className="flex items-center gap-3">
                        <CheckCircle className="w-5 h-5 text-emerald-500" />
                        <span className="text-slate-700 text-sm">{subscription.tier === 'free' ? 'Up to 3 websites' : 'Unlimited websites'}</span>
                      </li>
                      <li className="flex items-center gap-3">
                        <CheckCircle className="w-5 h-5 text-emerald-500" />
                        <span className="text-slate-700 text-sm">{subscription.tier === 'free' ? 'Daily automated scans' : 'Hourly automated scans'}</span>
                      </li>
                      <li className="flex items-center gap-3">
                        <CheckCircle className="w-5 h-5 text-emerald-500" />
                        <span className="text-slate-700 text-sm">{subscription.tier === 'free' ? 'Basic email alerts' : 'Advanced alerts with custom quiet hours'}</span>
                      </li>
                    </ul>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500">
                  {t('settings.loadSubError', 'Could not load subscription details.')}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Settings;

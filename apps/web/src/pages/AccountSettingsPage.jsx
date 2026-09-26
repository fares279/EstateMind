import React, { useState } from 'react';
import { Settings, Eye, EyeOff, Lock, Globe, Bell, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const CARD = 'rounded-2xl border border-white/10 bg-white/5 p-6';
const INP = 'w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2.5 text-sm text-white ' +
  'placeholder:text-gray-600 focus:outline-none focus:border-[#FF6B35]/60 focus:ring-1 focus:ring-[#FF6B35]/30';

export default function AccountSettingsPage() {
  const { user } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [settings, setSettings] = useState({
    twoFactorEnabled: false,
    emailNotifications: true,
    marketingEmails: false,
    profileVisibility: 'private',
    language: 'en',
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const handleToggle = (key) => {
    setSettings((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleChange = (key, value) => {
    setSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMsg('');
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 800));
      setMsg('Settings saved successfully.');
      setTimeout(() => setMsg(''), 3000);
    } catch (e) {
      setMsg('Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] px-4 pb-16 pt-24">
      <div className="mx-auto max-w-3xl space-y-6">
        {/* Header */}
        <section className={CARD}>
          <div className="flex items-center gap-3">
            <Settings className="w-6 h-6 text-[#FF6B35]" />
            <div>
              <h1 className="text-3xl font-black text-white">Account Settings</h1>
              <p className="text-sm text-gray-400 mt-1">Manage your account preferences and security</p>
            </div>
          </div>
          {msg && <p className="mt-3 text-sm text-green-300">{msg}</p>}
        </section>

        {/* Notifications */}
        <section className={CARD}>
          <div className="mb-4 flex items-center gap-2 text-white">
            <Bell size={18} />
            <h2 className="text-xl font-bold">Notifications</h2>
          </div>
          <div className="space-y-4">
            <label className="flex items-center justify-between p-3 rounded-lg hover:bg-white/5 cursor-pointer transition-colors">
              <div>
                <p className="text-sm font-medium text-white">Email Notifications</p>
                <p className="text-xs text-gray-500 mt-0.5">Receive updates about your account activity</p>
              </div>
              <input
                type="checkbox"
                checked={settings.emailNotifications}
                onChange={() => handleToggle('emailNotifications')}
                className="w-4 h-4 rounded accent-[#FF6B35]"
              />
            </label>
            <label className="flex items-center justify-between p-3 rounded-lg hover:bg-white/5 cursor-pointer transition-colors">
              <div>
                <p className="text-sm font-medium text-white">Marketing Emails</p>
                <p className="text-xs text-gray-500 mt-0.5">Receive news and promotions</p>
              </div>
              <input
                type="checkbox"
                checked={settings.marketingEmails}
                onChange={() => handleToggle('marketingEmails')}
                className="w-4 h-4 rounded accent-[#FF6B35]"
              />
            </label>
          </div>
        </section>

        {/* Privacy */}
        <section className={CARD}>
          <div className="mb-4 flex items-center gap-2 text-white">
            <Globe size={18} />
            <h2 className="text-xl font-bold">Privacy</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-400">Profile Visibility</label>
              <select
                value={settings.profileVisibility}
                onChange={(e) => handleChange('profileVisibility', e.target.value)}
                className={INP}
              >
                <option value="private">Private</option>
                <option value="investors-only">Investors Only</option>
                <option value="public">Public</option>
              </select>
              <p className="text-xs text-gray-500 mt-2">Choose who can see your profile information</p>
            </div>
          </div>
        </section>

        {/* Language */}
        <section className={CARD}>
          <div className="mb-4 flex items-center gap-2 text-white">
            <Globe size={18} />
            <h2 className="text-xl font-bold">Language & Region</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-400">Language</label>
              <select
                value={settings.language}
                onChange={(e) => handleChange('language', e.target.value)}
                className={INP}
              >
                <option value="en">English</option>
                <option value="fr">Français</option>
                <option value="ar">العربية</option>
              </select>
            </div>
          </div>
        </section>

        {/* Security */}
        <section className={CARD}>
          <div className="mb-4 flex items-center gap-2 text-white">
            <Shield size={18} />
            <h2 className="text-xl font-bold">Security</h2>
          </div>
          <div className="space-y-4">
            <label className="flex items-center justify-between p-3 rounded-lg hover:bg-white/5 cursor-pointer transition-colors">
              <div>
                <p className="text-sm font-medium text-white">Two-Factor Authentication</p>
                <p className="text-xs text-gray-500 mt-0.5">Add an extra layer of security to your account</p>
              </div>
              <input
                type="checkbox"
                checked={settings.twoFactorEnabled}
                onChange={() => handleToggle('twoFactorEnabled')}
                className="w-4 h-4 rounded accent-[#FF6B35]"
              />
            </label>
            <button className="w-full px-4 py-2.5 rounded-lg border border-[#FF6B35]/40 text-[#FFB38F] hover:bg-[#FF6B35]/10 font-medium text-sm transition-colors">
              <Lock size={14} className="inline mr-2" />
              Change Password
            </button>
          </div>
        </section>

        {/* Save Button */}
        <div className="flex gap-3 pt-4">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2.5 rounded-lg bg-[#FF6B35] text-white font-semibold hover:bg-[#E85C2C] disabled:opacity-60 transition-colors"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </main>
  );
}

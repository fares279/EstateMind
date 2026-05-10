import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Crown, Save, Trash2, User } from 'lucide-react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import PaymentModal from '../components/PaymentModal';

const CARD = 'rounded-2xl border border-white/10 bg-white/5 p-6';
const INP = 'w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2.5 text-sm text-white ' +
  'placeholder:text-gray-600 focus:outline-none focus:border-[#FF6B35]/60 focus:ring-1 focus:ring-[#FF6B35]/30';

const PLAN_META = {
  free: { label: 'Free', price: 'Free' },
  pro: { label: 'Pro', price: '$25.00/month' },
  investor: { label: 'Investor', price: '$50.00/month' },
};

export default function AccountDashboardPage() {
  const navigate = useNavigate();
  const { user, updateProfile, deleteAccount } = useAuth();

  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');

  const [saving, setSaving] = useState(false);
  const [upgrading, setUpgrading] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  // Payment modal state
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [clientSecret, setClientSecret] = useState(null);
  const [loadingPaymentForm, setLoadingPaymentForm] = useState(false);

  const currentPlan = (user?.plan || 'free').toLowerCase();

  useEffect(() => {
    setFullName(user?.full_name || '');
    setPhone(user?.phone || '');
  }, [user]);

  const onSaveProfile = async (e) => {
    e.preventDefault();
    setErr('');
    setMsg('');
    setSaving(true);
    try {
      await updateProfile({ full_name: fullName, phone });
      setMsg('Profile updated successfully.');
    } catch (e2) {
      setErr(e2?.response?.data?.detail || 'Could not update profile.');
    } finally {
      setSaving(false);
    }
  };

  const onUpgrade = async (plan) => {
    setErr('');
    setMsg('');
    setUpgrading(plan);
    setLoadingPaymentForm(true);

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${process.env.REACT_APP_API_URL}/billing/create-checkout-session/`,
        { plan },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      // Set payment modal data
      setSelectedPlan(plan);
      setClientSecret(response.data.client_secret);
      setShowPaymentModal(true);
      setMsg(`Payment form ready. Complete your payment to upgrade to ${PLAN_META[plan].label}.`);
    } catch (e2) {
      setErr(e2?.response?.data?.error || e2?.message || 'Failed to load payment form.');
      console.error('Upgrade error:', e2);
    } finally {
      setUpgrading('');
      setLoadingPaymentForm(false);
    }
  };

  const handlePaymentSuccess = () => {
    setShowPaymentModal(false);
    setClientSecret(null);
    setSelectedPlan(null);
    setMsg(`Successfully upgraded to ${PLAN_META[selectedPlan]?.label || 'new'} plan!`);
    window.location.reload();
  };

  const handlePaymentModalClose = () => {
    setShowPaymentModal(false);
    setClientSecret(null);
    setSelectedPlan(null);
  };

  const onDeleteAccount = async () => {
    setErr('');
    setMsg('');

    if (!password) {
      setErr('Please enter your password to delete your account.');
      return;
    }

    const ok = window.confirm('This will permanently delete your account. Continue?');
    if (!ok) return;

    setDeleting(true);
    try {
      await deleteAccount(password);
      navigate('/register', { replace: true });
    } catch (e2) {
      setErr(e2?.response?.data?.password || 'Could not delete account.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] px-4 pb-16 pt-24">
      <div className="mx-auto max-w-4xl space-y-6">
        <section className={CARD}>
          <p className="text-sm uppercase tracking-wider text-[#FFB38F]">Account Dashboard</p>
          <h1 className="mt-1 text-3xl font-black text-white">My Account</h1>
          <p className="mt-2 text-gray-400">
            Signed in as <span className="font-semibold text-white">{user?.email || '—'}</span>
          </p>
          <p className="mt-1 text-gray-400">
            Current plan: <span className="font-semibold text-white">{PLAN_META[currentPlan]?.label || currentPlan}</span>
          </p>
          {msg ? <p className="mt-3 text-sm text-green-300">{msg}</p> : null}
          {err ? <p className="mt-3 text-sm text-red-300">{err}</p> : null}
        </section>

        <section className={CARD}>
          <div className="mb-4 flex items-center gap-2 text-white">
            <User size={18} />
            <h2 className="text-xl font-bold">Edit Profile</h2>
          </div>
          <form onSubmit={onSaveProfile} className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-400">Full Name</label>
              <input className={INP} value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-400">Phone</label>
              <input className={INP} value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-xl bg-[#FF6B35] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#E85C2C] disabled:opacity-60"
              >
                <Save size={14} />
                {saving ? 'Saving...' : 'Save Profile'}
              </button>
            </div>
          </form>
        </section>

        <section className={CARD}>
          <div className="mb-4 flex items-center gap-2 text-white">
            <Crown size={18} />
            <h2 className="text-xl font-bold">Upgrade Plan</h2>
          </div>
          <p className="mb-4 text-sm text-gray-400">
            Upgrades use Stripe checkout. In local debug mode, a dev fallback can complete upgrade instantly.
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            {['free', 'pro', 'investor'].map((plan) => {
              const isCurrent = currentPlan === plan;
              return (
                <article key={plan} className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <p className="text-lg font-bold text-white">{PLAN_META[plan].label}</p>
                  <p className="mt-1 text-sm text-gray-400">{PLAN_META[plan].price}</p>
                  <button
                    type="button"
                    disabled={isCurrent || upgrading === plan || plan === 'free'}
                    onClick={() => onUpgrade(plan)}
                    className="mt-3 w-full rounded-lg border border-[#FF6B35]/40 px-3 py-2 text-sm font-semibold text-[#FFB38F] hover:bg-[#FF6B35]/10 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isCurrent ? 'Current Plan' : upgrading === plan ? 'Starting...' : `Upgrade to ${PLAN_META[plan].label}`}
                  </button>
                </article>
              );
            })}
          </div>
        </section>

        <section className="rounded-2xl border border-red-500/25 bg-red-500/5 p-6">
          <div className="mb-3 flex items-center gap-2 text-red-300">
            <Trash2 size={18} />
            <h2 className="text-xl font-bold">Delete Account</h2>
          </div>
          <p className="mb-3 text-sm text-gray-300">
            This permanently removes your account and cannot be undone.
          </p>
          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <input
              type="password"
              className={INP}
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              onClick={onDeleteAccount}
              disabled={deleting}
              className="rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-60"
            >
              {deleting ? 'Deleting...' : 'Delete My Account'}
            </button>
          </div>
        </section>
      </div>

      <PaymentModal
        isOpen={showPaymentModal}
        onClose={handlePaymentModalClose}
        clientSecret={clientSecret}
        plan={selectedPlan}
        onSuccess={handlePaymentSuccess}
        userEmail={user?.email}
              userFullName={user?.full_name || ''}
              userPhone={user?.phone || ''}
      />
    </main>
  );
}

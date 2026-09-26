import React, { useState } from 'react';
import { Key, Copy, Trash2, Plus, Eye, EyeOff, BookOpen, Code2, Lock, Globe } from 'lucide-react';

const CARD = 'rounded-2xl border border-white/10 bg-white/5 p-6';
const INP = 'w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2.5 text-sm text-white ' +
  'placeholder:text-gray-600 focus:outline-none focus:border-[#FF6B35]/60 focus:ring-1 focus:ring-[#FF6B35]/30';

const generatePublicKey = (env) => `estatemind_pk_${env === 'production' ? 'live' : 'test'}_${Math.random().toString(36).substr(2, 24)}`;
const generateSecretKey = (env) => `estatemind_sk_${env === 'production' ? 'live' : 'test'}_${Math.random().toString(36).substr(2, 40)}`;

const KEY_SCOPES = [
  { id: 'properties_read', label: 'Read Properties', description: 'Access property listings and details' },
  { id: 'valuations_read', label: 'Read Valuations', description: 'Access property valuations and estimates' },
  { id: 'analysis_read', label: 'Read Analysis', description: 'Access market analysis and trends' },
  { id: 'climate_read', label: 'Read Climate Data', description: 'Access climate risk assessments' },
  { id: 'simulator_read', label: 'Read Simulations', description: 'Access investment simulations' },
];

export default function AccountApiKeysPage() {
  const [apiKeys, setApiKeys] = useState([
    {
      id: 1,
      name: 'Web App Integration',
      type: 'pair',
      publicKey: 'estatemind_pk_live_sample_public_key',
      secretKey: 'estatemind_sk_live_sample_secret_key',
      environment: 'production',
      scopes: ['properties_read', 'valuations_read', 'analysis_read'],
      created: '2026-01-15',
      lastUsed: '2026-05-09',
      visibleSecret: false,
    },
    {
      id: 2,
      name: 'Mobile App Development',
      type: 'pair',
      publicKey: 'estatemind_pk_test_sample_public_key',
      secretKey: 'estatemind_sk_test_sample_secret_key',
      environment: 'development',
      scopes: ['properties_read', 'valuations_read', 'analysis_read', 'climate_read'],
      created: '2026-02-20',
      lastUsed: '2026-05-08',
      visibleSecret: false,
    },
  ]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newKeyConfig, setNewKeyConfig] = useState({
    name: '',
    environment: 'development',
    scopes: [],
  });
  const [copied, setCopied] = useState(null);
  const [msg, setMsg] = useState('');

  const handleCopy = (key, id) => {
    navigator.clipboard.writeText(key);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleToggleVisibility = (id) => {
    setApiKeys((prev) => prev.map((k) => (k.id === id ? { ...k, visibleSecret: !k.visibleSecret } : k)));
  };

  const handleToggleScope = (scope) => {
    setNewKeyConfig((prev) => ({
      ...prev,
      scopes: prev.scopes.includes(scope)
        ? prev.scopes.filter((s) => s !== scope)
        : [...prev.scopes, scope],
    }));
  };

  const handleCreateKey = () => {
    if (!newKeyConfig.name.trim()) {
      setMsg('Please enter a key name');
      return;
    }

    if (newKeyConfig.scopes.length === 0) {
      setMsg('Please select at least one scope');
      return;
    }

    const newKey = {
      id: apiKeys.length + 1,
      name: newKeyConfig.name,
      type: 'pair',
      publicKey: generatePublicKey(newKeyConfig.environment),
      secretKey: generateSecretKey(newKeyConfig.environment),
      environment: newKeyConfig.environment,
      scopes: newKeyConfig.scopes,
      created: new Date().toISOString().split('T')[0],
      lastUsed: null,
      visibleSecret: false,
    };

    setApiKeys((prev) => [newKey, ...prev]);
    setNewKeyConfig({ name: '', environment: 'development', scopes: [] });
    setShowCreateForm(false);
    setMsg('API key pair created successfully');
    setTimeout(() => setMsg(''), 3000);
  };

  const handleDeleteKey = (id) => {
    const ok = window.confirm('This action cannot be undone. The API key will be permanently deleted.');
    if (ok) {
      setApiKeys((prev) => prev.filter((k) => k.id !== id));
      setMsg('API key deleted');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const getScopeLabel = (scopeId) => {
    const scope = KEY_SCOPES.find((s) => s.id === scopeId);
    return scope ? scope.label : scopeId;
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] px-4 pb-16 pt-24">
      <div className="mx-auto max-w-5xl space-y-6">
        <section className={CARD}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Key className="w-6 h-6 text-[#FF6B35]" />
              <div>
                <h1 className="text-3xl font-black text-white">API Keys</h1>
                <p className="mt-1 text-sm text-gray-400">Manage credentials to integrate EstateMind with your platform</p>
              </div>
            </div>
            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="flex items-center gap-2 rounded-lg bg-[#FF6B35] px-4 py-2.5 font-semibold text-white transition-colors hover:bg-[#E85C2C]"
            >
              <Plus size={16} />
              New Key
            </button>
          </div>
          {msg && <p className="mt-3 text-sm text-green-300">{msg}</p>}
        </section>

        {showCreateForm && (
          <section className={CARD}>
            <h3 className="mb-4 text-lg font-semibold text-white">Create New API Key Pair</h3>
            <div className="space-y-5">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-300">Key Name *</label>
                <input
                  type="text"
                  value={newKeyConfig.name}
                  onChange={(e) => setNewKeyConfig({ ...newKeyConfig, name: e.target.value })}
                  placeholder="e.g., Production Web Integration"
                  className={INP}
                />
                <p className="mt-1 text-xs text-gray-500">A descriptive name to help you identify this key</p>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-gray-300">Environment *</label>
                <div className="grid gap-3 md:grid-cols-2">
                  {['development', 'production'].map((env) => (
                    <button
                      key={env}
                      onClick={() => setNewKeyConfig({ ...newKeyConfig, environment: env })}
                      className={`rounded-lg border p-3 text-left transition-colors ${
                        newKeyConfig.environment === env
                          ? 'border-[#FF6B35] bg-[#FF6B35]/20 text-white'
                          : 'border-white/15 text-gray-400 hover:border-white/30'
                      }`}
                    >
                      <p className="font-semibold capitalize">{env}</p>
                      <p className="mt-1 text-xs">{env === 'development' ? 'For testing and development' : 'For live production'}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="mb-3 block text-sm font-medium text-gray-300">Permissions (Scopes) *</label>
                <div className="space-y-2">
                  {KEY_SCOPES.map((scope) => (
                    <label key={scope.id} className="flex cursor-pointer items-start gap-3 rounded-lg p-3 transition-colors hover:bg-white/5">
                      <input
                        type="checkbox"
                        checked={newKeyConfig.scopes.includes(scope.id)}
                        onChange={() => handleToggleScope(scope.id)}
                        className="mt-1 h-4 w-4 rounded accent-[#FF6B35]"
                      />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-white">{scope.label}</p>
                        <p className="mt-0.5 text-xs text-gray-500">{scope.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-3">
                <button
                  onClick={handleCreateKey}
                  className="rounded-lg bg-[#FF6B35] px-6 py-2.5 font-semibold text-white transition-colors hover:bg-[#E85C2C]"
                >
                  Create Key Pair
                </button>
                <button
                  onClick={() => setShowCreateForm(false)}
                  className="rounded-lg border border-white/15 px-6 py-2.5 font-semibold text-white transition-colors hover:bg-white/5"
                >
                  Cancel
                </button>
              </div>
            </div>
          </section>
        )}

        <div className="space-y-4">
          {apiKeys.length === 0 ? (
            <section className={CARD}>
              <p className="text-center text-gray-400">No API keys yet. Create one to get started.</p>
            </section>
          ) : (
            apiKeys.map((apiKey) => (
              <section key={apiKey.id} className={CARD}>
                <div className="mb-4 flex items-start justify-between">
                  <div className="flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <h3 className="text-lg font-semibold text-white">{apiKey.name}</h3>
                      <span className={`rounded px-2 py-1 text-xs font-medium ${
                        apiKey.environment === 'production'
                          ? 'bg-red-500/20 text-red-300'
                          : 'bg-blue-500/20 text-blue-300'
                      }`}>
                        {apiKey.environment.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">Created: {apiKey.created} {apiKey.lastUsed && `• Last used: ${apiKey.lastUsed}`}</p>
                  </div>
                  <button
                    onClick={() => handleDeleteKey(apiKey.id)}
                    className="rounded-lg p-2 transition-colors hover:bg-red-500/20"
                    title="Delete"
                  >
                    <Trash2 size={16} className="text-red-400" />
                  </button>
                </div>

                <div className="mb-4 border-b border-white/10 pb-4">
                  <p className="mb-2 text-xs font-medium text-gray-400">PERMISSIONS</p>
                  <div className="flex flex-wrap gap-2">
                    {apiKey.scopes.map((scope) => (
                      <span key={scope} className="rounded-lg bg-white/10 px-2.5 py-1 text-xs font-medium text-gray-300">
                        {getScopeLabel(scope)}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-xs font-medium text-gray-400">PUBLIC KEY</p>
                      <button
                        onClick={() => handleCopy(apiKey.publicKey, `pub_${apiKey.id}`)}
                        className="rounded p-1 transition-colors hover:bg-white/10"
                      >
                        <Copy size={14} className={copied === `pub_${apiKey.id}` ? 'text-green-400' : 'text-gray-400'} />
                      </button>
                    </div>
                    <div className="break-all rounded-lg border border-white/5 bg-black/40 p-3 font-mono text-xs text-gray-300">
                      {apiKey.publicKey}
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-xs font-medium text-gray-400">SECRET KEY</p>
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleToggleVisibility(apiKey.id)}
                          className="rounded p-1 transition-colors hover:bg-white/10"
                        >
                          {apiKey.visibleSecret ? (
                            <EyeOff size={14} className="text-gray-400" />
                          ) : (
                            <Eye size={14} className="text-gray-400" />
                          )}
                        </button>
                        <button
                          onClick={() => handleCopy(apiKey.secretKey, `sec_${apiKey.id}`)}
                          className="rounded p-1 transition-colors hover:bg-white/10"
                        >
                          <Copy size={14} className={copied === `sec_${apiKey.id}` ? 'text-green-400' : 'text-gray-400'} />
                        </button>
                      </div>
                    </div>
                    <div className="break-all rounded-lg border border-red-500/20 bg-black/40 p-3 font-mono text-xs text-gray-300">
                      {apiKey.visibleSecret ? apiKey.secretKey : '••••••••••••••••••••••••••••••••••••••••••••••••••••'}
                    </div>
                    <p className="mt-2 text-xs text-red-400">⚠️ Keep your secret key confidential. Never expose it in client-side code.</p>
                  </div>
                </div>
              </section>
            ))
          )}
        </div>

        <section className={CARD}>
          <div className="mb-4 flex items-center gap-2">
            <BookOpen size={18} className="text-[#FF6B35]" />
            <h2 className="text-xl font-semibold text-white">Integration Guide</h2>
          </div>

          <div className="space-y-4">
            <div>
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <Code2 size={14} className="text-[#FF6B35]" />
                Authentication
              </h4>
              <div className="rounded-lg border border-white/5 bg-black/40 p-3">
                <p className="mb-2 font-mono text-xs text-gray-300">// Include Public Key in API requests</p>
                <p className="font-mono text-xs text-gray-300">curl -H &quot;Authorization: Bearer estatemind_pk_...&quot; https://api.estatemind.com/v1/properties</p>
              </div>
            </div>

            <div>
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
                <Globe size={14} className="text-[#FF6B35]" />
                API Endpoints
              </h4>
              <div className="space-y-2 text-xs">
                <p className="text-gray-300"><span className="font-mono text-[#FF6B35]">GET</span> /v1/properties - List properties</p>
                <p className="text-gray-300"><span className="font-mono text-[#FF6B35]">GET</span> /v1/valuations - Get property valuations</p>
                <p className="text-gray-300"><span className="font-mono text-[#FF6B35]">GET</span> /v1/analysis - Get market analysis</p>
                <p className="text-gray-300"><span className="font-mono text-[#FF6B35]">GET</span> /v1/climate - Get climate risk data</p>
              </div>
            </div>

            <div>
              <a href="#" className="inline-flex items-center gap-2 text-sm font-medium text-[#FF6B35] hover:text-[#FFB38F]">
                View Full API Documentation →
              </a>
            </div>
          </div>
        </section>

        <section className={CARD}>
          <div className="mb-4 flex items-center gap-2">
            <Lock size={18} className="text-[#FF6B35]" />
            <h2 className="text-xl font-semibold text-white">Best Practices</h2>
          </div>

          <ul className="space-y-2 text-sm text-gray-300">
            <li>✓ Never commit API keys to version control</li>
            <li>✓ Use environment variables to store keys securely</li>
            <li>✓ Rotate keys regularly for security</li>
            <li>✓ Use the least permissive scopes needed</li>
            <li>✓ Monitor key usage in your dashboard</li>
            <li>✓ Delete unused keys immediately</li>
          </ul>
        </section>
      </div>
    </main>
  );
}
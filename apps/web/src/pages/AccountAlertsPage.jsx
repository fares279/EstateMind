import React, { useState } from 'react';
import { Bell, Plus, Trash2, Edit2, MapPin, DollarSign, Home } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const CARD = 'rounded-2xl border border-white/10 bg-white/5 p-6';
const INP = 'w-full rounded-xl border border-white/15 bg-black/30 px-3 py-2.5 text-sm text-white ' +
  'placeholder:text-gray-600 focus:outline-none focus:border-[#FF6B35]/60 focus:ring-1 focus:ring-[#FF6B35]/30';

export default function AccountAlertsPage() {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState([
    {
      id: 1,
      name: 'Downtown Apartments',
      type: 'price-drop',
      location: 'Tunis, Tunisia',
      minPrice: null,
      maxPrice: 200000,
      propertyType: 'Apartment',
      active: true,
      created: '2026-04-10',
    },
    {
      id: 2,
      name: 'Investment Properties',
      type: 'new-listing',
      location: 'Sousse, Tunisia',
      minPrice: 150000,
      maxPrice: null,
      propertyType: 'Any',
      active: true,
      created: '2026-03-25',
    },
  ]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    type: 'price-drop',
    location: '',
    minPrice: '',
    maxPrice: '',
    propertyType: 'Any',
  });
  const [msg, setMsg] = useState('');

  const handleCreateOrUpdate = () => {
    if (!formData.name.trim() || !formData.location.trim()) {
      setMsg('Please fill in all required fields');
      return;
    }

    if (editingId) {
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === editingId
            ? {
                ...a,
                name: formData.name,
                type: formData.type,
                location: formData.location,
                minPrice: formData.minPrice ? parseInt(formData.minPrice) : null,
                maxPrice: formData.maxPrice ? parseInt(formData.maxPrice) : null,
                propertyType: formData.propertyType,
              }
            : a
        )
      );
      setMsg('Alert updated successfully');
    } else {
      const newAlert = {
        id: alerts.length + 1,
        name: formData.name,
        type: formData.type,
        location: formData.location,
        minPrice: formData.minPrice ? parseInt(formData.minPrice) : null,
        maxPrice: formData.maxPrice ? parseInt(formData.maxPrice) : null,
        propertyType: formData.propertyType,
        active: true,
        created: new Date().toISOString().split('T')[0],
      };
      setAlerts((prev) => [newAlert, ...prev]);
      setMsg('Alert created successfully');
    }

    setFormData({
      name: '',
      type: 'price-drop',
      location: '',
      minPrice: '',
      maxPrice: '',
      propertyType: 'Any',
    });
    setShowCreateForm(false);
    setEditingId(null);
    setTimeout(() => setMsg(''), 3000);
  };

  const handleEdit = (alert) => {
    setFormData({
      name: alert.name,
      type: alert.type,
      location: alert.location,
      minPrice: alert.minPrice ? alert.minPrice.toString() : '',
      maxPrice: alert.maxPrice ? alert.maxPrice.toString() : '',
      propertyType: alert.propertyType,
    });
    setEditingId(alert.id);
    setShowCreateForm(true);
  };

  const handleDelete = (id) => {
    const ok = window.confirm('Are you sure you want to delete this alert?');
    if (ok) {
      setAlerts((prev) => prev.filter((a) => a.id !== id));
      setMsg('Alert deleted');
      setTimeout(() => setMsg(''), 3000);
    }
  };

  const handleToggleActive = (id) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, active: !a.active } : a))
    );
  };

  const handleCancel = () => {
    setShowCreateForm(false);
    setEditingId(null);
    setFormData({
      name: '',
      type: 'price-drop',
      location: '',
      minPrice: '',
      maxPrice: '',
      propertyType: 'Any',
    });
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0B0F19] via-[#1A2332] to-[#0B0F19] px-4 pb-16 pt-24">
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Header */}
        <section className={CARD}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Bell className="w-6 h-6 text-[#FF6B35]" />
              <div>
                <h1 className="text-3xl font-black text-white">Property Alerts</h1>
                <p className="text-sm text-gray-400 mt-1">Get notified when properties matching your criteria are listed</p>
              </div>
            </div>
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-4 py-2.5 rounded-lg bg-[#FF6B35] text-white font-semibold hover:bg-[#E85C2C] flex items-center gap-2 transition-colors"
            >
              <Plus size={16} />
              New Alert
            </button>
          </div>
          {msg && <p className="mt-3 text-sm text-green-300">{msg}</p>}
        </section>

        {/* Create/Edit Form */}
        {showCreateForm && (
          <section className={CARD}>
            <h3 className="mb-4 text-lg font-semibold text-white">
              {editingId ? 'Edit Alert' : 'Create New Alert'}
            </h3>
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Alert Name *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Downtown Luxury Apartments"
                    className={INP}
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Alert Type *</label>
                  <select
                    value={formData.type}
                    onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                    className={INP}
                  >
                    <option value="price-drop">Price Drop</option>
                    <option value="new-listing">New Listings</option>
                    <option value="price-increase">Price Increase</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-gray-300">Location *</label>
                <input
                  type="text"
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                  placeholder="e.g., Tunis, Tunisia"
                  className={INP}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Min Price (TND)</label>
                  <input
                    type="number"
                    value={formData.minPrice}
                    onChange={(e) => setFormData({ ...formData, minPrice: e.target.value })}
                    placeholder="Optional"
                    className={INP}
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Max Price (TND)</label>
                  <input
                    type="number"
                    value={formData.maxPrice}
                    onChange={(e) => setFormData({ ...formData, maxPrice: e.target.value })}
                    placeholder="Optional"
                    className={INP}
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Property Type</label>
                  <select
                    value={formData.propertyType}
                    onChange={(e) => setFormData({ ...formData, propertyType: e.target.value })}
                    className={INP}
                  >
                    <option value="Any">Any</option>
                    <option value="Apartment">Apartment</option>
                    <option value="House">House</option>
                    <option value="Land">Land</option>
                    <option value="Commercial">Commercial</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleCreateOrUpdate}
                  className="px-6 py-2.5 rounded-lg bg-[#FF6B35] text-white font-semibold hover:bg-[#E85C2C] transition-colors"
                >
                  {editingId ? 'Update Alert' : 'Create Alert'}
                </button>
                <button
                  onClick={handleCancel}
                  className="px-6 py-2.5 rounded-lg border border-white/15 text-white font-semibold hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </section>
        )}

        {/* Alerts List */}
        <div className="space-y-3">
          {alerts.length === 0 ? (
            <section className={CARD}>
              <p className="text-center text-gray-400">No alerts yet. Create one to get started.</p>
            </section>
          ) : (
            alerts.map((alert) => (
              <section key={alert.id} className={CARD}>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-lg font-semibold text-white">{alert.name}</h3>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={alert.active}
                          onChange={() => handleToggleActive(alert.id)}
                          className="w-4 h-4 rounded accent-[#FF6B35]"
                        />
                        <span className="text-xs text-gray-400">{alert.active ? 'Active' : 'Inactive'}</span>
                      </label>
                    </div>

                    <div className="grid gap-2 md:grid-cols-2 mt-3">
                      <div className="flex items-center gap-2 text-sm text-gray-400">
                        <MapPin size={14} className="text-[#FF6B35]" />
                        {alert.location}
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-400">
                        <Home size={14} className="text-[#FF6B35]" />
                        {alert.propertyType}
                      </div>
                    </div>

                    {(alert.minPrice || alert.maxPrice) && (
                      <div className="flex items-center gap-2 text-sm text-gray-400 mt-2">
                        <DollarSign size={14} className="text-[#FF6B35]" />
                        {alert.minPrice && `TND ${alert.minPrice.toLocaleString()}`}
                        {alert.minPrice && alert.maxPrice && ' - '}
                        {alert.maxPrice && `TND ${alert.maxPrice.toLocaleString()}`}
                      </div>
                    )}

                    <p className="text-xs text-gray-500 mt-2">
                      Created: {alert.created} • Type: {alert.type.replace('-', ' ')}
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEdit(alert)}
                      className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <Edit2 size={16} className="text-gray-400" />
                    </button>
                    <button
                      onClick={() => handleDelete(alert.id)}
                      className="p-2 hover:bg-red-500/20 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={16} className="text-red-400" />
                    </button>
                  </div>
                </div>
              </section>
            ))
          )}
        </div>
      </div>
    </main>
  );
}

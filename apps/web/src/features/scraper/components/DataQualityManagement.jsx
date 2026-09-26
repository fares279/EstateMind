/**
 * Data Quality Management Page
 * 
 * Shows validation failures, quality violations, and decision history
 * Allows reviewing and fixing bad records at the Silver/Gold boundary
 */

import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  RotateCw,
  Filter,
  Download,
  Eye,
  Trash2,
  Clock,
} from 'lucide-react';
import api from '../../../services/api';

const DataQualityManagement = () => {
  const [violations, setViolations] = useState([]);
  const [filters, setFilters] = useState({
    status: 'all', // all, pending, approved, rejected, fixed
    severity: 'all', // all, critical, warning, info
    source: 'all',
  });
  const [selectedViolation, setSelectedViolation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchViolations();
  }, [filters]);

  const fetchViolations = async () => {
    try {
      setLoading(true);
      const params = {
        status: filters.status !== 'all' ? filters.status : undefined,
        severity: filters.severity !== 'all' ? filters.severity : undefined,
        source: filters.source !== 'all' ? filters.source : undefined,
      };
      const res = await api.get('/scraper/data-quality/violations/', { params });
      setViolations(res.data.violations || []);
      setStats(res.data.stats);
    } catch (error) {
      console.error('Error fetching violations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (violationId, correctedData) => {
    try {
      await api.post(`/scraper/data-quality/violations/${violationId}/approve/`, {
        corrected_data: correctedData,
        field_name: selectedViolation?.field_name,
      });
      setViolations(violations.filter(v => v.id !== violationId));
      setSelectedViolation(null);
    } catch (error) {
      console.error('Error approving violation:', error);
    }
  };

  const handleReject = async (violationId) => {
    try {
      await api.post(`/scraper/data-quality/violations/${violationId}/reject/`, {
        field_name: selectedViolation?.field_name,
      });
      setViolations(violations.filter(v => v.id !== violationId));
      setSelectedViolation(null);
    } catch (error) {
      console.error('Error rejecting violation:', error);
    }
  };

  const handleExport = async () => {
    try {
      const res = await api.get('/scraper/data-quality/violations/export/', {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `quality-violations-${new Date().toISOString()}.csv`;
      a.click();
    } catch (error) {
      console.error('Error exporting violations:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Data Quality Management</h1>
        <button
          onClick={handleExport}
          className="flex items-center px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
        >
          <Download className="w-4 h-4 mr-2" />
          Export Report
        </button>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <StatCard
            title="Total Violations"
            value={stats.total_violations}
            icon={<AlertTriangle className="w-6 h-6 text-red-500" />}
          />
          <StatCard
            title="Pending Review"
            value={stats.pending_violations}
            icon={<Clock className="w-6 h-6 text-yellow-500" />}
          />
          <StatCard
            title="Approved Fixes"
            value={stats.approved_violations}
            icon={<CheckCircle className="w-6 h-6 text-green-500" />}
          />
          <StatCard
            title="Rejected Records"
            value={stats.rejected_violations}
            icon={<Trash2 className="w-6 h-6 text-gray-500" />}
          />
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 flex items-center gap-4">
        <Filter className="w-5 h-5 text-gray-600" />
        <FilterSelect
          label="Status"
          options={['all', 'pending', 'approved', 'rejected', 'fixed']}
          value={filters.status}
          onChange={(val) => setFilters({ ...filters, status: val })}
        />
        <FilterSelect
          label="Severity"
          options={['all', 'critical', 'warning', 'info']}
          value={filters.severity}
          onChange={(val) => setFilters({ ...filters, severity: val })}
        />
        <FilterSelect
          label="Source"
          options={['all', 'tayara', 'mubawab', 'tecnocasa', 'tunisie_annonce', 'bigdatis']}
          value={filters.source}
          onChange={(val) => setFilters({ ...filters, source: val })}
        />
      </div>

      {/* Violations List */}
      <div className="grid grid-cols-3 gap-6">
        {/* Violations Table */}
        <div className="col-span-2 bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-100 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">
                    Record ID
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">
                    Violation Type
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">
                    Severity
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">
                    Field
                  </th>
                  <th className="px-6 py-3 text-center text-sm font-semibold text-gray-700">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {violations.map((violation) => (
                  <ViolationRow
                    key={violation.id}
                    violation={violation}
                    isSelected={selectedViolation?.id === violation.id}
                    onSelect={() => setSelectedViolation(violation)}
                  />
                ))}
              </tbody>
            </table>
          </div>
          {violations.length === 0 && (
            <div className="p-8 text-center text-gray-500">
              <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-500" />
              <p>No violations found. Your data is clean!</p>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {selectedViolation && (
          <ViolationDetailPanel
            violation={selectedViolation}
            onApprove={handleApprove}
            onReject={handleReject}
            onClose={() => setSelectedViolation(null)}
          />
        )}
      </div>
    </div>
  );
};

// ============================================================================
// Subcomponents
// ============================================================================

const StatCard = ({ title, value, icon }) => (
  <div className="bg-white rounded-lg shadow p-6 flex items-center">
    <div className="flex-1">
      <p className="text-gray-600 text-sm mb-1">{title}</p>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
    </div>
    <div className="ml-4 opacity-70">{icon}</div>
  </div>
);

const FilterSelect = ({ label, options, value, onChange }) => (
  <div>
    <label className="text-sm text-gray-600 mr-2">{label}:</label>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt.charAt(0).toUpperCase() + opt.slice(1)}
        </option>
      ))}
    </select>
  </div>
);

const ViolationRow = ({ violation, isSelected, onSelect }) => {
  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-800';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800';
      case 'info':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <tr
      className={`cursor-pointer hover:bg-gray-50 ${isSelected ? 'bg-blue-50' : ''}`}
      onClick={onSelect}
    >
      <td className="px-6 py-4 text-sm text-gray-900 font-mono">{violation.record_id}</td>
      <td className="px-6 py-4 text-sm text-gray-600">{violation.violation_type}</td>
      <td className="px-6 py-4 text-sm">
        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getSeverityColor(violation.severity)}`}>
          {violation.severity}
        </span>
      </td>
      <td className="px-6 py-4 text-sm text-gray-600">{violation.field_name}</td>
      <td className="px-6 py-4 text-center">
        <Eye className="w-4 h-4 text-blue-500 inline" />
      </td>
    </tr>
  );
};

const ViolationDetailPanel = ({ violation, onApprove, onReject, onClose }) => {
  const [correctedData, setCorrectedData] = useState(violation.original_value || '');
  const [action, setAction] = useState('view'); // view, edit

  const handleSaveCorrection = () => {
    onApprove(violation.id, correctedData);
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500 flex flex-col">
      <button
        onClick={onClose}
        className="self-end text-gray-400 hover:text-gray-600 mb-4"
      >
        ✕
      </button>

      <h3 className="text-lg font-semibold text-gray-900 mb-4">Violation Details</h3>

      {/* Record Info */}
      <div className="bg-gray-50 p-3 rounded mb-4 text-sm">
        <p><strong>Record ID:</strong> {violation.record_id}</p>
        <p><strong>Source:</strong> {violation.source}</p>
        <p><strong>Field:</strong> {violation.field_name}</p>
        <p><strong>Type:</strong> {violation.violation_type}</p>
      </div>

      {/* Violation Details */}
      <div className="bg-yellow-50 p-3 rounded mb-4 text-sm border border-yellow-200">
        <p className="font-semibold text-yellow-900 mb-2">Issue:</p>
        <p className="text-yellow-800">{violation.message}</p>
        <p className="text-xs text-yellow-700 mt-2">
          Expected: {violation.constraint}
        </p>
      </div>

      {/* Original vs Current */}
      <div className="space-y-3 mb-4 text-sm">
        <div>
          <label className="block font-semibold text-gray-700 mb-1">Original Value:</label>
          <input
            type="text"
            value={violation.original_value || ''}
            disabled
            className="w-full px-3 py-2 bg-gray-100 border border-gray-300 rounded text-gray-600"
          />
        </div>
        <div>
          <label className="block font-semibold text-gray-700 mb-1">Corrected Value:</label>
          <input
            type="text"
            value={correctedData}
            onChange={(e) => setCorrectedData(e.target.value)}
            disabled={action === 'view'}
            className={`w-full px-3 py-2 border border-gray-300 rounded ${
              action === 'view' ? 'bg-gray-100 text-gray-600' : 'bg-white text-gray-900'
            }`}
          />
        </div>
      </div>

      {/* Suggestions */}
      {violation.suggestions?.length > 0 && (
        <div className="bg-blue-50 p-3 rounded mb-4 text-sm border border-blue-200">
          <p className="font-semibold text-blue-900 mb-2">Suggestions:</p>
          <div className="space-y-1">
            {violation.suggestions.map((sug, idx) => (
              <button
                key={idx}
                onClick={() => setCorrectedData(sug)}
                className="block w-full text-left text-blue-700 hover:text-blue-900 hover:underline"
              >
                → {sug}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-auto pt-4 border-t">
        {action === 'view' ? (
          <>
            <button
              onClick={() => setAction('edit')}
              className="flex-1 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Fix & Approve
            </button>
            <button
              onClick={() => onReject(violation.id)}
              className="flex-1 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
            >
              Reject Record
            </button>
          </>
        ) : (
          <>
            <button
              onClick={handleSaveCorrection}
              className="flex-1 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
            >
              Save & Approve
            </button>
            <button
              onClick={() => {
                setAction('view');
                setCorrectedData(violation.original_value || '');
              }}
              className="flex-1 px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
            >
              Cancel
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default DataQualityManagement;

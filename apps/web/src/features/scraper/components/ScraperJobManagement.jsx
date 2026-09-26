/**
 * Scraper Job Management Page
 * 
 * View job history, trigger new scrape jobs, monitor progress in real-time
 */

import React, { useEffect, useState } from 'react';
import {
  Play,
  Pause,
  RotateCw,
  Download,
  Calendar,
  Clock,
  CheckCircle,
  AlertCircle,
  Zap,
  BarChart3,
  Database,
} from 'lucide-react';
import api from '../../../services/api';

const ScraperJobManagement = () => {
  const [jobs, setJobs] = useState([]);
  const [sources, setSources] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [selectedSource, setSelectedSource] = useState('all');

  useEffect(() => {
    fetchJobs();
    fetchSources();
    // Refresh every 10 seconds if there are running jobs
    const interval = setInterval(fetchJobs, 10000);
    return () => clearInterval(interval);
  }, [selectedSource]);

  const fetchJobs = async () => {
    try {
      const params = selectedSource !== 'all' ? { source: selectedSource } : {};
      const res = await api.get('/scraper/jobs/', { params });
      setJobs(res.data || []);
    } catch (error) {
      console.error('Error fetching jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSources = async () => {
    try {
      const res = await api.get('/scraper/sources/');
      setSources(res.data || []);
    } catch (error) {
      console.error('Error fetching sources:', error);
    }
  };

  const handleTriggerJob = async (sourceId) => {
    try {
      setTriggering(true);
      await api.post('/scraper/jobs/trigger/', { source_id: sourceId });
      fetchJobs();
    } catch (error) {
      console.error('Error triggering job:', error);
    } finally {
      setTriggering(false);
    }
  };

  const handleTriggerAllSources = async () => {
    try {
      setTriggering(true);
      await api.post('/scraper/jobs/trigger-all/');
      fetchJobs();
    } catch (error) {
      console.error('Error triggering all jobs:', error);
    } finally {
      setTriggering(false);
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
        <h1 className="text-3xl font-bold text-gray-900">Scraper Job Management</h1>
        <button
          onClick={handleTriggerAllSources}
          disabled={triggering}
          className="flex items-center px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
        >
          <Zap className="w-4 h-4 mr-2" />
          Trigger All Sources
        </button>
      </div>

      {/* Source Filter */}
      <div className="bg-white rounded-lg shadow p-4">
        <label className="text-sm font-semibold text-gray-700 mr-4">Filter by Source:</label>
        <select
          value={selectedSource}
          onChange={(e) => {
            setSelectedSource(e.target.value);
            setSelectedJob(null);
          }}
          className="px-4 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Sources</option>
          {sources.map((source) => (
            <option key={source.id} value={source.id}>
              {source.name}
            </option>
          ))}
        </select>
      </div>

      {/* Jobs Grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Jobs List */}
        <div className="col-span-2 space-y-4">
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              isSelected={selectedJob?.id === job.id}
              onSelect={() => setSelectedJob(job)}
              onTrigger={() => handleTriggerJob(job.source)}
              triggering={triggering}
            />
          ))}
          {jobs.length === 0 && (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              <Zap className="w-12 h-12 mx-auto mb-3 text-gray-400" />
              <p>No jobs found. Trigger a new scrape to get started.</p>
            </div>
          )}
        </div>

        {/* Job Details Panel */}
        {selectedJob && (
          <JobDetailPanel job={selectedJob} />
        )}
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 gap-4">
          {sources.map((source) => (
            <button
              key={source.id}
              onClick={() => handleTriggerJob(source.id)}
              disabled={triggering}
              className="p-4 border border-gray-200 rounded hover:border-blue-500 hover:bg-blue-50 disabled:opacity-50 text-left"
            >
              <div className="font-medium text-gray-900">{source.name}</div>
              <div className="text-xs text-gray-500 mt-1">
                Last run:{' '}
                {source.last_scraped_at
                  ? new Date(source.last_scraped_at).toLocaleString()
                  : 'Never'}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// Subcomponents
// ============================================================================

const getStatusIcon = (status) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    case 'failed':
      return <AlertCircle className="w-5 h-5 text-red-500" />;
    case 'running':
      return <Zap className="w-5 h-5 text-yellow-500 animate-pulse" />;
    case 'pending':
      return <Clock className="w-5 h-5 text-gray-500" />;
    default:
      return null;
  }
};

const getStatusBg = (status) => {
  switch (status) {
    case 'completed':
      return 'bg-green-50 border-green-200';
    case 'failed':
      return 'bg-red-50 border-red-200';
    case 'running':
      return 'bg-yellow-50 border-yellow-200';
    case 'pending':
      return 'bg-gray-50 border-gray-200';
    default:
      return 'bg-white';
  }
};

const JobCard = ({ job, isSelected, onSelect, onTrigger, triggering }) => {
  const progressPercent = job.status === 'completed' ? 100 :
                         job.status === 'failed' ? 0 :
                         job.status === 'running' ? (job.progress_percent || 0) : 0;

  return (
    <div
      onClick={onSelect}
      className={`border rounded-lg p-4 cursor-pointer transition ${
        isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'
      } ${getStatusBg(job.status)}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          {getStatusIcon(job.status)}
          <div>
            <h3 className="font-semibold text-gray-900">{job.source_name}</h3>
            <p className="text-xs text-gray-500">Job ID: {job.id}</p>
          </div>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
          job.status === 'completed' ? 'bg-green-100 text-green-800' :
          job.status === 'failed' ? 'bg-red-100 text-red-800' :
          job.status === 'running' ? 'bg-yellow-100 text-yellow-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {job.status.toUpperCase()}
        </span>
      </div>

      {/* Progress Bar */}
      {job.status === 'running' && (
        <div className="mb-3">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-yellow-500 h-2 rounded-full transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="text-xs text-gray-600 mt-1">{progressPercent}% complete</p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-2 mb-3 text-sm">
        <div>
          <p className="text-gray-600">Scraped</p>
          <p className="font-semibold">{job.records_scraped || 0}</p>
        </div>
        <div>
          <p className="text-gray-600">Normalized</p>
          <p className="font-semibold">{job.records_normalized || 0}</p>
        </div>
        <div>
          <p className="text-gray-600">Duplicates</p>
          <p className="font-semibold">{job.records_duplicates || 0}</p>
        </div>
        <div>
          <p className="text-gray-600">Imported</p>
          <p className="font-semibold">{job.records_imported || 0}</p>
        </div>
      </div>

      {/* Timestamps */}
      <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
        <span>
          <Calendar className="w-3 h-3 inline mr-1" />
          {new Date(job.created_at).toLocaleDateString()}
        </span>
        {job.finished_at && (
          <span>
            Duration: {Math.round((new Date(job.finished_at) - new Date(job.created_at)) / 1000)}s
          </span>
        )}
      </div>

      {/* Actions */}
      {job.status !== 'running' && (
        <div className="flex gap-2 pt-3 border-t">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onTrigger();
            }}
            disabled={triggering}
            className="flex-1 px-3 py-2 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 disabled:opacity-50"
          >
            <Play className="w-3 h-3 inline mr-1" />
            Trigger Again
          </button>
        </div>
      )}
    </div>
  );
};

const JobDetailPanel = ({ job }) => {
  const [logsExpanded, setLogsExpanded] = useState(false);

  return (
    <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500 h-fit sticky top-6">
      <h3 className="text-lg font-semibold mb-4 text-gray-900">Job Details</h3>

      {/* Summary Stats */}
      <div className="bg-gray-50 p-4 rounded mb-4 space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-600">Job ID:</span>
          <span className="font-mono font-semibold">{job.id}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Status:</span>
          <span className="font-semibold capitalize">{job.status}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Source:</span>
          <span className="font-semibold">{job.source_name}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Started:</span>
          <span>{new Date(job.created_at).toLocaleString()}</span>
        </div>
        {job.finished_at && (
          <div className="flex justify-between">
            <span className="text-gray-600">Completed:</span>
            <span>{new Date(job.finished_at).toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Stage Breakdown */}
      <div className="border-t pt-4 mb-4">
        <h4 className="font-semibold text-gray-900 mb-3 text-sm">Pipeline Stages</h4>
        <div className="space-y-2 text-sm">
          <StageRow
            label="Bronze"
            value={job.records_scraped}
            icon={<Database className="w-4 h-4" />}
          />
          <StageRow
            label="Silver"
            value={job.records_normalized}
            icon={<Zap className="w-4 h-4" />}
          />
          <StageRow
            label="Gold"
            value={job.records_imported}
            icon={<BarChart3 className="w-4 h-4" />}
          />
        </div>
      </div>

      {/* Errors (if any) */}
      {job.error_log && (
        <div className="bg-red-50 p-3 rounded border border-red-200">
          <h4 className="font-semibold text-red-900 mb-2 text-sm">Errors</h4>
          <p className="text-xs text-red-800 whitespace-pre-wrap">
            {job.error_log.substring(0, 500)}
            {job.error_log.length > 500 && '...'}
          </p>
        </div>
      )}
    </div>
  );
};

const StageRow = ({ label, value, icon }) => (
  <div className="flex items-center justify-between">
    <div className="flex items-center gap-2">
      {icon}
      <span className="text-gray-600">{label}:</span>
    </div>
    <span className="font-semibold text-gray-900">{value}</span>
  </div>
);

export default ScraperJobManagement;

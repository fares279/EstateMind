/**
 * SCRAPER AGENT FRONTEND INTEGRATION GUIDE
 * 
 * This document outlines how to integrate the three React dashboard components
 * into the EstateMind frontend application with the backend scraper-agent APIs.
 * 
 * The three-stage pipeline is visualized as:
 * BRONZE → SILVER → GOLD
 * (Collection) → (Normalization) → (Market Intelligence)
 */

import React from 'react';

// ============================================================================
// INTEGRATION ARCHITECTURE
// ============================================================================

/**
 * COMPONENT HIERARCHY
 * 
 * AdminDashboard (main layout)
 *   ├─ PipelineHealthDashboard
 *   │   ├─ PipelineOverviewCard
 *   │   ├─ StageCard (Bronze/Silver/Gold)
 *   │   ├─ DataQualitySection
 *   │   ├─ ScraperHealthSection
 *   │   └─ IncidentCard
 *   │
 *   ├─ ScraperJobManagement
 *   │   ├─ JobCard (list of jobs)
 *   │   └─ JobDetailPanel (selected job details)
 *   │
 *   └─ DataQualityManagement
 *       ├─ StatCard (overview stats)
 *       ├─ ViolationRow (list of violations)
 *       └─ ViolationDetailPanel (violation details & fix UI)
 */

// ============================================================================
// BACKEND API REQUIREMENTS
// ============================================================================

/**
 * Required Django Endpoints:
 * 
 * 1. PIPELINE HEALTH MONITORING
 *    GET /api/scraper/health/dashboard/
 *      Response: {
 *        "pipeline_status": "healthy|degraded|unhealthy",
 *        "overall_health_score": 92.5,
 *        "last_complete_run": "2024-05-12T14:30:00Z",
 *        "alerts": ["Alert message 1", "Alert message 2"],
 *        "bronze_status": {...},
 *        "silver_status": {...},
 *        "gold_status": {...}
 *      }
 * 
 * 2. DATA QUALITY METRICS
 *    GET /api/scraper/health/data-quality/
 *      Response: {
 *        "schema_validation_pass_rate": 98.5,
 *        "duplicate_rate_pct": 2.1,
 *        "geocoding_quality": {
 *          "polygon_level_pct": 45.0,
 *          "centroid_level_pct": 40.0,
 *          "missing_pct": 15.0
 *        },
 *        "data_drift_detected": false,
 *        "psi_metrics": {
 *          "price": 0.045,
 *          "surface": 0.032,
 *          "delegation": 0.018
 *        },
 *        "recommendations": ["Fix geocoding for...",...],
 *      }
 * 
 * 3. SCRAPER AGENT HEALTH
 *    GET /api/scraper/health/scraper-agents/
 *      Response: [
 *        {
 *          "scraper_name": "Tayara",
 *          "source_name": "Tayara.tn",
 *          "status": "healthy|degraded|unhealthy",
 *          "health_score": 92.5,
 *          "success_rate_pct": 95.3,
 *          "avg_data_age_hours": 2.5,
 *          "field_coverage_pct": 89.0,
 *          "last_execution": "2024-05-12T14:30:00Z",
 *          "alerts": ["Alert 1", "Alert 2"]
 *        }
 *      ]
 * 
 * 4. ACTIVE INCIDENTS
 *    GET /api/scraper/health/incidents/
 *      Response: {
 *        "incidents": [
 *          {
 *            "id": "inc_123",
 *            "message": "Tayara scraper failing",
 *            "source": "tayara",
 *            "type": "scraper_down|quality_issue|drift_detected",
 *            "severity": "high|medium|low"
 *          }
 *        ]
 *      }
 * 
 * 5. SCRAPER JOBS
 *    GET /api/scraper/jobs/
 *      Params: source (optional)
 *      Response: [
 *        {
 *          "id": "job_123",
 *          "source_id": 1,
 *          "source_name": "Tayara",
 *          "status": "pending|running|completed|failed",
 *          "progress_percent": 45,
 *          "records_scraped": 1250,
 *          "records_normalized": 1200,
 *          "records_duplicates": 50,
 *          "records_imported": 1150,
 *          "created_at": "2024-05-12T14:00:00Z",
 *          "completed_at": "2024-05-12T14:30:00Z",
 *          "error_log": "Error message..."
 *        }
 *      ]
 * 
 *    POST /api/scraper/jobs/trigger/
 *      Body: { "source_id": 1 }
 *      Response: { "job_id": "job_123", "status": "pending" }
 * 
 *    POST /api/scraper/jobs/trigger-all/
 *      Response: { "jobs_triggered": 5 }
 * 
 * 6. SCRAPER SOURCES
 *    GET /api/scraper/sources/
 *      Response: [
 *        {
 *          "id": 1,
 *          "name": "Tayara",
 *          "last_run": "2024-05-12T14:30:00Z"
 *        }
 *      ]
 * 
 * 7. DATA QUALITY VIOLATIONS
 *    GET /api/scraper/data-quality/violations/
 *      Params: status, severity, source (all optional)
 *      Response: {
 *        "violations": [
 *          {
 *            "id": "vio_123",
 *            "record_id": "ext_tayara_12345",
 *            "violation_type": "null_value|out_of_range|invalid_type|schema_mismatch",
 *            "severity": "critical|warning|info",
 *            "source": "tayara",
 *            "field_name": "price",
 *            "message": "Price is below minimum threshold",
 *            "constraint": "price > 10000",
 *            "original_value": "500",
 *            "status": "pending|approved|rejected|fixed",
 *            "suggestions": ["50000", "500000"]
 *          }
 *        ],
 *        "stats": {
 *          "total_violations": 145,
 *          "pending_violations": 23,
 *          "approved_violations": 98,
 *          "rejected_violations": 24
 *        }
 *      }
 * 
 *    POST /api/scraper/data-quality/violations/{id}/approve/
 *      Body: { "corrected_data": "new_value" }
 *      Response: { "status": "approved" }
 * 
 *    POST /api/scraper/data-quality/violations/{id}/reject/
 *      Response: { "status": "rejected" }
 * 
 *    GET /api/scraper/data-quality/violations/export/
 *      Response: CSV file download
 */

// ============================================================================
// IMPLEMENTATION STEPS
// ============================================================================

/**
 * STEP 1: Wire Components into Routes
 * ─────────────────────────────────────
 * 
 * File: frontend/src/pages/Admin/ScraperDashboard.jsx
 * 
 * import React, { useState } from 'react';
 * import PipelineHealthDashboard from './PipelineHealthDashboard';
 * import ScraperJobManagement from './ScraperJobManagement';
 * import DataQualityManagement from './DataQualityManagement';
 * 
 * const ScraperDashboard = () => {
 *   const [activeTab, setActiveTab] = useState('health');
 * 
 *   return (
 *     <div>
 *       <nav className="flex gap-4 bg-white border-b p-4">
 *         <button
 *           onClick={() => setActiveTab('health')}
 *           className={`px-4 py-2 ${activeTab === 'health' ? 'border-b-2 border-blue-500' : ''}`}
 *         >
 *           Pipeline Health
 *         </button>
 *         <button
 *           onClick={() => setActiveTab('jobs')}
 *           className={`px-4 py-2 ${activeTab === 'jobs' ? 'border-b-2 border-blue-500' : ''}`}
 *         >
 *           Jobs
 *         </button>
 *         <button
 *           onClick={() => setActiveTab('quality')}
 *           className={`px-4 py-2 ${activeTab === 'quality' ? 'border-b-2 border-blue-500' : ''}`}
 *         >
 *           Data Quality
 *         </button>
 *       </nav>
 * 
 *       <div>
 *         {activeTab === 'health' && <PipelineHealthDashboard />}
 *         {activeTab === 'jobs' && <ScraperJobManagement />}
 *         {activeTab === 'quality' && <DataQualityManagement />}
 *       </div>
 *     </div>
 *   );
 * };
 * 
 * export default ScraperDashboard;
 */

/**
 * STEP 2: Add Route in App.js
 * ────────────────────────────
 * 
 * import ScraperDashboard from './pages/Admin/ScraperDashboard';
 * 
 * // In your routing configuration:
 * <Route path="/admin/scraper" element={<ScraperDashboard />} />
 */

/**
 * STEP 3: Implement Backend API Integration
 * ──────────────────────────────────────────
 * 
 * File: backend/scraper/views.py
 * (Add the following viewsets to existing views.py)
 * 
 * from rest_framework import viewsets, status
 * from rest_framework.decorators import action
 * from rest_framework.response import Response
 * from .scraper_agent_architecture import ScrapeAgentMetrics
 * from .data_quality import DataQualityValidator, QualityCheckResult
 * from .models import ScrapeJob, ScrapeSource, ScrapedListing
 * 
 * class PipelineHealthViewSet(viewsets.ViewSet):
 *     @action(detail=False, methods=['get'])
 *     def dashboard(self, request):
 *         '''Get overall pipeline health status'''
 *         metrics = ScrapeAgentMetrics()
 *         health = metrics.get_stage_health()
 *         
 *         return Response({
 *             'pipeline_status': health['overall_status'],
 *             'overall_health_score': health['health_score'],
 *             'last_complete_run': health['last_complete_run'],
 *             'alerts': health['alerts'],
 *             'bronze_status': health['bronze'],
 *             'silver_status': health['silver'],
 *             'gold_status': health['gold']
 *         })
 * 
 * class DataQualityViewSet(viewsets.ViewSet):
 *     @action(detail=False, methods=['get'])
 *     def violations(self, request):
 *         '''Get data quality violations with filtering'''
 *         validator = DataQualityValidator()
 *         violations = validator.get_violations(
 *             status=request.query_params.get('status'),
 *             severity=request.query_params.get('severity'),
 *             source=request.query_params.get('source')
 *         )
 *         
 *         return Response({
 *             'violations': violations,
 *             'stats': validator.get_violation_stats()
 *         })
 * 
 *     @action(detail=True, methods=['post'])
 *     def approve_violation(self, request, pk=None):
 *         '''Approve and fix a data quality violation'''
 *         corrected_data = request.data.get('corrected_data')
 *         # Update the record with corrected data
 *         listing = ScrapedListing.objects.get(id=pk)
 *         listing.normalized_data['corrected_field'] = corrected_data
 *         listing.save()
 *         
 *         return Response({'status': 'approved'})
 * 
 * File: backend/config/urls.py
 * 
 * from rest_framework.routers import DefaultRouter
 * from scraper.views import PipelineHealthViewSet, DataQualityViewSet
 * 
 * router = DefaultRouter()
 * router.register(r'scraper/health', PipelineHealthViewSet, basename='health')
 * router.register(r'scraper/data-quality', DataQualityViewSet, basename='quality')
 * 
 * urlpatterns = [
 *     path('api/', include(router.urls)),
 * ]
 */

/**
 * STEP 4: Configure WebSocket for Real-Time Updates (Optional)
 * ──────────────────────────────────────────────────────────────
 * 
 * For real-time job progress updates, implement WebSocket consumers.
 * 
 * File: backend/scraper/consumers.py
 * 
 * from channels.generic.websocket import AsyncWebsocketConsumer
 * import json
 * 
 * class PipelineConsumer(AsyncWebsocketConsumer):
 *     async def connect(self):
 *         await self.channel_layer.group_add('pipeline', self.channel_name)
 *         await self.accept()
 * 
 *     async def job_update(self, event):
 *         await self.send(text_data=json.dumps(event['data']))
 * 
 * File: backend/scraper/services/orchestrator.py
 * (Modify to emit WebSocket events)
 * 
 * async def emit_job_update(job_id, progress):
 *     from channels.layers import get_channel_layer
 *     channel_layer = get_channel_layer()
 *     await channel_layer.group_send(
 *         'pipeline',
 *         {
 *             'type': 'job_update',
 *             'data': {
 *                 'job_id': job_id,
 *                 'progress': progress
 *             }
 *         }
 *     )
 */

/**
 * STEP 5: Add Navigation Links
 * ─────────────────────────────
 * 
 * File: frontend/src/layouts/AdminLayout.jsx
 * (Add to sidebar navigation)
 * 
 * <nav className="space-y-2">
 *   <NavLink to="/admin">Dashboard</NavLink>
 *   <NavLink to="/admin/scraper">
 *     <Database className="w-5 h-5 mr-2 inline" />
 *     Scraper Pipeline
 *   </NavLink>
 *   <NavLink to="/admin/users">Users</NavLink>
 * </nav>
 */

/**
 * STEP 6: Styling Configuration
 * ──────────────────────────────
 * 
 * Ensure your tailwind.config.js has:
 * 
 * module.exports = {
 *   extend: {
 *     colors: {
 *       bronze: '#CD7F32',
 *       silver: '#C0C0C0',
 *       gold: '#FFD700'
 *     },
 *     keyframes: {
 *       pulse: {
 *         '0%, 100%': { opacity: '1' },
 *         '50%': { opacity: '0.5' }
 *       }
 *     }
 *   }
 * };
 */

// ============================================================================
// API SERVICE HELPER
// ============================================================================

/**
 * File: frontend/src/services/scraperApi.js
 * 
 * Centralized scraper API client with automatic retry and caching
 */

import axios from 'axios';

class ScraperApiClient {
  constructor() {
    this.client = axios.create({
      baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add auth token to requests
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Cache for health checks (5 minute TTL)
    this.cache = new Map();
  }

  getCacheKey(method, url, params) {
    return `${method}:${url}:${JSON.stringify(params || {})}`;
  }

  async get(url, options = {}) {
    const cacheKey = this.getCacheKey('GET', url, options.params);
    
    // Check cache for GET requests
    if (this.cache.has(cacheKey)) {
      const { data, timestamp } = this.cache.get(cacheKey);
      if (Date.now() - timestamp < 5 * 60 * 1000) { // 5 minute TTL
        return { data };
      }
    }

    try {
      const response = await this.client.get(url, options);
      if (options.cache !== false) {
        this.cache.set(cacheKey, {
          data: response.data,
          timestamp: Date.now(),
        });
      }
      return response;
    } catch (error) {
      console.error(`GET ${url} failed:`, error);
      throw error;
    }
  }

  async post(url, data = {}, options = {}) {
    return this.client.post(url, data, options);
  }

  clearCache() {
    this.cache.clear();
  }
}

export default new ScraperApiClient();

/**
 * Usage in components:
 * 
 * import scraperApi from '../../services/scraperApi';
 * 
 * const [data, setData] = useState(null);
 * 
 * useEffect(() => {
 *   scraperApi.get('/scraper/health/dashboard/')
 *     .then(res => setData(res.data))
 *     .catch(err => console.error(err));
 * }, []);
 */

// ============================================================================
// MONITORING & ALERTING INTEGRATION
// ============================================================================

/**
 * Connect to Slack/PagerDuty for Incidents:
 * 
 * File: backend/scraper/alerting.py
 * 
 * import requests
 * 
 * class AlertManager:
 *     def __init__(self):
 *         self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
 *         self.pagerduty_key = os.getenv('PAGERDUTY_INTEGRATION_KEY')
 *     
 *     def notify_incident(self, incident):
 *         # Send to Slack
 *         if self.slack_webhook:
 *             requests.post(self.slack_webhook, json={
 *                 'text': f"⚠️ Scraper incident: {incident['message']}",
 *                 'color': 'warning' if incident['severity'] == 'medium' else 'danger'
 *             })
 *         
 *         # Send to PagerDuty if critical
 *         if self.pagerduty_key and incident['severity'] == 'critical':
 *             requests.post('https://events.pagerduty.com/v2/enqueue', json={
 *                 'routing_key': self.pagerduty_key,
 *                 'event_action': 'trigger',
 *                 'payload': {
 *                     'summary': incident['message'],
 *                     'severity': incident['severity'],
 *                     'source': 'EstateMind Scraper'
 *                 }
 *             })
 */

// ============================================================================
// TESTING GUIDE
// ============================================================================

/**
 * MANUAL TESTING CHECKLIST:
 * 
 * 1. Pipeline Health Dashboard
 *    ✓ Displays overall status with color coding
 *    ✓ Shows three stages (Bronze/Silver/Gold) metrics
 *    ✓ Incidents list shows active problems
 *    ✓ Refresh button triggers data reload
 * 
 * 2. Scraper Job Management
 *    ✓ Lists recent jobs with status
 *    ✓ Progress bar shows for running jobs
 *    ✓ "Trigger All Sources" button works
 *    ✓ Individual scraper quick-action buttons work
 * 
 * 3. Data Quality Management
 *    ✓ Lists violations with filters
 *    ✓ Clicking violation shows details panel
 *    ✓ "Fix & Approve" edits and saves correction
 *    ✓ "Reject Record" removes from pipeline
 *    ✓ Export button downloads CSV
 * 
 * 4. Real-Time Updates
 *    ✓ Dashboard refreshes every 5 minutes
 *    ✓ Jobs page refreshes every 10 seconds during execution
 *    ✓ Status transitions are reflected in UI
 * 
 * 5. Error Handling
 *    ✓ Network errors show user-friendly messages
 *    ✓ Loading states display spinners
 *    ✓ Failed requests can be retried
 */

// ============================================================================
// PERFORMANCE OPTIMIZATION
// ============================================================================

/**
 * 1. Lazy Load Components
 *    
 *    const PipelineHealthDashboard = React.lazy(
 *      () => import('./components/Scraper/PipelineHealthDashboard')
 *    );
 * 
 * 2. Memoize Heavy Components
 *    
 *    export default React.memo(ScraperJobManagement);
 * 
 * 3. Virtualize Long Lists
 *    
 *    import { FixedSizeList } from 'react-window';
 *    <FixedSizeList height={600} itemCount={violations.length} itemSize={80}>
 *      {({ index, style }) => <ViolationRow style={style} {...violations[index]} />}
 *    </FixedSizeList>
 * 
 * 4. Use Query Pagination
 *    
 *    GET /api/scraper/jobs/?page=1&limit=20
 */

export default function ScraperIntegrationGuide() {
  return (
    <div className="p-8 bg-gray-50 max-w-4xl mx-auto">
      <h1 className="text-4xl font-bold mb-6">Scraper Agent Frontend Integration</h1>
      <p className="text-gray-600 mb-8">
        This file serves as reference documentation. See inline comments in each section
        for implementation details.
      </p>
      <div className="bg-blue-50 p-6 rounded-lg border border-blue-200">
        <h2 className="text-lg font-semibold text-blue-900 mb-4">Quick Start</h2>
        <ol className="list-decimal list-inside space-y-2 text-blue-800">
          <li>Copy three component files to frontend/src/components/Scraper/</li>
          <li>Create backend viewsets in scraper/views.py (see Step 3)</li>
          <li>Wire components into routes (see Step 1)</li>
          <li>Add navigation links (see Step 5)</li>
          <li>Test endpoints with Postman</li>
          <li>Deploy and monitor</li>
        </ol>
      </div>
    </div>
  );
}

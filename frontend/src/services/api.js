/**
 * Centralized High-Performance API Service for React Dashboard.
 * Includes In-Memory Stale-While-Revalidate Caching for Instant (0ms) Tab Navigation.
 */

import axios from 'axios';

// In browser, relative '/api' utilizes the Vite dev proxy (or reverse proxy in production)
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor to normalize data extraction
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const errorMsg =
      error.response?.data?.error ||
      error.message ||
      'Unable to connect to the network backend on port 5000.';
    return Promise.reject(new Error(errorMsg));
  }
);

// ============================================================================
// Lightning-Fast In-Memory Cache (Sub-10ms Route Switching)
// ============================================================================

const memoryCache = new Map();
const DEFAULT_TTL_MS = 60 * 1000; // 60 seconds TTL

const getCacheKey = (url, params = {}) => {
  const sortedParams = Object.keys(params || {})
    .sort()
    .reduce((acc, key) => {
      acc[key] = params[key];
      return acc;
    }, {});
  return `${url}?${JSON.stringify(sortedParams)}`;
};

/**
 * Synchronously retrieves cached data for immediate component initialization (0ms render).
 */
export const getCachedData = (url, params = {}) => {
  const key = getCacheKey(url, params);
  const entry = memoryCache.get(key);
  if (entry && entry.data) {
    return entry.data;
  }
  return null;
};

/**
 * Invalidates specific cache keys or patterns (e.g. on manual user refresh).
 */
export const invalidateCache = (pattern = '') => {
  if (!pattern) {
    memoryCache.clear();
    return;
  }
  for (const key of memoryCache.keys()) {
    if (key.includes(pattern)) {
      memoryCache.delete(key);
    }
  }
};

/**
 * Clears the entire in-memory API cache.
 */
export const clearApiCache = () => {
  memoryCache.clear();
};

/**
 * Cached GET wrapper supporting instant cache returns and deduplicated in-flight requests.
 */
export async function cachedGet(url, params = {}, options = {}) {
  const { forceRefresh = false, ttl = DEFAULT_TTL_MS } = options;
  const key = getCacheKey(url, params);
  const now = Date.now();
  const cached = memoryCache.get(key);

  // If manual refresh requested, bust in-memory cache completely
  if (forceRefresh) {
    memoryCache.delete(key);
  } else if (cached && cached.data && now - cached.timestamp < ttl) {
    // Return cached data immediately if fresh and not force-refreshing
    return cached.data;
  }

  // Deduplicate in-flight promises (only when not force-refreshing)
  if (!forceRefresh && cached && cached.promise) {
    return cached.promise;
  }

  const reqConfig = {
    params: forceRefresh ? { ...params, _t: now } : params,
    headers: forceRefresh
      ? { 'Cache-Control': 'no-cache, no-store, must-revalidate', Pragma: 'no-cache' }
      : {},
  };

  const promise = apiClient
    .get(url, reqConfig)
    .then((data) => {
      memoryCache.set(key, {
        data,
        timestamp: Date.now(),
        promise: null,
      });
      return data;
    })
    .catch((err) => {
      // Evict failed requests so retry can happen
      memoryCache.delete(key);
      throw err;
    });

  memoryCache.set(key, {
    data: cached?.data || null,
    timestamp: cached?.timestamp || 0,
    promise,
  });

  return promise;
}

// ============================================================================
// Application API Endpoints (All Cached with SWR & Fast Revalidation)
// ============================================================================

// 1. Health & Status (Short 10s TTL)
export const getHealth = (options = {}) =>
  cachedGet('/health', {}, { ttl: 10000, ...options });

// 2. Monitoring Endpoints
export const getMonitoringFlows = (params = {}, options = {}) =>
  cachedGet('/monitoring/flows', params, options);
export const getMonitoringSummary = (options = {}) =>
  cachedGet('/monitoring/summary', {}, options);

// 3. Profiling Endpoints
export const getProfilingBehaviors = (params = {}, options = {}) =>
  cachedGet('/profiling/behaviors', params, options);
export const getProfilingClusters = (options = {}) =>
  cachedGet('/profiling/clusters', {}, options);

// 4. Congestion Prediction Endpoints
export const getCongestionPredictions = (params = {}, options = {}) =>
  cachedGet('/congestion/predictions', params, options);
export const getCongestionSummary = (options = {}) =>
  cachedGet('/congestion/summary', {}, options);

// 5. Traffic Classification Endpoints
export const getClassificationFlows = (params = {}, options = {}) =>
  cachedGet('/classification/flows', params, options);
export const getClassificationSummary = (options = {}) =>
  cachedGet('/classification/summary', {}, options);

// 6. QoS Policy Endpoints
export const getPolicyDecisions = (params = {}, options = {}) =>
  cachedGet('/policy/decisions', params, options);
export const getPolicySummary = (options = {}) =>
  cachedGet('/policy/summary', {}, options);

// 7. Adaptive Traffic Control Endpoints
export const getControlActions = (params = {}, options = {}) =>
  cachedGet('/control/actions', params, options);
export const getControlState = (params = {}, options = {}) =>
  cachedGet('/control/state', params, options);
export const getControlSummary = (options = {}) =>
  cachedGet('/control/summary', {}, options);

// 8. Decision Traces Endpoints
export const getTraces = (params = {}, options = {}) =>
  cachedGet('/traces', params, options);
export const getTraceById = (traceId, options = {}) =>
  cachedGet(`/traces/${encodeURIComponent(traceId)}`, {}, options);
export const getTraceSummary = (options = {}) =>
  cachedGet('/traces/summary', {}, options);

// 9. SHAP Explainability Endpoints
export const getExplainabilityLocal = (params = {}, options = {}) =>
  cachedGet('/explainability/local', params, options);
export const getExplainabilityGlobal = (options = {}) =>
  cachedGet('/explainability/global', {}, options);
export const getExplainabilitySummary = (options = {}) =>
  cachedGet('/explainability/summary', {}, options);

// 10. Natural-Language Explanations Endpoints
export const getExplanations = (params = {}, options = {}) =>
  cachedGet('/explanations', params, options);
export const getExplanationById = (traceId, options = {}) =>
  cachedGet(`/explanations/${encodeURIComponent(traceId)}`, {}, options);
export const getExplanationSummary = (options = {}) =>
  cachedGet('/explanations/summary', {}, options);

// 11. Live Packet Capture Endpoints (Direct real-time wire calls)
export const getLiveStats = () => apiClient.get('/live/stats');
export const getLivePackets = (params = {}) => apiClient.get('/live/packets', { params });
export const startLiveCapture = (data = {}) => apiClient.post('/live/start', data);
export const stopLiveCapture = () => apiClient.post('/live/stop');
export const clearLivePackets = () => apiClient.post('/live/clear');
export const getLiveInterfaces = () => apiClient.get('/live/interfaces');

// 12. Real-Time ML Pipeline Endpoints (Trained models on genuine captured traffic)
export const getLivePipelineStatus = () => apiClient.get('/live/pipeline/status');
export const getLivePipelineFlows = (params = {}) => apiClient.get('/live/pipeline/flows', { params });
export const getLivePipelinePredictions = (params = {}) => apiClient.get('/live/pipeline/predictions', { params });
export const getLivePipelineTraces = (params = {}) => apiClient.get('/live/pipeline/traces', { params });
export const clearLivePipeline = () => apiClient.post('/live/pipeline/clear');

export default apiClient;


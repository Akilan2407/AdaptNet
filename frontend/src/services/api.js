/**
 * Centralized API Service for Phase 19 React Dashboard.
 * Connects to Phase 18 Flask REST API backend.
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

// 1. Health & Status
export const getHealth = () => apiClient.get('/health');

// 2. Monitoring Endpoints
export const getMonitoringFlows = (params = {}) => apiClient.get('/monitoring/flows', { params });
export const getMonitoringSummary = () => apiClient.get('/monitoring/summary');

// 3. Profiling Endpoints
export const getProfilingBehaviors = (params = {}) => apiClient.get('/profiling/behaviors', { params });
export const getProfilingClusters = () => apiClient.get('/profiling/clusters');

// 4. Congestion Prediction Endpoints
export const getCongestionPredictions = (params = {}) => apiClient.get('/congestion/predictions', { params });
export const getCongestionSummary = () => apiClient.get('/congestion/summary');

// 5. Traffic Classification Endpoints
export const getClassificationFlows = (params = {}) => apiClient.get('/classification/flows', { params });
export const getClassificationSummary = () => apiClient.get('/classification/summary');

// 6. QoS Policy Endpoints
export const getPolicyDecisions = (params = {}) => apiClient.get('/policy/decisions', { params });
export const getPolicySummary = () => apiClient.get('/policy/summary');

// 7. Adaptive Traffic Control Endpoints
export const getControlActions = (params = {}) => apiClient.get('/control/actions', { params });
export const getControlState = (params = {}) => apiClient.get('/control/state', { params });
export const getControlSummary = () => apiClient.get('/control/summary');

// 8. Decision Traces Endpoints
export const getTraces = (params = {}) => apiClient.get('/traces', { params });
export const getTraceById = (traceId) => apiClient.get(`/traces/${encodeURIComponent(traceId)}`);
export const getTraceSummary = () => apiClient.get('/traces/summary');

// 9. SHAP Explainability Endpoints
export const getExplainabilityLocal = (params = {}) => apiClient.get('/explainability/local', { params });
export const getExplainabilityGlobal = () => apiClient.get('/explainability/global');
export const getExplainabilitySummary = () => apiClient.get('/explainability/summary');

// 10. Natural-Language Explanations Endpoints
export const getExplanations = (params = {}) => apiClient.get('/explanations', { params });
export const getExplanationById = (traceId) => apiClient.get(`/explanations/${encodeURIComponent(traceId)}`);
export const getExplanationSummary = () => apiClient.get('/explanations/summary');

export default apiClient;

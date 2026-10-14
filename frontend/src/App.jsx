import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import {
  getMonitoringSummary,
  getCongestionSummary,
  getPolicySummary,
  getControlSummary,
  getTraceSummary,
  getClassificationSummary,
  getProfilingClusters,
  getExplainabilitySummary,
  getExplanationSummary,
} from './services/api';

// View Pages
import Dashboard from './pages/Dashboard';
import Monitoring from './pages/Monitoring';
import LiveCapture from './pages/LiveCapture';
import Profiling from './pages/Profiling';
import Classification from './pages/Classification';
import Congestion from './pages/Congestion';
import Policies from './pages/Policies';
import Control from './pages/Control';
import Traces from './pages/Traces';
import Explainability from './pages/Explainability';
import Explanations from './pages/Explanations';

export default function App() {
  useEffect(() => {
    // Pre-warm API summaries in background on idle so all tab navigations are 0ms instant
    const prewarm = () => {
      getMonitoringSummary().catch(() => {});
      getCongestionSummary().catch(() => {});
      getPolicySummary().catch(() => {});
      getControlSummary().catch(() => {});
      getTraceSummary().catch(() => {});
      getClassificationSummary().catch(() => {});
      getProfilingClusters().catch(() => {});
      getExplainabilitySummary().catch(() => {});
      getExplanationSummary().catch(() => {});
    };

    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(prewarm, { timeout: 1000 });
    } else {
      setTimeout(prewarm, 200);
    }
  }, []);

  return (
    <BrowserRouter>
      <div className="app-layout">
        {/* Ambient Warm Champagne & Sunset Mesh Canvas */}
        <div className="sunset-canvas" aria-hidden="true">
          <div className="sunset-blob sunset-amber"></div>
          <div className="sunset-blob sunset-coral"></div>
          <div className="sunset-blob sunset-rose"></div>
          <div className="sunset-blob sunset-amethyst"></div>
          <div className="sunset-blob sunset-sage"></div>
        </div>
        <Navbar />
        <div className="layout-body">
          <Sidebar />
          <main className="main-viewport">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/live" element={<LiveCapture />} />
              <Route path="/profiling" element={<Profiling />} />
              <Route path="/classification" element={<Classification />} />
              <Route path="/congestion" element={<Congestion />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/control" element={<Control />} />
              <Route path="/traces" element={<Traces />} />
              <Route path="/explainability" element={<Explainability />} />
              <Route path="/explanations" element={<Explanations />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

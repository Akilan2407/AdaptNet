import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  IconDashboard,
  IconMonitoring,
  IconLiveCapture,
  IconProfiling,
  IconClassification,
  IconCongestion,
  IconPolicies,
  IconControl,
  IconTraces,
  IconExplainability,
  IconExplanations,
} from './Icons';
import {
  getMonitoringFlows,
  getMonitoringSummary,
  getProfilingBehaviors,
  getProfilingClusters,
  getClassificationFlows,
  getClassificationSummary,
  getCongestionPredictions,
  getCongestionSummary,
  getPolicyDecisions,
  getPolicySummary,
  getControlActions,
  getControlSummary,
  getTraces,
  getTraceSummary,
  getExplainabilityLocal,
  getExplainabilityGlobal,
  getExplanations,
  getExplanationSummary,
} from '../services/api';

const prefetchMap = {
  '/': () => {
    getMonitoringSummary();
    getCongestionSummary();
    getPolicySummary();
  },
  '/monitoring': () => {
    getMonitoringFlows({ limit: 15, offset: 0 });
    getMonitoringSummary();
  },
  '/profiling': () => {
    getProfilingBehaviors();
    getProfilingClusters();
  },
  '/classification': () => {
    getClassificationFlows({ limit: 15, offset: 0 });
    getClassificationSummary();
  },
  '/congestion': () => {
    getCongestionPredictions({ limit: 15, offset: 0 });
    getCongestionSummary();
  },
  '/policies': () => {
    getPolicyDecisions({ limit: 15, offset: 0 });
    getPolicySummary();
  },
  '/control': () => {
    getControlActions({ limit: 15, offset: 0 });
    getControlSummary();
  },
  '/traces': () => {
    getTraces({ limit: 15, offset: 0 });
    getTraceSummary();
  },
  '/explainability': () => {
    getExplainabilityLocal({ limit: 15, offset: 0 });
    getExplainabilityGlobal();
  },
  '/explanations': () => {
    getExplanations({ limit: 15, offset: 0 });
    getExplanationSummary();
  },
};

const navItems = [
  { path: '/', label: 'Overview', icon: IconDashboard, section: 'Core' },
  { path: '/monitoring', label: 'Telemetry Monitoring', icon: IconMonitoring, section: 'Data Collection' },
  { path: '/live', label: 'Live Wire Sniffer', icon: IconLiveCapture, section: 'Data Collection' },
  { path: '/profiling', label: 'Device Profiling', icon: IconProfiling, section: 'Data Collection' },
  { path: '/classification', label: 'Traffic Classification', icon: IconClassification, section: 'Intelligence' },
  { path: '/congestion', label: 'Congestion Forecast', icon: IconCongestion, section: 'Intelligence' },
  { path: '/policies', label: 'QoS Policy Engine', icon: IconPolicies, section: 'Network Control' },
  { path: '/control', label: 'Adaptive Traffic Control', icon: IconControl, section: 'Network Control' },
  { path: '/traces', label: 'Decision Traces', icon: IconTraces, section: 'Traceability & XAI' },
  { path: '/explainability', label: 'SHAP Explainability', icon: IconExplainability, section: 'Traceability & XAI' },
  { path: '/explanations', label: 'Plain Explanations', icon: IconExplanations, section: 'Traceability & XAI' },
];

export default function Sidebar() {
  const handlePrefetch = (path) => {
    const fn = prefetchMap[path];
    if (fn) {
      try {
        fn();
      } catch (_) {}
    }
  };

  return (
    <aside className="app-sidebar">
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
              onMouseEnter={() => handlePrefetch(item.path)}
              onFocus={() => handlePrefetch(item.path)}
            >
              <div className="nav-icon-wrap">
                <Icon size={16} />
              </div>
              <span className="nav-link-text">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}

import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  IconDashboard,
  IconMonitoring,
  IconProfiling,
  IconClassification,
  IconCongestion,
  IconPolicies,
  IconControl,
  IconTraces,
  IconExplainability,
  IconExplanations,
} from './Icons';

const navItems = [
  { path: '/', label: 'Overview', icon: IconDashboard, section: 'Core' },
  { path: '/monitoring', label: 'Telemetry Monitoring', icon: IconMonitoring, section: 'Data Collection' },
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
  return (
    <aside className="app-sidebar">
      <div className="sidebar-section-title">NAVIGATION</div>
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
            >
              <div className="nav-icon-wrap">
                <Icon size={16} />
              </div>
              <span className="nav-link-text">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-info-box">
          <div className="info-box-title">System Architecture</div>
          <p className="info-box-desc">
            C Monitoring &rarr; ML GRU &rarr; QoS Policy &rarr; Linux tc &rarr; SHAP XAI
          </p>
        </div>
      </div>
    </aside>
  );
}

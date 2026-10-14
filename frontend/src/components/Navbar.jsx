import React, { useEffect, useState } from 'react';
import { getHealth } from '../services/api';
import { IconRefresh, IconCheck, IconAlert } from './Icons';

export default function Navbar({ onRefreshAll = null }) {
  const [healthStatus, setHealthStatus] = useState('checking'); // 'connected', 'offline', 'checking'
  const [healthData, setHealthData] = useState(null);
  const [checking, setChecking] = useState(false);

  const checkHealth = async () => {
    setChecking(true);
    try {
      const res = await getHealth();
      setHealthData(res);
      setHealthStatus('connected');
    } catch (err) {
      setHealthStatus('offline');
      setHealthData(null);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Poll health every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="top-navbar">
      <div className="navbar-brand">
        <div className="brand-icon-glow">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
            <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
            <line x1="6" y1="6" x2="6.01" y2="6"></line>
            <line x1="6" y1="18" x2="6.01" y2="18"></line>
          </svg>
        </div>
        <div className="brand-titles">
          <h1 className="brand-main-title">Adaptive Network Traffic Management</h1>
        </div>
      </div>

      <div className="navbar-actions">
        {/* Backend Connection Indicator */}
        <div
          className={`connection-pill ${
            healthStatus === 'connected'
              ? 'status-connected'
              : healthStatus === 'offline'
              ? 'status-offline'
              : 'status-checking'
          }`}
          title={
            healthStatus === 'connected'
              ? `Connected to Flask API v${healthData?.version || '1.0.0'} on port 5000`
              : 'Flask API backend is unreachable on port 5000'
          }
        >
          <span className="connection-text">
            {healthStatus === 'connected'
              ? 'Backend Connected'
              : healthStatus === 'offline'
              ? 'Backend Offline'
              : 'Checking API...'}
          </span>
        </div>

        {onRefreshAll && (
          <button
            onClick={() => {
              checkHealth();
              onRefreshAll();
            }}
            disabled={checking}
            className="btn btn-icon btn-secondary"
            title="Refresh system status and current page"
          >
            <IconRefresh size={14} spinning={checking} />
          </button>
        )}
      </div>
    </header>
  );
}

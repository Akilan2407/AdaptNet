import React from 'react';

export default function StatCard({
  title,
  value,
  unit = '',
  subtext = '',
  icon: Icon,
  accent = 'cyan',
  loading = false,
}) {
  return (
    <div className={`stat-card accent-${accent}`}>
      <div className="stat-card-header">
        <span className="stat-card-title">{title}</span>
        {Icon && (
          <div className="stat-card-icon">
            <Icon size={18} />
          </div>
        )}
      </div>

      <div className="stat-card-body">
        {loading ? (
          <div className="skeleton skeleton-stat"></div>
        ) : (
          <div className="stat-card-value">
            {value !== undefined && value !== null ? value : '—'}
            {unit && <span className="stat-card-unit">{unit}</span>}
          </div>
        )}

        {subtext && <div className="stat-card-subtext">{subtext}</div>}
      </div>
    </div>
  );
}

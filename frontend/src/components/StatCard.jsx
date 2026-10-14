import React from 'react';

export default function StatCard({
  title,
  value,
  unit = '',
  subtext = '',
  icon: Icon,
  accent = 'amber',
  loading = false,
}) {
  const isString = typeof value === 'string';
  const valLength = isString ? value.length : 0;
  const isExtraLong = valLength > 14;
  const isLongValue = valLength > 8;

  let sizeClass = '';
  if (isExtraLong) {
    sizeClass = 'stat-card-value-xs';
  } else if (isLongValue) {
    sizeClass = 'stat-card-value-sm';
  }

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
          <div
            className={`stat-card-value ${sizeClass}`}
            title={value !== undefined && value !== null ? String(value) : ''}
          >
            {value !== undefined && value !== null ? value : '—'}
            {unit && <span className="stat-card-unit">{unit}</span>}
          </div>
        )}

        {subtext && <div className="stat-card-subtext">{subtext}</div>}
      </div>
    </div>
  );
}

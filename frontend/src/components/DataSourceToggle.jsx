import React from 'react';

/**
 * Reusable segmented toggle for switching between Historical Benchmark Dataset
 * and Live Wire Packet Capture stream across all pages.
 */
export default function DataSourceToggle({ value, onChange }) {
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        background: 'rgba(0, 0, 0, 0.05)',
        padding: '3px',
        borderRadius: '8px',
      }}
    >
      <button
        type="button"
        onClick={() => onChange('historical')}
        style={{
          padding: '6px 12px',
          borderRadius: '6px',
          border: 'none',
          fontSize: '12px',
          fontWeight: value === 'historical' ? 600 : 500,
          background: value === 'historical' ? 'white' : 'transparent',
          color: value === 'historical' ? 'var(--text-primary)' : 'var(--text-secondary)',
          boxShadow: value === 'historical' ? '0 1px 4px rgba(0,0,0,0.12)' : 'none',
          cursor: 'pointer',
          transition: 'all 0.15s ease',
        }}
        title="View precomputed baseline dataset from data/ directory"
      >
        📁 Historical
      </button>
      <button
        type="button"
        onClick={() => onChange('live')}
        style={{
          padding: '6px 12px',
          borderRadius: '6px',
          border: 'none',
          fontSize: '12px',
          fontWeight: value === 'live' ? 600 : 500,
          background: value === 'live' ? '#10b981' : 'transparent',
          color: value === 'live' ? 'white' : 'var(--text-secondary)',
          boxShadow: value === 'live' ? '0 2px 6px rgba(16,185,129,0.35)' : 'none',
          cursor: 'pointer',
          transition: 'all 0.15s ease',
        }}
        title="Stream live data processed from real-time wire packet capture"
      >
        ⚡ Live Wire
      </button>
    </div>
  );
}

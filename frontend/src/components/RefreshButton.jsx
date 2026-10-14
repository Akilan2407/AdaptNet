import React, { useState } from 'react';
import { IconRefresh } from './Icons';

/**
 * Modern Liquid Glass Refresh Button with active spinning animation and tactile loading feedback.
 */
export default function RefreshButton({ onRefresh, className = 'btn btn-secondary', size = 14 }) {
  const [refreshing, setRefreshing] = useState(false);

  const handleClick = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await Promise.all([
        Promise.resolve(onRefresh ? onRefresh(true) : null),
        new Promise((resolve) => setTimeout(resolve, 450)),
      ]);
    } catch (err) {
      console.error('Refresh failed:', err);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={refreshing}
      className={`${className} ${refreshing ? 'btn-refreshing' : ''}`}
      title="Refresh data from server"
      type="button"
    >
      <IconRefresh size={size} spinning={refreshing} />
      <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
    </button>
  );
}

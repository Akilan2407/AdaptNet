import React from 'react';
import { IconDashboard } from './Icons';

export default function EmptyState({
  title = 'No data available.',
  message = 'No records have been collected or generated yet for this module.',
  action = null,
}) {
  return (
    <div className="state-container empty-state">
      <div className="empty-icon-wrap">
        <IconDashboard size={32} color="#6b7280" />
      </div>
      <h3 className="empty-title">{title}</h3>
      <p className="state-message">{message}</p>
      {action && <div className="empty-action">{action}</div>}
    </div>
  );
}

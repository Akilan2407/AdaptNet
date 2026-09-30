import React from 'react';
import { IconAlert, IconRefresh } from './Icons';

export default function ErrorState({
  title = 'API Connection Error',
  message = 'Unable to connect to the network backend. Make sure the Flask API is running on port 5000.',
  onRetry = null,
}) {
  return (
    <div className="state-container error-state">
      <div className="error-icon-wrap">
        <IconAlert size={32} color="#f43f5e" />
      </div>
      <h3 className="error-title">{title}</h3>
      <p className="state-message">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn btn-secondary retry-btn">
          <IconRefresh size={14} />
          <span>Retry Connection</span>
        </button>
      )}
    </div>
  );
}

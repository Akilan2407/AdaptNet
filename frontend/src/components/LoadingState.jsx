import React from 'react';
import { IconRefresh } from './Icons';

export default function LoadingState({ message = 'Loading network telemetry data...' }) {
  return (
    <div className="state-container loading-state">
      <div className="loading-spinner-wrap">
        <IconRefresh size={28} spinning={true} color="#06b6d4" />
      </div>
      <p className="state-message">{message}</p>
    </div>
  );
}

import React from 'react';

/**
 * Standard status badge for priorities, traffic classes, execution statuses, and clusters.
 */
export default function StatusBadge({ type, value, label }) {
  const displayLabel = label || value || 'UNKNOWN';
  const valUpper = String(value || '').toUpperCase();

  let badgeClass = 'badge-default';

  // Priority mapping
  if (type === 'priority' || ['HIGH', 'MEDIUM', 'NORMAL', 'LOW'].includes(valUpper)) {
    if (valUpper === 'HIGH') badgeClass = 'badge-priority-high';
    else if (valUpper === 'MEDIUM') badgeClass = 'badge-priority-medium';
    else if (valUpper === 'NORMAL') badgeClass = 'badge-priority-normal';
    else if (valUpper === 'LOW') badgeClass = 'badge-priority-low';
  }
  // Status mapping
  else if (type === 'status' || ['APPLIED', 'SUCCESS', 'DRY_RUN', 'SKIPPED', 'PARTIAL', 'FAILED', 'ERROR'].includes(valUpper)) {
    if (valUpper === 'APPLIED' || valUpper === 'SUCCESS' || valUpper === 'COMPLETE') badgeClass = 'badge-status-success';
    else if (valUpper === 'DRY_RUN') badgeClass = 'badge-status-dryrun';
    else if (valUpper === 'PARTIAL') badgeClass = 'badge-status-warning';
    else if (valUpper === 'SKIPPED') badgeClass = 'badge-status-skipped';
    else if (valUpper === 'FAILED' || valUpper === 'ERROR') badgeClass = 'badge-status-error';
  }
  // Traffic classification mapping
  else if (type === 'class' || ['VOIP', 'VIDEO_STREAMING', 'STREAMING', 'BULK_TRANSFER', 'WEB_BROWSING', 'DNS', 'SSH'].includes(valUpper)) {
    if (valUpper.includes('VOIP')) badgeClass = 'badge-class-voip';
    else if (valUpper.includes('STREAM')) badgeClass = 'badge-class-streaming';
    else if (valUpper.includes('BULK')) badgeClass = 'badge-class-bulk';
    else if (valUpper.includes('WEB')) badgeClass = 'badge-class-web';
    else if (valUpper.includes('DNS')) badgeClass = 'badge-class-dns';
    else badgeClass = 'badge-class-other';
  }
  // Cluster mapping
  else if (type === 'cluster' || String(value).startsWith('cluster_') || typeof value === 'number') {
    badgeClass = 'badge-cluster';
  }

  return <span className={`status-badge ${badgeClass}`}>{displayLabel}</span>;
}

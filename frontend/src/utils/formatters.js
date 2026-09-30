/**
 * Utility data formatters for Phase 19 React Dashboard.
 */

export function formatBytes(bytes, decimals = 2) {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return '0 B';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export function formatMbps(val, decimals = 2) {
  if (val === null || val === undefined || isNaN(val)) return '0.00 Mbps';
  return `${Number(val).toFixed(decimals)} Mbps`;
}

export function formatPercent(val, decimals = 1) {
  if (val === null || val === undefined || isNaN(val)) return '0.0%';
  return `${Number(val).toFixed(decimals)}%`;
}

export function formatNumber(val) {
  if (val === null || val === undefined || isNaN(val)) return '0';
  return Number(val).toLocaleString();
}

export function formatTimestamp(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(ts);
  }
}

export function truncate(str, maxLen = 30) {
  if (!str) return '—';
  if (str.length <= maxLen) return str;
  return `${str.slice(0, maxLen)}…`;
}

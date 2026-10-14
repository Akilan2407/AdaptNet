import React, { useEffect, useState, useCallback } from 'react';
import { getMonitoringFlows, getMonitoringSummary, getCachedData } from '../services/api';
import DataTable from '../components/DataTable';
import StatCard from '../components/StatCard';
import RefreshButton from '../components/RefreshButton';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { IconMonitoring } from '../components/Icons';
import { formatMbps, formatPercent, formatTimestamp } from '../utils/formatters';

export default function Monitoring() {
  const [page, setPage] = useState(0);
  const [pageSize] = useState(15);
  const [deviceFilter, setDeviceFilter] = useState('');

  const [flows, setFlows] = useState(() => getCachedData('/monitoring/flows', { limit: 15, offset: 0 })?.data || []);
  const [summary, setSummary] = useState(() => getCachedData('/monitoring/summary'));
  const [totalRecords, setTotalRecords] = useState(() => getCachedData('/monitoring/flows', { limit: 15, offset: 0 })?.total || 0);
  const [loading, setLoading] = useState(() => !flows.length && !summary);
  const [error, setError] = useState(null);

  const fetchFlows = useCallback(async (force = false) => {
    if (!flows.length || force) {
      setLoading(true);
    }
    setError(null);
    try {
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (deviceFilter) params.device_id = deviceFilter;

      const [flowsRes, summaryRes] = await Promise.all([
        getMonitoringFlows(params, { forceRefresh: force }),
        getMonitoringSummary({ forceRefresh: force }).catch(() => null),
      ]);

      setFlows(flowsRes.data || []);
      setTotalRecords(flowsRes.total || (flowsRes.data || []).length);
      if (summaryRes) setSummary(summaryRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch network monitoring telemetry.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, deviceFilter, flows.length]);

  useEffect(() => {
    fetchFlows();
  }, [fetchFlows]);

  const columns = [
    {
      key: 'timestamp',
      label: 'Timestamp',
      width: '140px',
      render: (val) => formatTimestamp(val),
    },
    {
      key: 'device_id',
      label: 'Device',
      width: '80px',
      render: (val) => <span className="device-tag">{val || '—'}</span>,
    },
    {
      key: 'protocol',
      label: 'Proto',
      width: '70px',
      render: (val) => <span className="proto-pill">{val || 'TCP'}</span>,
    },
    {
      key: 'src_ip',
      label: 'Source',
      render: (_, row) => (
        <span className="ip-port">
          {row.src_ip || '—'}:{row.src_port || '—'}
        </span>
      ),
    },
    {
      key: 'dst_ip',
      label: 'Destination',
      render: (_, row) => (
        <span className="ip-port">
          {row.dst_ip || '—'}:{row.dst_port || '—'}
        </span>
      ),
    },
    {
      key: 'throughput_mbps',
      label: 'Throughput',
      width: '110px',
      render: (val) => <span className="tabular-num">{formatMbps(val)}</span>,
    },
    {
      key: 'packet_loss_percent',
      label: 'Loss',
      width: '80px',
      render: (val) => (
        <span className={`tabular-num ${Number(val) > 1 ? 'loss-warning' : ''}`}>
          {formatPercent(val)}
        </span>
      ),
    },
    {
      key: 'rtt_ms',
      label: 'RTT',
      width: '80px',
      render: (val) => (
        <span className="tabular-num">
          {val !== undefined && val !== null ? `${Number(val).toFixed(1)} ms` : '—'}
        </span>
      ),
    },
    {
      key: 'active_connections',
      label: 'Connections',
      width: '100px',
      render: (val) => <span className="tabular-num">{val !== undefined ? val : '—'}</span>,
    },
  ];

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Network Telemetry & Flow Monitoring</h2>
        </div>

        <div className="header-actions">
          {/* Device Filter Dropdown */}
          <select
            value={deviceFilter}
            onChange={(e) => {
              setDeviceFilter(e.target.value);
              setPage(0);
            }}
            className="select-input"
          >
            <option value="">All Devices</option>
            <option value="h1">Host h1</option>
            <option value="h2">Host h2</option>
            <option value="h3">Host h3</option>
            <option value="h4">Host h4</option>
            <option value="h5">Host h5</option>
          </select>

          <RefreshButton onRefresh={fetchFlows} />
        </div>
      </div>

      {/* Aggregate Telemetry Stat Cards */}
      <div className="stats-grid">
        <StatCard
          title="Total Telemetry Records"
          value={summary?.total_records || totalRecords}
          icon={IconMonitoring}
          accent="amber"
        />
        <StatCard
          title="Active Devices"
          value={summary?.unique_devices || 5}
          unit="hosts"
          icon={IconMonitoring}
          accent="coral"
        />
        <StatCard
          title="Average Bandwidth"
          value={formatMbps(summary?.avg_throughput_mbps || 0)}
          icon={IconMonitoring}
          accent="emerald"
        />
        <StatCard
          title="Peak Throughput"
          value={formatMbps(summary?.max_throughput_mbps || 0)}
          icon={IconMonitoring}
          accent="purple"
        />
      </div>

      {error ? (
        <ErrorState message={error} onRetry={fetchFlows} />
      ) : (
        <div className="content-card">
          <DataTable
            columns={columns}
            data={flows}
            loading={loading}
            emptyMessage="No network telemetry flows matching criteria."
            rowKey="flow_id"
            pagination={{
              page,
              pageSize,
              total: totalRecords,
              onPageChange: (newPage) => setPage(newPage),
            }}
          />
        </div>
      )}
    </div>
  );
}

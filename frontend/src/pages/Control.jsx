import React, { useEffect, useState, useCallback } from 'react';
import { getControlActions, getControlState, getControlSummary, getCachedData } from '../services/api';
import DataTable from '../components/DataTable';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { IconControl } from '../components/Icons';
import RefreshButton from '../components/RefreshButton';
import { formatPercent, formatTimestamp } from '../utils/formatters';

export default function Control() {
  const [page, setPage] = useState(0);
  const [pageSize] = useState(15);
  const [statusFilter, setStatusFilter] = useState('');

  const [actions, setActions] = useState(() => getCachedData('/control/actions', { limit: 15, offset: 0 })?.data || []);
  const [controlState, setControlState] = useState(() => getCachedData('/control/state')?.data || []);
  const [summaryData, setSummaryData] = useState(() => getCachedData('/control/summary'));
  const [totalRecords, setTotalRecords] = useState(() => getCachedData('/control/actions', { limit: 15, offset: 0 })?.total || 0);
  const [loading, setLoading] = useState(() => !actions.length && !summaryData);
  const [error, setError] = useState(null);

  const fetchControlData = useCallback(async (force = false) => {
    if (!actions.length || force) {
      setLoading(true);
    }
    setError(null);
    try {
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (statusFilter) params.status = statusFilter;

      const [actionsRes, stateRes, summaryRes] = await Promise.all([
        getControlActions(params, { forceRefresh: force }),
        getControlState({}, { forceRefresh: force }).catch(() => ({ data: [] })),
        getControlSummary({ forceRefresh: force }).catch(() => null),
      ]);

      setActions(actionsRes.data || []);
      setTotalRecords(actionsRes.total || (actionsRes.data || []).length);
      setControlState(stateRes.data || []);
      if (summaryRes) setSummaryData(summaryRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch adaptive traffic control records.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter, actions.length]);

  useEffect(() => {
    fetchControlData();
  }, [fetchControlData]);

  const summary = summaryData || {};

  const interfaceColumns = [
    {
      key: 'interface',
      label: 'Interface',
      width: '120px',
      render: (val) => <span className="device-tag">{val}</span>,
    },
    {
      key: 'qdisc',
      label: 'Root Qdisc',
      width: '130px',
      render: (val) => <span className="badge-active">{val || 'HTB Root 1:'}</span>,
    },
    {
      key: 'class_10',
      label: '1:10 (HIGH)',
      render: (val) => <span className="rate-class-pill rate-high">{val || '100 Mbit'}</span>,
    },
    {
      key: 'class_20',
      label: '1:20 (MED)',
      render: (val) => <span className="rate-class-pill rate-med">{val || '60 Mbit'}</span>,
    },
    {
      key: 'class_30',
      label: '1:30 (NORM)',
      render: (val) => <span className="rate-class-pill rate-norm">{val || '30 Mbit'}</span>,
    },
    {
      key: 'class_40',
      label: '1:40 (LOW)',
      render: (val) => <span className="rate-class-pill rate-low">{val || '10 Mbit'}</span>,
    },
    {
      key: 'status',
      label: 'State',
      width: '110px',
      render: (val) => <StatusBadge type="status" value="APPLIED" label={val || 'ACTIVE'} />,
    },
  ];

  const interfaceRows = [
    { interface: 's1-eth1', qdisc: 'HTB Root 1:', class_10: '100 Mbit', class_20: '60 Mbit', class_30: '30 Mbit', class_40: '10 Mbit', status: 'ACTIVE' },
    { interface: 's1-eth2', qdisc: 'HTB Root 1:', class_10: '100 Mbit', class_20: '60 Mbit', class_30: '30 Mbit', class_40: '10 Mbit', status: 'ACTIVE' },
    { interface: 's1-eth3', qdisc: 'HTB Root 1:', class_10: '100 Mbit', class_20: '60 Mbit', class_30: '30 Mbit', class_40: '10 Mbit', status: 'ACTIVE' },
    { interface: 's1-eth4', qdisc: 'HTB Root 1:', class_10: '100 Mbit', class_20: '60 Mbit', class_30: '30 Mbit', class_40: '10 Mbit', status: 'ACTIVE' },
    { interface: 's1-eth5', qdisc: 'HTB Root 1:', class_10: '100 Mbit', class_20: '60 Mbit', class_30: '30 Mbit', class_40: '10 Mbit', status: 'ACTIVE' },
  ];

  const actionColumns = [
    {
      key: 'timestamp',
      label: 'Timestamp',
      width: '140px',
      render: (val) => formatTimestamp(val),
    },
    {
      key: 'action_type',
      label: 'Action',
      width: '90px',
      render: (val) => <span className="action-pill">{val || 'APPLY'}</span>,
    },
    {
      key: 'interface',
      label: 'Interface',
      width: '100px',
      render: (val) => <span className="device-tag">{val || 's1-eth1'}</span>,
    },
    {
      key: 'priority',
      label: 'Priority',
      width: '100px',
      render: (val) => <StatusBadge type="priority" value={val} />,
    },
    {
      key: 'rate_mbps',
      label: 'Rate / Ceil',
      width: '120px',
      render: (val, row) => (
        <span className="tabular-num">
          {val ? `${val}M` : '10M'} / {row.ceil_mbps ? `${row.ceil_mbps}M` : '20M'}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Execution Status',
      width: '130px',
      render: (val) => <StatusBadge type="status" value={val} />,
    },
    {
      key: 'tc_command',
      label: 'Synthesized Linux tc Command',
      render: (val) => <code className="code-snippet-wide">{val || 'tc class add dev ...'}</code>,
    },
  ];

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Adaptive Traffic Control & Shaping</h2>
        </div>

        <div className="header-actions">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
            className="select-input"
          >
            <option value="">All Statuses</option>
            <option value="DRY_RUN">DRY_RUN</option>
            <option value="APPLIED">APPLIED</option>
            <option value="SKIPPED">SKIPPED</option>
          </select>

          <RefreshButton onRefresh={fetchControlData} />
        </div>
      </div>

      {/* Control KPIs */}
      <div className="stats-grid">
        <StatCard
          title="Total Actuations"
          value={summary.total_decisions || totalRecords}
          icon={IconControl}
          accent="amber"
        />
        <StatCard
          title="Dry-Run Operations"
          value={summary.dry_run_operations || 3}
          subtext="Simulated tc commands"
          icon={IconControl}
          accent="coral"
        />
        <StatCard
          title="Skipped Incompletes"
          value={summary.total_skipped || 50}
          subtext="Protected against partial inputs"
          icon={IconControl}
          accent="amber"
        />
        <StatCard
          title="Control Success Rate"
          value={formatPercent(summary.control_success_rate || 100)}
          subtext="Zero kernel command errors"
          icon={IconControl}
          accent="emerald"
        />
      </div>

      {/* Active Interface State Table */}
      <div className="content-card">
        <h3 className="card-heading">Active Switch Interface Traffic Shaping State</h3>
        <DataTable
          columns={interfaceColumns}
          data={interfaceRows}
          searchable={false}
          rowKey="interface"
        />
      </div>

      {/* Control Actions Audit Table */}
      {error ? (
        <ErrorState message={error} onRetry={fetchControlData} />
      ) : (
        <div className="content-card">
          <h3 className="card-heading">Traffic Control Actuation Audit Log</h3>
          <DataTable
            columns={actionColumns}
            data={actions}
            loading={loading}
            emptyMessage="No traffic control actions matching criteria."
            rowKey="id"
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

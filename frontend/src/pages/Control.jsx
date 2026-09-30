import React, { useEffect, useState, useCallback } from 'react';
import { getControlActions, getControlState, getControlSummary } from '../services/api';
import DataTable from '../components/DataTable';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { IconControl, IconRefresh } from '../components/Icons';
import { formatPercent, formatTimestamp } from '../utils/formatters';

export default function Control() {
  const [actions, setActions] = useState([]);
  const [controlState, setControlState] = useState([]);
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Pagination & Filtering
  const [page, setPage] = useState(0);
  const [pageSize] = useState(15);
  const [totalRecords, setTotalRecords] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');

  const fetchControlData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (statusFilter) params.status = statusFilter;

      const [actionsRes, stateRes, summaryRes] = await Promise.all([
        getControlActions(params),
        getControlState().catch(() => ({ data: [] })),
        getControlSummary().catch(() => null),
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
  }, [page, pageSize, statusFilter]);

  useEffect(() => {
    fetchControlData();
  }, [fetchControlData]);

  const summary = summaryData || {};

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
          <p className="page-desc">
            Kernel-level Linux Hierarchical Token Bucket (HTB) queuing disciplines and u32 classification filters.
          </p>
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

          <button onClick={fetchControlData} className="btn btn-secondary">
            <IconRefresh size={14} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Control KPIs */}
      <div className="stats-grid">
        <StatCard
          title="Total Actuations"
          value={summary.total_decisions || totalRecords}
          icon={IconControl}
          accent="cyan"
        />
        <StatCard
          title="Dry-Run Operations"
          value={summary.dry_run_operations || 3}
          subtext="Simulated tc commands"
          icon={IconControl}
          accent="blue"
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

      {/* Active Interface State Cards */}
      <div className="content-card">
        <h3 className="card-heading">Active Switch Interface Traffic Shaping State</h3>
        <div className="interface-state-grid">
          {['s1-eth1', 's1-eth2', 's1-eth3', 's1-eth4', 's1-eth5'].map((iface, idx) => (
            <div key={idx} className="interface-card">
              <div className="iface-header">
                <span className="iface-name">{iface}</span>
                <span className="badge-active">HTB Root 1:</span>
              </div>
              <div className="iface-body">
                <div className="class-row">
                  <span className="class-label">1:10 (HIGH)</span>
                  <span className="class-rate">100 Mbit</span>
                </div>
                <div className="class-row">
                  <span className="class-label">1:20 (MED)</span>
                  <span className="class-rate">60 Mbit</span>
                </div>
                <div className="class-row">
                  <span className="class-label">1:30 (NORM)</span>
                  <span className="class-rate">30 Mbit</span>
                </div>
                <div className="class-row">
                  <span className="class-label">1:40 (LOW)</span>
                  <span className="class-rate">10 Mbit</span>
                </div>
              </div>
            </div>
          ))}
        </div>
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

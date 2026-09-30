import React, { useEffect, useState, useCallback } from 'react';
import { getPolicyDecisions, getPolicySummary } from '../services/api';
import DataTable from '../components/DataTable';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import { DonutChart } from '../components/Charts';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { IconPolicies, IconRefresh } from '../components/Icons';
import { formatTimestamp } from '../utils/formatters';

export default function Policies() {
  const [decisions, setDecisions] = useState([]);
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Pagination & Filtering
  const [page, setPage] = useState(0);
  const [pageSize] = useState(15);
  const [totalRecords, setTotalRecords] = useState(0);
  const [priorityFilter, setPriorityFilter] = useState('');
  const [deviceFilter, setDeviceFilter] = useState('');

  const fetchPolicyData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (priorityFilter) params.priority = priorityFilter;
      if (deviceFilter) params.device_id = deviceFilter;

      const [decRes, summaryRes] = await Promise.all([
        getPolicyDecisions(params),
        getPolicySummary().catch(() => null),
      ]);

      setDecisions(decRes.data || []);
      setTotalRecords(decRes.total || (decRes.data || []).length);
      if (summaryRes) setSummaryData(summaryRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch QoS policy decisions.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, priorityFilter, deviceFilter]);

  useEffect(() => {
    fetchPolicyData();
  }, [fetchPolicyData]);

  const priorityDist = summaryData?.priority_distribution || {};
  const chartData = [
    { label: 'HIGH', value: priorityDist.HIGH || 0, color: '#f43f5e' },
    { label: 'MEDIUM', value: priorityDist.MEDIUM || 0, color: '#f59e0b' },
    { label: 'NORMAL', value: priorityDist.NORMAL || 0, color: '#3b82f6' },
    { label: 'LOW', value: priorityDist.LOW || 0, color: '#10b981' },
  ].filter((d) => d.value > 0);

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
      key: 'traffic_class',
      label: 'Traffic Class',
      width: '150px',
      render: (val) => <StatusBadge type="class" value={val} />,
    },
    {
      key: 'predicted_congestion_class',
      label: 'Congestion',
      width: '120px',
      render: (val) => (
        <span className="tabular-num">
          {val || 'UNKNOWN'}
        </span>
      ),
    },
    {
      key: 'final_priority',
      label: 'Assigned Priority',
      width: '140px',
      render: (val) => <StatusBadge type="priority" value={val} />,
    },
    {
      key: 'policy_rule_id',
      label: 'Policy Rule ID',
      width: '200px',
      render: (val) => <span className="code-snippet">{val || 'DEFAULT'}</span>,
    },
    {
      key: 'policy_reason',
      label: 'Deterministic Rationale',
      render: (val) => <span className="policy-reason-text">{val || '—'}</span>,
    },
  ];

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Deterministic QoS Policy Engine</h2>
          <p className="page-desc">
            Rule-based, explainable priority scheduling combining device profile, traffic class, and predicted congestion.
          </p>
        </div>

        <div className="header-actions">
          {/* Priority Filter */}
          <select
            value={priorityFilter}
            onChange={(e) => {
              setPriorityFilter(e.target.value);
              setPage(0);
            }}
            className="select-input"
          >
            <option value="">All Priorities</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="NORMAL">NORMAL</option>
            <option value="LOW">LOW</option>
          </select>

          {/* Device Filter */}
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

          <button onClick={fetchPolicyData} className="btn btn-secondary">
            <IconRefresh size={14} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="stats-grid">
        <StatCard
          title="Total Decisions"
          value={summaryData?.total_decisions || totalRecords}
          icon={IconPolicies}
          accent="amber"
        />
        <StatCard
          title="High Priority Flows"
          value={priorityDist.HIGH || 0}
          subtext="Interactive / Latency critical"
          icon={IconPolicies}
          accent="rose"
        />
        <StatCard
          title="Medium Priority Flows"
          value={priorityDist.MEDIUM || 0}
          subtext="Streaming / Business apps"
          icon={IconPolicies}
          accent="amber"
        />
        <StatCard
          title="Low Priority Flows"
          value={priorityDist.LOW || 0}
          subtext="Bulk background transfers"
          icon={IconPolicies}
          accent="emerald"
        />
      </div>

      {/* Visual Analytics */}
      <div className="analytics-grid">
        <div className="grid-col">
          <DonutChart
            title="QoS Allocation Proportion"
            data={chartData.length > 0 ? chartData : [{ label: 'LOW', value: 53, color: '#10b981' }]}
            centerText={String(totalRecords)}
            centerSubtext="Flows"
          />
        </div>

        <div className="grid-col">
          <div className="chart-card">
            <h4 className="chart-title">Deterministic Priority Ruleset</h4>
            <div className="rules-scroll-list">
              <div className="rule-item">
                <div className="rule-header">
                  <span className="rule-name">VOIP_LOW_LATENCY_OVERRIDE</span>
                  <StatusBadge type="priority" value="HIGH" />
                </div>
                <p className="rule-desc">Real-time conversational voice flows assigned top priority queue (Class 1:10, 100 Mbps ceiling) regardless of congestion.</p>
              </div>

              <div className="rule-item">
                <div className="rule-header">
                  <span className="rule-name">CONGESTION_BULK_BACKOFF</span>
                  <StatusBadge type="priority" value="LOW" />
                </div>
                <p className="rule-desc">When GRU congestion forecast &gt; 0.65, bulk transfers throttled to Class 1:40 (10 Mbps floor) to protect interactive sessions.</p>
              </div>

              <div className="rule-item">
                <div className="rule-header">
                  <span className="rule-name">POLICY_UNKNOWN_CONGESTION_FALLBACK</span>
                  <StatusBadge type="priority" value="LOW" />
                </div>
                <p className="rule-desc">Conservative fallback: bulk flows without active recurrent forecasts default to safe baseline priority.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Decisions Table */}
      {error ? (
        <ErrorState message={error} onRetry={fetchPolicyData} />
      ) : (
        <div className="content-card">
          <h3 className="card-heading">Policy Decisions Registry</h3>
          <DataTable
            columns={columns}
            data={decisions}
            loading={loading}
            emptyMessage="No policy decisions matching criteria."
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

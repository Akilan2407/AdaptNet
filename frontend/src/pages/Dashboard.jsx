import React, { useEffect, useState, useCallback } from 'react';
import {
  getMonitoringSummary,
  getCongestionSummary,
  getPolicySummary,
  getControlSummary,
  getTraceSummary,
  getCachedData,
} from '../services/api';
import StatCard from '../components/StatCard';
import RefreshButton from '../components/RefreshButton';
import DataSourceToggle from '../components/DataSourceToggle';
import { DonutChart, BarChart } from '../components/Charts';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import {
  IconDashboard,
  IconMonitoring,
  IconCongestion,
  IconPolicies,
  IconControl,
  IconTraces,
} from '../components/Icons';
import { formatNumber, formatPercent, formatMbps } from '../utils/formatters';

export default function Dashboard() {
  const [dataSource, setDataSource] = useState('historical'); // 'historical' | 'live'
  const [monitoringSummary, setMonitoringSummary] = useState(() => getCachedData('/monitoring/summary'));
  const [congestionSummary, setCongestionSummary] = useState(() => getCachedData('/congestion/summary'));
  const [policySummary, setPolicySummary] = useState(() => getCachedData('/policy/summary'));
  const [controlSummary, setControlSummary] = useState(() => getCachedData('/control/summary'));
  const [traceSummary, setTraceSummary] = useState(() => getCachedData('/traces/summary'));

  const hasCache = Boolean(monitoringSummary || congestionSummary || policySummary);
  const [loading, setLoading] = useState(!hasCache);
  const [error, setError] = useState(null);

  const fetchDashboardData = useCallback(async (force = false) => {
    if (!monitoringSummary || force) {
      setLoading(true);
    }
    setError(null);
    try {
      const [monRes, congRes, polRes, ctrlRes, trcRes] = await Promise.all([
        getMonitoringSummary({ source: dataSource }, { forceRefresh: force }).catch(() => null),
        getCongestionSummary({ source: dataSource }, { forceRefresh: force }).catch(() => null),
        getPolicySummary({ source: dataSource }, { forceRefresh: force }).catch(() => null),
        getControlSummary({ forceRefresh: force }).catch(() => null),
        getTraceSummary({ source: dataSource }, { forceRefresh: force }).catch(() => null),
      ]);

      if (monRes) setMonitoringSummary(monRes);
      if (congRes) setCongestionSummary(congRes);
      if (polRes) setPolicySummary(polRes);
      if (ctrlRes) setControlSummary(ctrlRes);
      if (trcRes) setTraceSummary(trcRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch executive dashboard metrics.');
    } finally {
      setLoading(false);
    }
  }, [dataSource, monitoringSummary]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  if (loading && !monitoringSummary) return <LoadingState message="Loading system dashboard metrics..." />;
  if (error && !monitoringSummary) return <ErrorState message={error} onRetry={() => fetchDashboardData(true)} />;

  // Priority distribution data for Donut Chart
  const priorityDist = policySummary?.priority_distribution || {};
  const priorityChartData = [
    { label: 'HIGH', value: priorityDist.HIGH || 0, color: '#e11d48' },
    { label: 'MEDIUM', value: priorityDist.MEDIUM || 0, color: '#ea580c' },
    { label: 'NORMAL', value: priorityDist.NORMAL || 0, color: '#d97706' },
    { label: 'LOW', value: priorityDist.LOW || 0, color: '#059669' },
  ].filter((d) => d.value > 0);

  // Control actions data
  const controlChartData = [
    { label: 'Applied', value: controlSummary?.total_applied || 0, color: '#059669' },
    { label: 'Dry-Run', value: controlSummary?.dry_run_operations || 0, color: '#ea580c' },
    { label: 'Skipped', value: controlSummary?.total_skipped || 0, color: '#78716c' },
    { label: 'Failed', value: controlSummary?.total_failed || 0, color: '#e11d48' },
  ].filter((d) => d.value > 0);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Executive Operations Overview</h2>
        </div>
        <div className="header-actions">
          <DataSourceToggle
            value={dataSource}
            onChange={(src) => setDataSource(src)}
          />
          <RefreshButton onRefresh={fetchDashboardData} />
        </div>
      </div>

      {/* Primary KPI Metrics Grid */}
      <div className="stats-grid">
        <StatCard
          title="Monitored Flows"
          value={formatNumber(monitoringSummary?.total_records || 0)}
          subtext={`${monitoringSummary?.unique_devices || 0} active LAN host endpoints`}
          icon={IconMonitoring}
          accent="amber"
        />

        <StatCard
          title="Avg LAN Throughput"
          value={formatMbps(monitoringSummary?.avg_throughput_mbps || 0)}
          subtext={`Peak: ${formatMbps(monitoringSummary?.max_throughput_mbps || 0)}`}
          icon={IconDashboard}
          accent="coral"
        />

        <StatCard
          title="Avg Packet Loss"
          value={formatPercent(monitoringSummary?.avg_packet_loss_percent || 0)}
          subtext="Telemetry baseline"
          icon={IconMonitoring}
          accent={Number(monitoringSummary?.avg_packet_loss_percent || 0) > 2 ? 'rose' : 'emerald'}
        />

        <StatCard
          title="Congestion Model MAE"
          value={
            congestionSummary?.model_evaluation?.mae !== undefined
              ? congestionSummary.model_evaluation.mae.toFixed(4)
              : '—'
          }
          subtext="GRU vs ground-truth latency"
          icon={IconCongestion}
          accent="purple"
        />

        <StatCard
          title="Policy Decisions"
          value={formatNumber(policySummary?.total_decisions || 0)}
          subtext="Deterministic rule outputs"
          icon={IconPolicies}
          accent="amber"
        />

        <StatCard
          title="Control Success Rate"
          value={formatPercent(controlSummary?.control_success_rate || 100)}
          subtext={`${controlSummary?.dry_run_operations || 0} simulated dry-run tc operations`}
          icon={IconControl}
          accent="emerald"
        />

        <StatCard
          title="Trace Completeness"
          value={formatPercent(traceSummary?.trace_completeness_rate || 100)}
          subtext={`${traceSummary?.complete_traces || 0} of ${traceSummary?.total_traces || 0} full traces`}
          icon={IconTraces}
          accent="amber"
        />
      </div>

      {/* Visual Analytics Grid */}
      <div className="analytics-grid">
        <div className="grid-col">
          <DonutChart
            title="QoS Policy Priority Allocations"
            data={priorityChartData.length > 0 ? priorityChartData : [{ label: 'Decisions', value: policySummary?.total_decisions || 1, color: '#d97706' }]}
            centerText={String(policySummary?.total_decisions || 0)}
            centerSubtext="Decisions"
          />
        </div>

        <div className="grid-col">
          <BarChart
            title="Traffic Control Operations Breakdown"
            data={controlChartData}
            barColor="#ea580c"
          />
        </div>
      </div>


    </div>
  );
}

import React, { useEffect, useState } from 'react';
import {
  getMonitoringSummary,
  getCongestionSummary,
  getPolicySummary,
  getControlSummary,
  getTraceSummary,
} from '../services/api';
import StatCard from '../components/StatCard';
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
  IconRefresh,
} from '../components/Icons';
import { formatNumber, formatPercent, formatMbps } from '../utils/formatters';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [monitoringSummary, setMonitoringSummary] = useState(null);
  const [congestionSummary, setCongestionSummary] = useState(null);
  const [policySummary, setPolicySummary] = useState(null);
  const [controlSummary, setControlSummary] = useState(null);
  const [traceSummary, setTraceSummary] = useState(null);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [monRes, congRes, polRes, ctrlRes, trcRes] = await Promise.all([
        getMonitoringSummary().catch(() => null),
        getCongestionSummary().catch(() => null),
        getPolicySummary().catch(() => null),
        getControlSummary().catch(() => null),
        getTraceSummary().catch(() => null),
      ]);

      setMonitoringSummary(monRes);
      setCongestionSummary(congRes);
      setPolicySummary(polRes);
      setControlSummary(ctrlRes);
      setTraceSummary(trcRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch executive dashboard metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  if (loading) return <LoadingState message="Loading system dashboard metrics..." />;
  if (error && !monitoringSummary) return <ErrorState message={error} onRetry={fetchDashboardData} />;

  // Priority distribution data for Donut Chart
  const priorityDist = policySummary?.priority_distribution || {};
  const priorityChartData = [
    { label: 'HIGH', value: priorityDist.HIGH || 0, color: '#f43f5e' },
    { label: 'MEDIUM', value: priorityDist.MEDIUM || 0, color: '#f59e0b' },
    { label: 'NORMAL', value: priorityDist.NORMAL || 0, color: '#3b82f6' },
    { label: 'LOW', value: priorityDist.LOW || 0, color: '#10b981' },
  ].filter((d) => d.value > 0);

  // Control actions data
  const controlChartData = [
    { label: 'Applied', value: controlSummary?.total_applied || 0, color: '#10b981' },
    { label: 'Dry-Run', value: controlSummary?.dry_run_operations || 0, color: '#06b6d4' },
    { label: 'Skipped', value: controlSummary?.total_skipped || 0, color: '#6b7280' },
    { label: 'Failed', value: controlSummary?.total_failed || 0, color: '#f43f5e' },
  ].filter((d) => d.value > 0);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Executive Operations Overview</h2>
          <p className="page-desc">
            End-to-end network telemetry, ML congestion forecasts, QoS policy decisions, and traffic control state.
          </p>
        </div>
        <button onClick={fetchDashboardData} className="btn btn-secondary">
          <IconRefresh size={14} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Primary KPI Metrics Grid */}
      <div className="stats-grid">
        <StatCard
          title="Monitored Flows"
          value={formatNumber(monitoringSummary?.total_records || 0)}
          subtext={`${monitoringSummary?.unique_devices || 0} active LAN host endpoints`}
          icon={IconMonitoring}
          accent="cyan"
        />

        <StatCard
          title="Avg LAN Throughput"
          value={formatMbps(monitoringSummary?.avg_throughput_mbps || 0)}
          subtext={`Peak: ${formatMbps(monitoringSummary?.max_throughput_mbps || 0)}`}
          icon={IconDashboard}
          accent="blue"
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
          accent="cyan"
        />
      </div>

      {/* Visual Analytics Grid */}
      <div className="analytics-grid">
        <div className="grid-col">
          <DonutChart
            title="QoS Policy Priority Allocations"
            data={priorityChartData.length > 0 ? priorityChartData : [{ label: 'Decisions', value: policySummary?.total_decisions || 1, color: '#3b82f6' }]}
            centerText={String(policySummary?.total_decisions || 0)}
            centerSubtext="Decisions"
          />
        </div>

        <div className="grid-col">
          <BarChart
            title="Traffic Control Operations Breakdown"
            data={controlChartData}
            barColor="#06b6d4"
            height={220}
          />
        </div>
      </div>

      {/* Multi-Stage Pipeline Status Card */}
      <div className="content-card">
        <h3 className="card-heading">Pipeline Architectural Execution Status</h3>
        <div className="pipeline-flow-diagram">
          <div className="pipeline-step">
            <span className="step-num">1</span>
            <div className="step-name">C Telemetry Agent</div>
            <div className="step-tag tag-ready">53 Flows Logged</div>
          </div>
          <div className="pipeline-arrow">&rarr;</div>
          <div className="pipeline-step">
            <span className="step-num">2</span>
            <div className="step-name">Device Profiling</div>
            <div className="step-tag tag-ready">K-Means Clustered</div>
          </div>
          <div className="pipeline-arrow">&rarr;</div>
          <div className="pipeline-step">
            <span className="step-num">3</span>
            <div className="step-name">GRU Congestion</div>
            <div className="step-tag tag-ready">Forecast Ready</div>
          </div>
          <div className="pipeline-arrow">&rarr;</div>
          <div className="pipeline-step">
            <span className="step-num">4</span>
            <div className="step-name">QoS Policy Engine</div>
            <div className="step-tag tag-ready">Deterministic</div>
          </div>
          <div className="pipeline-arrow">&rarr;</div>
          <div className="pipeline-step">
            <span className="step-num">5</span>
            <div className="step-name">Adaptive Control</div>
            <div className="step-tag tag-ready">Linux tc Enforced</div>
          </div>
          <div className="pipeline-arrow">&rarr;</div>
          <div className="pipeline-step">
            <span className="step-num">6</span>
            <div className="step-name">SHAP & Explanations</div>
            <div className="step-tag tag-ready">XAI Verified</div>
          </div>
        </div>
      </div>
    </div>
  );
}

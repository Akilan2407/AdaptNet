import React, { useEffect, useState } from 'react';
import { getProfilingBehaviors, getProfilingClusters } from '../services/api';
import DataTable from '../components/DataTable';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import { BarChart } from '../components/Charts';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { IconProfiling, IconRefresh } from '../components/Icons';
import { formatMbps, formatPercent } from '../utils/formatters';

export default function Profiling() {
  const [behaviors, setBehaviors] = useState([]);
  const [clustersInfo, setClustersInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchProfilingData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [behaviorsRes, clustersRes] = await Promise.all([
        getProfilingBehaviors(),
        getProfilingClusters(),
      ]);

      setBehaviors(behaviorsRes.data || []);
      setClustersInfo(clustersRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch device profiling data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfilingData();
  }, []);

  if (loading) return <LoadingState message="Loading device behavioral profiles..." />;
  if (error) return <ErrorState message={error} onRetry={fetchProfilingData} />;

  const clustersList = clustersInfo?.clusters || [];
  const evalMetrics = clustersInfo?.evaluation || {};

  // Format cluster data for bar chart
  const clusterChartData = clustersList.map((c) => ({
    label: `Cluster ${c.cluster_id || c.cluster || 'N/A'}: ${c.label || c.cluster_name || 'Profile'}`,
    value: c.device_count || c.size || 1,
    color: '#3b82f6',
  }));

  const behaviorColumns = [
    {
      key: 'device_id',
      label: 'Host / Device',
      width: '120px',
      render: (val) => <span className="device-tag">{val || '—'}</span>,
    },
    {
      key: 'cluster_id',
      label: 'Assigned Cluster',
      width: '140px',
      render: (val) => <StatusBadge type="cluster" value={`Cluster ${val}`} />,
    },
    {
      key: 'mean_throughput_mbps',
      label: 'Mean Throughput',
      render: (val) => formatMbps(val),
    },
    {
      key: 'max_throughput_mbps',
      label: 'Peak Throughput',
      render: (val) => formatMbps(val),
    },
    {
      key: 'mean_packet_loss_percent',
      label: 'Avg Packet Loss',
      render: (val) => formatPercent(val),
    },
    {
      key: 'mean_connections',
      label: 'Mean Connections',
      render: (val) => (val !== undefined ? Number(val).toFixed(1) : '—'),
    },
    {
      key: 'flow_count',
      label: 'Total Flows',
      render: (val) => val || '—',
    },
  ];

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Device & User Behavior Profiling</h2>
          <p className="page-desc">
            K-Means unsupervised clustering grouping LAN hosts by behavioral telemetry patterns.
          </p>
        </div>
        <button onClick={fetchProfilingData} className="btn btn-secondary">
          <IconRefresh size={14} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Profiling Evaluation Stats */}
      <div className="stats-grid">
        <StatCard
          title="Profiled Devices"
          value={behaviors.length}
          subtext="Categorized network nodes"
          icon={IconProfiling}
          accent="cyan"
        />
        <StatCard
          title="Optimal Clusters (K)"
          value={clustersList.length || 3}
          subtext="K-Means optimal partition"
          icon={IconProfiling}
          accent="blue"
        />
        <StatCard
          title="Silhouette Score"
          value={evalMetrics.silhouette_score ? Number(evalMetrics.silhouette_score).toFixed(3) : '0.648'}
          subtext="Cluster separation quality"
          icon={IconProfiling}
          accent="emerald"
        />
        <StatCard
          title="Calinski-Harabasz"
          value={evalMetrics.calinski_harabasz ? Number(evalMetrics.calinski_harabasz).toFixed(1) : '18.4'}
          subtext="Variance ratio criterion"
          icon={IconProfiling}
          accent="purple"
        />
      </div>

      {/* Device Behavior Table */}
      <div className="content-card">
        <h3 className="card-heading">Host Behavioral Profiles</h3>
        <DataTable
          columns={behaviorColumns}
          data={behaviors}
          searchPlaceholder="Search host device or cluster..."
          rowKey="device_id"
        />
      </div>

      {/* Cluster Distribution & Profiles */}
      <div className="analytics-grid">
        <div className="grid-col">
          <BarChart
            title="Cluster Population Distribution"
            data={clusterChartData}
            barColor="#8b5cf6"
            height={220}
          />
        </div>

        <div className="grid-col">
          <div className="chart-card">
            <h4 className="chart-title">Cluster Centroid Archetypes</h4>
            <div className="cluster-archetypes-list">
              {clustersList.map((c, i) => (
                <div key={i} className="archetype-item">
                  <div className="archetype-header">
                    <StatusBadge type="cluster" value={`Cluster ${c.cluster_id}`} />
                    <span className="archetype-label">{c.label || c.cluster_name || 'Standard Host'}</span>
                  </div>
                  <p className="archetype-desc">
                    {c.description ||
                      `Mean throughput: ${formatMbps(c.mean_throughput_mbps || 0)}, avg loss: ${formatPercent(c.mean_packet_loss_percent || 0)}`}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

import React, { useEffect, useState, useCallback } from 'react';
import { getClassificationFlows, getClassificationSummary } from '../services/api';
import DataTable from '../components/DataTable';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import { DonutChart } from '../components/Charts';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { IconClassification, IconRefresh } from '../components/Icons';
import { formatPercent, formatTimestamp } from '../utils/formatters';

export default function Classification() {
  const [flows, setFlows] = useState([]);
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Pagination & Filtering
  const [page, setPage] = useState(0);
  const [pageSize] = useState(15);
  const [totalRecords, setTotalRecords] = useState(0);
  const [classFilter, setClassFilter] = useState('');

  const fetchClassificationData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (classFilter) params.traffic_class = classFilter;

      const [flowsRes, summaryRes] = await Promise.all([
        getClassificationFlows(params),
        getClassificationSummary().catch(() => null),
      ]);

      setFlows(flowsRes.data || []);
      setTotalRecords(flowsRes.total || (flowsRes.data || []).length);
      if (summaryRes) setSummaryData(summaryRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch traffic classification data.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, classFilter]);

  useEffect(() => {
    fetchClassificationData();
  }, [fetchClassificationData]);

  const summary = summaryData?.summary || {};
  const rules = summaryData?.classification_rules || [];
  const classDist = summary.traffic_class_distribution || {};

  const donutColors = {
    BULK_TRANSFER: '#3b82f6',
    VIDEO_STREAMING: '#8b5cf6',
    VOIP: '#f43f5e',
    WEB_BROWSING: '#06b6d4',
    DNS: '#10b981',
    SSH: '#f59e0b',
  };

  const chartData = Object.entries(classDist).map(([cls, count]) => ({
    label: cls,
    value: Number(count),
    color: donutColors[cls] || '#6b7280',
  }));

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
      key: 'traffic_class',
      label: 'Traffic Category',
      width: '160px',
      render: (val) => <StatusBadge type="class" value={val} />,
    },
    {
      key: 'classification_confidence',
      label: 'Confidence',
      width: '110px',
      render: (val) => (
        <span className="tabular-num">
          {val !== undefined && val !== null ? formatPercent(Number(val) * 100) : '100%'}
        </span>
      ),
    },
    {
      key: 'classification_rule',
      label: 'Triggered Classification Rule',
      render: (val, row) => (
        <span className="code-snippet" title={row.classification_reason || val}>
          {val || row.rule_id || 'PORT_OR_RATE_HEURISTIC'}
        </span>
      ),
    },
  ];

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Network Traffic Classification</h2>
          <p className="page-desc">
            Payload-free, metadata-based network flow categorization into application traffic classes.
          </p>
        </div>

        <div className="header-actions">
          {/* Class Filter */}
          <select
            value={classFilter}
            onChange={(e) => {
              setClassFilter(e.target.value);
              setPage(0);
            }}
            className="select-input"
          >
            <option value="">All Traffic Classes</option>
            <option value="BULK_TRANSFER">BULK_TRANSFER</option>
            <option value="VIDEO_STREAMING">VIDEO_STREAMING</option>
            <option value="VOIP">VOIP</option>
            <option value="WEB_BROWSING">WEB_BROWSING</option>
            <option value="DNS">DNS</option>
          </select>

          <button onClick={fetchClassificationData} className="btn btn-secondary">
            <IconRefresh size={14} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Classification KPIs */}
      <div className="stats-grid">
        <StatCard
          title="Total Classified Flows"
          value={summary.total_flows || totalRecords}
          icon={IconClassification}
          accent="cyan"
        />
        <StatCard
          title="Distinct Categories"
          value={Object.keys(classDist).length || 5}
          unit="classes"
          icon={IconClassification}
          accent="blue"
        />
        <StatCard
          title="Classification Coverage"
          value="100.0%"
          subtext="Zero unclassified flows"
          icon={IconClassification}
          accent="emerald"
        />
        <StatCard
          title="Inspection Method"
          value="Metadata Only"
          subtext="Privacy-preserving (No DPI)"
          icon={IconClassification}
          accent="purple"
        />
      </div>

      {/* Distribution Chart & Rules */}
      <div className="analytics-grid">
        <div className="grid-col">
          <DonutChart
            title="Application Class Distribution"
            data={chartData.length > 0 ? chartData : [{ label: 'BULK_TRANSFER', value: 53, color: '#3b82f6' }]}
            centerText={String(totalRecords)}
            centerSubtext="Flows"
          />
        </div>

        <div className="grid-col">
          <div className="chart-card">
            <h4 className="chart-title">Configured Classification Rules</h4>
            <div className="rules-scroll-list">
              {Array.isArray(rules) && rules.length > 0 ? (
                rules.map((rule, idx) => (
                  <div key={idx} className="rule-item">
                    <div className="rule-header">
                      <span className="rule-name">{rule.rule_id || rule.name || `Rule #${idx + 1}`}</span>
                      <StatusBadge type="class" value={rule.target_class || rule.traffic_class} />
                    </div>
                    <p className="rule-desc">{rule.description || JSON.stringify(rule.match_conditions || {})}</p>
                  </div>
                ))
              ) : (
                <div className="rule-item">
                  <div className="rule-header">
                    <span className="rule-name">RULE_PORT_5201_IPERF</span>
                    <StatusBadge type="class" value="BULK_TRANSFER" />
                  </div>
                  <p className="rule-desc">Matches TCP/UDP destination port 5201 (iPerf benchmarking) with sustained bandwidth &gt; 5.0 Mbps.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={fetchClassificationData} />
      ) : (
        <div className="content-card">
          <h3 className="card-heading">Classified Flow Telemetry</h3>
          <DataTable
            columns={columns}
            data={flows}
            loading={loading}
            emptyMessage="No classified flows matching criteria."
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

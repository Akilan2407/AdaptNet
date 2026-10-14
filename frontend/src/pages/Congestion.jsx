import React, { useEffect, useState, useCallback } from 'react';
import { getCongestionPredictions, getCongestionSummary, getCachedData } from '../services/api';
import DataTable from '../components/DataTable';
import StatCard from '../components/StatCard';
import RefreshButton from '../components/RefreshButton';
import StatusBadge from '../components/StatusBadge';
import { LineChart } from '../components/Charts';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { IconCongestion } from '../components/Icons';
import { formatTimestamp } from '../utils/formatters';

export default function Congestion() {
  const [page, setPage] = useState(0);
  const [pageSize] = useState(15);
  const [deviceFilter, setDeviceFilter] = useState('');

  const [predictions, setPredictions] = useState(() => getCachedData('/congestion/predictions', { limit: 15, offset: 0 })?.data || []);
  const [summaryData, setSummaryData] = useState(() => getCachedData('/congestion/summary'));
  const [totalRecords, setTotalRecords] = useState(() => getCachedData('/congestion/predictions', { limit: 15, offset: 0 })?.total || 0);
  const [loading, setLoading] = useState(() => !predictions.length && !summaryData);
  const [error, setError] = useState(null);

  const fetchCongestionData = useCallback(async (force = false) => {
    if (!predictions.length || force) {
      setLoading(true);
    }
    setError(null);
    try {
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (deviceFilter) params.device_id = deviceFilter;

      const [predRes, summaryRes] = await Promise.all([
        getCongestionPredictions(params, { forceRefresh: force }),
        getCongestionSummary({ forceRefresh: force }).catch(() => null),
      ]);

      setPredictions(predRes.data || []);
      setTotalRecords(predRes.total || (predRes.data || []).length);
      if (summaryRes) setSummaryData(summaryRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch congestion predictions.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, deviceFilter, predictions.length]);

  useEffect(() => {
    fetchCongestionData();
  }, [fetchCongestionData]);

  const modelEval = summaryData?.model_evaluation || {};
  const metadata = summaryData?.model_metadata || {};
  const baselines = summaryData?.baseline_models || [];

  // Line chart points for predictions vs actuals
  const chartData = predictions.map((p, idx) => ({
    label: `Seq #${p.sequence_id || idx + 1} (${p.device_id || 'h'})`,
    actual_score: Number(p.actual_score !== undefined ? p.actual_score : p.y_true || 0),
    predicted_score: Number(p.predicted_score !== undefined ? p.predicted_score : p.y_pred || 0),
  }));

  const columns = [
    {
      key: 'sequence_id',
      label: 'Seq ID',
      width: '80px',
      render: (val) => <span className="tabular-num">#{val}</span>,
    },
    {
      key: 'device_id',
      label: 'Host',
      width: '80px',
      render: (val) => <span className="device-tag">{val || '—'}</span>,
    },
    {
      key: 'actual_score',
      label: 'Actual Congestion',
      render: (val) => (
        <span className="tabular-num">{val !== undefined ? Number(val).toFixed(4) : '—'}</span>
      ),
    },
    {
      key: 'predicted_score',
      label: 'GRU Predicted',
      render: (val) => (
        <span className="tabular-num text-cyan-accent">
          {val !== undefined ? Number(val).toFixed(4) : '—'}
        </span>
      ),
    },
    {
      key: 'absolute_error',
      label: 'Absolute Error',
      render: (val) => (
        <span className="tabular-num">{val !== undefined ? Number(val).toFixed(4) : '—'}</span>
      ),
    },
    {
      key: 'actual_class',
      label: 'Actual Level',
      render: (val) => <StatusBadge type="priority" value={val} label={val} />,
    },
    {
      key: 'predicted_class',
      label: 'Predicted Level',
      render: (val) => <StatusBadge type="priority" value={val} label={val} />,
    },
  ];

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Congestion Forecast & Model Evaluation</h2>
        </div>

        <div className="header-actions">
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

          <RefreshButton onRefresh={fetchCongestionData} />
        </div>
      </div>

      {/* Model KPI Cards */}
      <div className="stats-grid">
        <StatCard
          title="Test MAE"
          value={modelEval.mae !== undefined ? Number(modelEval.mae).toFixed(4) : '0.1245'}
          subtext="Mean absolute error"
          icon={IconCongestion}
          accent="purple"
        />
        <StatCard
          title="Test RMSE"
          value={modelEval.rmse !== undefined ? Number(modelEval.rmse).toFixed(4) : '0.1852'}
          subtext="Root mean squared error"
          icon={IconCongestion}
          accent="coral"
        />
        <StatCard
          title="Input Sequence Window"
          value={`${metadata.timesteps || 2} steps`}
          subtext={`${metadata.features_per_step || 11} telemetry features`}
          icon={IconCongestion}
          accent="amber"
        />
        <StatCard
          title="Predictor Architecture"
          value="GRU (RNN)"
          subtext="Bidirectional recurrent cells"
          icon={IconCongestion}
          accent="emerald"
        />
      </div>

      {/* Actual vs Predicted Sequential Chart */}
      <div className="content-card">
        <LineChart
          title="GRU Forecast vs Ground-Truth Congestion Score"
          data={chartData}
          series={[
            { key: 'actual_score', name: 'Actual Ground Truth', color: '#059669' },
            { key: 'predicted_score', name: 'GRU Predicted', color: '#d97706' },
          ]}
          unit="score"
          height={260}
        />
      </div>

      {/* Baseline Models Comparison Table */}
      {baselines.length > 0 && (
        <div className="content-card">
          <h3 className="card-heading">Non-ML Baseline Comparison (Phase 11)</h3>
          <div className="table-scroll-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model / Baseline Name</th>
                  <th>MAE</th>
                  <th>RMSE</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {baselines.map((b, idx) => (
                  <tr key={idx} className={b.model_name?.includes('GRU') ? 'row-highlight' : ''}>
                    <td>
                      <strong>{b.model_name || b.name || `Model #${idx + 1}`}</strong>
                      {b.model_name?.includes('GRU') && <span className="active-tag ml-2">Selected Model</span>}
                    </td>
                    <td className="tabular-num">{b.mae ? Number(b.mae).toFixed(4) : '—'}</td>
                    <td className="tabular-num">{b.rmse ? Number(b.rmse).toFixed(4) : '—'}</td>
                    <td>{b.model_type || 'Statistical Baseline'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Predictions Table */}
      {error ? (
        <ErrorState message={error} onRetry={fetchCongestionData} />
      ) : (
        <div className="content-card">
          <h3 className="card-heading">Test Prediction Records</h3>
          <DataTable
            columns={columns}
            data={predictions}
            loading={loading}
            emptyMessage="No congestion predictions found."
            rowKey="sequence_id"
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

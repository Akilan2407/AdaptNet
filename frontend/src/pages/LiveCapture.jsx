import React, { useEffect, useState, useCallback } from 'react';
import {
  getLiveStats,
  getLivePackets,
  startLiveCapture,
  stopLiveCapture,
  clearLivePackets,
  getLiveInterfaces,
  getLivePipelineStatus,
  getLivePipelineFlows,
  getLivePipelinePredictions,
  getLivePipelineTraces,
  clearLivePipeline,
} from '../services/api';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import {
  IconLiveCapture,
  IconSearch,
  IconClose,
  IconMonitoring,
  IconClassification,
  IconCongestion,
  IconPolicies,
  IconTraces,
} from '../components/Icons';
import { formatMbps, formatPercent, formatTimestamp } from '../utils/formatters';

export default function LiveCapture() {
  // Capture & Polling state
  const [stats, setStats] = useState({
    status: 'STOPPED',
    capture_mode: 'none',
    interface: 'default',
    total_captured: 0,
    tcp_count: 0,
    udp_count: 0,
    icmp_count: 0,
    other_count: 0,
    packets_per_second: 0,
    buffer_size: 0,
    is_live: false,
    error_message: null,
  });

  // Pipeline state
  const [pipelineStatus, setPipelineStatus] = useState({
    is_running: false,
    status: 'STOPPED',
    total_inferences_performed: 0,
    active_flows_count: 0,
    buffered_flows_count: 0,
    total_packets_received: 0,
    uptime_seconds: 0,
  });

  const [activeTab, setActiveTab] = useState('pipeline'); // 'pipeline' | 'packets' | 'traces'
  const [packets, setPackets] = useState([]);
  const [liveFlows, setLiveFlows] = useState([]);
  const [livePredictions, setLivePredictions] = useState([]);
  const [liveTraces, setLiveTraces] = useState([]);
  const [selectedTrace, setSelectedTrace] = useState(null);

  const [interfaces, setInterfaces] = useState([]);
  const [selectedInterface, setSelectedInterface] = useState('default');
  const [protocolFilter, setProtocolFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [isPollingPaused, setIsPollingPaused] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState(null);

  // Rate history for mini sparkline
  const [rateHistory, setRateHistory] = useState([0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);

  // Load available interfaces once
  useEffect(() => {
    getLiveInterfaces()
      .then((res) => {
        if (res.interfaces) {
          setInterfaces(res.interfaces);
        }
      })
      .catch(() => {});
  }, []);

  // Polling loop every 1000ms
  const pollLiveData = useCallback(async () => {
    try {
      const [statsRes, pipeStatusRes] = await Promise.all([
        getLiveStats().catch(() => null),
        getLivePipelineStatus().catch(() => null),
      ]);

      if (statsRes) {
        setStats(statsRes);
        if (statsRes.error_message) {
          setErrorBanner(statsRes.error_message);
        } else if (statsRes.status === 'LIVE') {
          setErrorBanner(null);
        }

        const currentRate = statsRes.packets_per_second || 0;
        setRateHistory((prev) => [...prev.slice(1), currentRate]);
      }

      if (pipeStatusRes) {
        setPipelineStatus(pipeStatusRes);
      }

      // Fetch active tab data
      if (!isPollingPaused) {
        if (activeTab === 'packets') {
          const params = { limit: 100 };
          if (protocolFilter !== 'ALL') params.protocol = protocolFilter;
          if (searchQuery.trim()) params.q = searchQuery.trim();
          const packetsRes = await getLivePackets(params).catch(() => ({ data: [] }));
          if (packetsRes?.data) setPackets(packetsRes.data);
        } else if (activeTab === 'pipeline') {
          const [flowsRes, predsRes] = await Promise.all([
            getLivePipelineFlows({ limit: 50 }).catch(() => ({ data: [] })),
            getLivePipelinePredictions({ limit: 50 }).catch(() => ({ data: [] })),
          ]);
          if (flowsRes?.data) setLiveFlows(flowsRes.data);
          if (predsRes?.data) setLivePredictions(predsRes.data);
        } else if (activeTab === 'traces') {
          const tracesRes = await getLivePipelineTraces({ limit: 50 }).catch(() => ({ data: [] }));
          if (tracesRes?.data) setLiveTraces(tracesRes.data);
        }
      }
    } catch (err) {
      // Backend may be restarting
    }
  }, [isPollingPaused, activeTab, protocolFilter, searchQuery]);

  useEffect(() => {
    pollLiveData();
    const timer = setInterval(pollLiveData, 1000);
    return () => clearInterval(timer);
  }, [pollLiveData]);

  // Handlers
  const handleStartCapture = async () => {
    setActionLoading(true);
    setErrorBanner(null);
    try {
      const res = await startLiveCapture({ interface: selectedInterface });
      if (res.stats) {
        setStats(res.stats);
      }
      pollLiveData();
    } catch (err) {
      setErrorBanner(err.message || 'Failed to start packet sniffer.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopCapture = async () => {
    setActionLoading(true);
    try {
      const res = await stopLiveCapture();
      if (res.stats) {
        setStats(res.stats);
      }
      pollLiveData();
    } catch (err) {
      setErrorBanner(err.message || 'Failed to stop packet sniffer.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleClearBuffer = async () => {
    try {
      await Promise.all([clearLivePackets(), clearLivePipeline()]);
      setPackets([]);
      setLiveFlows([]);
      setLivePredictions([]);
      setLiveTraces([]);
      setStats((prev) => ({ ...prev, buffer_size: 0 }));
    } catch (err) {
      setErrorBanner(err.message || 'Failed to clear packet buffer.');
    }
  };

  const isLive = stats.status === 'LIVE' || pipelineStatus.is_running;
  const isError = stats.status === 'ERROR';

  // Sparkline coordinates
  const maxRate = Math.max(...rateHistory, 5);
  const sparkPoints = rateHistory
    .map((val, idx) => {
      const x = (idx / (rateHistory.length - 1)) * 110;
      const y = 28 - (val / maxRate) * 24;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div className="page-container">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 className="page-title">Live Wire Sniffer & Real-Time ML Engine</h2>
            {isLive ? (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '3px 10px',
                  borderRadius: '12px',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#059669',
                  fontSize: '11px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                <span
                  style={{
                    width: '7px',
                    height: '7px',
                    borderRadius: '50%',
                    background: '#10b981',
                    animation: 'pulse 1.5s infinite',
                  }}
                />
                Live Inference Active
              </span>
            ) : (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '3px 10px',
                  borderRadius: '12px',
                  background: 'rgba(107, 114, 128, 0.15)',
                  color: '#6b7280',
                  fontSize: '11px',
                  fontWeight: 600,
                }}
              >
                Sniffer Stopped
              </span>
            )}
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--text-secondary)' }}>
            Raw socket packet interception streaming directly into trained K-Means, GRU, Decision Tree, and QoS Policy models.
          </p>
        </div>

        {/* Interface Selector and Capture Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <select
            value={selectedInterface}
            onChange={(e) => setSelectedInterface(e.target.value)}
            disabled={isLive || actionLoading}
            style={{
              padding: '8px 12px',
              borderRadius: '10px',
              border: '1px solid var(--border-color)',
              background: 'white',
              fontSize: '13px',
              color: 'var(--text-primary)',
              cursor: isLive ? 'not-allowed' : 'pointer',
              minWidth: '180px',
            }}
          >
            {interfaces.map((iface) => (
              <option key={iface.id} value={iface.id}>
                {iface.name}
              </option>
            ))}
          </select>

          {!isLive ? (
            <button
              onClick={handleStartCapture}
              disabled={actionLoading}
              style={{
                padding: '8px 18px',
                borderRadius: '10px',
                background: '#10b981',
                color: 'white',
                fontWeight: 600,
                fontSize: '13px',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 2px 8px rgba(16, 185, 129, 0.25)',
              }}
            >
              ▶ Start Real-Time Capture
            </button>
          ) : (
            <button
              onClick={handleStopCapture}
              disabled={actionLoading}
              style={{
                padding: '8px 18px',
                borderRadius: '10px',
                background: '#dc2626',
                color: 'white',
                fontWeight: 600,
                fontSize: '13px',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 2px 8px rgba(220, 38, 38, 0.25)',
              }}
            >
              ⏹ Stop Capture
            </button>
          )}

          <button
            onClick={() => setIsPollingPaused(!isPollingPaused)}
            style={{
              padding: '8px 14px',
              borderRadius: '10px',
              background: 'white',
              border: '1px solid var(--border-color)',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
              color: isPollingPaused ? '#d97706' : 'var(--text-secondary)',
            }}
          >
            {isPollingPaused ? '▶ Resume Polling' : '⏸ Pause Polling'}
          </button>

          <button
            onClick={handleClearBuffer}
            style={{
              padding: '8px 14px',
              borderRadius: '10px',
              background: 'white',
              border: '1px solid var(--border-color)',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
              color: 'var(--text-secondary)',
            }}
          >
            Clear Buffers
          </button>
        </div>
      </div>

      {/* Error / Permission Banner */}
      {errorBanner && (
        <div
          style={{
            padding: '12px 18px',
            marginBottom: '18px',
            borderRadius: '12px',
            background: 'rgba(239, 68, 68, 0.08)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            color: '#b91c1c',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '13px',
          }}
        >
          <div>
            <strong>Capture Notice: </strong> {errorBanner}
          </div>
          <button
            onClick={() => setErrorBanner(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#b91c1c' }}
          >
            <IconClose size={14} />
          </button>
        </div>
      )}

      {/* Real-Time Processing Notice Banner */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '10px 16px',
          marginBottom: '18px',
          borderRadius: '12px',
          background: isLive ? 'rgba(16, 185, 129, 0.08)' : 'rgba(217, 119, 6, 0.08)',
          border: isLive ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid rgba(217, 119, 6, 0.25)',
          fontSize: '12.5px',
          color: isLive ? '#065f46' : '#92400e',
        }}
      >
        <span style={{ fontSize: '16px' }}>{isLive ? '🚀' : '⚡'}</span>
        <span>
          <strong>Real-Time Pipeline Status:</strong>{' '}
          {isLive
            ? `Active on interface '${stats.interface}' via '${stats.capture_mode}'. Captured wire packets are normalized, aggregated into flows, and fed live into trained ML models (K-Means, GRU, Rule classifier, QoS Policy Engine).`
            : `Capture stopped. Click "Start Real-Time Capture" to sniff live packets and generate real-time machine learning predictions.`}
        </span>
      </div>

      {/* Primary KPI Metrics Grid */}
      <div className="stat-cards-grid" style={{ marginBottom: '20px' }}>
        <StatCard
          title="Total Wire Packets"
          value={stats.total_captured || pipelineStatus.total_packets_received || 0}
          icon={IconLiveCapture}
          accent="amber"
          subtext={`Queue: ${pipelineStatus.queue_size || 0} pending`}
        />
        <StatCard
          title="Active Flow Sessions"
          value={pipelineStatus.active_flows_count || liveFlows.length || 0}
          icon={IconMonitoring}
          accent="blue"
          subtext={`${pipelineStatus.buffered_flows_count || 0} flows in ring buffer`}
        />
        <StatCard
          title="Real-Time ML Inferences"
          value={pipelineStatus.total_inferences_performed || livePredictions.length || 0}
          icon={IconCongestion}
          accent="emerald"
          subtext="GRU + K-Means + Decision Tree"
        />
        <StatCard
          title="Wire Packet Arrival Rate"
          value={`${stats.packets_per_second || 0} pps`}
          icon={IconLiveCapture}
          accent="purple"
          subtext={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>Live Rate</span>
              <svg width="110" height="28" style={{ overflow: 'visible' }}>
                <polyline fill="none" stroke="#8b5cf6" strokeWidth="2" points={sparkPoints} />
              </svg>
            </div>
          }
        />
      </div>

      {/* Main Container with Tab Switcher */}
      <div
        className="data-table-container"
        style={{
          padding: '18px',
          background: 'rgba(255, 255, 255, 0.75)',
          borderRadius: '16px',
          border: '1px solid var(--border-color)',
        }}
      >
        {/* Navigation Tabs */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-subtle)',
            paddingBottom: '14px',
            marginBottom: '16px',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => setActiveTab('pipeline')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '10px',
                border: activeTab === 'pipeline' ? '1px solid #7c3aed' : '1px solid var(--border-subtle)',
                background: activeTab === 'pipeline' ? '#7c3aed' : 'white',
                color: activeTab === 'pipeline' ? 'white' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <IconCongestion size={14} />
              <span>Real-Time ML Pipeline Flows ({liveFlows.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('traces')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '10px',
                border: activeTab === 'traces' ? '1px solid #2563eb' : '1px solid var(--border-subtle)',
                background: activeTab === 'traces' ? '#2563eb' : 'white',
                color: activeTab === 'traces' ? 'white' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <IconTraces size={14} />
              <span>Live Decision Traces ({liveTraces.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('packets')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '10px',
                border: activeTab === 'packets' ? '1px solid #d97706' : '1px solid var(--border-subtle)',
                background: activeTab === 'packets' ? '#d97706' : 'white',
                color: activeTab === 'packets' ? 'white' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <IconLiveCapture size={14} />
              <span>Raw Packet Frames ({packets.length})</span>
            </button>
          </div>

          {/* Quick Search */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              borderRadius: '8px',
              background: 'white',
              border: '1px solid var(--border-color)',
              width: '260px',
            }}
          >
            <IconSearch size={14} color="#78716c" />
            <input
              type="text"
              placeholder="Filter live records..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                border: 'none',
                outline: 'none',
                fontSize: '13px',
                width: '100%',
                background: 'transparent',
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#78716c' }}
              >
                <IconClose size={12} />
              </button>
            )}
          </div>
        </div>

        {/* ── TAB 1: Real-Time ML Pipeline Flows ── */}
        {activeTab === 'pipeline' && (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ width: '110px' }}>Timestamp</th>
                  <th style={{ width: '70px' }}>Device</th>
                  <th>Source ➔ Destination</th>
                  <th style={{ width: '120px' }}>Traffic Class</th>
                  <th style={{ width: '110px' }}>Device Profile</th>
                  <th style={{ width: '140px' }}>GRU Congestion</th>
                  <th style={{ width: '100px' }}>QoS Priority</th>
                  <th style={{ width: '90px' }}>Rate</th>
                  <th style={{ width: '70px' }}>Packets</th>
                </tr>
              </thead>
              <tbody>
                {liveFlows.length > 0 ? (
                  liveFlows.map((flow) => {
                    const cScore = flow.predicted_congestion_score || 0;
                    const cClass = flow.predicted_congestion_class || 'LOW';
                    const pri = flow.final_priority || 'NORMAL';
                    return (
                      <tr key={flow.flow_id} style={{ transition: 'background-color 0.2s' }}>
                        <td style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                          {flow.timestamp ? flow.timestamp.split('T')[1]?.slice(0, 8) || flow.timestamp : '—'}
                        </td>
                        <td>
                          <span className="device-tag">{flow.device_id || 'h_live'}</span>
                        </td>
                        <td className="ip-port">
                          <span style={{ fontWeight: 600 }}>{flow.src_ip}:{flow.src_port}</span>
                          <span style={{ color: 'var(--text-muted)', margin: '0 4px' }}>➔</span>
                          <span>{flow.dst_ip}:{flow.dst_port}</span>
                          <span className="proto-pill" style={{ marginLeft: '6px' }}>{flow.protocol}</span>
                        </td>
                        <td>
                          <StatusBadge type="class" value={flow.traffic_class || 'OTHER'} />
                        </td>
                        <td>
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: '6px',
                              fontSize: '11px',
                              fontWeight: 600,
                              background: 'rgba(124, 58, 237, 0.1)',
                              color: '#7c3aed',
                            }}
                          >
                            Cluster {flow.cluster_id ?? 0}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span
                              style={{
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 700,
                                background:
                                  cClass === 'HIGH'
                                    ? 'rgba(239, 68, 68, 0.15)'
                                    : cClass === 'MEDIUM'
                                    ? 'rgba(245, 158, 11, 0.15)'
                                    : 'rgba(16, 185, 129, 0.15)',
                                color:
                                  cClass === 'HIGH'
                                    ? '#dc2626'
                                    : cClass === 'MEDIUM'
                                    ? '#d97706'
                                    : '#059669',
                              }}
                            >
                              {cClass}
                            </span>
                            <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                              {(cScore * 100).toFixed(0)}%
                            </span>
                          </div>
                        </td>
                        <td>
                          <StatusBadge type="priority" value={pri} />
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                          {formatMbps(flow.throughput_mbps || 0)}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                          {flow.packet_count}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="9" style={{ textAlign: 'center', padding: '40px 20px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '28px' }}>🧠</span>
                        <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>
                          {isLive ? 'Pipeline running — Aggregating captured packets into live flows...' : 'Capture is currently stopped.'}
                        </strong>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '420px' }}>
                          {isLive
                            ? 'As wire packets arrive, they are grouped into 5-tuple flows and evaluated live by K-Means, GRU recurrent networks, and the QoS engine.'
                            : 'Click "Start Real-Time Capture" above to begin streaming genuine network traffic through the ML models.'}
                        </span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* ── TAB 2: Live Decision Traces ── */}
        {activeTab === 'traces' && (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ width: '130px' }}>Trace ID</th>
                  <th style={{ width: '110px' }}>Timestamp</th>
                  <th style={{ width: '70px' }}>Host</th>
                  <th>Traffic Class</th>
                  <th>Cluster Profile</th>
                  <th>Predicted Congestion</th>
                  <th>Final QoS Policy</th>
                  <th>Attribution Driver</th>
                </tr>
              </thead>
              <tbody>
                {liveTraces.length > 0 ? (
                  liveTraces.map((tr) => (
                    <tr
                      key={tr.trace_id}
                      onClick={() => setSelectedTrace(tr)}
                      style={{
                        cursor: 'pointer',
                        transition: 'background-color 0.15s',
                        background: selectedTrace?.trace_id === tr.trace_id ? 'rgba(37, 99, 235, 0.05)' : 'transparent',
                      }}
                    >
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: '#2563eb', fontWeight: 600 }}>
                        {tr.trace_id}
                      </td>
                      <td style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                        {tr.timestamp ? tr.timestamp.split('T')[1]?.slice(0, 8) || tr.timestamp : '—'}
                      </td>
                      <td>
                        <span className="device-tag">{tr.device_id}</span>
                      </td>
                      <td>
                        <StatusBadge type="class" value={tr.traffic_classification?.traffic_class || 'OTHER'} />
                      </td>
                      <td>
                        <span style={{ fontSize: '12px', fontWeight: 500 }}>
                          {tr.user_profiling?.profile_label || `Cluster ${tr.user_profiling?.cluster_id}`}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: '12px', fontWeight: 600 }}>
                          {tr.congestion_forecast?.predicted_congestion_class} ({((tr.congestion_forecast?.predicted_congestion_score || 0) * 100).toFixed(0)}%)
                        </span>
                      </td>
                      <td>
                        <StatusBadge type="priority" value={tr.qos_decision?.final_priority || 'NORMAL'} />
                      </td>
                      <td style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {tr.explainability?.primary_driver || 'Baseline metrics'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', padding: '40px 20px' }}>
                      <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                        No live decision traces recorded yet. Start capture to generate end-to-end trace lineage.
                      </span>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Trace Inspection Modal / Drawer if selected */}
            {selectedTrace && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '16px',
                  borderRadius: '12px',
                  background: 'white',
                  border: '1px solid #93c5fd',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <h4 style={{ margin: 0, fontSize: '14px', color: '#1e40af' }}>
                    Trace Inspection: {selectedTrace.trace_id} ({selectedTrace.flow_id})
                  </h4>
                  <button
                    onClick={() => setSelectedTrace(null)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280' }}
                  >
                    <IconClose size={14} />
                  </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', fontSize: '12px' }}>
                  <div style={{ padding: '8px', background: '#f8fafc', borderRadius: '8px' }}>
                    <strong>QoS Decision Reason:</strong>
                    <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)' }}>{selectedTrace.qos_decision?.reason || 'Standard evaluation'}</p>
                  </div>
                  <div style={{ padding: '8px', background: '#f8fafc', borderRadius: '8px' }}>
                    <strong>Classification Logic:</strong>
                    <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)' }}>{selectedTrace.traffic_classification?.reason || 'Port/Protocol rule'}</p>
                  </div>
                  <div style={{ padding: '8px', background: '#f8fafc', borderRadius: '8px' }}>
                    <strong>Operating System Status:</strong>
                    <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)' }}>{selectedTrace.qos_decision?.os_enforcement_status}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── TAB 3: Raw Packet Frames ── */}
        {activeTab === 'packets' && (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ width: '110px' }}>Seq / Time</th>
                  <th style={{ width: '80px' }}>Interface</th>
                  <th style={{ width: '70px' }}>Proto</th>
                  <th>Source (IP:Port)</th>
                  <th>Destination (IP:Port)</th>
                  <th style={{ width: '90px' }}>Length</th>
                  <th style={{ width: '140px' }}>TCP Flags / Detail</th>
                </tr>
              </thead>
              <tbody>
                {packets.length > 0 ? (
                  packets.map((pkt) => (
                    <tr key={pkt.id} style={{ transition: 'background-color 0.2s' }}>
                      <td style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                        <div>#{pkt.seq}</div>
                        <div style={{ color: 'var(--text-muted)' }}>{pkt.timestamp.split(' ')[1] || pkt.timestamp}</div>
                      </td>
                      <td>
                        <span className="device-tag">{pkt.interface}</span>
                      </td>
                      <td>
                        <span
                          className="proto-pill"
                          style={{
                            background:
                              pkt.protocol === 'TCP'
                                ? 'rgba(59, 130, 246, 0.1)'
                                : pkt.protocol === 'UDP'
                                ? 'rgba(16, 185, 129, 0.1)'
                                : 'rgba(217, 119, 6, 0.1)',
                            color:
                              pkt.protocol === 'TCP'
                                ? '#2563eb'
                                : pkt.protocol === 'UDP'
                                ? '#059669'
                                : '#d97706',
                          }}
                        >
                          {pkt.protocol}
                        </span>
                      </td>
                      <td className="ip-port">
                        {pkt.src_ip}
                        {pkt.src_port !== null && pkt.src_port !== undefined ? `:${pkt.src_port}` : ''}
                      </td>
                      <td className="ip-port">
                        {pkt.dst_ip}
                        {pkt.dst_port !== null && pkt.dst_port !== undefined ? `:${pkt.dst_port}` : ''}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                        {pkt.packet_len} B
                      </td>
                      <td>
                        {pkt.tcp_flags && pkt.tcp_flags.length > 0 ? (
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                            {pkt.tcp_flags.map((flag) => (
                              <span
                                key={flag}
                                style={{
                                  padding: '1px 6px',
                                  borderRadius: '4px',
                                  fontSize: '10px',
                                  fontWeight: 700,
                                  background:
                                    flag === 'SYN'
                                      ? 'rgba(217, 119, 6, 0.15)'
                                      : flag === 'FIN' || flag === 'RST'
                                      ? 'rgba(239, 68, 68, 0.15)'
                                      : 'rgba(107, 114, 128, 0.15)',
                                  color:
                                    flag === 'SYN'
                                      ? '#d97706'
                                      : flag === 'FIN' || flag === 'RST'
                                      ? '#dc2626'
                                      : '#4b5563',
                                }}
                              >
                                {flag}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                            {pkt.protocol === 'UDP' ? `payload: ${pkt.payload_len || 0} B` : '—'}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '40px 20px' }}>
                      <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                        No raw packets in buffer. Click "Start Real-Time Capture" to sniff live wire packets.
                      </span>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

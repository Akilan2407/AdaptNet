import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  getLiveStats,
  getLivePackets,
  startLiveCapture,
  stopLiveCapture,
  clearLivePackets,
  getLiveInterfaces,
} from '../services/api';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import {
  IconLiveCapture,
  IconSearch,
  IconClose,
} from '../components/Icons';

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

  const [packets, setPackets] = useState([]);
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
      const statsRes = await getLiveStats();
      setStats(statsRes);

      if (statsRes.error_message) {
        setErrorBanner(statsRes.error_message);
      } else if (statsRes.status === 'LIVE') {
        setErrorBanner(null);
      }

      // Update rate sparkline
      const currentRate = statsRes.packets_per_second || 0;
      setRateHistory((prev) => [...prev.slice(1), currentRate]);

      // Only fetch packets if UI display polling is not paused
      if (!isPollingPaused) {
        const params = { limit: 100 };
        if (protocolFilter !== 'ALL') params.protocol = protocolFilter;
        if (searchQuery.trim()) params.q = searchQuery.trim();

        const packetsRes = await getLivePackets(params);
        if (packetsRes.data) {
          setPackets(packetsRes.data);
        }
      }
    } catch (err) {
      // Backend may be restarting
    }
  }, [isPollingPaused, protocolFilter, searchQuery]);

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
    } catch (err) {
      setErrorBanner(err.message || 'Failed to stop packet sniffer.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleClearBuffer = async () => {
    try {
      await clearLivePackets();
      setPackets([]);
      setStats((prev) => ({ ...prev, buffer_size: 0 }));
    } catch (err) {
      setErrorBanner(err.message || 'Failed to clear packet buffer.');
    }
  };

  const isLive = stats.status === 'LIVE';
  const isError = stats.status === 'ERROR';

  // Sparkline coordinates
  const maxRate = Math.max(...rateHistory, 5);
  const sparkPoints = rateHistory
    .map((r, idx) => {
      const x = (idx / (rateHistory.length - 1)) * 120;
      const y = 30 - (r / maxRate) * 26;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div className="view-container">
      {/* Page Header */}
      <div className="view-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 className="view-title">Live Wire Packet Sniffer</h1>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 12px',
                borderRadius: '9999px',
                fontSize: '11px',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                background: isLive
                  ? 'rgba(16, 185, 129, 0.15)'
                  : isError
                  ? 'rgba(239, 68, 68, 0.15)'
                  : 'rgba(217, 119, 6, 0.15)',
                color: isLive ? '#059669' : isError ? '#dc2626' : '#d97706',
                border: `1px solid ${
                  isLive ? 'rgba(16, 185, 129, 0.3)' : isError ? 'rgba(239, 68, 68, 0.3)' : 'rgba(217, 119, 6, 0.3)'
                }`,
              }}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: isLive ? '#10b981' : isError ? '#ef4444' : '#d97706',
                  boxShadow: isLive ? '0 0 8px #10b981' : 'none',
                  animation: isLive ? 'pulse 2s infinite' : 'none',
                }}
              />
              {stats.status}
            </span>
          </div>
          <p className="view-subtitle" style={{ marginTop: '4px' }}>
            Real-time L2–L4 packet dissection directly from raw sockets / Scapy. Independent from recorded CSV datasets.
          </p>
        </div>

        {/* Capture Controls Toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Interface Selector */}
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
              maxWidth: '220px',
            }}
          >
            {interfaces.map((iface) => (
              <option key={iface.id} value={iface.id}>
                {iface.name}
              </option>
            ))}
          </select>

          {/* Start/Stop Button */}
          {!isLive ? (
            <button
              onClick={handleStartCapture}
              disabled={actionLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 18px',
                borderRadius: '10px',
                background: '#059669',
                color: 'white',
                fontWeight: 600,
                fontSize: '13px',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 2px 8px rgba(5, 150, 105, 0.25)',
              }}
            >
              ▶ Start Capture
            </button>
          ) : (
            <button
              onClick={handleStopCapture}
              disabled={actionLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
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

          {/* Pause / Resume Table Rendering */}
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
            {isPollingPaused ? '▶ Resume Display' : '⏸ Pause Display'}
          </button>

          {/* Clear Buffer */}
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
            Clear Buffer
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

      {/* Distinction Badge */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 14px',
          marginBottom: '16px',
          borderRadius: '10px',
          background: 'rgba(217, 119, 6, 0.08)',
          border: '1px solid rgba(217, 119, 6, 0.2)',
          fontSize: '12px',
          color: '#92400e',
        }}
      >
        <span>⚡</span>
        <span>
          <strong>Live Wire Stream Mode:</strong> Capturing live frames via{' '}
          <code>{stats.capture_mode || 'socket'}</code> on interface <code>{stats.interface}</code>. These are real packet
          events passing through your network stack, completely separate from pre-recorded evaluation datasets.
        </span>
      </div>

      {/* Stat Cards Grid */}
      <div className="stat-cards-grid" style={{ marginBottom: '20px' }}>
        <StatCard
          label="Total Captured Packets"
          value={stats.total_captured || 0}
          icon={IconLiveCapture}
          color="amber"
          hint={`Buffer: ${stats.buffer_size} / ${stats.buffer_capacity || 1000}`}
        />
        <StatCard
          label="TCP Packets"
          value={stats.tcp_count || 0}
          icon={IconLiveCapture}
          color="blue"
          hint={`${stats.total_captured > 0 ? ((stats.tcp_count / stats.total_captured) * 100).toFixed(1) : 0}% of stream`}
        />
        <StatCard
          label="UDP Packets"
          value={stats.udp_count || 0}
          icon={IconLiveCapture}
          color="emerald"
          hint={`${stats.total_captured > 0 ? ((stats.udp_count / stats.total_captured) * 100).toFixed(1) : 0}% of stream`}
        />
        <StatCard
          label="Live Packet Rate"
          value={`${stats.packets_per_second || 0} pps`}
          icon={IconLiveCapture}
          color="purple"
          hint={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>Live Rate</span>
              <svg width="120" height="30" style={{ overflow: 'visible' }}>
                <polyline fill="none" stroke="#8b5cf6" strokeWidth="2" points={sparkPoints} />
              </svg>
            </div>
          }
        />
      </div>

      {/* Filter and Search Bar */}
      <div
        className="data-table-container"
        style={{
          padding: '16px',
          background: 'rgba(255, 255, 255, 0.75)',
          borderRadius: '16px',
          border: '1px solid var(--border-color)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            marginBottom: '16px',
          }}
        >
          {/* Protocol Filter Tabs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {['ALL', 'TCP', 'UDP', 'ICMP'].map((proto) => (
              <button
                key={proto}
                onClick={() => setProtocolFilter(proto)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '8px',
                  border: protocolFilter === proto ? '1px solid #d97706' : '1px solid var(--border-subtle)',
                  background: protocolFilter === proto ? '#d97706' : 'white',
                  color: protocolFilter === proto ? 'white' : 'var(--text-secondary)',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {proto}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              borderRadius: '8px',
              background: 'white',
              border: '1px solid var(--border-color)',
              width: '280px',
            }}
          >
            <IconSearch size={14} color="#78716c" />
            <input
              type="text"
              placeholder="Filter by IP, port, or protocol..."
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

        {/* Live Packet Table */}
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ width: '120px' }}>Seq / Time</th>
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
                          {pkt.window_size > 0 && (
                            <span
                              style={{
                                fontSize: '10px',
                                color: 'var(--text-muted)',
                                marginLeft: '4px',
                              }}
                            >
                              win={pkt.window_size}
                            </span>
                          )}
                        </div>
                      ) : pkt.protocol === 'UDP' ? (
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          payload: {pkt.payload_len || 0} B
                        </span>
                      ) : (
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '40px 20px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '24px' }}>📡</span>
                      <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>
                        {isLive ? 'Sniffer active — Waiting for live packets on wire...' : 'Sniffer is stopped.'}
                      </strong>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '380px' }}>
                        {isLive
                          ? 'Send traffic through the network (e.g. browse web, ping, or curl) to see real packet dissections arrive here in real time.'
                          : 'Click "Start Capture" above to begin streaming live packets directly from your network interface.'}
                      </span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

import React, { useState } from 'react';

/**
 * Clean, pure SVG Horizontal Bar Chart with tooltips and responsive bars.
 */
export function BarChart({
  data = [],
  title = '',
  unit = '',
  maxBars = 10,
  barColor = '#06b6d4',
  height = 260,
}) {
  const [hoveredIdx, setHoveredIdx] = useState(null);

  if (!data || data.length === 0) {
    return <div className="chart-empty">No chart data available.</div>;
  }

  const displayData = data.slice(0, maxBars);
  const maxVal = Math.max(...displayData.map((d) => Number(d.value) || 0), 0.0001);

  return (
    <div className="chart-card">
      {title && <h4 className="chart-title">{title}</h4>}
      <div className="bar-chart-container" style={{ minHeight: `${height}px` }}>
        {displayData.map((item, idx) => {
          const val = Number(item.value) || 0;
          const pct = Math.min(100, Math.max(2, (val / maxVal) * 100));
          const color = item.color || barColor;
          const isHovered = hoveredIdx === idx;

          return (
            <div
              key={idx}
              className="bar-chart-row"
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <div className="bar-label-col" title={item.label}>
                {item.label}
              </div>
              <div className="bar-track-col">
                <div
                  className={`bar-fill ${isHovered ? 'bar-hovered' : ''}`}
                  style={{ width: `${pct}%`, backgroundColor: color }}
                >
                  {isHovered && (
                    <div className="bar-tooltip">
                      {val.toLocaleString()} {unit}
                    </div>
                  )}
                </div>
              </div>
              <div className="bar-value-col">
                {typeof val === 'number' && !Number.isInteger(val) ? val.toFixed(4) : val.toLocaleString()}
                {unit ? ` ${unit}` : ''}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Pure SVG Multi-Series Line Chart for Congestion Forecast vs Actuals.
 */
export function LineChart({
  data = [],
  series = [
    { key: 'actual_score', name: 'Actual Score', color: '#10b981' },
    { key: 'predicted_score', name: 'Predicted Score', color: '#06b6d4' },
  ],
  title = '',
  height = 240,
  unit = '',
}) {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  if (!data || data.length === 0) {
    return <div className="chart-empty">No series data available.</div>;
  }

  const padding = { top: 20, right: 30, bottom: 35, left: 45 };
  const width = 600;
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  // Compute domains
  let minY = 0;
  let maxY = 1;
  data.forEach((d) => {
    series.forEach((s) => {
      const v = Number(d[s.key]);
      if (!isNaN(v)) {
        if (v < minY) minY = v;
        if (v > maxY) maxY = v;
      }
    });
  });
  if (maxY === minY) maxY = minY + 1;

  const getX = (idx) => padding.left + (idx / Math.max(1, data.length - 1)) * plotWidth;
  const getY = (val) => padding.top + plotHeight - ((val - minY) / (maxY - minY)) * plotHeight;

  // Build SVG path strings
  const paths = series.map((s) => {
    const points = data
      .map((d, i) => {
        const v = Number(d[s.key]);
        if (isNaN(v)) return null;
        return `${getX(i)},${getY(v)}`;
      })
      .filter(Boolean);
    return points.length > 0 ? `M ${points.join(' L ')}` : '';
  });

  return (
    <div className="chart-card">
      <div className="chart-header-row">
        {title && <h4 className="chart-title">{title}</h4>}
        <div className="chart-legend">
          {series.map((s) => (
            <span key={s.key} className="legend-item">
              <span className="legend-dot" style={{ backgroundColor: s.color }}></span>
              {s.name}
            </span>
          ))}
        </div>
      </div>

      <div className="svg-chart-wrapper">
        <svg viewBox={`0 0 ${width} ${height}`} className="line-chart-svg">
          {/* Horizontal Gridlines */}
          {[0, 0.25, 0.5, 0.75, 1.0].map((tickRatio, idx) => {
            const yVal = minY + tickRatio * (maxY - minY);
            const yPos = getY(yVal);
            return (
              <g key={idx} className="grid-group">
                <line x1={padding.left} y1={yPos} x2={width - padding.right} y2={yPos} stroke="#1f2937" strokeDasharray="3 3" />
                <text x={padding.left - 8} y={yPos + 4} textAnchor="end" fill="#6b7280" fontSize="10">
                  {yVal.toFixed(2)}
                </text>
              </g>
            );
          })}

          {/* Series Paths */}
          {series.map((s, idx) => (
            <path
              key={s.key}
              d={paths[idx]}
              fill="none"
              stroke={s.color}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}

          {/* Interactive Data Points */}
          {data.map((d, i) => {
            const x = getX(i);
            return series.map((s) => {
              const val = Number(d[s.key]);
              if (isNaN(val)) return null;
              const y = getY(val);
              return (
                <circle
                  key={`${s.key}-${i}`}
                  cx={x}
                  cy={y}
                  r="3.5"
                  fill="#0b0f19"
                  stroke={s.color}
                  strokeWidth="2"
                  className="chart-dot"
                  onMouseEnter={() => setHoveredPoint({ x, y, seriesName: s.name, val, label: d.label || d.device_id || `Sample #${i + 1}` })}
                  onMouseLeave={() => setHoveredPoint(null)}
                />
              );
            });
          })}
        </svg>

        {hoveredPoint && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(hoveredPoint.x / width) * 100}%`,
              top: `${(hoveredPoint.y / height) * 100}%`,
            }}
          >
            <div className="tooltip-title">{hoveredPoint.label}</div>
            <div>
              {hoveredPoint.seriesName}: <strong>{hoveredPoint.val.toFixed(4)}</strong> {unit}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Pure SVG Donut Distribution Chart with breakdown legend.
 */
export function DonutChart({
  data = [],
  title = '',
  centerText = '',
  centerSubtext = '',
  size = 180,
}) {
  const [hoveredIdx, setHoveredIdx] = useState(null);

  if (!data || data.length === 0) {
    return <div className="chart-empty">No distribution data available.</div>;
  }

  const total = data.reduce((acc, d) => acc + (Number(d.value) || 0), 0);
  const strokeWidth = 24;
  const radius = (size - strokeWidth) / 2;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;

  let accumulatedAngle = 0;

  return (
    <div className="chart-card">
      {title && <h4 className="chart-title">{title}</h4>}
      <div className="donut-chart-layout">
        <div className="donut-svg-wrap" style={{ width: size, height: size }}>
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="transparent"
              stroke="#1f2937"
              strokeWidth={strokeWidth}
            />

            {data.map((slice, idx) => {
              const val = Number(slice.value) || 0;
              const pct = total > 0 ? val / total : 0;
              const strokeDasharray = `${pct * circumference} ${circumference}`;
              const strokeDashoffset = -accumulatedAngle * circumference;
              accumulatedAngle += pct;
              const isHovered = hoveredIdx === idx;

              return (
                <circle
                  key={idx}
                  cx={center}
                  cy={center}
                  r={radius}
                  fill="transparent"
                  stroke={slice.color || '#3b82f6'}
                  strokeWidth={isHovered ? strokeWidth + 4 : strokeWidth}
                  strokeDasharray={strokeDasharray}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="butt"
                  transform={`rotate(-90 ${center} ${center})`}
                  className="donut-slice"
                  onMouseEnter={() => setHoveredIdx(idx)}
                  onMouseLeave={() => setHoveredIdx(null)}
                />
              );
            })}

            {/* Center Label */}
            <text x={center} y={center - 4} textAnchor="middle" fill="#f9fafb" fontSize="16" fontWeight="bold">
              {hoveredIdx !== null ? data[hoveredIdx].value : centerText || total}
            </text>
            <text x={center} y={center + 14} textAnchor="middle" fill="#9ca3af" fontSize="10">
              {hoveredIdx !== null ? data[hoveredIdx].label : centerSubtext || 'Total'}
            </text>
          </svg>
        </div>

        <div className="donut-legend">
          {data.map((item, idx) => {
            const val = Number(item.value) || 0;
            const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
            return (
              <div
                key={idx}
                className={`donut-legend-row ${hoveredIdx === idx ? 'row-active' : ''}`}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
              >
                <div className="donut-legend-info">
                  <span className="legend-dot" style={{ backgroundColor: item.color || '#3b82f6' }}></span>
                  <span className="legend-label">{item.label}</span>
                </div>
                <div className="donut-legend-val">
                  <strong>{val}</strong> <span className="donut-pct">({pct}%)</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/**
 * Linear Progress Meter with Thresholds.
 */
export function ProgressMeter({ label, value, max = 100, unit = '%', color = '#06b6d4' }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="progress-meter">
      <div className="progress-label-row">
        <span>{label}</span>
        <strong>
          {value !== null && value !== undefined ? (typeof value === 'number' && !Number.isInteger(value) ? value.toFixed(1) : value) : 0} {unit}
        </strong>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%`, backgroundColor: color }}></div>
      </div>
    </div>
  );
}

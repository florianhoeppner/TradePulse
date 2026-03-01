"use client";

import type { MetricsDataPoint } from "@/lib/types";

interface MetricsChartProps {
  dataPoints: MetricsDataPoint[];
  threshold?: number;
}

export default function MetricsChart({
  dataPoints,
  threshold = 2000,
}: MetricsChartProps) {
  const width = 320;
  const height = 160;
  const padding = { top: 10, right: 10, bottom: 25, left: 45 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Use last 20 data points
  const visiblePoints = dataPoints.slice(-20);

  if (visiblePoints.length === 0) {
    return (
      <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-400 mb-2">
          p99 Latency (ms)
        </h4>
        <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
          Waiting for metrics...
        </div>
      </div>
    );
  }

  const maxValue = Math.max(
    threshold * 1.5,
    ...visiblePoints.map((p) => p.value)
  );
  const yScale = (v: number) =>
    padding.top + chartHeight - (v / maxValue) * chartHeight;
  const xScale = (i: number) =>
    padding.left + (i / Math.max(visiblePoints.length - 1, 1)) * chartWidth;

  const linePath = visiblePoints
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(p.value)}`)
    .join(" ");

  const areaPath = `${linePath} L ${xScale(visiblePoints.length - 1)} ${yScale(0)} L ${xScale(0)} ${yScale(0)} Z`;

  const currentValue = visiblePoints[visiblePoints.length - 1]?.value ?? 0;
  const isBreached = currentValue > threshold;

  return (
    <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-gray-400">p99 Latency</h4>
        <span
          className={`text-lg font-bold font-mono ${
            isBreached ? "text-accent-red" : "text-accent-green"
          }`}
        >
          {Math.round(currentValue)}ms
        </span>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = padding.top + chartHeight * (1 - ratio);
          const label = Math.round(maxValue * ratio);
          return (
            <g key={ratio}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="#1a2332"
                strokeWidth="1"
              />
              <text
                x={padding.left - 5}
                y={y + 3}
                textAnchor="end"
                fontSize="8"
                fill="#6b7280"
              >
                {label}
              </text>
            </g>
          );
        })}

        {/* Threshold line */}
        <line
          x1={padding.left}
          y1={yScale(threshold)}
          x2={width - padding.right}
          y2={yScale(threshold)}
          stroke="#ef4444"
          strokeWidth="1"
          strokeDasharray="4 3"
          opacity="0.6"
        />
        <text
          x={width - padding.right}
          y={yScale(threshold) - 4}
          textAnchor="end"
          fontSize="7"
          fill="#ef4444"
          opacity="0.8"
        >
          {threshold}ms threshold
        </text>

        {/* Area fill */}
        <path
          d={areaPath}
          fill={isBreached ? "rgba(239, 68, 68, 0.1)" : "rgba(16, 185, 129, 0.1)"}
        />

        {/* Line */}
        <path
          d={linePath}
          fill="none"
          stroke={isBreached ? "#ef4444" : "#10b981"}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Current point */}
        <circle
          cx={xScale(visiblePoints.length - 1)}
          cy={yScale(currentValue)}
          r="3"
          fill={isBreached ? "#ef4444" : "#10b981"}
        />
      </svg>
    </div>
  );
}

"use client";

import { useState, useEffect, useRef } from "react";
import type { MetricsDataPoint } from "@/lib/types";

interface ImpactCounterProps {
  metrics: MetricsDataPoint[];
  threshold?: number;
  isIncident: boolean;
  revenuePerMinute?: number | null;
}

export default function ImpactCounter({
  metrics,
  threshold = 2000,
  isIncident,
  revenuePerMinute,
}: ImpactCounterProps) {
  const [estimatedLoss, setEstimatedLoss] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lossRef = useRef(0);

  useEffect(() => {
    if (!isIncident) {
      // Reset when incident resolves
      if (intervalRef.current) clearInterval(intervalRef.current);
      lossRef.current = 0;
      setEstimatedLoss(0);
      return;
    }

    // During incident: accumulate losses per second while latency exceeds threshold
    intervalRef.current = setInterval(() => {
      const latest = metrics[metrics.length - 1];
      if (latest && latest.value > threshold) {
        // Use economic profile revenue rate, or synthetic fallback
        const increment = revenuePerMinute
          ? revenuePerMinute / 60
          : (latest.value - threshold) / 1000 * 30 * (Math.random() * 0.5 + 0.5);
        lossRef.current += increment;
        setEstimatedLoss(lossRef.current);
      }
    }, 1000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isIncident, metrics, threshold, revenuePerMinute]);

  if (!isIncident || estimatedLoss === 0) return null;

  return (
    <div className="bg-accent-red/10 border border-accent-red/30 rounded-lg p-4 animate-glow">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-2 h-2 bg-accent-red rounded-full animate-pulse" />
        <h4 className="text-sm font-medium text-accent-red">
          Estimated Impact
        </h4>
      </div>
      <div className="text-2xl font-bold font-mono text-accent-red">
        ${estimatedLoss.toLocaleString("en-US", {
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        })}
      </div>
      <p className="text-xs text-accent-red/60 mt-1">
        Revenue at risk while p99 exceeds threshold
      </p>
    </div>
  );
}

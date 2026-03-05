"use client";

import type { TradeActivity } from "@/lib/types";

interface ActivityFeedProps {
  trades: TradeActivity[];
}

function latencyColor(ms: number): string {
  if (ms > 500) return "text-accent-red";
  if (ms > 100) return "text-accent-amber";
  return "text-accent-green";
}

export default function ActivityFeed({ trades }: ActivityFeedProps) {
  if (trades.length === 0) {
    return (
      <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-400 mb-2">
          Trading Activity
        </h4>
        <div className="text-gray-500 text-xs text-center py-3">
          Waiting for trades...
        </div>
      </div>
    );
  }

  // Show newest first, limit to 8
  const recent = [...trades].reverse().slice(0, 8);

  return (
    <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-4">
      <h4 className="text-sm font-medium text-gray-400 mb-2">
        Trading Activity
      </h4>
      <div className="space-y-1 max-h-48 overflow-y-auto custom-scrollbar">
        {recent.map((trade, i) => {
          const time = new Date(trade.timestamp).toLocaleTimeString();
          return (
            <div
              key={`${trade.timestamp}-${i}`}
              className="flex items-center justify-between text-xs font-mono py-0.5"
            >
              <div className="flex items-center gap-1.5">
                <span
                  className={
                    trade.side === "BUY"
                      ? "text-accent-green"
                      : "text-accent-red"
                  }
                >
                  {trade.side}
                </span>
                <span className="text-gray-300">
                  {trade.quantity} {trade.symbol}
                </span>
                {trade.price !== null && (
                  <span className="text-gray-500">
                    @${trade.price.toFixed(2)}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className={latencyColor(trade.latency_ms)}>
                  {trade.latency_ms.toFixed(0)}ms
                </span>
                <span className="text-gray-600">{time}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

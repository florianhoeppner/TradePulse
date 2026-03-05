"use client";

import { useState, useEffect } from "react";
import type { StockQuote } from "@/lib/types";

interface StockCardProps {
  stock: StockQuote;
}

function Sparkline({ data, isUp }: { data: number[]; isUp: boolean }) {
  if (data.length < 2) return null;
  const w = 80;
  const h = 28;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  });

  const color = isUp ? "#10b981" : "#ef4444";

  return (
    <svg width={w} height={h} className="flex-shrink-0">
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function StockCard({ stock }: StockCardProps) {
  const [secondsAgo, setSecondsAgo] = useState(0);
  const isUp = stock.change >= 0;

  useEffect(() => {
    const update = () => {
      const elapsed = Math.floor(
        (Date.now() - new Date(stock.lastUpdated).getTime()) / 1000
      );
      setSecondsAgo(Math.max(0, elapsed));
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [stock.lastUpdated]);

  const staleLevel =
    secondsAgo > 10 ? "text-accent-red" : secondsAgo > 5 ? "text-accent-amber" : "text-gray-500";
  const staleBorder =
    secondsAgo > 10
      ? "border-accent-red/40 animate-pulse"
      : "border-navy-700";

  return (
    <div
      className={`bg-navy-800/50 border rounded-lg p-3 transition-colors ${staleBorder}`}
    >
      <div className="flex items-start justify-between mb-1">
        <div>
          <span className="text-sm font-bold text-white">{stock.symbol}</span>
          <span className="text-xs text-gray-500 ml-1.5">{stock.name}</span>
        </div>
        <Sparkline data={stock.history} isUp={isUp} />
      </div>
      <div className="flex items-end justify-between">
        <div>
          <span className="text-lg font-bold font-mono text-white">
            ${stock.price.toFixed(2)}
          </span>
          <div
            className={`text-xs font-mono ${
              isUp ? "text-accent-green" : "text-accent-red"
            }`}
          >
            {isUp ? "+" : ""}
            {stock.change.toFixed(2)} ({isUp ? "+" : ""}
            {stock.changePercent.toFixed(2)}%)
          </div>
        </div>
        <span className={`text-xs font-mono ${staleLevel}`}>
          {secondsAgo}s ago
        </span>
      </div>
    </div>
  );
}

"use client";

import type { StockQuote } from "@/lib/types";

interface TickerBarProps {
  stocks: StockQuote[];
  isStale: boolean;
}

function TickerItem({ stock, isStale }: { stock: StockQuote; isStale: boolean }) {
  const isUp = stock.change >= 0;
  return (
    <span
      className={`inline-flex items-center gap-2 px-4 py-1 text-sm font-mono whitespace-nowrap ${
        isStale ? "opacity-50" : ""
      }`}
    >
      <span className="font-semibold text-white">{stock.symbol}</span>
      <span className={isUp ? "text-accent-green" : "text-accent-red"}>
        ${stock.price.toFixed(2)}
      </span>
      <span
        className={`text-xs ${isUp ? "text-accent-green" : "text-accent-red"}`}
      >
        {isUp ? "\u25B2" : "\u25BC"} {Math.abs(stock.change).toFixed(2)} (
        {Math.abs(stock.changePercent).toFixed(2)}%)
      </span>
      {isStale && (
        <span className="text-accent-red text-xs animate-pulse">STALE</span>
      )}
    </span>
  );
}

export default function TickerBar({ stocks, isStale }: TickerBarProps) {
  if (stocks.length === 0) return null;

  // Duplicate items for seamless scroll loop
  const items = [...stocks, ...stocks];

  return (
    <div className="w-full bg-navy-900/80 border-b border-navy-700 overflow-hidden">
      <div className="ticker-scroll flex items-center py-1">
        {items.map((stock, i) => (
          <span key={`${stock.symbol}-${i}`} className="flex items-center">
            <TickerItem stock={stock} isStale={isStale} />
            <span className="text-navy-600 mx-1">|</span>
          </span>
        ))}
      </div>
      <style jsx>{`
        .ticker-scroll {
          animation: scroll-left 20s linear infinite;
          width: max-content;
        }
        .ticker-scroll:hover {
          animation-play-state: paused;
        }
        @keyframes scroll-left {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
      `}</style>
    </div>
  );
}

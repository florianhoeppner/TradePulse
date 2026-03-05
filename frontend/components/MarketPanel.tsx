"use client";

import type { StockQuote } from "@/lib/types";
import StockCard from "./StockCard";

interface MarketPanelProps {
  stocks: StockQuote[];
  isStale: boolean;
}

export default function MarketPanel({ stocks, isStale }: MarketPanelProps) {
  if (stocks.length === 0) {
    return (
      <div className="bg-navy-800/50 border border-navy-700 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-400 mb-2">
          Live Market Data
        </h4>
        <div className="flex items-center justify-center h-20 text-gray-500 text-sm">
          Connecting to market feed...
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-gray-400">Live Market Data</h4>
        {isStale && (
          <span className="text-xs text-accent-red font-mono animate-pulse">
            FEED DELAYED
          </span>
        )}
      </div>
      <div className="space-y-2">
        {stocks.map((stock) => (
          <StockCard key={stock.symbol} stock={stock} />
        ))}
      </div>
    </div>
  );
}

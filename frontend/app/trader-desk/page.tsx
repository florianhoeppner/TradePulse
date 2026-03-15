"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useAgentStreamContext } from "@/lib/AgentStreamContext";
import { useMarketData } from "@/lib/useMarketData";
import { fetchMarketStatus } from "@/lib/api";
import Navbar from "@/components/Navbar";
import TickerBar from "@/components/TickerBar";
import MarketCommentary from "@/components/MarketCommentary";
import type { StockQuote, TradeActivity, MarketStatus } from "@/lib/types";

// ---------- helpers ----------

function latencyColor(ms: number): string {
  if (ms > 500) return "text-accent-red";
  if (ms > 100) return "text-accent-amber";
  return "text-accent-green";
}

function panelBorder(isStale: boolean): string {
  return isStale
    ? "border-accent-red/40 animate-pulse"
    : "border-navy-700";
}

// Deterministic pseudo-random from a seed for order book depth
function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

// ---------- sub-components (inline) ----------

function ConnectionBanner({
  isConnected,
  isStale,
  lastFetchTime,
}: {
  isConnected: boolean;
  isStale: boolean;
  lastFetchTime: number | null;
}) {
  const [secondsAgo, setSecondsAgo] = useState(0);

  useEffect(() => {
    const tick = () => {
      if (lastFetchTime) {
        setSecondsAgo(Math.floor((Date.now() - lastFetchTime) / 1000));
      }
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [lastFetchTime]);

  if (isConnected && !isStale) return null;

  return (
    <div className="bg-accent-red/15 border border-accent-red/40 text-accent-red px-4 py-2 flex items-center justify-center gap-3 animate-pulse">
      <span className="w-2.5 h-2.5 rounded-full bg-accent-red" />
      {!isConnected ? (
        <span className="text-sm font-bold tracking-wide">
          CONNECTION LOST &mdash; Live data unavailable
        </span>
      ) : (
        <span className="text-sm font-bold tracking-wide">
          DATA STALE &mdash; Last update {secondsAgo}s ago
        </span>
      )}
    </div>
  );
}

function MarketClosedBanner({
  marketStatus,
}: {
  marketStatus: MarketStatus | null;
}) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (!marketStatus || marketStatus.is_open) return null;

  const nextOpen = new Date(marketStatus.next_open_utc).getTime();
  const diff = Math.max(0, nextOpen - now);
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);

  const countdown =
    hours > 0
      ? `${hours}h ${minutes}m ${seconds}s`
      : minutes > 0
        ? `${minutes}m ${seconds}s`
        : `${seconds}s`;

  return (
    <div className="bg-accent-amber/10 border-b border-accent-amber/30 px-4 py-2 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="w-2 h-2 rounded-full bg-accent-amber" />
        <span className="text-sm font-bold text-accent-amber tracking-wide">
          {marketStatus.exchange} &mdash; Market Closed
        </span>
        <span className="text-xs text-gray-400">
          Displaying last close prices
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm font-mono text-accent-amber">
          Opens in {countdown}
        </span>
        <span className="text-xs text-gray-500 font-mono">
          {marketStatus.current_time_et}
        </span>
      </div>
    </div>
  );
}

function Watchlist({
  stocks,
  selectedSymbol,
  onSelect,
  isStale,
}: {
  stocks: StockQuote[];
  selectedSymbol: string;
  onSelect: (s: string) => void;
  isStale: boolean;
}) {
  return (
    <div
      className={`bg-navy-800/50 border rounded-lg p-3 flex flex-col h-full ${panelBorder(isStale)}`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
          Watchlist
        </h3>
        {isStale && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-red/20 text-accent-red font-bold animate-pulse">
            STALE
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-gray-500 border-b border-navy-700">
              <th className="text-left py-1 pr-2">Symbol</th>
              <th className="text-right py-1 pr-2">Last</th>
              <th className="text-right py-1 pr-2">Chg</th>
              <th className="text-right py-1">%</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((stock) => {
              const isUp = stock.change >= 0;
              const isSelected = stock.symbol === selectedSymbol;
              return (
                <tr
                  key={stock.symbol}
                  onClick={() => onSelect(stock.symbol)}
                  className={`cursor-pointer transition-colors border-b border-navy-700/50 ${
                    isSelected
                      ? "bg-accent-blue/10"
                      : "hover:bg-navy-700/40"
                  } ${isStale ? "opacity-50" : ""}`}
                >
                  <td className="py-1.5 pr-2">
                    <span className="font-bold text-white">
                      {stock.symbol}
                    </span>
                    <span className="text-gray-500 ml-1 text-[10px] hidden lg:inline">
                      {stock.name}
                    </span>
                  </td>
                  <td className="text-right py-1.5 pr-2 text-white">
                    ${stock.price.toFixed(2)}
                  </td>
                  <td
                    className={`text-right py-1.5 pr-2 ${
                      isUp ? "text-accent-green" : "text-accent-red"
                    }`}
                  >
                    {isUp ? "+" : ""}
                    {stock.change.toFixed(2)}
                  </td>
                  <td
                    className={`text-right py-1.5 ${
                      isUp ? "text-accent-green" : "text-accent-red"
                    }`}
                  >
                    {isUp ? "+" : ""}
                    {stock.changePercent.toFixed(2)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PriceChart({
  stock,
  isStale,
}: {
  stock: StockQuote | undefined;
  isStale: boolean;
}) {
  if (!stock || stock.history.length < 2) {
    return (
      <div
        className={`bg-navy-800/50 border rounded-lg p-3 flex items-center justify-center h-full ${panelBorder(isStale)}`}
      >
        <span className="text-gray-500 text-sm">
          Select a stock to view chart
        </span>
      </div>
    );
  }

  const data = stock.history;
  const isUp = stock.change >= 0;
  const w = 500;
  const h = 220;
  const pad = { top: 15, right: 15, bottom: 25, left: 55 };
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const xScale = (i: number) =>
    pad.left + (i / Math.max(data.length - 1, 1)) * cw;
  const yScale = (v: number) => pad.top + ch - ((v - min) / range) * ch;

  const linePath = data
    .map((v, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yScale(v)}`)
    .join(" ");
  const areaPath = `${linePath} L ${xScale(data.length - 1)} ${yScale(min)} L ${xScale(0)} ${yScale(min)} Z`;

  const color = isUp ? "#10b981" : "#ef4444";
  const colorFaint = isUp ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)";

  const gridValues = [0, 0.25, 0.5, 0.75, 1].map(
    (r) => min + range * r
  );

  return (
    <div
      className={`bg-navy-800/50 border rounded-lg p-3 flex flex-col h-full ${panelBorder(isStale)}`}
    >
      <div className="flex items-center justify-between mb-1">
        <div>
          <span className="text-sm font-bold text-white">{stock.symbol}</span>
          <span className="text-xs text-gray-500 ml-2">{stock.name}</span>
        </div>
        <div className="flex items-center gap-3">
          {isStale && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-amber/20 text-accent-amber font-bold">
              DATA DELAYED
            </span>
          )}
          <span className="text-lg font-bold font-mono text-white">
            ${stock.price.toFixed(2)}
          </span>
          <span
            className={`text-sm font-mono ${
              isUp ? "text-accent-green" : "text-accent-red"
            }`}
          >
            {isUp ? "+" : ""}
            {stock.change.toFixed(2)} ({isUp ? "+" : ""}
            {stock.changePercent.toFixed(2)}%)
          </span>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-full">
          {/* Grid lines */}
          {gridValues.map((v, i) => (
            <g key={i}>
              <line
                x1={pad.left}
                y1={yScale(v)}
                x2={w - pad.right}
                y2={yScale(v)}
                stroke="#1a2332"
                strokeWidth="1"
              />
              <text
                x={pad.left - 5}
                y={yScale(v) + 3}
                textAnchor="end"
                fontSize="8"
                fill="#6b7280"
              >
                ${v.toFixed(2)}
              </text>
            </g>
          ))}

          {/* Area fill */}
          <path d={areaPath} fill={colorFaint} />

          {/* Line */}
          <path
            d={linePath}
            fill="none"
            stroke={isStale ? "#6b7280" : color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={isStale ? "4 3" : "none"}
          />

          {/* Current price dot */}
          <circle
            cx={xScale(data.length - 1)}
            cy={yScale(data[data.length - 1])}
            r="4"
            fill={isStale ? "#6b7280" : color}
          />

          {/* Current price label */}
          <text
            x={xScale(data.length - 1) + 8}
            y={yScale(data[data.length - 1]) + 3}
            fontSize="9"
            fill={isStale ? "#6b7280" : color}
            fontWeight="bold"
          >
            ${data[data.length - 1].toFixed(2)}
          </text>
        </svg>
      </div>
    </div>
  );
}

function OrderBook({
  stock,
  isStale,
}: {
  stock: StockQuote | undefined;
  isStale: boolean;
}) {
  const levels = useMemo(() => {
    if (!stock) return [];
    const spread = stock.price * 0.002; // 0.2% spread
    const mid = stock.price;
    const result: {
      price: number;
      size: number;
      side: "bid" | "ask";
    }[] = [];

    // 8 ask levels (ascending)
    for (let i = 7; i >= 0; i--) {
      const price = mid + spread * (i + 1) * 0.5;
      const size = Math.floor(
        seededRandom(Math.floor(price * 100) + i) * 800 + 100
      );
      result.push({ price, size, side: "ask" });
    }
    // 8 bid levels (descending)
    for (let i = 0; i < 8; i++) {
      const price = mid - spread * (i + 1) * 0.5;
      const size = Math.floor(
        seededRandom(Math.floor(price * 100) + i + 50) * 800 + 100
      );
      result.push({ price, size, side: "bid" });
    }
    return result;
  }, [stock]);

  const maxSize = Math.max(...levels.map((l) => l.size), 1);

  return (
    <div
      className={`bg-navy-800/50 border rounded-lg p-3 flex flex-col h-full relative ${panelBorder(isStale)}`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
          Order Book {stock ? `- ${stock.symbol}` : ""}
        </h3>
        <span className="text-[10px] text-gray-500 font-mono">
          {stock ? `Spread: $${(stock.price * 0.002).toFixed(2)}` : ""}
        </span>
      </div>

      {isStale && (
        <div className="absolute inset-0 bg-navy-900/70 rounded-lg flex items-center justify-center z-10">
          <span className="text-accent-red font-bold text-sm animate-pulse">
            NO LIVE DATA
          </span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <table className="w-full text-[11px] font-mono">
          <thead>
            <tr className="text-gray-500">
              <th className="text-left py-0.5">Price</th>
              <th className="text-right py-0.5">Size</th>
              <th className="text-left py-0.5 w-1/2">Depth</th>
            </tr>
          </thead>
          <tbody>
            {levels.map((level, i) => {
              const pct = (level.size / maxSize) * 100;
              const isAsk = level.side === "ask";
              return (
                <tr
                  key={i}
                  className={
                    i === 7
                      ? "border-b border-navy-600"
                      : i === 8
                        ? "border-t border-navy-600"
                        : ""
                  }
                >
                  <td
                    className={`py-0.5 ${
                      isAsk ? "text-accent-red" : "text-accent-green"
                    }`}
                  >
                    ${level.price.toFixed(2)}
                  </td>
                  <td className="text-right py-0.5 text-gray-300">
                    {level.size}
                  </td>
                  <td className="py-0.5 pl-2">
                    <div className="relative h-3 bg-navy-900 rounded-sm overflow-hidden">
                      <div
                        className={`absolute top-0 left-0 h-full rounded-sm ${
                          isAsk ? "bg-accent-red/30" : "bg-accent-green/30"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {stock && !isStale && (
        <div className="mt-1 pt-1 border-t border-navy-700 text-center">
          <span className="text-[10px] text-gray-500">Mid: </span>
          <span className="text-[10px] text-white font-bold font-mono">
            ${stock.price.toFixed(2)}
          </span>
        </div>
      )}
    </div>
  );
}

function Positions({
  trades,
  stocks,
  isStale,
}: {
  trades: TradeActivity[];
  stocks: StockQuote[];
  isStale: boolean;
}) {
  const positions = useMemo(() => {
    const map: Record<
      string,
      { qty: number; totalCost: number; symbol: string }
    > = {};

    for (const t of trades) {
      if (t.status !== "filled" || t.price === null) continue;
      if (!map[t.symbol]) {
        map[t.symbol] = { qty: 0, totalCost: 0, symbol: t.symbol };
      }
      const sign = t.side === "BUY" ? 1 : -1;
      map[t.symbol].qty += sign * t.quantity;
      map[t.symbol].totalCost += sign * t.quantity * t.price;
    }

    const priceMap: Record<string, number> = {};
    for (const s of stocks) priceMap[s.symbol] = s.price;

    return Object.values(map)
      .filter((p) => p.qty !== 0)
      .map((p) => {
        const avgPrice = Math.abs(p.totalCost / p.qty);
        const currentPrice = priceMap[p.symbol] ?? avgPrice;
        const pnl = (currentPrice - avgPrice) * p.qty;
        const pnlPct = ((currentPrice - avgPrice) / avgPrice) * 100;
        return {
          symbol: p.symbol,
          qty: p.qty,
          avgPrice,
          currentPrice,
          pnl,
          pnlPct,
        };
      });
  }, [trades, stocks]);

  const totalPnl = positions.reduce((s, p) => s + p.pnl, 0);

  return (
    <div
      className={`bg-navy-800/50 border rounded-lg p-3 flex flex-col h-full ${panelBorder(isStale)}`}
    >
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
        Positions
      </h3>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {positions.length === 0 ? (
          <div className="text-gray-500 text-xs text-center py-4">
            No open positions
          </div>
        ) : (
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr className="text-gray-500 border-b border-navy-700">
                <th className="text-left py-1">Sym</th>
                <th className="text-right py-1">Qty</th>
                <th className="text-right py-1">Avg</th>
                <th className="text-right py-1">Curr</th>
                <th className="text-right py-1">P&L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const isProfit = p.pnl >= 0;
                return (
                  <tr key={p.symbol} className="border-b border-navy-700/30">
                    <td className="py-1 text-white font-bold">{p.symbol}</td>
                    <td className="text-right py-1 text-gray-300">{p.qty}</td>
                    <td className="text-right py-1 text-gray-400">
                      ${p.avgPrice.toFixed(2)}
                    </td>
                    <td className="text-right py-1 text-white">
                      ${p.currentPrice.toFixed(2)}
                    </td>
                    <td
                      className={`text-right py-1 ${
                        isProfit ? "text-accent-green" : "text-accent-red"
                      }`}
                    >
                      {isProfit ? "+" : ""}${p.pnl.toFixed(2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {positions.length > 0 && (
        <div className="mt-1 pt-1 border-t border-navy-700 flex items-center justify-between">
          <span className="text-[10px] text-gray-500">Total P&L</span>
          <span
            className={`text-xs font-bold font-mono ${
              totalPnl >= 0 ? "text-accent-green" : "text-accent-red"
            }`}
          >
            {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
          </span>
        </div>
      )}
    </div>
  );
}

function TradeBlotter({
  trades,
  isStale,
}: {
  trades: TradeActivity[];
  isStale: boolean;
}) {
  const recent = [...trades].reverse();

  return (
    <div
      className={`bg-navy-800/50 border rounded-lg p-3 flex flex-col h-full ${panelBorder(isStale)}`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
          Trade Blotter
        </h3>
        <span className="text-[10px] text-gray-500 font-mono">
          {recent.length} fills
        </span>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {recent.length === 0 ? (
          <div className="text-gray-500 text-xs text-center py-4">
            No trades yet
          </div>
        ) : (
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr className="text-gray-500 border-b border-navy-700">
                <th className="text-left py-1">Time</th>
                <th className="text-left py-1">Side</th>
                <th className="text-left py-1">Sym</th>
                <th className="text-right py-1">Qty</th>
                <th className="text-right py-1">Price</th>
                <th className="text-right py-1">Lat.</th>
                <th className="text-right py-1">Sts</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((trade, i) => {
                const time = new Date(trade.timestamp).toLocaleTimeString();
                const highLatency = trade.latency_ms > 500;
                return (
                  <tr
                    key={`${trade.timestamp}-${i}`}
                    className={`border-b border-navy-700/30 ${
                      highLatency ? "bg-accent-red/5" : ""
                    }`}
                  >
                    <td className="py-1 text-gray-400">{time}</td>
                    <td
                      className={`py-1 font-bold ${
                        trade.side === "BUY"
                          ? "text-accent-green"
                          : "text-accent-red"
                      }`}
                    >
                      {trade.side}
                    </td>
                    <td className="py-1 text-white">{trade.symbol}</td>
                    <td className="text-right py-1 text-gray-300">
                      {trade.quantity}
                    </td>
                    <td className="text-right py-1 text-white">
                      {trade.price !== null ? `$${trade.price.toFixed(2)}` : "-"}
                    </td>
                    <td
                      className={`text-right py-1 ${latencyColor(
                        trade.latency_ms
                      )} ${highLatency ? "animate-pulse font-bold" : ""}`}
                    >
                      {trade.latency_ms.toFixed(0)}ms
                    </td>
                    <td
                      className={`text-right py-1 ${
                        trade.status === "filled"
                          ? "text-accent-green"
                          : "text-accent-red"
                      }`}
                    >
                      {trade.status === "filled" ? "OK" : "ERR"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function SystemStatus({
  isConnected,
  isStale,
  lastFetchTime,
  currentState,
  metrics,
}: {
  isConnected: boolean;
  isStale: boolean;
  lastFetchTime: number | null;
  currentState: string;
  metrics: { time: number; value: number }[];
}) {
  const [secondsAgo, setSecondsAgo] = useState(0);

  useEffect(() => {
    const tick = () => {
      if (lastFetchTime) {
        setSecondsAgo(Math.floor((Date.now() - lastFetchTime) / 1000));
      }
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [lastFetchTime]);

  const latestMetric = metrics.length > 0 ? metrics[metrics.length - 1].value : 0;
  const threshold = 2000;
  const latencyPct = Math.min((latestMetric / threshold) * 100, 100);
  const latencyBreached = latestMetric > threshold;

  const staleLevel =
    secondsAgo > 10
      ? "text-accent-red"
      : secondsAgo > 5
        ? "text-accent-amber"
        : "text-accent-green";

  const stateLabels: Record<string, { text: string; color: string }> = {
    idle: { text: "IDLE", color: "bg-gray-600/20 text-gray-400" },
    monitoring: { text: "MONITORING", color: "bg-accent-blue/20 text-accent-blue" },
    anomaly_detected: { text: "ALERT", color: "bg-accent-red/20 text-accent-red" },
    incident_created: { text: "INCIDENT", color: "bg-accent-red/20 text-accent-red" },
    investigating: { text: "INVESTIGATING", color: "bg-accent-amber/20 text-accent-amber" },
    analyzing: { text: "ANALYZING", color: "bg-accent-amber/20 text-accent-amber" },
    fix_generated: { text: "FIX READY", color: "bg-accent-green/20 text-accent-green" },
    awaiting_approval: { text: "AWAITING", color: "bg-accent-amber/20 text-accent-amber" },
    resolved: { text: "RESOLVED", color: "bg-accent-green/20 text-accent-green" },
    error: { text: "ERROR", color: "bg-accent-red/20 text-accent-red" },
  };

  const stateInfo = stateLabels[currentState] ?? {
    text: currentState.toUpperCase(),
    color: "bg-gray-600/20 text-gray-400",
  };

  return (
    <div
      className={`bg-navy-800/50 border rounded-lg p-3 flex flex-col h-full ${
        !isConnected || isStale
          ? "border-accent-red/40"
          : "border-navy-700"
      }`}
    >
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">
        System Status
      </h3>

      <div className="space-y-3 flex-1">
        {/* Connection */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Connection</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-accent-green" : "bg-accent-red animate-pulse"
              }`}
            />
            <span
              className={`text-xs font-bold ${
                isConnected ? "text-accent-green" : "text-accent-red"
              }`}
            >
              {isConnected ? "LIVE" : "DOWN"}
            </span>
          </div>
        </div>

        {/* Data Freshness */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Data Age</span>
          <span className={`text-xs font-bold font-mono ${staleLevel}`}>
            {secondsAgo}s
          </span>
        </div>

        {/* Latency Gauge */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-400">p99 Latency</span>
            <span
              className={`text-xs font-bold font-mono ${
                latencyBreached ? "text-accent-red" : "text-accent-green"
              }`}
            >
              {Math.round(latestMetric)}ms
            </span>
          </div>
          <div className="h-2 bg-navy-900 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                latencyBreached ? "bg-accent-red" : "bg-accent-green"
              }`}
              style={{ width: `${latencyPct}%` }}
            />
          </div>
          <div className="flex justify-between mt-0.5">
            <span className="text-[9px] text-gray-600">0ms</span>
            <span className="text-[9px] text-gray-600">{threshold}ms</span>
          </div>
        </div>

        {/* Agent State */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Agent</span>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${stateInfo.color}`}
          >
            {stateInfo.text}
          </span>
        </div>

        {/* Latency Warning */}
        {latencyBreached && (
          <div className="bg-accent-red/10 border border-accent-red/30 rounded px-2 py-1.5 mt-1">
            <span className="text-[10px] text-accent-red font-bold animate-pulse">
              HIGH LATENCY DETECTED
            </span>
          </div>
        )}

        {/* Disconnected Warning */}
        {!isConnected && (
          <div className="bg-accent-red/10 border border-accent-red/30 rounded px-2 py-1.5 mt-1">
            <span className="text-[10px] text-accent-red font-bold animate-pulse">
              BACKEND UNREACHABLE
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- page ----------

export default function TraderDesk() {
  const { currentState, metrics, isConnected } = useAgentStreamContext();
  const { stocks, trades, lastFetchTime, isStale } = useMarketData();

  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);

  // Default to first stock when loaded
  useEffect(() => {
    if (stocks.length > 0 && !selectedSymbol) {
      setSelectedSymbol(stocks[0].symbol);
    }
  }, [stocks, selectedSymbol]);

  // Poll market status every 30 seconds
  const pollMarketStatus = useCallback(async () => {
    const res = await fetchMarketStatus();
    if (res.ok && res.data) {
      setMarketStatus(res.data as MarketStatus);
    }
  }, []);

  useEffect(() => {
    pollMarketStatus();
    const t = setInterval(pollMarketStatus, 30000);
    return () => clearInterval(t);
  }, [pollMarketStatus]);

  const selectedStock = stocks.find((s) => s.symbol === selectedSymbol);

  return (
    <div className="min-h-screen bg-navy-950">
      <Navbar isConnected={isConnected} />
      <TickerBar stocks={stocks} isStale={isStale} />
      <MarketClosedBanner marketStatus={marketStatus} />
      <ConnectionBanner
        isConnected={isConnected}
        isStale={isStale}
        lastFetchTime={lastFetchTime}
      />

      <div className="max-w-[1600px] mx-auto px-3 py-3">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-lg font-bold text-white">Trader Desk</h1>
            <p className="text-xs text-gray-500">
              Real-time market data &amp; order management
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-gray-500 font-mono">
              {new Date().toLocaleDateString("en-US", {
                weekday: "short",
                month: "short",
                day: "numeric",
              })}
            </span>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                !isConnected || isStale
                  ? "bg-accent-red/20 text-accent-red animate-pulse"
                  : marketStatus && !marketStatus.is_open
                    ? "bg-accent-amber/20 text-accent-amber"
                    : "bg-accent-green/20 text-accent-green"
              }`}
            >
              {!isConnected || isStale
                ? "DEGRADED"
                : marketStatus && !marketStatus.is_open
                  ? "CLOSED"
                  : "LIVE"}
            </span>
          </div>
        </div>

        {/* Grid layout — 3 columns, 2 rows */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          {/* Row 1 */}
          {/* Watchlist — 3 cols */}
          <div className="lg:col-span-3 lg:row-span-1" style={{ minHeight: "300px" }}>
            <Watchlist
              stocks={stocks}
              selectedSymbol={selectedSymbol}
              onSelect={setSelectedSymbol}
              isStale={isStale}
            />
          </div>

          {/* Price Chart — 5 cols */}
          <div className="lg:col-span-5" style={{ minHeight: "300px" }}>
            <PriceChart stock={selectedStock} isStale={isStale} />
          </div>

          {/* Order Book — 4 cols */}
          <div className="lg:col-span-4" style={{ minHeight: "300px" }}>
            <OrderBook stock={selectedStock} isStale={isStale} />
          </div>

          {/* Row 2 */}
          {/* Positions — 3 cols */}
          <div className="lg:col-span-3" style={{ minHeight: "260px" }}>
            <Positions trades={trades} stocks={stocks} isStale={isStale} />
          </div>

          {/* Trade Blotter — 5 cols */}
          <div className="lg:col-span-5" style={{ minHeight: "260px" }}>
            <TradeBlotter trades={trades} isStale={isStale} />
          </div>

          {/* System Status — 4 cols */}
          <div className="lg:col-span-4" style={{ minHeight: "260px" }}>
            <SystemStatus
              isConnected={isConnected}
              isStale={isStale}
              lastFetchTime={lastFetchTime}
              currentState={currentState}
              metrics={metrics}
            />
          </div>

          {/* AI Market Commentary — full width */}
          <div className="lg:col-span-12">
            <MarketCommentary />
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { fetchMarketPrices, fetchMarketActivity } from "./api";
import type { StockQuote, TradeActivity } from "./types";

const POLL_INTERVAL_MS = 3000;

export function useMarketData() {
  const [stocks, setStocks] = useState<StockQuote[]>([]);
  const [trades, setTrades] = useState<TradeActivity[]>([]);
  const [lastFetchTime, setLastFetchTime] = useState<number | null>(null);
  const [isStale, setIsStale] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const staleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    const [pricesRes, activityRes] = await Promise.all([
      fetchMarketPrices(),
      fetchMarketActivity(),
    ]);

    if (pricesRes.ok && pricesRes.data) {
      const data = pricesRes.data as { quotes: StockQuote[] };
      setStocks(data.quotes || []);
      setLastFetchTime(Date.now());
      setIsStale(false);
    }

    if (activityRes.ok && activityRes.data) {
      const data = activityRes.data as { trades: TradeActivity[] };
      setTrades(data.trades || []);
    }
  }, []);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  // Track staleness — if no successful fetch in 10s, mark stale
  useEffect(() => {
    staleTimerRef.current = setInterval(() => {
      if (lastFetchTime && Date.now() - lastFetchTime > 10000) {
        setIsStale(true);
      }
    }, 1000);
    return () => {
      if (staleTimerRef.current) clearInterval(staleTimerRef.current);
    };
  }, [lastFetchTime]);

  return { stocks, trades, lastFetchTime, isStale };
}

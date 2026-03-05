"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { fetchMarketCommentary } from "@/lib/api";

const COMMENTARY_INTERVAL_MS = 30000; // Every 30 seconds

interface CommentaryData {
  commentary: string;
  isIncident: boolean;
  timestamp: string;
}

export default function MarketCommentary() {
  const [data, setData] = useState<CommentaryData | null>(null);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    const res = await fetchMarketCommentary();
    if (res.ok && res.data) {
      setData(res.data as CommentaryData);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetch();
    intervalRef.current = setInterval(fetch, COMMENTARY_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetch]);

  const borderColor = data?.isIncident
    ? "border-accent-red/40"
    : "border-navy-700";
  const bgColor = data?.isIncident ? "bg-accent-red/5" : "bg-navy-800/50";

  return (
    <div className={`${bgColor} border ${borderColor} rounded-lg p-4`}>
      <div className="flex items-center gap-2 mb-2">
        <div
          className={`w-1.5 h-1.5 rounded-full ${
            data?.isIncident
              ? "bg-accent-red animate-pulse"
              : "bg-accent-blue animate-pulse"
          }`}
        />
        <h4 className="text-sm font-medium text-gray-400">
          AI Market Analysis
        </h4>
        {loading && (
          <span className="text-xs text-gray-600 ml-auto">updating...</span>
        )}
      </div>
      {data ? (
        <p
          className={`text-xs leading-relaxed ${
            data.isIncident ? "text-accent-red/90" : "text-gray-300"
          }`}
        >
          {data.commentary}
        </p>
      ) : (
        <p className="text-xs text-gray-500">Generating analysis...</p>
      )}
    </div>
  );
}

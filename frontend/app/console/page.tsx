"use client";

import { useRef, useEffect, useState } from "react";
import { useAgentStream } from "@/lib/useAgentStream";
import Navbar from "@/components/Navbar";
import type { ConsoleEntry } from "@/lib/types";

function ConsoleEntryRow({ entry }: { entry: ConsoleEntry }) {
  const [expanded, setExpanded] = useState(false);
  const time = new Date(entry.timestamp).toLocaleTimeString();

  const typeConfig = {
    thinking: { icon: "\uD83E\uDDE0", color: "text-accent-blue", label: "THINK" },
    tool_call: { icon: "\uD83D\uDD27", color: "text-accent-amber", label: "TOOL" },
    state_change: { icon: "\u25CF", color: "text-accent-green", label: "STATE" },
    error: { icon: "\u2717", color: "text-accent-red", label: "ERROR" },
  };

  const config = typeConfig[entry.type] ?? typeConfig.state_change;

  return (
    <div className="border-b border-navy-800 py-2 px-3 hover:bg-navy-800/30">
      <div
        className="flex items-start gap-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs text-gray-500 font-mono w-20 flex-shrink-0 pt-0.5">
          {time}
        </span>
        <span
          className={`text-xs font-mono px-1.5 py-0.5 rounded ${config.color} bg-navy-700 flex-shrink-0`}
        >
          {config.label}
        </span>
        <span className="text-sm text-gray-300 flex-1 truncate">
          {entry.type === "thinking"
            ? (entry.data.reasoning as string)?.slice(0, 120)
            : entry.type === "tool_call"
            ? `${entry.data.tool}${
                entry.data.status === "running" ? " (running...)" : ""
              }`
            : entry.type === "state_change"
            ? `→ ${entry.data.state}${
                entry.data.message ? `: ${entry.data.message}` : ""
              }`
            : (entry.data.message as string) ?? "Error"}
        </span>
        <span className="text-gray-600 text-xs flex-shrink-0">
          {expanded ? "\u25B2" : "\u25BC"}
        </span>
      </div>

      {expanded && (
        <div className="mt-2 ml-[5.5rem]">
          <pre className="bg-navy-950 rounded p-3 text-xs text-gray-400 overflow-x-auto max-h-60 scrollbar-thin">
            {JSON.stringify(entry.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function ConsolePage() {
  const { consoleLog, isConnected } = useAgentStream();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [consoleLog.length]);

  return (
    <div className="min-h-screen">
      <Navbar isConnected={isConnected} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Agent Console</h1>
            <p className="text-sm text-gray-400 mt-1">
              Real-time agent reasoning, tool calls, and state transitions
            </p>
          </div>
          <span className="text-xs text-gray-500 font-mono">
            {consoleLog.length} events
          </span>
        </div>

        <div className="bg-navy-900 border border-navy-700 rounded-lg overflow-hidden">
          {/* Header bar */}
          <div className="flex items-center gap-2 px-4 py-2 bg-navy-800 border-b border-navy-700">
            <div className="w-3 h-3 rounded-full bg-accent-red/60" />
            <div className="w-3 h-3 rounded-full bg-accent-amber/60" />
            <div className="w-3 h-3 rounded-full bg-accent-green/60" />
            <span className="text-xs text-gray-500 ml-2 font-mono">
              tradepulse-agent
            </span>
          </div>

          {/* Log entries */}
          <div className="max-h-[calc(100vh-14rem)] overflow-y-auto scrollbar-thin">
            {consoleLog.length === 0 && (
              <div className="p-8 text-center text-gray-500 text-sm">
                No events yet. Start the agent from the Dashboard to see
                activity.
              </div>
            )}
            {consoleLog.map((entry) => (
              <ConsoleEntryRow key={entry.id} entry={entry} />
            ))}
            <div ref={bottomRef} />
          </div>
        </div>
      </main>
    </div>
  );
}

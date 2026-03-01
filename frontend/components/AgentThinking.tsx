"use client";

import { motion, AnimatePresence } from "framer-motion";

interface AgentThinkingProps {
  reasoning: string;
  isActive: boolean;
}

export default function AgentThinking({
  reasoning,
  isActive,
}: AgentThinkingProps) {
  return (
    <AnimatePresence>
      {isActive && reasoning && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="bg-navy-800/50 border border-navy-700 rounded-lg p-3 mb-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-accent-blue animate-pulse" />
            <span className="text-xs font-medium text-accent-blue">
              Agent Reasoning
            </span>
          </div>
          <p className="text-sm text-gray-300 leading-relaxed">{reasoning}</p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

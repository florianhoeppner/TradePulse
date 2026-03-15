"use client";

import { AgentStreamProvider } from "@/lib/AgentStreamContext";

export default function Providers({ children }: { children: React.ReactNode }) {
  return <AgentStreamProvider>{children}</AgentStreamProvider>;
}

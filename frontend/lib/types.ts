export type AgentState =
  | "idle"
  | "monitoring"
  | "anomaly_detected"
  | "cache_activated"
  | "load_shedding_enabled"
  | "backup_pricing_active"
  | "incident_created"
  | "investigating"
  | "analyzing"
  | "fix_generated"
  | "ticket_created"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "resolved"
  | "error";

export interface TimelineStepData {
  id: string;
  status: "pending" | "active" | "done" | "error";
  title: string;
  subtitle?: string;
  link?: string;
  data?: Record<string, unknown>;
  timestamp?: string;
  track?: "short-term" | "long-term";
}

export interface ToolCallEvent {
  tool: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  status: "running" | "done" | "error";
}

export interface ConsoleEntry {
  id: string;
  type: "thinking" | "tool_call" | "state_change" | "error";
  timestamp: string;
  data: Record<string, unknown>;
}

export interface MetricsDataPoint {
  time: number;
  value: number;
}

export interface RunHistoryEntry {
  timestamp: string;
  outcome: string;
  steps: number;
  duration_ms: number;
  details: Record<string, unknown>;
}

export interface ConfigEntry {
  configured: boolean;
  length: number;
}

export interface StockQuote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  lastUpdated: string;
  history: number[];
}

export interface TradeActivity {
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number | null;
  latency_ms: number;
  timestamp: string;
  status: "filled" | "error";
}

export interface MarketStatus {
  is_open: boolean;
  exchange: string;
  next_open_utc: string;
  current_time_et: string;
}

export interface EconomicProfile {
  avg_order_value_usd: number;
  orders_per_minute: number;
  sla_breach_penalty_usd: number;
  downtime_cost_per_hour_usd: number;
  currency: string;
}

export interface RiskFinding {
  finding_name: string;
  risk_usd_low: number;
  risk_usd_high: number;
  sla_relevant: boolean;
  rationale: string;
}

export interface RiskTableData {
  type: "risk_table";
  findings: RiskFinding[];
  total_low: number;
  total_high: number;
}

export interface RiskNeutralized {
  neutralized_low: number;
  neutralized_high: number;
  remaining_low: number;
  remaining_high: number;
}

export interface PlatformStatus {
  cache: { active: boolean; age_seconds: number };
  load_shedding: { active: boolean; shed_count: number; queue_depth: number };
  pricing_source: "primary" | "backup";
  chaos_mode: boolean;
}

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

interface ApiResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}

async function apiCall<T = unknown>(
  path: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${BACKEND_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = await response.json();
    if (!response.ok) {
      return { ok: false, error: data.error || data.detail || "Request failed" };
    }
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Network error" };
  }
}

export function startAgent() {
  return apiCall("/agent/start", { method: "POST" });
}

export function approveAction() {
  return apiCall("/agent/approve", { method: "POST" });
}

export function rejectAction() {
  return apiCall("/agent/reject", { method: "POST" });
}

export function resetDemo() {
  return apiCall("/admin/reset", { method: "POST" });
}

export function toggleChaos(enable: boolean) {
  return apiCall(`/admin/chaos/${enable ? "enable" : "disable"}`, {
    method: "POST",
  });
}

export function getStatus() {
  return apiCall("/agent/status");
}

export function getHistory() {
  return apiCall("/admin/history");
}

export function getConfig() {
  return apiCall("/admin/config");
}

export { BACKEND_URL };

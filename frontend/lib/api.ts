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
    // Backend may return 200 with an error field when downstream services fail
    if (data.error) {
      return { ok: false, error: data.error };
    }
    return { ok: true, data };
  } catch (e) {
    const message = e instanceof Error ? e.message : "Network error";
    return { ok: false, error: `Could not reach backend (${BACKEND_URL}): ${message}` };
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

export function getChaosStatus() {
  return apiCall("/admin/chaos/status");
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

export function fetchMarketPrices() {
  return apiCall("/market/prices");
}

export function fetchMarketActivity() {
  return apiCall("/market/activity");
}

export function fetchMarketCommentary() {
  return apiCall("/market/commentary", { method: "POST" });
}

export function fetchMarketStatus() {
  return apiCall("/market/status");
}

export function fetchPlatformStatus() {
  return apiCall("/admin/platform-status");
}

export function toggleCache(activate: boolean) {
  return apiCall(`/admin/cache/${activate ? "activate" : "deactivate"}`, {
    method: "POST",
  });
}

export function toggleLoadShedding(activate: boolean) {
  return apiCall(`/admin/load-shedding/${activate ? "activate" : "deactivate"}`, {
    method: "POST",
  });
}

export function switchPricingSource(backup: boolean) {
  return apiCall(`/admin/pricing-source/${backup ? "backup" : "primary"}`, {
    method: "POST",
  });
}

export { BACKEND_URL };

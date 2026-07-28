import type {
  Benchmark,
  BenchmarkHistoryItem,
  CreateBenchmark,
  Insights,
  Provider,
  SessionKeyInfo,
} from "@/types";
const BASE = import.meta.env.VITE_API_URL || "";
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export const api = {
  providers: () => request<Provider[]>("/api/providers"),
  createBenchmark: (body: CreateBenchmark) =>
    request<Benchmark>("/api/benchmarks", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  history: (limit = 20, offset = 0) =>
    request<BenchmarkHistoryItem[]>(
      `/api/benchmarks?limit=${limit}&offset=${offset}`,
    ),
  benchmark: (id: number) => request<Benchmark>(`/api/benchmarks/${id}`),
  deleteBenchmark: (id: number) =>
    request<void>(`/api/benchmarks/${id}`, { method: "DELETE" }),
  insights: () => request<Insights>("/api/insights"),
  saveSessionKey: (provider: string, key: string) =>
    request<{ provider: string; saved: boolean }>("/api/session-key", {
      method: "POST",
      body: JSON.stringify({ provider, key }),
    }),
  clearSessionKeys: () =>
    request<{ cleared: boolean }>("/api/session-key", {
      method: "DELETE",
    }),
  sessionKeys: () => request<SessionKeyInfo>("/api/session-key"),
};

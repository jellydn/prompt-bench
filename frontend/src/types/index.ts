export interface ModelPricing {
  input: number;
  output: number;
}
export interface ProviderModel {
  id: string;
  name: string;
  pricing: ModelPricing;
}
export interface Provider {
  id: string;
  name: string;
  configured: boolean;
  byok_eligible: boolean;
  base_url: string | null;
  models: ProviderModel[];
}
export interface BenchmarkResult {
  id: number;
  provider: string;
  model: string;
  input_tokens: number | null;
  output_tokens: number | null;
  ttft_ms: number | null;
  total_latency_ms: number | null;
  cost: number | null;
  response_chars: number | null;
  response_text: string | null;
  error: string | null;
}
export interface Benchmark {
  id: number;
  prompt: string;
  system_prompt: string | null;
  temperature: number;
  max_tokens: number;
  status: string;
  created_at: string;
  results: BenchmarkResult[];
}
export interface BenchmarkHistoryItem {
  id: number;
  prompt: string;
  created_at: string;
  model_count: number;
  total_cost: number;
  total_tokens: number;
  avg_latency_ms: number;
  status: string;
}
export interface Insights {
  most_expensive_prompt: {
    benchmark_id: number;
    prompt: string;
    total_cost: number;
  } | null;
  fastest_model: {
    provider: string;
    model: string;
    avg_latency_ms: number;
  } | null;
  lowest_cost_model: {
    provider: string;
    model: string;
    avg_cost: number;
  } | null;
  best_cost_performance: {
    provider: string;
    model: string;
    avg_cost: number;
    avg_latency_ms: number;
    score: number;
  } | null;
}
export interface CreateBenchmark {
  prompt: string;
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
  models: { provider: string; model: string }[];
  cache?: boolean;
  client_keys?: Record<string, string>;
}

export interface SessionKeyInfo {
  providers: string[];
}

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import BenchmarkResults from "@/pages/BenchmarkResults";

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ id: "1" }),
    useNavigate: () => mockNavigate,
  };
});

// Mock the API module
vi.mock("@/lib/api", () => ({
  api: {
    benchmark: vi.fn(),
  },
}));

import { api } from "@/lib/api";

// Mock recharts — it uses ResizeObserver which jsdom doesn't have
vi.mock("recharts", async () => {
  const actual = await vi.importActual("recharts");
  return {
    ...(actual as object),
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const legacyResult = {
  id: 1,
  provider: "openai",
  model: "gpt-4o-mini",
  input_tokens: 100,
  output_tokens: 50,
  ttft_ms: 300,
  total_latency_ms: 1200,
  cost: 0.0025,
  response_chars: 500,
  response_text: "Hello, this is a test response.",
  error: null,
  // Legacy result: all cache fields are null
  cache_hit: null,
  cache_type: null,
  cache_lookup_ms: null,
  provider_latency_ms: null,
};

const legacyBenchmark = {
  id: 1,
  prompt: "What is caching?",
  system_prompt: "You are a helpful assistant.",
  temperature: 0.0,
  max_tokens: 256,
  status: "completed",
  created_at: "2026-01-01T00:00:00Z",
  results: [legacyResult],
};

describe("BenchmarkResults — legacy null cache fields", () => {
  it("renders without crashing and shows benchmark details", async () => {
    vi.mocked(api.benchmark).mockResolvedValue(legacyBenchmark);

    renderWithClient(<BenchmarkResults />);

    // Once the query resolves, the benchmark title should appear
    expect(await screen.findByText("Benchmark #1")).toBeInTheDocument();

    // Prompt text should be visible
    expect(screen.getByText("What is caching?")).toBeInTheDocument();

    // System prompt should be visible
    expect(screen.getByText(/You are a helpful assistant/)).toBeInTheDocument();

    // Temperature and max tokens should show
    expect(screen.getByText("Temperature 0")).toBeInTheDocument();
    expect(screen.getByText(/Max tokens 256/)).toBeInTheDocument();

    // Results table should show the provider and model
    expect(screen.getByText("openai")).toBeInTheDocument();
    // "gpt-4o-mini" appears twice: in the table cell and in the tabs trigger
    const modelElements = screen.getAllByText("gpt-4o-mini");
    expect(modelElements).toHaveLength(2);

    // The status badge should show "Success" (not "Error")
    expect(screen.getByText("Success")).toBeInTheDocument();

    // The "Model responses" section should be visible
    expect(screen.getByText("Model responses")).toBeInTheDocument();

    // The response text should be visible
    expect(screen.getByText("Hello, this is a test response.")).toBeInTheDocument();

    // Cache performance section should NOT be visible for legacy results
    expect(screen.queryByText("Cache performance")).toBeNull();
    expect(screen.queryByText("Latency breakdown")).toBeNull();
  });

  it("renders without crashing even when cache fields are null", () => {
    vi.mocked(api.benchmark).mockResolvedValue(legacyBenchmark);

    // This should not throw — the main smoke test for legacy null cache fields
    expect(() => renderWithClient(<BenchmarkResults />)).not.toThrow();
  });
});

describe("BenchmarkResults — error states", () => {
  it("shows error message on API failure", async () => {
    vi.mocked(api.benchmark).mockRejectedValue(new Error("Network error"));

    renderWithClient(<BenchmarkResults />);

    expect(
      await screen.findByText(/Could not load results/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Network error/)).toBeInTheDocument();
  });
});

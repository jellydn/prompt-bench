# 6. Frontend Testing with Vitest + React Testing Library — Test Architecture for Component Rendering

Date: 2026-07-28

## Status

Accepted

## Context

The PromptBench frontend had no automated tests for its React components. The codebase is a Vite + React 19 SPA with React Router 7, React Query (TanStack Query), Recharts, and shadcn/ui. It renders three primary pages — BenchmarkRun, History, Insights — and several result-display components like BenchmarkResults and BenchmarkCacheSection.

Key risks without tests:

- **Null cache fields on legacy results**: BenchmarkResult rows created before the caching feature was added have `cache_hit`, `cache_type`, `cache_lookup_ms`, and `provider_latency_ms` all set to `null`. The UI must not crash when rendering these rows, but without tests, any refactoring that assumes non-null values could introduce runtime errors.
- **API failure states**: The UI fetches data from `/api/benchmarks/:id`. Network errors, 404s, and 500s must render a user-facing error message, not a blank page.
- **Complex mocks**: The app depends on React Router (`useParams`, `useNavigate`), React Query (`useQuery`), Recharts (which uses `ResizeObserver` from the DOM API), and a custom API client. Each of these must be mocked correctly for jsdom to render without crashing.

## Decision

Adopt **Vitest** as the test runner and **React Testing Library** for component assertions, with **jsdom** as the DOM environment. Structure tests alongside components in `src/__tests__/`.

### Stack

| Layer | Choice | Why |
|---|---|---|
| Test runner | Vitest 4.x | Same Vite config as the app (aliases, plugins); native ESM; faster than Jest in a Vite project |
| DOM environment | jsdom | Lightweight, bundled with Vitest; sufficient for component rendering tests |
| Assertion library | vitest `expect` + `@testing-library/jest-dom` | `toBeInTheDocument()`, `toHaveTextContent()`, etc. — idiomatic for DOM assertions |
| Component rendering | `@testing-library/react` 16.x | React 19 compatible; `render()`, `screen`, `waitFor`, `findByText` |
| Query mocking | `QueryClientProvider` wrapper | Isolate each test's React Query cache; disable retries for deterministic error states |
| Chart mocking | Module mock on `recharts` | `ResponsiveContainer` uses `ResizeObserver` (not in jsdom); stub it to a plain `<div>` |

### Config (`vitest.config.ts`)

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
```

Key decisions:

- **`@` alias matches `vite.config.ts`**: Tests import components the same way the app does (`@/pages/BenchmarkResults`).
- **`setupFiles` loads jest-dom matchers once**: No per-test imports needed.
- **`include` scoped to `src/`**: Test files live alongside source, discoverable by glob.

### Test wrapper pattern (`renderWithClient`)

Every test that renders a component using React Query must wrap it in a fresh `QueryClientProvider`:

```typescript
function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}
```

This prevents test isolation leaks — each test gets its own query cache, and `retry: false` ensures error states resolve immediately rather than retrying with exponential backoff.

### Module mocks

**React Router** — `useParams` and `useNavigate` are mocked at the module level:

```typescript
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ id: "1" }),
    useNavigate: () => mockNavigate,
  };
});
```

This preserves all other React Router exports (`Routes`, `Route`, `Link`, etc.) while stubbing the two hooks that components call directly.

**API client** — the `@/lib/api` module is fully mocked so tests never hit the network:

```typescript
vi.mock("@/lib/api", () => ({ api: { benchmark: vi.fn() } }));
```

Each test then sets `vi.mocked(api.benchmark).mockResolvedValue(...)` to control the response.

**Recharts** — `ResponsiveContainer` is stubbed to avoid `ResizeObserver` dependency:

```typescript
vi.mock("recharts", async () => {
  const actual = await vi.importActual("recharts");
  return {
    ...(actual as object),
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});
```

All chart components (`BarChart`, `XAxis`, `Tooltip`, etc.) pass through from the real `recharts`; only the container is replaced.

### Initial test suite — 3 tests

The first test file (`src/__tests__/BenchmarkResults.test.tsx`) covers two scenarios:

**1. Legacy null cache fields — full render verification**

Renders `BenchmarkResults` with a `BenchmarkResult` where all cache fields are `null`. Asserts:

- Page title (`Benchmark #1`), prompt, system prompt, temperature, max tokens all render
- Results table shows provider/model with "Success" badge
- Model responses tab shows the response text
- **Cache performance** and **Latency breakdown** sections are absent (null cache fields → sections hidden)
- No `TypeError` from accessing properties on `null`

**2. API error state**

Rejects the API call with `Error("Network error")`. Asserts:

- "Could not load results" message appears
- The specific error text (`Network error`) is displayed

### Running tests

```bash
npm test          # vitest run (single pass)
npm run test:watch  # vitest (watch mode)
```

## Consequences

### Positive

- **Regression safety for legacy data**: Any future change to cache field handling is verified against null-values input. The test fails if `benchmark.results[0].cache_hit` is accessed without a null guard.
- **Same toolchain**: Vitest reuses the Vite config (aliases, plugins) — no separate Jest config to maintain or desync.
- **Fast execution**: 3 tests run in under 1 second; mock-heavy approach avoids slow browser rendering.
- **Pattern extensible to other components**: The `renderWithClient` wrapper and mock patterns apply to any page that uses React Query + React Router. Adding a test for `History.tsx` or `Insights.tsx` follows the same template.
- **No network dependency**: All data comes from mocked `api.*` functions. Tests run offline and deterministically.

### Negative

- **Not a real browser**: jsdom lacks layout, painting, and many DOM APIs (`ResizeObserver`, `IntersectionObserver`, `getComputedStyle` with CSS). Visual regressions (broken flexbox, overlapping elements, blank renders) will not be caught. This is a known limitation recorded here so future contributors don't expect visual coverage from these tests.
- **Mock maintenance**: Every new React Router hook or API endpoint used by a component must be added to the mock setup. If a component starts calling `useLocation()` or `api.cacheStats()`, the test will break until the mock is extended.
- **Recharts mock is incomplete**: The stub replaces `ResponsiveContainer` with a `<div>` — chart-specific assertions (bar heights, axis labels) are impossible. This is acceptable for the current test suite, which only verifies that chart sections render or don't render based on cache data, but it would block tests that assert on chart content.
- **No integration tests**: Component tests mock the API layer and React Router — they don't verify that the real API contract matches the mock shape. A backend schema change that breaks the frontend would not be caught by these tests.

### Alternatives Considered

**Jest + React Testing Library**: The industry default, but requires `ts-jest` or `babel-jest` to transform TypeScript/JSX, and a separate config for module aliases. Rejected — Vitest shares Vite's config, avoiding the dual-config maintenance burden.

**Playwright / Cypress end-to-end tests**: Real browser tests would catch rendering bugs (flexbox, charts, layout). Rejected for v1 — requires a running backend with seed data, adds significant CI runtime, and belongs in a separate test suite alongside the component tests. Component tests and E2E tests are complementary, not alternatives.

**Testing Library's `renderHook` for `useQuery` isolation**: Test the data-fetching hook separately from the component. Rejected — the component test pattern renders the full page, which catches integration issues between hooks, props, and JSX that isolated hook tests would miss.

**Snapshot testing**: `expect(container).toMatchSnapshot()`. Rejected — snapshots are brittle (break on any DOM change), hard to review at PR time, and don't communicate intent. Explicit assertions (`getByText`, `queryByText`) document what the test cares about.

**Storybook + Chromatic visual testing**: Visual regression tests would catch the rendering bugs jsdom misses. Deferred — requires Storybook setup and a Chromatic subscription; could be added later without changing the existing test patterns.

## Migration path for existing pages

To add tests for `History.tsx`, `Insights.tsx`, or `CompareRuns.tsx`:

1. Copy the mock setup from `BenchmarkResults.test.tsx` (React Router, API, Recharts).
2. Add any additional API mocks the page uses (`api.history()`, `api.cacheStats()`, etc.).
3. Create a minimal "happy path" test first — mock the API to return one result, verify the page renders without crashing.
4. Add error-state and edge-case tests incrementally.

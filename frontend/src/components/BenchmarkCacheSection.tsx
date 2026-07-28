import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Database, Zap } from "lucide-react";
import { latency, money } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { BenchmarkResult } from "@/types";

/** Reusable cache status badge: Cache hit / Cache miss / Cache disabled. */
export function CacheBadge({ result }: { result: BenchmarkResult }) {
  if (result.cache_hit == null) {
    return <Badge variant="secondary">Cache disabled</Badge>;
  }
  return (
    <Badge
      variant="default"
      className={
        result.cache_hit
          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
          : ""
      }
    >
      {result.cache_hit ? "Cache hit" : "Cache miss"}
    </Badge>
  );
}

interface Props {
  results: BenchmarkResult[];
  cacheBackend?: string;
}

/** Cache performance comparison table, summary cards, and latency breakdown chart. */
export default function BenchmarkCacheSection({ results, cacheBackend }: Props) {
  if (!results.some((r) => r.cache_hit != null)) return null;

  return (
    <>
      {/* ── Cache performance comparison table ─────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="size-5" />
            Cache performance
            {cacheBackend && (
              <Badge variant="secondary" className="ml-2 text-xs font-normal">
                {cacheBackend}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                {[
                  "Provider / Model",
                  "Cache",
                  "Provider latency",
                  "Cache lookup",
                  "Total latency",
                  "Cost",
                ].map((x) => (
                  <TableHead key={x}>{x}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">
                    {r.provider} / {r.model}
                  </TableCell>
                  <TableCell>
                    <CacheBadge result={r} />
                  </TableCell>
                  <TableCell>{latency(r.provider_latency_ms)}</TableCell>
                  <TableCell>{latency(r.cache_lookup_ms)}</TableCell>
                  <TableCell>{latency(r.total_latency_ms)}</TableCell>
                  <TableCell>{money(r.cost)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <Separator className="my-4" />

          {/* ── Summary cards ──────────────────────────────────────────── */}
          <div className="grid gap-4 md:grid-cols-3">
            {results.map((r) => {
              if (r.cache_hit == null) return null;
              const latReduction =
                r.provider_latency_ms != null && r.provider_latency_ms > 0
                  ? Math.round(
                      Math.max(
                        0,
                        ((r.provider_latency_ms - (r.cache_lookup_ms ?? 0)) /
                          r.provider_latency_ms) *
                          100,
                      ),
                    )
                  : 0;
              const latencySaved =
                r.provider_latency_ms != null
                  ? Math.max(0, r.provider_latency_ms - (r.cache_lookup_ms ?? 0))
                  : 0;
              return (
                <div
                  key={r.id}
                  className="rounded-lg border p-4 space-y-2"
                >
                  <p className="text-sm font-medium">
                    {r.provider} / {r.model}
                  </p>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Zap className="size-4" />
                    <span>
                      {r.cache_hit
                        ? `Cache hit — saved ${latency(latencySaved)} (${latReduction}% reduction)`
                        : `Cache miss — provider called (${latency(r.provider_latency_ms)})`}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>
                      {r.cache_hit
                        ? `Cost avoided: ${money(r.cost)}`
                        : `Provider cost: ${money(r.cost)}`}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* ── Latency breakdown chart ────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="size-5" />
            Latency breakdown (provider vs cache lookup)
          </CardTitle>
        </CardHeader>
        <CardContent className="h-72">
          {(() => {
            const chartData = results
              .filter((r) => r.cache_hit != null)
              .map((r) => ({
                name: r.model,
                provider: r.provider_latency_ms ?? 0,
                cache: r.cache_lookup_ms ?? 0,
              }));
            if (chartData.length === 0) {
              return (
                <p className="text-muted-foreground">
                  No cache metrics available.
                </p>
              );
            }
            return (
              <ResponsiveContainer>
                <BarChart data={chartData}>
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(value: number) => `${value}ms`} />
                  <Legend />
                  <Bar
                    dataKey="provider"
                    name="Provider latency"
                    fill="#f59e0b"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="cache"
                    name="Cache lookup"
                    fill="#10b981"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            );
          })()}
        </CardContent>
      </Card>
    </>
  );
}

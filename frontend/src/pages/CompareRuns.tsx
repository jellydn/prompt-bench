import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, GitCompare, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { latency, money } from "@/lib/utils";
import type { BenchmarkResult } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Pairs = Map<
  string,
  { runA: BenchmarkResult; runB: BenchmarkResult | null }
>;

export default function CompareRuns() {
  const navigate = useNavigate();
  const [idA, setIdA] = useState("");
  const [idB, setIdB] = useState("");
  const [submitted, setSubmitted] = useState<[number, number] | null>(null);

  const qA = useQuery({
    queryKey: ["benchmark", submitted?.[0]],
    queryFn: () => api.benchmark(submitted![0]),
    enabled: submitted != null && !Number.isNaN(submitted[0]),
  });
  const qB = useQuery({
    queryKey: ["benchmark", submitted?.[1]],
    queryFn: () => api.benchmark(submitted![1]),
    enabled: submitted != null && !Number.isNaN(submitted[1]),
  });

  const handleCompare = () => {
    const a = Number(idA);
    const b = Number(idB);
    if (Number.isNaN(a) || Number.isNaN(b) || a === b) return;
    setSubmitted([a, b]);
  };

  const isLoading = qA.isLoading || qB.isLoading;
  const error = qA.error ?? qB.error;

  // Build matched pairs keyed by "provider:model"
  // Use total_latency_ms as a heuristic: higher = likely miss, lower = likely hit
  const pairs: Pairs = new Map();
  if (qA.data && qB.data) {
    for (const r of qA.data.results.filter((r) => !r.error)) {
      const key = `${r.provider}:${r.model}`;
      pairs.set(key, { runA: r, runB: null });
    }
    for (const r of qB.data.results.filter((r) => !r.error)) {
      const key = `${r.provider}:${r.model}`;
      const existing = pairs.get(key);
      if (existing) {
        // Swap so runA is always the miss (higher latency)
        const latA = existing.runA.total_latency_ms ?? 0;
        const latB = r.total_latency_ms ?? 0;
        if (latA > latB) {
          existing.runB = r;
        } else {
          existing.runB = existing.runA;
          existing.runA = r;
        }
      }
    }
  }

  const comparison = [...pairs.entries()]
    .filter(([, v]) => v.runB != null)
    .map(([key, v]) => {
      const missLatency = v.runA.total_latency_ms ?? 0;
      const hitLatency = v.runB!.total_latency_ms ?? 0;
      const missCost = v.runA.cost ?? 0;
      const hitCost = v.runB!.cost ?? 0;
      const latencyReduction =
        missLatency > 0
          ? Math.round(((missLatency - hitLatency) / missLatency) * 100)
          : 0;
      const costAvoided = Math.max(0, missCost - hitCost);
      const speedup =
        hitLatency > 0
          ? Math.round((missLatency / hitLatency) * 10) / 10
          : missLatency > 0
            ? Infinity
            : 0;
      return { key, miss: v.runA, hit: v.runB!, latencyReduction, costAvoided, speedup };
    })
    .sort((x, y) => y.latencyReduction - x.latencyReduction);

  const showEmpty =
    submitted != null && !isLoading && !error && comparison.length === 0;

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate("/history")}>
        <ArrowLeft className="size-4" />
        Back to history
      </Button>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitCompare className="size-5" />
            Compare benchmark runs
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Enter two benchmark IDs from the History page. The comparison auto-detects
            which run was the cache MISS and which was the HIT by comparing latencies.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="run-a">Run A</Label>
              <Input
                id="run-a"
                type="number"
                placeholder="Benchmark ID"
                value={idA}
                onChange={(e) => setIdA(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCompare()}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="run-b">Run B</Label>
              <Input
                id="run-b"
                type="number"
                placeholder="Benchmark ID"
                value={idB}
                onChange={(e) => setIdB(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCompare()}
              />
            </div>
          </div>
          <Button
            onClick={handleCompare}
            disabled={idA.trim() === "" || idB.trim() === "" || idA.trim() === idB.trim() || isLoading}
          >
            Compare
          </Button>

          {isLoading && (
            <p className="text-muted-foreground">Loading benchmarks…</p>
          )}
          {error && (
            <p className="text-destructive">Error: {error.message}</p>
          )}
          {showEmpty && (
            <p className="text-muted-foreground">
              No matching provider/model pairs found. Ensure both benchmarks
              use the same providers and models.
            </p>
          )}
        </CardContent>
      </Card>

      {comparison.length > 0 && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="size-5" />
                Results — {comparison.length} model(s) compared
                <span className="text-sm font-normal text-muted-foreground">
                  (Benchmark #{qA.data?.id} vs #{qB.data?.id})
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Provider / Model</TableHead>
                    <TableHead>Run A (miss)</TableHead>
                    <TableHead>Run B (hit)</TableHead>
                    <TableHead>Latency reduction</TableHead>
                    <TableHead>Cost avoided</TableHead>
                    <TableHead>Speedup</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {comparison.map((c) => (
                    <TableRow key={c.key}>
                      <TableCell className="font-medium">{c.key}</TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground">
                          {latency(c.miss.total_latency_ms)} · {money(c.miss.cost)}
                        </span>
                        <Badge variant="secondary" className="ml-2 text-[10px]">
                          MISS
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground">
                          {latency(c.hit.total_latency_ms)} · {money(c.hit.cost)}
                        </span>
                        <Badge
                          variant="default"
                          className="ml-2 text-[10px] bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                        >
                          HIT
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-semibold text-emerald-600">
                          −{c.latencyReduction}%
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="font-semibold text-emerald-600">
                          {money(c.costAvoided)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="font-semibold text-emerald-600">
                          {c.speedup === Infinity ? "∞" : `${c.speedup}×`}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <Separator className="my-4" />
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-lg border p-4">
                  <p className="text-xs text-muted-foreground">
                    Total latency saved
                  </p>
                  <p className="text-2xl font-bold text-emerald-600">
                    −
                    {Math.round(
                      comparison.reduce(
                        (sum, c) =>
                          sum +
                          (c.miss.total_latency_ms ?? 0) -
                          (c.hit.total_latency_ms ?? 0),
                        0,
                      ),
                    )}
                    ms
                  </p>
                </div>
                <div className="rounded-lg border p-4">
                  <p className="text-xs text-muted-foreground">
                    Total cost avoided
                  </p>
                  <p className="text-2xl font-bold text-emerald-600">
                    {money(
                      comparison.reduce((sum, c) => sum + c.costAvoided, 0),
                    )}
                  </p>
                </div>
                <div className="rounded-lg border p-4">
                  <p className="text-xs text-muted-foreground">
                    Average speedup
                  </p>
                  <p className="text-2xl font-bold text-emerald-600">
                    {(() => {
                      const finite = comparison
                        .map((c) => c.speedup)
                        .filter((s) => s !== Infinity && s > 0);
                      if (finite.length === 0) return "∞";
                      return `${Math.round(finite.reduce((s, v) => s + v, 0) / finite.length)}×`;
                    })()}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {pairs.size > comparison.length && (
            <Card>
              <CardHeader>
                <CardTitle>Unmatched models</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {pairs.size - comparison.length} model(s) only appear in one
                  run and cannot be compared. Ensure both benchmarks use the same
                  provider/model pairs.
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

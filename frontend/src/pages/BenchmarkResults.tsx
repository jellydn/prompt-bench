import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { ArrowLeft, Database, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { latency, money, tokens } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
export default function BenchmarkResults() {
  const { id: idParam } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = Number(idParam);
  const q = useQuery({
    queryKey: ["benchmark", id],
    queryFn: () => api.benchmark(id),
    enabled: !Number.isNaN(id),
  });
  const back = () => navigate("/history");
  if (Number.isNaN(id)) return <p className="text-destructive">Invalid benchmark ID.</p>;
  if (q.isLoading) return <p>Loading results…</p>;
  if (q.isError)
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={back}>
          <ArrowLeft />
          Back
        </Button>
        <p className="text-destructive">
          Could not load results: {q.error.message}
        </p>
      </div>
    );
  if (!q.data) return null;
  const b = q.data;
  const good = b.results.filter((r) => !r.error);
  if (good.length === 0) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={back}>
          <ArrowLeft />
          Back to history
        </Button>
        <Card>
          <CardHeader>
            <CardTitle>Benchmark #{b.id}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-lg">{b.prompt}</p>
            {b.system_prompt && (
              <p className="mt-3 text-sm text-muted-foreground">
                System: {b.system_prompt}
              </p>
            )}
            <div className="mt-4 flex gap-4 text-sm text-muted-foreground">
              <span>Temperature {b.temperature}</span>
              <span>Max tokens {tokens(b.max_tokens)}</span>
              <Badge
                variant={b.status === "completed" ? "success" : "secondary"}
              >
                {b.status}
              </Badge>
            </div>
            <p className="mt-4 text-destructive">All models returned errors.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Results</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              No successful results to display.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }
  const fastest = good.reduce(
    (a, r) =>
      r.total_latency_ms != null &&
      r.total_latency_ms < (a?.total_latency_ms ?? Infinity)
        ? r
        : a,
    good[0],
  );
  const cheapest = good.reduce(
    (a, r) => (r.cost != null && r.cost < (a?.cost ?? Infinity) ? r : a),
    good[0],
  );
  const data = b.results.map((r) => ({
    name: `${r.provider} / ${r.model}`,
    latency: r.total_latency_ms ?? 0,
    cost: r.cost ?? 0,
    input: r.input_tokens ?? 0,
    output: r.output_tokens ?? 0,
  }));
  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={back}>
        <ArrowLeft />
        Back to history
      </Button>
      <Card>
        <CardHeader>
          <CardTitle>Benchmark #{b.id}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap text-lg">{b.prompt}</p>
          {b.system_prompt && (
            <p className="mt-3 text-sm text-muted-foreground">
              System: {b.system_prompt}
            </p>
          )}
          <div className="mt-4 flex gap-4 text-sm text-muted-foreground">
            <span>Temperature {b.temperature}</span>
            <span>Max tokens {tokens(b.max_tokens)}</span>
            <Badge variant={b.status === "completed" ? "success" : "secondary"}>
              {b.status}
            </Badge>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                {[
                  "Provider",
                  "Model",
                  "Input",
                  "Output",
                  "TTFT",
                  "Total latency",
                  "Cost",
                  "Chars",
                  "Status",
                ].map((x) => (
                  <TableHead key={x}>{x}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {b.results.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.provider}</TableCell>
                  <TableCell className="font-medium">
                    {r.model}{" "}
                    <span className="space-x-1">
                      {r === fastest && (
                        <Badge variant="success">Fastest</Badge>
                      )}
                      {r === cheapest && (
                        <Badge variant="success">Cheapest</Badge>
                      )}
                    </span>
                  </TableCell>
                  <TableCell>{tokens(r.input_tokens)}</TableCell>
                  <TableCell>{tokens(r.output_tokens)}</TableCell>
                  <TableCell>{latency(r.ttft_ms)}</TableCell>
                  <TableCell>{latency(r.total_latency_ms)}</TableCell>
                  <TableCell>{money(r.cost)}</TableCell>
                  <TableCell>{tokens(r.response_chars)}</TableCell>
                  <TableCell>
                    <span className="space-x-1">
                      <Badge variant={r.error ? "destructive" : "success"}>
                        {r.error ? "Error" : "Success"}
                      </Badge>
                      {r.cache_hit != null && (
                        <Badge
                          variant="default"
                          className={
                            r.cache_hit
                              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                              : ""
                          }
                        >
                          {r.cache_hit ? "Cache hit" : "Cache miss"}
                        </Badge>
                      )}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <div className="grid gap-5 xl:grid-cols-3">
        {[
          ["Total latency (ms)", "latency", "#6366f1"],
          ["Cost (USD)", "cost", "#10b981"],
        ].map(([title, key, color]) => (
          <Card key={key}>
            <CardHeader>
              <CardTitle className="text-base">{title}</CardTitle>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer>
                <BarChart data={data}>
                  <XAxis dataKey="name" hide />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey={key} fill={color} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        ))}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Token usage</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer>
              <BarChart data={data}>
                <XAxis dataKey="name" hide />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="input" stackId="t" fill="#6366f1" />
                <Bar dataKey="output" stackId="t" fill="#a78bfa" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
      {/* Cache comparison section — only shown when cache metrics exist */}
      {good.some((r) => r.cache_hit != null) && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="size-5" />
                Cache performance
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
                  {good.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium">
                        {r.provider} / {r.model}
                      </TableCell>
                      <TableCell>
                        {r.cache_hit != null ? (
                          <Badge
                            variant="default"
                            className={
                              r.cache_hit
                                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                : ""
                            }
                          >
                            {r.cache_hit ? "HIT" : "MISS"}
                          </Badge>
                        ) : (
                          <Badge variant="secondary">DISABLED</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {latency(r.provider_latency_ms)}
                      </TableCell>
                      <TableCell>
                        {latency(r.cache_lookup_ms)}
                      </TableCell>
                      <TableCell>
                        {latency(r.total_latency_ms)}
                      </TableCell>
                      <TableCell>{money(r.cost)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <Separator className="my-4" />
              <div className="grid gap-4 md:grid-cols-3">
                {good.map((r) => {
                  if (r.cache_hit == null) return null;
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
                            ? "Cache hit — served from cache"
                            : `Cache miss — provider called (${latency(r.provider_latency_ms)})`}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>Cost: {money(0)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
          {/* Latency breakdown chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="size-5" />
                Latency breakdown (provider vs cache lookup)
              </CardTitle>
            </CardHeader>
            <CardContent className="h-72">
              {(() => {
                const chartData = good
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
                      <Tooltip
                        formatter={(value: number) => `${value}ms`}
                      />
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
      )}
      <Card>
        <CardHeader>
          <CardTitle>Model responses</CardTitle>
        </CardHeader>
        <CardContent>
          {b.results.length ? (
            <Tabs defaultValue={String(b.results[0].id)}>
              <TabsList className="max-w-full flex-wrap">
                {b.results.map((r) => (
                  <TabsTrigger key={r.id} value={String(r.id)}>
                    {r.model}
                  </TabsTrigger>
                ))}
              </TabsList>
              {b.results.map((r) => (
                <TabsContent key={r.id} value={String(r.id)}>
                  <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-4 font-sans text-sm">
                    {r.error || r.response_text || "No response returned."}
                  </pre>
                </TabsContent>
              ))}
            </Tabs>
          ) : (
            <p className="text-muted-foreground">No model responses.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

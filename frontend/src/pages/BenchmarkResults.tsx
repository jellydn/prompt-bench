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
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { latency, money, tokens } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
export default function BenchmarkResults({
  id,
  onBack,
}: {
  id: number;
  onBack: () => void;
}) {
  const q = useQuery({
    queryKey: ["benchmark", id],
    queryFn: () => api.benchmark(id),
  });
  if (q.isLoading) return <p>Loading results…</p>;
  if (q.isError)
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft />
          Back
        </Button>
        <p className="text-destructive">
          Could not load results: {q.error.message}
        </p>
      </div>
    );
  const b = q.data!;
  const good = b.results.filter((r) => !r.error);
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
      <Button variant="ghost" onClick={onBack}>
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
                  "Length",
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
                  <TableCell>{tokens(r.response_length)}</TableCell>
                  <TableCell>
                    <Badge variant={r.error ? "destructive" : "success"}>
                      {r.error ? "Error" : "Success"}
                    </Badge>
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

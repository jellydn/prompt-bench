import { useQuery } from "@tanstack/react-query";
import { DollarSign, Clock, TrendingUp, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { money, latency } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
export default function Insights({ onOpen }: { onOpen: (id: number) => void }) {
  const q = useQuery({ queryKey: ["insights"], queryFn: api.insights });
  const x = q.data;
  const cards = x
    ? [
        {
          title: "Most Expensive Prompt",
          icon: DollarSign,
          body: x.most_expensive_prompt && (
            <>
              <p className="line-clamp-3">{x.most_expensive_prompt.prompt}</p>
              <strong className="text-xl text-red-500">
                {money(x.most_expensive_prompt.total_cost)}
              </strong>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onOpen(x.most_expensive_prompt!.benchmark_id)}
              >
                View benchmark
              </Button>
            </>
          ),
        },
        {
          title: "Fastest Model",
          icon: Zap,
          body: x.fastest_model && (
            <>
              <strong>
                {x.fastest_model.provider} / {x.fastest_model.model}
              </strong>
              <p className="text-2xl font-bold text-emerald-500">
                {latency(x.fastest_model.avg_latency_ms)}
              </p>
            </>
          ),
        },
        {
          title: "Lowest Cost Model",
          icon: DollarSign,
          body: x.lowest_cost_model && (
            <>
              <strong>
                {x.lowest_cost_model.provider} / {x.lowest_cost_model.model}
              </strong>
              <p className="text-2xl font-bold text-emerald-500">
                {money(x.lowest_cost_model.avg_cost)}
              </p>
            </>
          ),
        },
        {
          title: "Best Cost / Performance",
          icon: Clock,
          body: x.best_cost_performance && (
            <>
              <strong>
                {x.best_cost_performance.provider} / {x.best_cost_performance.model}
              </strong>
              <p>
                Score <b>{x.best_cost_performance.score.toFixed(2)}</b>
              </p>
              <p className="text-sm text-muted-foreground">
                {money(x.best_cost_performance.avg_cost)} ·{" "}
                {latency(x.best_cost_performance.avg_latency_ms)}
              </p>
            </>
          ),
        },
      ]
    : [];
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Insights</h1>
        <p className="text-muted-foreground">
          Trends and standouts from all your benchmark runs.
        </p>
      </div>
      {q.isLoading && <p>Loading insights…</p>}
      {q.isError && (
        <p className="text-destructive">
          Could not load insights: {q.error.message}
        </p>
      )}
      {!q.isLoading && !q.isError && x && Object.values(x).every((v) => v === null) && (
        <div className="py-24 text-center">
          <TrendingUp className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h1 className="text-2xl font-bold">Run benchmarks to see insights</h1>
        </div>
      )}
      {!q.isLoading && !q.isError && x && !Object.values(x).every((v) => v === null) && (
        <div className="grid gap-5 md:grid-cols-2">
          {cards.map((c) => (
            <Card key={c.title}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <c.icon className="h-5 w-5" />
                  {c.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-start gap-3">
                {c.body || (
                  <p className="text-muted-foreground">Not enough data</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, History as HistoryIcon } from "lucide-react";
import { api } from "@/lib/api";
import { money, latency, tokens } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
export default function History() {
  const navigate = useNavigate();
  const limit = 20;
  const [offset, setOffset] = useState(0);
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["history", offset],
    queryFn: () => api.history(limit, offset),
  });
  const del = useMutation({
    mutationFn: api.deleteBenchmark,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }),
  });
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Benchmark history</h1>
        <p className="text-muted-foreground">
          Review and compare previous runs.
        </p>
      </div>
      <Card>
        <CardContent className="pt-6">
          {q.isError ? (
            <p className="text-destructive">
              Could not load history: {q.error.message}
            </p>
          ) : q.isLoading ? (
            <p>Loading history…</p>
          ) : !q.data?.length ? (
            <div className="py-16 text-center text-muted-foreground">
              <HistoryIcon className="mx-auto mb-3 h-10 w-10" />
              No benchmarks yet. Run your first comparison.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Prompt</TableHead>
                  <TableHead>Models</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Tokens</TableHead>
                  <TableHead>Avg latency</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((x) => (
                  <TableRow
                    key={x.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/results/${x.id}`)}
                  >
                    <TableCell className="whitespace-nowrap">
                      {new Date(x.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="max-w-xs truncate font-medium">
                      {x.prompt}
                    </TableCell>
                    <TableCell>{x.model_count}</TableCell>
                    <TableCell>{money(x.total_cost)}</TableCell>
                    <TableCell>{tokens(x.total_tokens)}</TableCell>
                    <TableCell>{latency(x.avg_latency_ms)}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          x.status === "completed" ? "success" : "secondary"
                        }
                      >
                        {x.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        aria-label="Delete"
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm("Delete this benchmark?"))
                            del.mutate(x.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {q.isSuccess && (
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            disabled={(q.data?.length ?? 0) < limit}
            onClick={() => setOffset(offset + limit)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

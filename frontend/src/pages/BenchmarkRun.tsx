import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Play, LoaderCircle, Server, Key, Eye, EyeOff } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
export default function BenchmarkRun({
  onComplete,
}: {
  onComplete: (id: number) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [system, setSystem] = useState("");
  const [temp, setTemp] = useState(0.7);
  const [max, setMax] = useState(1000);
  const [selected, setSelected] = useState<string[]>([]);
  const [clientKeys, setClientKeys] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: api.providers,
  });
  const run = useMutation({
    mutationFn: api.createBenchmark,
    onSuccess: (b) => onComplete(b.id),
  });
  const toggle = (key: string) =>
    setSelected((s) =>
      s.includes(key) ? s.filter((x) => x !== key) : [...s, key],
    );
  const hasClientKey = (providerId: string) =>
    (clientKeys[providerId]?.length ?? 0) > 0;
  const isConfigured = (p: { id: string; configured: boolean }) =>
    p.configured || hasClientKey(p.id);
  const maskKey = (key: string) =>
    key.length > 8 ? `${key.slice(0, 4)}${'•'.repeat(key.length - 8)}${key.slice(-4)}` : '••••••••';
  const nonEmptyClientKeys = Object.fromEntries(
    Object.entries(clientKeys).filter(([, v]) => v.trim()),
  );
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Run a benchmark</h1>
        <p className="mt-1 text-muted-foreground">
          Compare one prompt across your configured AI models.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Prompt</CardTitle>
          <CardDescription>
            Enter the instructions each selected model will receive.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="prompt">User prompt *</Label>
            <Textarea
              id="prompt"
              className="min-h-40"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Explain quantum computing in simple terms..."
            />
          </div>
          <div className="space-y-2">
            <Label>
              System prompt{" "}
              <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Textarea
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              placeholder="You are a clear, concise assistant."
            />
          </div>
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="space-y-3">
              <Label>Temperature: {temp.toFixed(1)}</Label>
              <Slider
                min={0}
                max={2}
                step={0.1}
                value={temp}
                onChange={(e) => setTemp(+e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Max tokens</Label>
              <Input
                type="number"
                min={1}
                value={max}
                onChange={(e) => setMax(+e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Select models</CardTitle>
          <CardDescription>
            Choose one or more models to compare.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {providers.isLoading && <p>Loading providers…</p>}
          {providers.isError && (
            <p className="text-destructive">
              Could not load providers: {providers.error.message}
            </p>
          )}
          {providers.data?.map((p) => {
            const conf = isConfigured(p);
            return (
            <div
              key={p.id}
              title={!conf ? "API key not set" : undefined}
              className={cn(
                "rounded-lg border p-4",
                !conf && "cursor-not-allowed opacity-45",
              )}
            >
              <div className="mb-3 flex items-center gap-2 font-semibold">
                <Server className="h-4 w-4" />
                {p.name}
                <span className="ml-auto text-xs text-muted-foreground">
                  {p.configured
                    ? "Configured"
                    : hasClientKey(p.id)
                      ? "Your key"
                      : "API key not set"}
                </span>
              </div>
              {/* BYOK key input — shown for eligible providers not server-configured */}
              {!p.configured && p.byok_eligible && (
                <div className="mb-3 flex items-center gap-2">
                  <Key className="h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    type={showKeys[p.id] ? "text" : "password"}
                    className="flex-1 rounded border bg-background px-2 py-1 text-xs font-mono"
                    placeholder={`${p.name} API key…`}
                    value={clientKeys[p.id] || ""}
                    onChange={(e) =>
                      setClientKeys((prev) => ({ ...prev, [p.id]: e.target.value }))
                    }
                    autoComplete="off"
                    spellCheck={false}
                  />
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground"
                    onClick={() =>
                      setShowKeys((prev) => ({ ...prev, [p.id]: !prev[p.id] }))
                    }
                    title={showKeys[p.id] ? "Hide key" : "Show key"}
                  >
                    {showKeys[p.id] ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                </div>
              )}
              {hasClientKey(p.id) && !p.configured && !showKeys[p.id] && (
                <p className="mb-2 text-[10px] text-muted-foreground">
                  {maskKey(clientKeys[p.id])}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {p.models.map((m) => {
                  const k = `${p.id}:${m.id}`;
                  return (
                    <label
                      key={k}
                      className={cn(
                        "cursor-pointer rounded-full border px-3 py-1.5 text-sm",
                        selected.includes(k) &&
                          "border-primary bg-primary text-primary-foreground",
                      )}
                    >
                      <input
                        className="sr-only"
                        type="checkbox"
                        disabled={!conf}
                        checked={selected.includes(k)}
                        onChange={() => toggle(k)}
                      />
                      {m.name}
                    </label>
                  );
                })}
              </div>
            </div>
          )})}
        </CardContent>
      </Card>
      {run.isError && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {run.error.message}
        </p>
      )}
      <Button
        size="lg"
        disabled={!prompt.trim() || !selected.length || run.isPending}
        onClick={() =>
          run.mutate({
            prompt: prompt.trim(),
            system_prompt: system.trim() || undefined,
            temperature: temp,
            max_tokens: max,
            models: selected.map((x) => {
              const [provider, model] = x.split(":");
              return { provider, model };
            }),
            ...(Object.keys(nonEmptyClientKeys).length > 0
              ? { client_keys: nonEmptyClientKeys }
              : {}),
          })
        }
      >
        {run.isPending ? <LoaderCircle className="animate-spin" /> : <Play />}
        {run.isPending ? "Running benchmark…" : "Run Benchmark"}
      </Button>
    </div>
  );
}

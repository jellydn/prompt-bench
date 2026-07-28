import { Suspense, lazy, useEffect, useState } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import {
  Activity,
  History as HistoryIcon,
  Play,
  TrendingUp,
  Moon,
  Sun,
  Menu,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const BenchmarkRun = lazy(() => import("@/pages/BenchmarkRun"));
const BenchmarkResults = lazy(() => import("@/pages/BenchmarkResults"));
const History = lazy(() => import("@/pages/History"));
const Insights = lazy(() => import("@/pages/Insights"));

export default function App() {
  const [dark, setDark] = useState(
    () => localStorage.getItem("theme") === "dark",
  );
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  const nav = [
    { to: "/", label: "Run Benchmark", icon: Play, end: true },
    { to: "/history", label: "History", icon: HistoryIcon },
    { to: "/insights", label: "Insights", icon: TrendingUp },
  ];

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="fixed inset-x-0 top-0 z-20 flex h-16 items-center border-b bg-background px-4 md:hidden">
        <Button variant="ghost" size="icon" onClick={() => setOpen(!open)} aria-label="Open navigation">
          <Menu />
        </Button>
        <Activity className="ml-3 h-6 w-6" />
        <b className="ml-2">PromptBench</b>
      </header>
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 w-64 border-r bg-background p-5 transition-transform md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <NavLink
          to="/"
          className="mb-8 flex items-center gap-3 text-xl font-bold"
          onClick={() => setOpen(false)}
        >
          <span className="rounded-lg bg-primary p-2 text-primary-foreground">
            <Activity />
          </span>
          PromptBench
        </NavLink>
        <nav className="space-y-1">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="absolute bottom-5 left-5 right-5">
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={() => setDark(!dark)}
          >
            {dark ? <Sun /> : <Moon />}
            {dark ? "Light mode" : "Dark mode"}
          </Button>
        </div>
      </aside>
      {open && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-20 bg-black/30 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}
      <main className="px-4 pb-10 pt-24 md:ml-64 md:p-8">
        <Suspense
          fallback={
            <div className="flex h-64 items-center justify-center text-muted-foreground">
              Loading…
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<BenchmarkRun />} />
            <Route path="/history" element={<History />} />
            <Route path="/insights" element={<Insights />} />
            <Route path="/results/:id" element={<BenchmarkResults />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

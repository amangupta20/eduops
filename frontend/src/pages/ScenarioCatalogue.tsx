import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Clock3, ShieldCheck, Sparkles } from "lucide-react";

import SearchBar from "@/components/SearchBar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { notifySuccess, notifyWarning } from "@/lib/notify";
import { listScenarios } from "@/services/api";
import type { Scenario } from "@/types";

const difficultyLabel: Record<Scenario["difficulty"], "Beginner" | "Intermediate" | "Advanced"> = {
  easy: "Beginner",
  medium: "Intermediate",
  hard: "Advanced",
};

const fallbackScenarios: Scenario[] = [
  {
    id: "incident-101",
    title: "Incident Triage Fundamentals",
    description:
      "Practice identifying high-signal alerts, assigning severity, and sequencing first-response actions.",
    difficulty: "easy",
    tags: ["alert triage", "severity", "first response"],
    source: "bundled",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "oncall-incident-bridge",
    title: "On-Call Bridge Coordination",
    description:
      "Run a coordinated incident bridge, route ownership, and keep communication loops tight under pressure.",
    difficulty: "medium",
    tags: ["coordination", "communication", "incident bridge"],
    source: "bundled",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "multi-region-outage",
    title: "Multi-Region Outage Simulation",
    description:
      "Handle a cascading outage with partial observability and prioritize restoration decisions with trade-offs.",
    difficulty: "hard",
    tags: ["outage", "recovery", "multi-region"],
    source: "bundled",
    created_at: "2026-01-01T00:00:00Z",
  },
];

export default function ScenarioCatalogue() {
  const navigate = useNavigate();
  const [catalogue, setCatalogue] = useState<Scenario[]>([]);
  const [visibleScenarios, setVisibleScenarios] = useState<Scenario[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadCatalogue = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const scenarios = await listScenarios();
      setCatalogue(scenarios);
      setVisibleScenarios(scenarios);
      notifySuccess("Scenarios loaded", `Found ${scenarios.length} scenario${scenarios.length === 1 ? "" : "s"}.`);
    } catch {
      setLoadError("Backend unavailable. Showing local demo scenarios.");
      setCatalogue(fallbackScenarios);
      setVisibleScenarios(fallbackScenarios);
      notifyWarning("Backend unavailable", "Showing local demo scenarios until API is reachable.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCatalogue();
  }, [loadCatalogue]);

  const totalCount = useMemo(() => catalogue.length, [catalogue.length]);

  return (
    <main className="min-h-screen bg-background">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-6 py-12 lg:py-16">
        <header className="relative overflow-hidden rounded-2xl border border-blue-500/30 bg-gradient-to-br from-slate-900/80 via-slate-900/65 to-black/85 p-6 shadow-2xl shadow-blue-500/15 backdrop-blur-md sm:p-8">
          <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-blue-500/20 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-16 -left-12 h-44 w-44 rounded-full bg-emerald-500/10 blur-3xl" />
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="gap-1.5 rounded-md border-blue-500/40 bg-blue-500/15 px-3 py-1 text-blue-100">
              <Sparkles className="size-3.5" />
              EduOps Simulations
            </Badge>
            <Badge className="rounded-md border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-emerald-100">
              {totalCount} curated scenarios
            </Badge>
          </div>
          <h1 className="mt-4 text-4xl font-extrabold tracking-tight text-slate-50 sm:text-5xl">
            Scenario Catalogue
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-300 sm:text-base">
            Build operational confidence with realistic environments. Pick a scenario to launch
            your workspace and practice triage, communication, and recovery decisions.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-4 text-xs text-slate-300 sm:text-sm">
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="size-4 text-emerald-400" />
              Guided playbooks
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Clock3 className="size-4 text-blue-300" />
              Time-boxed sessions
            </span>
          </div>
          <div className="mt-6">
            <SearchBar catalogue={catalogue} onResultsChange={setVisibleScenarios} />
          </div>
        </header>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {isLoading && (
            <Card className="md:col-span-2 lg:col-span-3 border-blue-500/25 bg-slate-900/60">
              <CardContent className="p-6 text-sm text-slate-300">Loading scenarios...</CardContent>
            </Card>
          )}

          {!isLoading &&
            loadError && (
              <Card className="md:col-span-2 lg:col-span-3 border-amber-500/30 bg-amber-500/10">
                <CardContent className="flex items-center justify-between gap-3 p-4 text-sm text-amber-100">
                  <span>{loadError}</span>
                  <Button
                    variant="outline"
                    className="border-amber-500/40 bg-amber-500/5 text-amber-100 hover:bg-amber-500/15"
                    onClick={() => void loadCatalogue()}
                  >
                    Retry API
                  </Button>
                </CardContent>
              </Card>
            )}

          {!isLoading &&
            !loadError &&
            visibleScenarios.map((scenario) => (
            <Card
              key={scenario.id}
              className="group flex h-full flex-col justify-between border-blue-500/25 bg-gradient-to-br from-slate-800/50 via-slate-900/50 to-black/60 shadow-xl shadow-blue-500/5 transition-all duration-300 hover:-translate-y-1 hover:border-blue-500/60 hover:shadow-2xl hover:shadow-blue-500/30"
            >
              <CardHeader className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <Badge className="border-blue-500/35 bg-blue-500/15 text-blue-100">
                    {difficultyLabel[scenario.difficulty]}
                  </Badge>
                  <span className="inline-flex items-center gap-1 text-xs text-slate-300">
                    <Clock3 className="size-3.5 text-blue-300" />
                    {scenario.tags.slice(0, 2).join(" • ") || "Guided session"}
                  </span>
                </div>
                <CardTitle className="text-xl text-slate-50">{scenario.title}</CardTitle>
                <CardDescription className="leading-relaxed text-slate-300">
                  {scenario.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100/90">
                  Primary focus:{" "}
                  <span className="font-semibold text-emerald-100">
                    {scenario.tags[0] ?? "Scenario practice"}
                  </span>
                </div>
              </CardContent>
              <CardFooter>
                <Button
                  className="w-full gap-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-600/40 hover:from-blue-500 hover:to-blue-600"
                  onClick={() => navigate(`/workspace/${scenario.id}`)}
                >
                  Start Scenario
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}

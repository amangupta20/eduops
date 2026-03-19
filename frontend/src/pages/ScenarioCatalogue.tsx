import { useNavigate } from "react-router-dom";
import { ArrowRight, Clock3, ShieldCheck, Sparkles } from "lucide-react";

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

type Scenario = {
  id: string;
  title: string;
  level: "Beginner" | "Intermediate" | "Advanced";
  duration: string;
  description: string;
  focus: string;
};

const scenarios: Scenario[] = [
  {
    id: "incident-101",
    title: "Incident Triage Fundamentals",
    level: "Beginner",
    duration: "20 min",
    focus: "Alert Triage",
    description:
      "Practice identifying high-signal alerts, assigning severity, and sequencing first-response actions.",
  },
  {
    id: "oncall-incident-bridge",
    title: "On-Call Bridge Coordination",
    level: "Intermediate",
    duration: "35 min",
    focus: "Bridge Operations",
    description:
      "Run a coordinated incident bridge, route ownership, and keep communication loops tight under pressure.",
  },
  {
    id: "multi-region-outage",
    title: "Multi-Region Outage Simulation",
    level: "Advanced",
    duration: "45 min",
    focus: "Recovery Strategy",
    description:
      "Handle a cascading outage with partial observability and prioritize restoration decisions with trade-offs.",
  },
];

export default function ScenarioCatalogue() {
  const navigate = useNavigate();

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
              3 curated scenarios
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
        </header>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {scenarios.map((scenario) => (
            <Card
              key={scenario.id}
              className="group flex h-full flex-col justify-between border-blue-500/25 bg-gradient-to-br from-slate-800/50 via-slate-900/50 to-black/60 shadow-xl shadow-blue-500/5 transition-all duration-300 hover:-translate-y-1 hover:border-blue-500/60 hover:shadow-2xl hover:shadow-blue-500/30"
            >
              <CardHeader className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <Badge className="border-blue-500/35 bg-blue-500/15 text-blue-100">
                    {scenario.level}
                  </Badge>
                  <span className="inline-flex items-center gap-1 text-xs text-slate-300">
                    <Clock3 className="size-3.5 text-blue-300" />
                    {scenario.duration}
                  </span>
                </div>
                <CardTitle className="text-xl text-slate-50">{scenario.title}</CardTitle>
                <CardDescription className="leading-relaxed text-slate-300">
                  {scenario.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100/90">
                  Primary focus: <span className="font-semibold text-emerald-100">{scenario.focus}</span>
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

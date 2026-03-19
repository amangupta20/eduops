import { useParams } from "react-router-dom";
import { CheckCircle2, Circle, TerminalSquare, MessageSquareText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function ScenarioWorkspace() {
  const { id } = useParams<"id">();
  const sessionId = id ?? "unknown-session";

  return (
    <main className="min-h-screen bg-background">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-10 lg:py-12">
        <Card className="sticky top-6 z-20 border-blue-500/30 bg-gradient-to-br from-slate-800/60 via-slate-900/70 to-slate-950 shadow-xl shadow-blue-500/10 backdrop-blur-md">
          <CardHeader className="flex flex-col gap-4 space-y-0 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <p className="text-sm text-slate-400">Task Panel</p>
              <CardTitle className="text-3xl font-bold text-slate-50">Scenario Workspace</CardTitle>
              <p className="text-sm text-slate-300">
                Follow the checklist, keep logs in view, and coordinate your response in chat.
              </p>
            </div>
            <Badge className="w-fit border-blue-500/40 bg-blue-500/10 text-blue-100" variant="outline">
              Session: {sessionId}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-md border border-emerald-500/25 bg-emerald-500/10 p-3 text-sm">
                <div className="mb-2 flex items-center gap-2 font-medium">
                  <CheckCircle2 className="size-4 text-emerald-500" />
                  <span className="text-emerald-100">Define impact scope</span>
                </div>
                <p className="text-xs text-emerald-100/80">Identify affected regions and services.</p>
              </div>
              <div className="rounded-md border border-blue-500/20 bg-blue-500/10 p-3 text-sm">
                <div className="mb-2 flex items-center gap-2 font-medium">
                  <Circle className="size-4 text-blue-400" />
                  <span className="text-blue-100">Assign ownership</span>
                </div>
                <p className="text-xs text-blue-100/75">Route responders and set update cadence.</p>
              </div>
              <div className="rounded-md border border-blue-500/20 bg-blue-500/5 p-3 text-sm">
                <div className="mb-2 flex items-center gap-2 font-medium">
                  <Circle className="size-4 text-slate-500" />
                  <span className="text-slate-200">Propose mitigation</span>
                </div>
                <p className="text-xs text-slate-300/80">Submit a recovery plan with rationale.</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button className="bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-600/40 hover:from-blue-500 hover:to-blue-600">
                Submit
              </Button>
              <Button
                variant="outline"
                className="border-red-500/40 bg-red-500/5 text-red-100 hover:bg-red-500/10 hover:text-red-50"
              >
                End Session
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="min-h-[500px] border-emerald-500/30 bg-gradient-to-b from-black/90 to-slate-950 shadow-2xl shadow-emerald-500/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base text-emerald-100">
                <TerminalSquare className="size-4 text-emerald-400" />
                Logs
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[420px]">
              <ScrollArea className="h-full rounded-md border border-emerald-500/30 bg-black/95 p-4 font-mono text-xs text-emerald-50/85 shadow-[0_0_40px_rgba(16,185,129,0.1)]">
                <div className="space-y-2">
                  <p><span className="text-emerald-400">[12:10:07]</span> Initializing scenario runtime...</p>
                  <p><span className="text-blue-400">[12:10:10]</span> Connected to incident bridge.</p>
                  <p><span className="text-yellow-400">[12:10:16]</span> Alert burst detected in eu-west.</p>
                  <p><span className="text-red-400">[12:10:18]</span> Elevated latency above SLO threshold.</p>
                  <p><span className="text-emerald-400">[12:10:21]</span> Waiting for live stream events...</p>
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <Card className="min-h-[500px] border-blue-500/30 bg-gradient-to-b from-black/80 to-slate-950 shadow-2xl shadow-blue-500/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base text-blue-100">
                <MessageSquareText className="size-4 text-blue-400" />
                Chat
              </CardTitle>
            </CardHeader>
            <CardContent className="flex h-[420px] flex-col gap-3">
              <div className="rounded-md border border-blue-500/25 bg-gradient-to-br from-slate-800 to-slate-900 p-3 text-sm shadow-[0_4px_20px_rgba(37,99,235,0.2)]">
                <p className="font-medium text-blue-100">AI Assistant</p>
                <p className="mt-1 text-slate-300">
                  Confirm your initial severity and share the first remediation step.
                </p>
              </div>
              <div className="flex-1 rounded-md border border-dashed border-blue-500/20 bg-slate-900/40 p-3 text-sm text-slate-300">
                Conversation stream placeholder
              </div>
              <div className="flex items-center gap-2">
                <Input
                  className="border-blue-500/30 bg-slate-900/70 text-slate-100 placeholder:text-slate-400 focus-visible:ring-blue-500/40"
                  placeholder="Send a message to assistant..."
                />
                <Button className="bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-600/40 hover:from-blue-500 hover:to-blue-600">
                  Send
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </main>
  );
}

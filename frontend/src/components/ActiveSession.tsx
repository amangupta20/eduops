import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { notifyError, notifySuccess } from "@/lib/notify";
import { ApiError, deleteSession, getActiveSession } from "@/services/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

type ActiveSessionProps = {
  sessionId: string;
};

export default function ActiveSession({ sessionId }: ActiveSessionProps) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [cleanupWorkspace, setCleanupWorkspace] = useState(false);
  const [workspacePath, setWorkspacePath] = useState<string>("Loading workspace path...");
  const [isEndingSession, setIsEndingSession] = useState(false);
  const [isLoadingWorkspacePath, setIsLoadingWorkspacePath] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const loadActiveSession = async () => {
      setIsLoadingWorkspacePath(true);
      try {
        const session = await getActiveSession();
        if (!isMounted) return;
        if (session.id === sessionId) {
          setWorkspacePath(session.workspace_path);
        } else {
          setWorkspacePath(`Workspace path unavailable for session ${sessionId}`);
        }
      } catch {
        if (!isMounted) return;
        setWorkspacePath(`Workspace path unavailable for session ${sessionId}`);
      } finally {
        if (isMounted) {
          setIsLoadingWorkspacePath(false);
        }
      }
    };

    void loadActiveSession();

    return () => {
      isMounted = false;
    };
  }, [sessionId]);

  const progressLabel = useMemo(() => {
    if (!isEndingSession) return "End Session";
    return cleanupWorkspace ? "Ending session and deleting workspace..." : "Ending session...";
  }, [cleanupWorkspace, isEndingSession]);

  const handleEndSession = async () => {
    setIsEndingSession(true);
    try {
      await deleteSession(sessionId, { cleanup_workspace: cleanupWorkspace });
      notifySuccess(
        "Session ended",
        cleanupWorkspace ? "Session ended and workspace deleted." : "Session ended. Workspace preserved.",
      );
      setOpen(false);
      navigate("/");
    } catch (error) {
      const detail =
        error instanceof ApiError
          ? error.message
          : "Unable to end session right now. Please try again.";
      notifyError("Failed to end session", detail);
    } finally {
      setIsEndingSession(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          className="border-red-500/40 bg-red-500/5 text-red-100 hover:bg-red-500/10 hover:text-red-50"
        >
          End Session
        </Button>
      </DialogTrigger>
      <DialogContent className="border-red-500/30 bg-slate-950 text-slate-100">
        <DialogHeader>
          <DialogTitle>End active session?</DialogTitle>
          <DialogDescription className="text-slate-300">
            This will stop the active session and run cleanup.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-md border border-slate-700 bg-slate-900/80 p-3 text-sm">
            <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">Workspace path</p>
            <p className="break-all font-mono text-xs text-slate-200">
              {isLoadingWorkspacePath ? "Loading workspace path..." : workspacePath}
            </p>
          </div>

          <label className="flex items-start gap-3 rounded-md border border-slate-700 bg-slate-900/60 p-3 text-sm">
            <input
              type="checkbox"
              checked={cleanupWorkspace}
              onChange={(event) => setCleanupWorkspace(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-slate-500 bg-slate-900 accent-red-500"
            />
            <span className="text-slate-200">
              Delete workspace files at{" "}
              <span className="font-mono text-xs text-slate-300">{workspacePath}</span>
            </span>
          </label>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={isEndingSession}
            className="border-slate-600 bg-transparent text-slate-200 hover:bg-slate-800"
          >
            Cancel
          </Button>
          <Button
            onClick={() => void handleEndSession()}
            disabled={isEndingSession}
            className="bg-red-600 text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-80"
          >
            {progressLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

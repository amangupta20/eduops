import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { notifyWarning } from "@/lib/notify";
import { searchScenarios } from "@/services/api";
import type { Scenario } from "@/types";

type SearchBarProps = {
  catalogue: Scenario[];
  onResultsChange: (scenarios: Scenario[]) => void;
};

export default function SearchBar({ catalogue, onResultsChange }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [resultCount, setResultCount] = useState(catalogue.length);
  const hasShownSearchFallbackToast = useRef(false);

  const trimmedQuery = useMemo(() => query.trim(), [query]);

  useEffect(() => {
    setResultCount(catalogue.length);
    if (!trimmedQuery) {
      setHasSearched(false);
    }
  }, [catalogue.length, trimmedQuery]);

  useEffect(() => {
    if (!trimmedQuery) {
      onResultsChange(catalogue);
      setResultCount(catalogue.length);
      setIsSearching(false);
      return;
    }

    const timeoutId = window.setTimeout(async () => {
      setIsSearching(true);
      setHasSearched(true);

      try {
        const results = await searchScenarios(trimmedQuery);
        onResultsChange(results);
        setResultCount(results.length);
        hasShownSearchFallbackToast.current = false;
      } catch {
        // Fallback keeps UX functional even if search endpoint is unavailable.
        if (!hasShownSearchFallbackToast.current) {
          notifyWarning("Search API unavailable", "Using local search fallback.");
          hasShownSearchFallbackToast.current = true;
        }
        const lowerQuery = trimmedQuery.toLowerCase();
        const fallbackResults = catalogue.filter((scenario) => {
          const haystack = `${scenario.title} ${scenario.description} ${scenario.tags.join(" ")}`.toLowerCase();
          return haystack.includes(lowerQuery);
        });
        onResultsChange(fallbackResults);
        setResultCount(fallbackResults.length);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [catalogue, onResultsChange, trimmedQuery]);

  const showNoResults = hasSearched && !isSearching && resultCount === 0;

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search scenarios (e.g. bind mounts, debugging containers...)"
          className="border-blue-500/30 bg-slate-900/70 pl-9 pr-10 text-slate-100 placeholder:text-slate-400 focus-visible:ring-blue-500/40"
          aria-label="Search scenarios"
        />
        {query.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setHasSearched(false);
              setResultCount(catalogue.length);
              onResultsChange(catalogue);
            }}
            className="absolute right-2 top-1/2 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
            aria-label="Clear search"
          >
            <X className="size-4" />
          </button>
        )}
      </div>

      <div className="text-xs text-slate-400">
        {isSearching ? "Searching..." : `${resultCount} result${resultCount === 1 ? "" : "s"}`}
      </div>

      {showNoResults && (
        <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
          No results found. Try different keywords.
        </p>
      )}
    </div>
  );
}

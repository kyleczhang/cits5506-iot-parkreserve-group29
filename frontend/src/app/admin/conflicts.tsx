/**
 * Conflicts queue — `/admin/conflicts`.
 *
 * Two-column layout: filter + list on the left, drawer detail on the
 * right. Rows animate in/out as the realtime bus flips
 * `conflict.raised` / `conflict.resolved`.
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";

import { listOpenConflicts } from "@/api/conflicts";
import { qk } from "@/api/queryKeys";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { formatRelative } from "@/lib/time";
import { cn } from "@/lib/cn";
import { ConflictDrawer } from "./conflict-drawer";

export function ConflictsPage() {
  const list = useQuery({
    queryKey: qk.conflicts.open(),
    queryFn: listOpenConflicts,
  });
  const [filter, setFilter] = useState<"all" | "strong" | "weak">("all");
  const [selected, setSelected] = useState<string | null>(null);

  const rows = useMemo(() => {
    const all = list.data ?? [];
    return filter === "all" ? all : all.filter((c) => c.kind === filter);
  }, [list.data, filter]);

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">
          Open conflicts
        </h1>
        <span className="text-sm text-text-muted">
          {list.data?.length ?? 0} unresolved
        </span>
      </header>

      <div className="inline-flex rounded-lg border border-border bg-surface p-1">
        {(["all", "strong", "weak"] as const).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setFilter(k)}
            aria-pressed={filter === k}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors duration-150 cursor-pointer",
              filter === k
                ? "bg-surface-2 text-text"
                : "text-text-muted hover:bg-surface-2",
            )}
          >
            {k}
          </button>
        ))}
      </div>

      {list.isLoading ? (
        <div className="grid h-40 place-items-center">
          <Spinner label="Loading conflicts" />
        </div>
      ) : list.isError ? (
        <Card className="p-4 text-sm text-danger">
          Couldn&apos;t load conflicts.
        </Card>
      ) : rows.length === 0 ? (
        <Card className="flex items-center gap-3 p-6 text-text-muted">
          <ShieldAlert className="h-5 w-5 text-success" aria-hidden="true" />
          No {filter === "all" ? "" : filter + " "}open conflicts. The facility
          is calm.
        </Card>
      ) : (
        <ul className="space-y-2">
          {rows.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => setSelected(c.id)}
                className="flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4 text-left transition-shadow duration-150 hover:shadow-card-hover cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "inline-flex h-9 w-9 items-center justify-center rounded-full",
                      c.kind === "strong"
                        ? "bg-danger/15 text-danger"
                        : "bg-warn/15 text-warn",
                    )}
                  >
                    <ShieldAlert className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="font-medium">
                      Bay <span className="font-mono">{c.bay_code}</span>
                      <span
                        className={cn(
                          "ml-2 inline-flex rounded-full border px-2 py-0.5 text-xs font-medium",
                          c.kind === "strong"
                            ? "border-danger/40 bg-danger/10 text-danger"
                            : "border-warn/40 bg-warn/10 text-warn",
                        )}
                      >
                        {c.kind}
                      </span>
                    </p>
                    <p className="font-mono text-xs text-text-muted">
                      {c.recognised_plate
                        ? `Plate ${c.recognised_plate} · `
                        : ""}
                      {formatRelative(c.detected_at)}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-text-muted">Open →</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected ? (
        <ConflictDrawer id={selected} onClose={() => setSelected(null)} />
      ) : null}
    </div>
  );
}

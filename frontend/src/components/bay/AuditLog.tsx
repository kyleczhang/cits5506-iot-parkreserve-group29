/**
 * Bay audit-log list with keyset pagination.
 *
 * Each row shows the event kind chip, family-coloured dot, an absolute
 * timestamp, optional state transition, and an expandable JSON viewer
 * for the free-form payload. Pagination uses the oldest row's
 * `created_at` as the `before` cursor on the next request.
 */
import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";

import { listBayEvents } from "@/api/bays";
import { qk } from "@/api/queryKeys";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/cn";
import { formatAbsolute, formatRelative } from "@/lib/time";
import type { BayEventKind, BayEventOut } from "@/schemas/bay";

const PAGE = 50;

const KIND_FAMILY: Record<BayEventKind, "state" | "sensor" | "reservation" | "conflict"> = {
  state_changed: "state",
  sensor_online: "sensor",
  sensor_offline: "sensor",
  pending_check_in: "state",
  auto_check_in: "state",
  check_in_confirmed: "state",
  conflict_strong: "conflict",
  conflict_weak: "conflict",
  conflict_resolved: "conflict",
  no_show: "conflict",
  reservation_created: "reservation",
  reservation_cancelled: "reservation",
  reservation_completed: "reservation",
  plates_updated: "reservation",
};

const FAMILY_DOT: Record<string, string> = {
  state: "bg-accent",
  sensor: "bg-state-offline",
  reservation: "bg-brand",
  conflict: "bg-state-conflict",
};

interface Props {
  code: string;
}

export function AuditLog({ code }: Props) {
  const query = useInfiniteQuery({
    queryKey: qk.bays.events(code, "audit"),
    queryFn: ({ pageParam }) =>
      listBayEvents(code, {
        limit: PAGE,
        ...(pageParam ? { before: pageParam } : {}),
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => {
      if (!last.length) return undefined;
      const oldest = last[last.length - 1];
      return oldest?.created_at;
    },
  });

  if (query.isLoading) {
    return (
      <div className="grid h-32 place-items-center">
        <Spinner label="Loading audit log" />
      </div>
    );
  }
  if (query.isError) {
    return (
      <p className="text-sm text-danger">Couldn&apos;t load the audit log.</p>
    );
  }

  const rows = query.data?.pages.flat() ?? [];

  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-surface-2 p-4 text-sm text-text-muted">
        No events recorded for this bay yet.
      </p>
    );
  }

  return (
    <>
      <ul className="space-y-2">
        {rows.map((row) => (
          <AuditRow key={row.id} row={row} />
        ))}
      </ul>
      <div className="mt-4 flex justify-center">
        {query.hasNextPage ? (
          <Button
            variant="secondary"
            loading={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            Load older
          </Button>
        ) : (
          <p className="text-xs text-text-muted">End of history.</p>
        )}
      </div>
    </>
  );
}

function AuditRow({ row }: { row: BayEventOut }) {
  const [open, setOpen] = useState(false);
  const family = KIND_FAMILY[row.kind] ?? "state";
  const Chev = open ? ChevronDown : ChevronRight;
  const hasPayload = Object.keys(row.payload ?? {}).length > 0;

  return (
    <li className="rounded-lg border border-border bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn(
          "flex w-full items-center gap-3 p-3 text-left",
          "transition-colors duration-150 hover:bg-surface-2 cursor-pointer",
        )}
      >
        <span
          aria-hidden="true"
          className={cn("h-2 w-2 shrink-0 rounded-full", FAMILY_DOT[family])}
        />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-baseline gap-2">
            <span className="font-medium">{prettifyKind(row.kind)}</span>
            {row.from_state && row.to_state ? (
              <span className="font-mono text-xs text-text-muted">
                {row.from_state} → {row.to_state}
              </span>
            ) : null}
          </p>
          <p className="font-mono text-xs text-text-muted">
            {formatAbsolute(row.created_at)} · {formatRelative(row.created_at)}
          </p>
        </div>
        {hasPayload ? <Chev className="h-4 w-4 text-text-muted" aria-hidden="true" /> : null}
      </button>
      {open && hasPayload ? (
        <pre className="mx-3 mb-3 overflow-x-auto rounded bg-surface-2 p-3 font-mono text-xs">
          {JSON.stringify(row.payload, null, 2)}
        </pre>
      ) : null}
    </li>
  );
}

function prettifyKind(kind: BayEventKind): string {
  return kind.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

/**
 * Vertical status timeline — reused in the reservation cockpit and the
 * per-bay drill-down's audit log. Each node has a colour from the
 * event-kind family palette and an absolute timestamp.
 */
import { cn } from "@/lib/cn";
import { formatAbsolute, formatRelative } from "@/lib/time";

export interface TimelineNode {
  /** Stable id (UUID, bay-event row id, etc.). */
  id: string;
  /** Short label for the node (e.g. "Reserved", "Auto check-in"). */
  label: string;
  /** Optional richer description rendered below the label. */
  description?: string;
  /** ISO timestamp. */
  at: string;
  /** Event-kind family driving the dot colour. */
  family?: "state" | "sensor" | "reservation" | "conflict" | "payment" | "info";
  /** Render `description` as preformatted JSON-ish content. */
  monoDescription?: boolean;
}

const FAMILY_COLOUR: Record<NonNullable<TimelineNode["family"]>, string> = {
  state: "bg-accent",
  sensor: "bg-state-offline",
  reservation: "bg-brand",
  conflict: "bg-state-conflict",
  payment: "bg-success",
  info: "bg-text-muted",
};

interface Props {
  nodes: ReadonlyArray<TimelineNode>;
  /** Render newest-first (default) or oldest-first. */
  order?: "newest-first" | "oldest-first";
  className?: string;
}

export function StatusTimeline({
  nodes,
  order = "newest-first",
  className,
}: Props) {
  const ordered =
    order === "newest-first"
      ? [...nodes].sort(
          (a, b) => Date.parse(b.at) - Date.parse(a.at),
        )
      : [...nodes].sort(
          (a, b) => Date.parse(a.at) - Date.parse(b.at),
        );

  if (ordered.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-surface-2 p-4 text-sm text-text-muted">
        No events yet.
      </p>
    );
  }

  return (
    <ol className={cn("relative space-y-4 border-l border-border pl-4", className)}>
      {ordered.map((node) => {
        const colour = FAMILY_COLOUR[node.family ?? "info"];
        return (
          <li key={node.id} className="relative">
            <span
              aria-hidden="true"
              className={cn(
                "absolute -left-[1.4rem] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-bg",
                colour,
              )}
            />
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-sm font-medium text-text">{node.label}</p>
              <time
                className="font-mono text-xs text-text-muted"
                dateTime={node.at}
                title={formatAbsolute(node.at)}
              >
                {formatRelative(node.at)}
              </time>
            </div>
            {node.description ? (
              <p
                className={cn(
                  "mt-0.5 text-xs text-text-muted",
                  node.monoDescription && "whitespace-pre-wrap font-mono",
                )}
              >
                {node.description}
              </p>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

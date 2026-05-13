/**
 * Single payment ledger row.
 *
 * Visual rule (plan §5.7):
 *   - amount in red when money leaves the wallet (`pre_auth`,
 *     `penalty_capture`),
 *   - amount in green when money returns (`release`, `refund`).
 *
 * Action chips use a dedicated colour family so the *type* of payment
 * is also legible at a glance, not only by colour of the number.
 */
import { ArrowDownCircle, ArrowUpCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatCents, isOutboundPayment } from "@/lib/money";
import { formatAbsolute } from "@/lib/time";
import type { TransactionOut } from "@/schemas/payment";

const ACTION_META: Record<
  TransactionOut["action"],
  { label: string; chip: string }
> = {
  pre_auth: {
    label: "Held",
    chip: "border-warn/40 bg-warn/10 text-warn",
  },
  release: {
    label: "Released",
    chip: "border-success/40 bg-success/10 text-success",
  },
  refund: {
    label: "Refunded",
    chip: "border-accent/40 bg-accent/10 text-accent",
  },
  penalty_capture: {
    label: "Penalty captured",
    chip: "border-danger/40 bg-danger/10 text-danger",
  },
};

interface Props {
  row: TransactionOut;
  onClick?: (id: string) => void;
}

export function LedgerRow({ row, onClick }: Props) {
  const out = isOutboundPayment(row.action);
  const meta = ACTION_META[row.action];
  const ArrowIcon = out ? ArrowUpCircle : ArrowDownCircle;

  return (
    <button
      type="button"
      onClick={() => onClick?.(row.id)}
      className={cn(
        "flex w-full items-center gap-4 rounded-lg border border-border bg-surface p-4",
        "text-left transition-shadow duration-150 cursor-pointer",
        "hover:shadow-card-hover focus-visible:shadow-card-hover",
      )}
    >
      <ArrowIcon
        aria-hidden="true"
        className={cn("h-6 w-6 shrink-0", out ? "text-danger" : "text-success")}
      />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
              meta.chip,
            )}
          >
            {meta.label}
          </span>
          {row.penalty_kind ? (
            <span className="text-xs text-text-muted">
              · {row.penalty_kind.replace("_", " ")}
            </span>
          ) : null}
        </p>
        <p className="mt-1 font-mono text-xs text-text-muted">
          Reservation{" "}
          <span className="break-all">{row.reservation_id.slice(0, 8)}…</span> ·{" "}
          {formatAbsolute(row.occurred_at)}
        </p>
      </div>
      <p
        className={cn(
          "font-mono tabular-nums text-base font-semibold",
          out ? "text-danger" : "text-success",
        )}
      >
        {out ? "−" : "+"}
        {formatCents(row.amount_cents)}
      </p>
    </button>
  );
}

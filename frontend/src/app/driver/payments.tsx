/**
 * Payments ledger — `/app/payments`.
 *
 * Read-only mock-payment view. Top-of-page banner reminds the user
 * that all amounts are mock-only (rubric "scope honesty"). A row
 * click opens a Drawer with the transaction detail fetched lazily.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ReceiptText, ArrowLeft, ShieldAlert } from "lucide-react";

import { getPayment, listPayments } from "@/api/payments";
import { qk } from "@/api/queryKeys";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Drawer } from "@/components/ui/Drawer";
import { LedgerRow } from "@/components/payment/LedgerRow";
import { ReservationOutcomes } from "@/components/chart/ReservationOutcomes";
import { formatCents, isOutboundPayment } from "@/lib/money";
import { formatAbsolute } from "@/lib/time";

export function PaymentsPage() {
  const list = useQuery({ queryKey: qk.payments.list(), queryFn: listPayments });
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to="/app"
        className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to home
      </Link>
      <header className="mt-3 flex items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">
          Payments ledger
        </h1>
        <ReceiptText className="h-5 w-5 text-text-muted" aria-hidden="true" />
      </header>

      <p className="mt-3 inline-flex items-start gap-2 rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden="true" />
        Mock-payment only — no real bank network is ever contacted in this
        prototype.
      </p>

      <section className="mt-5">
        <Card className="p-5">
          <header className="mb-3">
            <h2 className="text-base font-semibold tracking-tight">
              Weekly outcomes
            </h2>
            <p className="text-xs text-text-muted">
              How your reservations have settled over time.
            </p>
          </header>
          <ReservationOutcomes />
        </Card>
      </section>

      <section className="mt-5">
        {list.isLoading ? (
          <Card className="grid h-32 place-items-center">
            <Spinner label="Loading payments" />
          </Card>
        ) : list.isError ? (
          <Card className="p-4 text-sm text-danger">
            Couldn&apos;t load your ledger.
          </Card>
        ) : (list.data?.length ?? 0) === 0 ? (
          <Card className="p-6 text-center text-sm text-text-muted">
            No payments yet. Book a bay and a pre-auth hold will appear here.
          </Card>
        ) : (
          <ul className="flex flex-col gap-2">
            {list.data?.map((row) => (
              <li key={row.id}>
                <LedgerRow row={row} onClick={setOpenId} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {openId ? (
        <PaymentDetailDrawer
          id={openId}
          onClose={() => setOpenId(null)}
        />
      ) : null}
    </div>
  );
}

function PaymentDetailDrawer({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const detail = useQuery({
    queryKey: qk.payments.detail(id),
    queryFn: () => getPayment(id),
  });

  return (
    <Drawer
      open={Boolean(id)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Transaction detail"
      description="Mock-payment row from the in-process ledger."
    >
      {detail.isLoading ? (
        <Spinner label="Loading" />
      ) : detail.isError || !detail.data ? (
        <p className="text-sm text-danger">Couldn&apos;t load this transaction.</p>
      ) : (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-text-muted">ID</dt>
          <dd className="break-all font-mono">{detail.data.id}</dd>
          <dt className="text-text-muted">Reservation</dt>
          <dd className="break-all font-mono">{detail.data.reservation_id}</dd>
          <dt className="text-text-muted">Action</dt>
          <dd>{detail.data.action.replace("_", " ")}</dd>
          {detail.data.penalty_kind ? (
            <>
              <dt className="text-text-muted">Penalty</dt>
              <dd>{detail.data.penalty_kind.replace("_", " ")}</dd>
            </>
          ) : null}
          <dt className="text-text-muted">Amount</dt>
          <dd
            className={
              "font-mono " +
              (isOutboundPayment(detail.data.action)
                ? "text-danger"
                : "text-success")
            }
          >
            {isOutboundPayment(detail.data.action) ? "−" : "+"}
            {formatCents(detail.data.amount_cents)}
          </dd>
          <dt className="text-text-muted">Status</dt>
          <dd>{detail.data.status}</dd>
          <dt className="text-text-muted">Occurred</dt>
          <dd className="font-mono">{formatAbsolute(detail.data.occurred_at)}</dd>
        </dl>
      )}
    </Drawer>
  );
}

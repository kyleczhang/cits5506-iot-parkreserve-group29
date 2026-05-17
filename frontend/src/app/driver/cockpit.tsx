/**
 * Reservation cockpit — `/app/reservations/:id`.
 *
 * State-driven action region per plan §5.5. The IN_CONFLICT path is a
 * single banner (driver can't distinguish weak from strong because
 * `ReservationOut` doesn't carry `conflict_kind` and `/api/v1/conflicts`
 * is admin-only); we offer one "Late check-in" button optimistically
 * and swap to a victim banner if the backend 409s with strong.
 *
 * Refund copy reflects the immediate refund on `_on_conflict_strong`
 * — see backend/app/services/event_dispatcher.py:294.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useState } from "react";
import {
  AlertOctagon,
  ArrowLeft,
  Ban,
  CheckCircle2,
  QrCode,
  ShieldCheck,
} from "lucide-react";

import { getBay } from "@/api/bays";
import {
  cancelReservation,
  checkInReservation,
  getReservation,
} from "@/api/reservations";
import { qk } from "@/api/queryKeys";
import { ApiError } from "@/api/client";
import { ReservationStatusBadge } from "@/components/reservation/ReservationStatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { CountdownPill } from "@/components/reservation/CountdownPill";
import { StatusTimeline } from "@/components/reservation/StatusTimeline";
import { pushToast } from "@/components/ui/toastStore";
import { formatAbsolute } from "@/lib/time";
import type { BayOut } from "@/schemas/bay";
import type { ReservationStatus } from "@/schemas/reservation";
import type { ReservationOut } from "@/schemas/reservation";
import type { TimelineNode } from "@/components/reservation/StatusTimeline";

export function ReservationCockpit() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [conflictIsStrong, setConflictIsStrong] = useState(false);

  const reservation = useQuery({
    queryKey: qk.reservations.detail(id),
    queryFn: () => getReservation(id),
    enabled: Boolean(id),
  });
  // Strong conflict keeps the reservation row in `active` / `checked_in`
  // (CLAUDE.md "Conflict semantics"). We mirror the bay's live state so
  // the cockpit can surface the incident even though the reservation
  // lifecycle hasn't moved — `bay.updated` invalidates this key.
  const bayCode = reservation.data?.bay_code;
  const bay = useQuery({
    queryKey: qk.bays.detail(bayCode ?? ""),
    queryFn: () => getBay(bayCode as string),
    enabled: Boolean(bayCode),
  });

  // ---- mutations ----------------------------------------------------------
  const cancelMutation = useMutation({
    mutationFn: () => cancelReservation(id),
    onSuccess: (res) => {
      syncAvailableBayCache(queryClient, res);
      queryClient.setQueryData(qk.reservations.detail(id), res);
      void queryClient.invalidateQueries({ queryKey: qk.bays.list() });
      void queryClient.invalidateQueries({ queryKey: qk.bays.detail(res.bay_code) });
      void queryClient.invalidateQueries({ queryKey: qk.reservations.list() });
      void queryClient.invalidateQueries({ queryKey: qk.payments.list() });
      pushToast({
        tone: res.status === "cancelled_late" ? "warn" : "success",
        title:
          res.status === "cancelled_late"
            ? "Reservation cancelled (late)"
            : "Reservation cancelled",
        description:
          res.status === "cancelled_late"
            ? "A late-cancel penalty was captured from your deposit."
            : "Your deposit has been released.",
      });
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        pushToast({ tone: "danger", title: "Couldn't cancel", description: err.message });
      }
    },
  });

  const checkInMutation = useMutation({
    mutationFn: (source: "qr" | "manual") =>
      checkInReservation(id, {
        bay_code: reservation.data?.bay_code ?? "",
        source,
      }),
    onSuccess: (res) => {
      queryClient.setQueryData(qk.reservations.detail(id), res);
      void queryClient.invalidateQueries({ queryKey: qk.reservations.list() });
      pushToast({
        tone: "success",
        title: `Checked in at Bay ${res.bay_code}`,
      });
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        if (err.code === "vehicle_not_detected_yet") {
          // Silent — we trust the next `reservation.pending_check_in` WS
          // event to flip the status (plan §5.5 / openapi.yaml).
          pushToast({
            tone: "info",
            title: "Waiting for vehicle…",
            description:
              "Drive up to the bay and we'll auto-check you in when the sensor fires.",
          });
        } else if (err.code === "reservation_in_conflict") {
          // Strong conflict — surface the victim banner (plan §5.5).
          setConflictIsStrong(true);
          void queryClient.invalidateQueries({
            queryKey: qk.reservations.detail(id),
          });
          pushToast({
            tone: "danger",
            title: "This conflict requires staff intervention",
            description:
              "Your deposit has been refunded — facility staff will resolve the bay.",
          });
        } else {
          pushToast({
            tone: "danger",
            title: "Couldn't check in",
            description: err.message,
          });
        }
      }
    },
  });

  if (!id) {
    return <p className="text-sm text-danger">Missing reservation id.</p>;
  }
  if (reservation.isLoading) {
    return (
      <div className="grid h-40 place-items-center">
        <Spinner label="Loading reservation" />
      </div>
    );
  }
  if (reservation.isError) {
    return (
      <Card className="border-danger/30 bg-danger/10 p-4 text-sm text-danger">
        Couldn&apos;t load this reservation.
      </Card>
    );
  }
  if (!reservation.data) return null;

  const r = reservation.data;
  const timeline = buildTimeline(r);

  // Countdown target depends on the current status.
  const countdownTarget =
    r.status === "active"
      ? r.expected_arrival_time
      : r.status === "pending_check_in"
        ? (r.check_in_grace_expires_at ?? null)
        : null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to="/app"
        className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to home
      </Link>

      <header className="rounded-2xl border border-border bg-surface p-6 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wider text-text-muted">
              Reservation
            </p>
            <h1 className="mt-1 font-mono text-3xl font-semibold tracking-tight">
              Bay {r.bay_code}
            </h1>
            <p className="mt-1 text-sm text-text-muted">
              Arrival{" "}
              <time dateTime={r.expected_arrival_time} className="font-mono">
                {formatAbsolute(r.expected_arrival_time)}
              </time>
            </p>
          </div>
          <ReservationStatusBadge status={r.status} />
        </div>
        {countdownTarget ? (
          <div className="mt-4">
            <CountdownPill
              target={countdownTarget}
              label={
                r.status === "active" ? "until arrival" : "grace remaining"
              }
              onExpire={() => {
                // Refetch to confirm the server-side transition.
                void queryClient.invalidateQueries({
                  queryKey: qk.reservations.detail(id),
                });
              }}
            />
          </div>
        ) : null}
      </header>

      {/* In-conflict banner */}
      {(() => {
        // `in_conflict` = weak conflict (driver breach, grace expired).
        // `bay.state === "conflict"` while the reservation is still
        // `active` / `pending_check_in` / `checked_in` = strong conflict
        // (wrong vehicle at the bay). Both surface here; copy differs.
        const isNonTerminal =
          r.status === "active" ||
          r.status === "pending_check_in" ||
          r.status === "checked_in" ||
          r.status === "in_conflict";
        const bayInConflict =
          isNonTerminal &&
          bay.data?.state === "conflict" &&
          r.status !== "in_conflict";
        if (r.status !== "in_conflict" && !bayInConflict) return null;
        return (
        <Card
          className={
            "border-danger/40 bg-danger/10 p-4 " +
            (conflictIsStrong ? "ring-1 ring-danger/30" : "")
          }
          role="status"
        >
          <header className="flex items-start gap-3">
            <AlertOctagon
              aria-hidden="true"
              className="mt-0.5 h-5 w-5 shrink-0 text-danger"
            />
            <div>
              <p className="font-semibold text-text">
                {bayInConflict
                  ? "Another vehicle is currently at your bay — staff have been notified."
                  : "Conflict detected at your bay — facility staff have been notified."}
              </p>
              {bayInConflict ? (
                <p className="mt-1 text-sm text-text-muted">
                  Your reservation is being held while the facility resolves
                  the incident. If the other vehicle leaves before your arrival
                  you&apos;ll be able to check in as normal; otherwise staff
                  may terminate the reservation and refund your deposit.
                </p>
              ) : conflictIsStrong ? (
                <p className="mt-1 text-sm text-text-muted">
                  This conflict requires staff intervention. Your deposit has
                  been refunded — see the payments tab for the receipt.
                </p>
              ) : (
                <p className="mt-1 text-sm text-text-muted">
                  If you&apos;re already at the bay, try a late check-in below.
                  If LPR saw a different plate, this becomes a facility incident
                  and your deposit is refunded automatically.
                </p>
              )}
            </div>
          </header>
        </Card>
        );
      })()}

      {/* Action region */}
      <ActionRegion
        status={r.status}
        canLateCheckIn={r.status === "in_conflict" && !conflictIsStrong}
        cancelling={cancelMutation.isPending}
        checkingIn={checkInMutation.isPending}
        onCancel={() => cancelMutation.mutate()}
        onCheckIn={(source) => checkInMutation.mutate(source)}
      />

      {/* Timeline */}
      <section aria-labelledby="timeline-heading" className="space-y-3">
        <h2
          id="timeline-heading"
          className="text-base font-semibold tracking-tight text-text"
        >
          Reservation timeline
        </h2>
        <Card className="p-5">
          <StatusTimeline nodes={timeline} />
        </Card>
      </section>

      <button
        type="button"
        onClick={() => navigate("/app/payments")}
        className="text-sm text-brand hover:underline cursor-pointer"
      >
        View the payments ledger →
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface ActionProps {
  status: ReservationStatus;
  canLateCheckIn: boolean;
  cancelling: boolean;
  checkingIn: boolean;
  onCancel: () => void;
  onCheckIn: (source: "qr" | "manual") => void;
}

function ActionRegion(props: ActionProps) {
  const { status, canLateCheckIn, cancelling, checkingIn, onCancel, onCheckIn } =
    props;

  if (status === "active") {
    return (
      <Card className="space-y-3 p-5">
        <p className="text-sm text-text-muted">
          Cancelling close to your arrival time may be charged as a late
          cancel. The actual verdict is settled by the backend the moment you
          confirm.
        </p>
        <Button
          variant="danger"
          loading={cancelling}
          onClick={onCancel}
          leadingIcon={<Ban className="h-4 w-4" />}
        >
          Cancel reservation
        </Button>
      </Card>
    );
  }

  if (status === "pending_check_in" || canLateCheckIn) {
    return (
      <Card className="grid gap-3 p-5 sm:grid-cols-2">
        <Button
          loading={checkingIn}
          onClick={() => onCheckIn("manual")}
          leadingIcon={<CheckCircle2 className="h-4 w-4" />}
        >
          Check in (manual)
        </Button>
        <Button
          variant="secondary"
          loading={checkingIn}
          onClick={() => onCheckIn("qr")}
          leadingIcon={<QrCode className="h-4 w-4" />}
        >
          Check in (QR)
        </Button>
        {canLateCheckIn ? (
          <p className="sm:col-span-2 text-xs text-text-muted">
            <strong>Heads up.</strong> The weak-conflict penalty captured when
            the grace window expired is not refunded — a late check-in clears
            the alarm but doesn&apos;t undo the cost.
          </p>
        ) : null}
      </Card>
    );
  }

  if (status === "checked_in") {
    return (
      <Card className="flex items-center gap-3 p-5">
        <ShieldCheck className="h-6 w-6 text-success" aria-hidden="true" />
        <div>
          <p className="font-medium">You&apos;re checked in.</p>
          <p className="text-sm text-text-muted">
            Drive out whenever you&apos;re ready — the facility exit gate
            handles billing for the actual parking time.
          </p>
        </div>
      </Card>
    );
  }

  if (status === "completed") {
    return (
      <Card className="border-success/30 bg-success/5 p-5">
        <p className="font-medium">Reservation complete.</p>
        <p className="mt-1 text-sm text-text-muted">
          Any held deposit remainder has been released back to your card.
        </p>
      </Card>
    );
  }

  if (
    status === "cancelled" ||
    status === "cancelled_late" ||
    status === "expired_no_show"
  ) {
    return (
      <Card className="p-5">
        <p className="font-medium">
          {status === "cancelled" && "Cancelled."}
          {status === "cancelled_late" && "Cancelled (late)."}
          {status === "expired_no_show" && "Marked as no-show."}
        </p>
        <p className="mt-1 text-sm text-text-muted">
          See the payments ledger for the matching capture or release row.
        </p>
      </Card>
    );
  }

  return null;
}

/**
 * Synthesise a timeline of reservation events from the reservation row.
 * Per plan §6.5 the timeline is reused with audit-log rows in the admin
 * drill-down, but the driver view only has the fields exposed via
 * `ReservationOut`.
 */
function buildTimeline(
  r: ReturnType<typeof normaliseInput>,
): TimelineNode[] {
  const out: TimelineNode[] = [];
  out.push({
    id: `${r.id}-booked`,
    label: "Reservation created",
    at: r.booked_at,
    family: "reservation",
  });
  if (r.checked_in_at) {
    out.push({
      id: `${r.id}-checked-in`,
      label:
        r.check_in_mechanism === "auto_lpr"
          ? "Auto check-in (LPR)"
          : r.check_in_mechanism === "qr"
            ? "Checked in (QR)"
            : "Checked in (manual)",
      at: r.checked_in_at,
      family: "state",
    });
  }
  if (r.cancelled_at) {
    out.push({
      id: `${r.id}-cancelled`,
      label:
        r.status === "cancelled_late"
          ? "Cancelled (late)"
          : "Cancelled",
      at: r.cancelled_at,
      family: "reservation",
    });
  }
  if (r.completed_at) {
    out.push({
      id: `${r.id}-completed`,
      label: "Completed",
      at: r.completed_at,
      family: "state",
    });
  }
  return out;
}

function normaliseInput<T>(x: T): T {
  return x;
}

function syncAvailableBayCache(queryClient: QueryClient, reservation: ReservationOut): void {
  const clearReservation = (bay: BayOut): BayOut =>
    bay.code === reservation.bay_code
      ? {
          ...bay,
          state: "available",
          current_reservation_id: null,
          current_reservation_arrival: null,
          check_in_grace_expires_at: null,
        }
      : bay;

  queryClient.setQueryData<BayOut[] | undefined>(qk.bays.list(), (current) =>
    current?.map(clearReservation),
  );
  queryClient.setQueryData<BayOut | undefined>(
    qk.bays.detail(reservation.bay_code),
    (current) => (current ? clearReservation(current) : current),
  );
}

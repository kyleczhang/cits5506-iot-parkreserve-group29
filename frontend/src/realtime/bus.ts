/**
 * Realtime event bus.
 *
 * Subscribes to the socket once, validates each payload with its Zod
 * schema, then dispatches to:
 *   1. `queryClient.invalidateQueries` for cache freshness
 *      (the default — see plan §4),
 *   2. an in-memory toast queue for user-visible notifications,
 *   3. ONE documented setQueryData exception:
 *      `reservation.auto_checked_in`'s payload is a superset of
 *      `ReservationOut`, so we patch the cached detail entry directly
 *      so the cockpit status pill flips without a refetch round-trip.
 *      Gated by a runtime shape assertion — see plan §4 "single rule,
 *      single exception".
 */
import type { QueryClient } from "@tanstack/react-query";

import { qk } from "@/api/queryKeys";
import { pushToast } from "@/components/ui/toastStore";
import { getSocket } from "./socket";
import {
  wsBayUpdated,
  wsConflict,
  wsPaymentDepositReleased,
  wsPaymentPenaltyCaptured,
  wsPaymentRefunded,
  wsPlateUpdated,
  wsReservationAutoCheckedIn,
  wsReservationPendingCheckIn,
  wsReservationUpdated,
} from "@/schemas/realtime";
import { formatCents } from "@/lib/money";

interface AttachOptions {
  /**
   * Current user's id. Owner-targeted events (`reservation.*`,
   * `payment.*`, `plate.updated`) are dropped when `user_id` differs —
   * the backend broadcasts to all `/ws` sockets today (plan §10.1).
   */
  userId: string | null;
}

/** Detach handle returned by `attachBus`. Idempotent. */
export type DetachBus = () => void;

/**
 * Wire all known events. Returns a detacher you should invoke on sign-out
 * (or whenever the user id changes). Internally guards against double-attach
 * by checking `socket.hasListeners` so HMR doesn't multiply handlers.
 */
export function attachBus(
  queryClient: QueryClient,
  { userId }: AttachOptions,
): DetachBus {
  const socket = getSocket();
  if (socket.hasListeners("bay.updated")) {
    // Already attached — return a no-op detacher so callers can still cleanup.
    return () => undefined;
  }

  let invalidateBaysHandle: ReturnType<typeof setTimeout> | null = null;
  /**
   * Coalesce bay.updated bursts (250 ms) to keep the grid jank-free.
   * We refetch rather than patch in place because the WS payload is a
   * strict subset of `BayOut` (see plan §4).
   */
  function scheduleBaysRefetch() {
    if (invalidateBaysHandle) return;
    invalidateBaysHandle = setTimeout(() => {
      invalidateBaysHandle = null;
      void queryClient.invalidateQueries({ queryKey: qk.bays.list() });
    }, 250);
  }

  // ---- Bay --------------------------------------------------------------
  socket.on("bay.updated", (raw: unknown) => {
    const parsed = wsBayUpdated.safeParse(raw);
    if (!parsed.success) {
      console.warn("ws.bay_updated.invalid", parsed.error.message);
      return;
    }
    scheduleBaysRefetch();
    void queryClient.invalidateQueries({
      queryKey: qk.bays.detail(parsed.data.code),
    });
  });

  // ---- Reservations ----------------------------------------------------
  socket.on("reservation.updated", (raw: unknown) => {
    const parsed = wsReservationUpdated.safeParse(raw);
    if (!parsed.success) return;
    if (userId && parsed.data.user_id !== userId) return;
    void queryClient.invalidateQueries({ queryKey: qk.reservations.list() });
    void queryClient.invalidateQueries({
      queryKey: qk.reservations.detail(parsed.data.id),
    });
  });

  socket.on("reservation.pending_check_in", (raw: unknown) => {
    const parsed = wsReservationPendingCheckIn.safeParse(raw);
    if (!parsed.success) return;
    if (userId && parsed.data.user_id !== userId) return;
    void queryClient.invalidateQueries({
      queryKey: qk.reservations.detail(parsed.data.id),
    });
    pushToast({
      tone: "warn",
      title: "Vehicle detected — please check in",
      description: `Bay ${parsed.data.bay_code} is waiting for you.`,
      ariaLive: "assertive",
    });
  });

  /**
   * THE documented `setQueryData` exception.
   *
   * The WS payload is built from `_reservation_payload + recognised_plate
   * + checked_in_at` (backend/app/sockets/events.py), which is a
   * superset of the cached `ReservationOut`. Asserting the shape here
   * means any future drift throws in dev rather than silently corrupting
   * the cache.
   */
  socket.on("reservation.auto_checked_in", (raw: unknown) => {
    const parsed = wsReservationAutoCheckedIn.safeParse(raw);
    if (!parsed.success) {
      console.warn("ws.auto_checked_in.shape_drift", parsed.error.message);
      return;
    }
    if (userId && parsed.data.user_id !== userId) return;
    queryClient.setQueryData(
      qk.reservations.detail(parsed.data.id),
      // Strip the WS-only `recognised_plate` before priming the cache so
      // the shape stays `ReservationOut`-clean.
      stripWsOnlyFields(parsed.data),
    );
    void queryClient.invalidateQueries({ queryKey: qk.reservations.list() });
    pushToast({
      tone: "success",
      title: `You're checked in at Bay ${parsed.data.bay_code}`,
      description: `LPR matched plate ${parsed.data.recognised_plate}.`,
    });
  });

  // ---- Plates ----------------------------------------------------------
  socket.on("plate.updated", (raw: unknown) => {
    const parsed = wsPlateUpdated.safeParse(raw);
    if (!parsed.success) return;
    if (userId && parsed.data.user_id !== userId) return;
    void queryClient.invalidateQueries({ queryKey: qk.plates.list() });
  });

  // ---- Conflicts (admin only) -----------------------------------------
  socket.on("conflict.raised", (raw: unknown) => {
    const parsed = wsConflict.safeParse(raw);
    if (!parsed.success) return;
    void queryClient.invalidateQueries({ queryKey: qk.conflicts.open() });
    pushToast({
      tone: "danger",
      title: `Conflict (${parsed.data.kind}) at Bay ${parsed.data.bay_code}`,
      description:
        parsed.data.recognised_plate !== null &&
        parsed.data.recognised_plate !== undefined
          ? `LPR saw plate ${parsed.data.recognised_plate}.`
          : undefined,
      ariaLive: "assertive",
    });
  });
  socket.on("conflict.resolved", (raw: unknown) => {
    const parsed = wsConflict.safeParse(raw);
    if (!parsed.success) return;
    void queryClient.invalidateQueries({ queryKey: qk.conflicts.open() });
  });

  // ---- Payments --------------------------------------------------------
  socket.on("payment.deposit_released", (raw: unknown) => {
    const parsed = wsPaymentDepositReleased.safeParse(raw);
    if (!parsed.success) return;
    if (userId && parsed.data.user_id !== userId) return;
    void queryClient.invalidateQueries({ queryKey: qk.payments.list() });
    pushToast({
      tone: "success",
      title: "Deposit released",
      description: `${formatCents(parsed.data.amount_cents)} returned to your card.`,
    });
  });
  socket.on("payment.refunded", (raw: unknown) => {
    const parsed = wsPaymentRefunded.safeParse(raw);
    if (!parsed.success) return;
    if (userId && parsed.data.user_id !== userId) return;
    void queryClient.invalidateQueries({ queryKey: qk.payments.list() });
    pushToast({
      tone: "success",
      title: "Refund issued",
      description: `${formatCents(parsed.data.amount_cents)} refunded after a facility conflict.`,
    });
  });
  socket.on("payment.penalty_captured", (raw: unknown) => {
    const parsed = wsPaymentPenaltyCaptured.safeParse(raw);
    if (!parsed.success) return;
    if (userId && parsed.data.user_id !== userId) return;
    void queryClient.invalidateQueries({ queryKey: qk.payments.list() });
    pushToast({
      tone: "warn",
      title: `${prettyPenalty(parsed.data.penalty_kind)} captured`,
      description: `${formatCents(parsed.data.amount_cents)} kept from your deposit.`,
    });
  });

  return () => {
    if (invalidateBaysHandle) clearTimeout(invalidateBaysHandle);
    socket.off("bay.updated");
    socket.off("reservation.updated");
    socket.off("reservation.pending_check_in");
    socket.off("reservation.auto_checked_in");
    socket.off("plate.updated");
    socket.off("conflict.raised");
    socket.off("conflict.resolved");
    socket.off("payment.deposit_released");
    socket.off("payment.refunded");
    socket.off("payment.penalty_captured");
  };
}

/** Drop the `recognised_plate` field before caching as `ReservationOut`. */
function stripWsOnlyFields<T extends { recognised_plate?: unknown }>(
  payload: T,
): Omit<T, "recognised_plate"> {
  const clone: Record<string, unknown> = { ...payload };
  delete clone["recognised_plate"];
  return clone as Omit<T, "recognised_plate">;
}

function prettyPenalty(kind: "late_cancel" | "no_show" | "weak_conflict"): string {
  switch (kind) {
    case "late_cancel":
      return "Late cancel";
    case "no_show":
      return "No-show";
    case "weak_conflict":
      return "Weak conflict";
  }
}

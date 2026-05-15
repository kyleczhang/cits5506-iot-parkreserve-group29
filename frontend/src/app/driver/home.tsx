/**
 * Driver home — landing page after sign-in.
 *
 * Two-column layout on `lg+`:
 *   - Left: live bay grid (compact tiles) — driven by `bay.updated` WS.
 *   - Right: "Your reservations" stack — driven by `reservation.*` WS.
 *
 * The booking wizard and reservation cockpit are stubs in this turn;
 * clicking "Book this bay" links to a coming-soon placeholder.
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { AlertOctagon, CalendarClock, Car, ParkingSquare } from "lucide-react";

import { listBays } from "@/api/bays";
import { listReservations } from "@/api/reservations";
import { listPlates } from "@/api/plates";
import { qk } from "@/api/queryKeys";
import { BayTile } from "@/components/bay/BayTile";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { formatRelative } from "@/lib/time";
import { ReservationStatusBadge } from "@/components/reservation/ReservationStatusBadge";

const HOME_RESERVATIONS_LIMIT = 5;

export function DriverHome() {
  const navigate = useNavigate();
  const bays = useQuery({ queryKey: qk.bays.list(), queryFn: listBays });
  const reservations = useQuery({
    queryKey: qk.reservations.list(),
    queryFn: listReservations,
  });
  const plates = useQuery({ queryKey: qk.plates.list(), queryFn: listPlates });
  const recentReservations = useMemo(
    () =>
      [...(reservations.data ?? [])]
        .sort(
          (a, b) =>
            new Date(b.booked_at).getTime() - new Date(a.booked_at).getTime(),
        )
        .slice(0, HOME_RESERVATIONS_LIMIT),
    [reservations.data],
  );
  // Strong conflict keeps the reservation `active` by design (a wrong
  // vehicle is at the bay but the driver may still arrive once it leaves
  // — see CLAUDE.md "Conflict semantics"). Cross-reference the live bay
  // state so the card surfaces the incident without lying about the
  // reservation lifecycle.
  const bayStateByCode = useMemo(() => {
    const m = new Map<string, string>();
    for (const b of bays.data ?? []) m.set(b.code, b.state);
    return m;
  }, [bays.data]);

  return (
    <div className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
      {/* Bays column */}
      <section aria-labelledby="bays-heading">
        <header className="mb-4 flex items-baseline justify-between">
          <h2
            id="bays-heading"
            className="text-xl font-semibold tracking-tight text-text"
          >
            Available bays
          </h2>
          <span className="text-sm text-text-muted">
            Live · updates over WebSocket
          </span>
        </header>

        {bays.isLoading ? (
          <div className="grid h-40 place-items-center">
            <Spinner label="Loading bays" />
          </div>
        ) : bays.isError ? (
          <p className="rounded-lg bg-danger/10 p-3 text-sm text-danger">
            Couldn&apos;t load bay status. Is the backend running?
          </p>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2">
            {bays.data?.map((bay) => (
              <li key={bay.code}>
                <BayTile
                  bay={bay}
                  onBook={(code) =>
                    navigate(`/app/reservations/new?bay=${encodeURIComponent(code)}`)
                  }
                />
              </li>
            ))}
          </ul>
        )}

        {!plates.isLoading && (plates.data?.length ?? 0) === 0 ? (
          <Card className="mt-6 border-warn/40 bg-warn/10 p-4">
            <p className="text-sm">
              <strong>Heads up.</strong> You haven&apos;t bound any licence
              plates yet — the backend requires at least one plate before you
              can reserve a bay (so the on-bay LPR knows it&apos;s you).{" "}
              <Link
                to="/app/plates"
                className="font-medium text-brand hover:underline"
              >
                Add a plate now
              </Link>
              .
            </p>
          </Card>
        ) : null}
      </section>

      {/* Reservations column */}
      <section aria-labelledby="res-heading">
        <header className="mb-4 flex items-baseline justify-between">
          <h2
            id="res-heading"
            className="text-xl font-semibold tracking-tight text-text"
          >
            Your reservations
          </h2>
          <span className="text-sm text-text-muted">
            Most recent {HOME_RESERVATIONS_LIMIT}
          </span>
        </header>

        {reservations.isLoading ? (
          <Card className="grid h-40 place-items-center">
            <Spinner label="Loading reservations" />
          </Card>
        ) : reservations.isError ? (
          <Card className="p-4 text-sm text-danger">
            Couldn&apos;t load reservations.
          </Card>
        ) : (reservations.data?.length ?? 0) === 0 ? (
          <Card className="flex flex-col items-center gap-3 p-6 text-center">
            <ParkingSquare
              aria-hidden="true"
              className="h-10 w-10 text-text-muted"
            />
            <p className="text-sm text-text-muted">
              You don&apos;t have any active reservations.
            </p>
            <Link to="/app/reservations/new">
              <Button>Book a bay</Button>
            </Link>
          </Card>
        ) : (
          <ul className="flex flex-col gap-3">
            {recentReservations.map((r) => {
              const isNonTerminal =
                r.status === "active" ||
                r.status === "pending_check_in" ||
                r.status === "checked_in" ||
                r.status === "in_conflict";
              const bayInConflict =
                isNonTerminal &&
                bayStateByCode.get(r.bay_code) === "conflict" &&
                r.status !== "in_conflict";
              return (
              <li key={r.id}>
                <Card
                  interactive
                  onClick={() => navigate(`/app/reservations/${r.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      navigate(`/app/reservations/${r.id}`);
                    }
                  }}
                  tabIndex={0}
                  role="link"
                  aria-label={`Open reservation for bay ${r.bay_code}`}
                  className="p-4"
                >
                  <header className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-lg font-semibold leading-none">
                        Bay {r.bay_code}
                      </p>
                      <p className="mt-1 text-xs text-text-muted">
                        Booked {formatRelative(r.booked_at)}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1.5">
                      <ReservationStatusBadge status={r.status} variant="compact" />
                      {bayInConflict ? (
                        <span
                          className="inline-flex items-center gap-1 rounded-full bg-state-conflict/15 px-2 py-0.5 text-[11px] font-medium text-state-conflict"
                          role="status"
                          aria-label="Bay is in conflict"
                        >
                          <AlertOctagon aria-hidden="true" className="h-3 w-3" />
                          Bay in conflict
                        </span>
                      ) : null}
                    </div>
                  </header>
                  {bayInConflict ? (
                    <p className="mt-2 text-xs text-state-conflict">
                      Another vehicle is at your bay. Your reservation is being
                      held while staff investigate.
                    </p>
                  ) : null}
                  <dl className="mt-3 grid grid-cols-2 gap-y-1 text-xs">
                    <dt className="flex items-center gap-1 text-text-muted">
                      <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />
                      Arrival
                    </dt>
                    <dd className="text-right font-mono text-text">
                      {formatRelative(r.expected_arrival_time)}
                    </dd>
                    {r.check_in_mechanism ? (
                      <>
                        <dt className="flex items-center gap-1 text-text-muted">
                          <Car className="h-3.5 w-3.5" aria-hidden="true" />
                          Check-in
                        </dt>
                        <dd className="text-right text-text">
                          {r.check_in_mechanism}
                        </dd>
                      </>
                    ) : null}
                  </dl>
                </Card>
              </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

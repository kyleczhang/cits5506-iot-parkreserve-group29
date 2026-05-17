/**
 * Booking wizard — `/app/reservations/new[?bay=BXX]`.
 *
 * Three steps live in a single mounted component so wizard state is
 * preserved across step changes (per plan §5.4 — no router-level
 * navigation between steps).
 *
 *   1. Pick a bay      → only AVAILABLE bays selectable
 *   2. Pick a time     → constrained `[now+1min, now+60min]`
 *   3. Mock card       → submit POST /api/v1/reservations
 *
 * Error mapping is the spec-verified table in plan §5.4.
 */
import { useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  CreditCard,
  ParkingSquare,
} from "lucide-react";
import { z } from "zod";

import { listBays } from "@/api/bays";
import { createReservation } from "@/api/reservations";
import { listPlates } from "@/api/plates";
import { qk } from "@/api/queryKeys";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/Spinner";
import { Stepper } from "@/components/ui/Stepper";
import { BayTile } from "@/components/bay/BayTile";
import { MockCardForm } from "@/components/payment/MockCardForm";
import { reservationCreateRequest } from "@/schemas/reservation";
import type { BayOut } from "@/schemas/bay";
import type { ReservationOut } from "@/schemas/reservation";
import { BOOKING_WINDOW_MINUTES_DEFAULT } from "@/lib/env";
import { formatCents } from "@/lib/money";
import { pushToast } from "@/components/ui/toastStore";

const STEPS = [
  { id: "bay", label: "Bay" },
  { id: "time", label: "Time" },
  { id: "card", label: "Payment" },
] as const;
const DEMO_ARRIVAL_OFFSETS_MINUTES = [1, 5, 30] as const;

/**
 * Local form schema — wraps the OpenAPI mirror with UI-friendly
 * required-field handling. The `expected_arrival_time` arrives from a
 * `datetime-local` field as a naive local string; we convert to ISO
 * before submission.
 */
const formSchema = reservationCreateRequest.extend({
  // Allow the empty string while the user is still on earlier steps;
  // `step 2 → step 3` transition enforces non-empty.
  expected_arrival_time: z.string().min(1, "pick an arrival time"),
});
type FormValues = z.infer<typeof formSchema>;

export function BookingWizard() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const presetBay = params.get("bay") ?? "";

  const [step, setStep] = useState(0);
  const [topError, setTopError] = useState<string | null>(null);

  const baysQuery = useQuery({
    queryKey: qk.bays.list(),
    queryFn: listBays,
  });
  const platesQuery = useQuery({
    queryKey: qk.plates.list(),
    queryFn: listPlates,
  });

  // datetime-local bounds — see plan §5.4 step 2.
  const { minLocal, maxLocal } = useMemo(() => {
    const now = new Date();
    const min = new Date(now.getTime() + 60 * 1000);
    const max = new Date(now.getTime() + BOOKING_WINDOW_MINUTES_DEFAULT * 60 * 1000);
    return { minLocal: toLocalInput(min), maxLocal: toLocalInput(max) };
  }, []);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      bay_code: presetBay,
      expected_arrival_time: "",
      card: {
        number: "",
        cvv: "",
        expiry_month: 1,
        expiry_year: 2030,
        holder_name: "",
      },
    },
  });

  const submitMutation = useMutation({
    mutationFn: (values: FormValues) =>
      createReservation({
        ...values,
        // The backend expects an ISO-8601 string; the `datetime-local`
        // input emits a naive local string we need to coerce.
        expected_arrival_time: new Date(values.expected_arrival_time).toISOString(),
      }),
    onSuccess: (res) => {
      syncReservedBayCache(queryClient, res);
      queryClient.setQueryData(qk.reservations.detail(res.id), res);
      void queryClient.invalidateQueries({ queryKey: qk.reservations.list() });
      pushToast({
        tone: "success",
        title: `Bay ${res.bay_code} reserved`,
        description: res.payment
          ? `${formatCents(res.payment.deposit_cents)} held on your mock card.`
          : undefined,
      });
      navigate(`/app/reservations/${res.id}`);
    },
    onError: (err) => {
      setTopError(translateBookingError(err));
      if (err instanceof ApiError && err.status === 409) {
        // Bay availability may have changed underneath us — refresh and
        // bounce to step 1 (plan §5.4).
        void queryClient.invalidateQueries({ queryKey: qk.bays.list() });
        if (err.code === "bay_offline" || err.code === "bay_not_available") {
          setStep(0);
        } else if (err.code === "reservation_already_active") {
          setStep(0);
        }
      }
    },
  });

  // If the user has no plates, the backend will 422 with `no_bound_plates` —
  // we block submission proactively rather than letting them get there.
  const hasPlates = (platesQuery.data?.length ?? 0) > 0;

  const fillDemoArrivalTime = (minutesFromNow: (typeof DEMO_ARRIVAL_OFFSETS_MINUTES)[number]) => {
    form.setValue(
      "expected_arrival_time",
      toLocalInput(new Date(Date.now() + minutesFromNow * 60 * 1000)),
      {
        shouldDirty: true,
        shouldTouch: true,
        shouldValidate: true,
      },
    );
  };

  const onContinueBay = () => {
    if (!form.getValues("bay_code")) {
      form.setError("bay_code", { message: "Pick a bay first." });
      return;
    }
    setStep(1);
  };

  const onContinueTime = () => {
    const t = form.getValues("expected_arrival_time");
    if (!t) {
      form.setError("expected_arrival_time", { message: "Pick an arrival time." });
      return;
    }
    const ms = new Date(t).getTime();
    const now = Date.now();
    if (ms <= now) {
      form.setError("expected_arrival_time", {
        message: "Arrival must be in the future.",
      });
      return;
    }
    if (ms - now > BOOKING_WINDOW_MINUTES_DEFAULT * 60 * 1000 + 5_000) {
      form.setError("expected_arrival_time", {
        message: `At most ${BOOKING_WINDOW_MINUTES_DEFAULT} minutes ahead.`,
      });
      return;
    }
    setStep(2);
  };

  const onSubmit = form.handleSubmit((values) => {
    setTopError(null);
    submitMutation.mutate(values);
  });

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-6 flex flex-col gap-2">
        <Link
          to="/app"
          className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to home
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Book a bay</h1>
        <Stepper steps={STEPS} current={step} className="mt-2" />
      </header>

      {!hasPlates && !platesQuery.isLoading ? (
        <Card className="mb-6 border-warn/40 bg-warn/10 p-4 text-sm">
          You need at least one bound plate before you can reserve. {" "}
          <Link to="/app/plates" className="font-medium text-brand hover:underline">
            Add a plate
          </Link>{" "}
          first.
        </Card>
      ) : null}

      <form onSubmit={onSubmit} noValidate>
        {/* STEP 1 — pick a bay */}
        <section hidden={step !== 0} aria-labelledby="step-bay">
          <h2 id="step-bay" className="sr-only">
            Pick a bay
          </h2>
          {baysQuery.isLoading ? (
            <div className="grid h-40 place-items-center">
              <Spinner label="Loading bays" />
            </div>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
              {baysQuery.data?.map((bay) => {
                const selectable = bay.state === "available";
                const selected = form.watch("bay_code") === bay.code;
                return (
                  <li key={bay.code}>
                    <button
                      type="button"
                      disabled={!selectable}
                      aria-pressed={selected}
                      onClick={() => {
                        form.setValue("bay_code", bay.code, {
                          shouldValidate: true,
                        });
                      }}
                      className={
                        "block w-full text-left transition-shadow duration-150 " +
                        (selected
                          ? "rounded-xl ring-2 ring-brand"
                          : selectable
                            ? "cursor-pointer rounded-xl hover:shadow-card-hover"
                            : "rounded-xl opacity-60")
                      }
                    >
                      <BayTile bay={bay} />
                      {!selectable ? (
                        <p className="mt-1 text-center text-xs text-text-muted">
                          Not bookable
                        </p>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {form.formState.errors.bay_code ? (
            <p role="alert" className="mt-3 text-sm text-danger">
              {form.formState.errors.bay_code.message}
            </p>
          ) : null}
          <div className="mt-6 flex justify-end">
            <Button
              type="button"
              onClick={onContinueBay}
              disabled={!hasPlates}
              trailingIcon={<ArrowRight className="h-4 w-4" />}
            >
              Continue
            </Button>
          </div>
        </section>

        {/* STEP 2 — pick a time */}
        <section hidden={step !== 1} aria-labelledby="step-time">
          <h2 id="step-time" className="sr-only">
            Pick a time
          </h2>
          <Card className="p-5">
            <Field
              label="Expected arrival time"
              type="datetime-local"
              required
              min={minLocal}
              max={maxLocal}
              helper={`Must be within ${BOOKING_WINDOW_MINUTES_DEFAULT} minutes from now. The server is authoritative — late edits may be rejected on submit.`}
              leadingIcon={<CalendarClock className="h-4 w-4" aria-hidden="true" />}
              error={form.formState.errors.expected_arrival_time?.message}
              {...form.register("expected_arrival_time")}
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-sm text-text-muted">Demo quick fill:</span>
              {DEMO_ARRIVAL_OFFSETS_MINUTES.map((minutes) => (
                <Button
                  key={minutes}
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => fillDemoArrivalTime(minutes)}
                >
                  {minutes} min
                </Button>
              ))}
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Reserving Bay{" "}
              <span className="font-mono text-text">
                {form.watch("bay_code")}
              </span>
              .
            </p>
          </Card>
          <div className="mt-6 flex justify-between">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setStep(0)}
              leadingIcon={<ArrowLeft className="h-4 w-4" />}
            >
              Back
            </Button>
            <Button
              type="button"
              onClick={onContinueTime}
              trailingIcon={<ArrowRight className="h-4 w-4" />}
            >
              Continue to payment
            </Button>
          </div>
        </section>

        {/* STEP 3 — mock card */}
        <section hidden={step !== 2} aria-labelledby="step-card">
          <h2 id="step-card" className="sr-only">
            Mock-payment details
          </h2>
          <Card className="space-y-4 p-5">
            <MockCardForm
              register={form.register}
              setValue={form.setValue}
              errors={form.formState.errors}
            />
            <Summary
              bay={form.watch("bay_code")}
              arrival={form.watch("expected_arrival_time")}
            />
            {topError ? (
              <p
                role="alert"
                className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
              >
                {topError}
              </p>
            ) : null}
          </Card>
          <div className="mt-6 flex justify-between">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setStep(1)}
              leadingIcon={<ArrowLeft className="h-4 w-4" />}
            >
              Back
            </Button>
            <Button
              type="submit"
              loading={submitMutation.isPending}
              leadingIcon={<CreditCard className="h-4 w-4" />}
            >
              Confirm reservation
            </Button>
          </div>
          <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-text-muted">
            <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />A 10 AUD
            deposit is held on submission (mock card only).
          </p>
        </section>
      </form>
    </div>
  );
}

function Summary({ bay, arrival }: { bay: string; arrival: string }) {
  return (
    <dl className="grid grid-cols-2 gap-y-1.5 rounded-lg bg-surface-2 p-3 text-sm">
      <dt className="flex items-center gap-1.5 text-text-muted">
        <ParkingSquare aria-hidden="true" className="h-4 w-4" /> Bay
      </dt>
      <dd className="text-right font-mono text-text">{bay || "—"}</dd>
      <dt className="flex items-center gap-1.5 text-text-muted">
        <CalendarClock aria-hidden="true" className="h-4 w-4" /> Arrival
      </dt>
      <dd className="text-right text-text">
        {arrival ? new Date(arrival).toLocaleString() : "—"}
      </dd>
    </dl>
  );
}

function syncReservedBayCache(queryClient: QueryClient, reservation: ReservationOut): void {
  const applyReservation = (bay: BayOut): BayOut =>
    bay.code === reservation.bay_code
      ? {
          ...bay,
          state: "reserved",
          current_reservation_id: reservation.id,
          current_reservation_arrival: reservation.expected_arrival_time,
        }
      : bay;

  queryClient.setQueryData<BayOut[] | undefined>(qk.bays.list(), (current) =>
    current?.map(applyReservation),
  );
  queryClient.setQueryData<BayOut | undefined>(
    qk.bays.detail(reservation.bay_code),
    (current) => (current ? applyReservation(current) : current),
  );
}

/**
 * Spec-verified error code → user-facing message map (plan §5.4).
 * `ApiError.code` values come from
 * backend/app/services/{reservation,payment}_service.py.
 */
function translateBookingError(err: unknown): string {
  if (!(err instanceof ApiError)) return "Something went wrong. Please try again.";
  switch (err.code) {
    case "invalid_arrival_time":
      return "Arrival time must be in the future.";
    case "outside_booking_window":
      return `Reservation must be within the booking window.`;
    case "no_bound_plates":
      return "Please bind at least one licence plate before booking.";
    case "card_invalid":
      return "We couldn't validate that card number.";
    case "card_expired":
      return "That card has expired.";
    case "insufficient_funds":
      return "Insufficient funds on the mock card.";
    case "bay_offline":
      return "That bay is currently offline. Pick another one.";
    case "bay_not_available":
      return "That bay is no longer available — refreshing the grid.";
    case "reservation_already_active":
      return "Another driver just booked this bay. Try a different one.";
    default:
      return err.message || "Booking failed.";
  }
}

/** Convert a `Date` to the `YYYY-MM-DDTHH:MM` shape `datetime-local` wants. */
function toLocalInput(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

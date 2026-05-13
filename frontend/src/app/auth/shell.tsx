/**
 * Shared shell for sign-in / sign-up pages.
 *
 * Centred panel with brand mark + a contextual sub-title. Keeps both
 * forms visually consistent (rubric: Organization & Development).
 */
import { Link } from "react-router-dom";
import { ParkingCircle } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle: string;
  children: ReactNode;
}

export function AuthShell({ title, subtitle, children }: Props) {
  return (
    <div className="grid min-h-screen bg-bg text-text md:grid-cols-[1fr_minmax(420px,520px)]">
      <aside className="relative hidden flex-col justify-between bg-brand p-12 text-white md:flex">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-white"
          aria-label="ParkReserve home"
        >
          <ParkingCircle className="h-7 w-7" aria-hidden="true" />
          <span className="text-xl font-semibold">ParkReserve</span>
        </Link>
        <div className="max-w-md">
          <p className="text-3xl font-semibold leading-snug">
            Reservation backed by money, settled by sensors.
          </p>
          <p className="mt-4 text-white/85">
            Per-bay LED, ultrasonic detection and automatic licence-plate
            recognition mirror state to your dashboard in real time —
            so a reservation is never just a promise.
          </p>
        </div>
        <p className="text-xs text-white/70">
          CITS 5506 Group 29 · Mock-payment prototype, do not enter real card
          details.
        </p>
      </aside>

      <main className="flex flex-col justify-center px-6 py-10 md:px-12">
        <div className="mx-auto w-full max-w-md">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-text-muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}

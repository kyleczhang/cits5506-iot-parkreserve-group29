/**
 * `/help` — in-app how-to-use guide.
 *
 * Mirrors the README's rubric-required *How-to-guide* sections, written
 * for an in-product audience. The README remains the canonical version
 * for someone reading on GitHub; this page is what the live demo
 * graders see when they click "Help".
 */
import { Link } from "react-router-dom";
import {
  ParkingCircle,
  Cpu,
  Wrench,
  PlaySquare,
  ShieldAlert,
  KeyRound,
  ScrollText,
  ArrowLeft,
} from "lucide-react";

export function HelpPage() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-text"
            aria-label="ParkReserve home"
          >
            <ParkingCircle className="h-6 w-6 text-brand" aria-hidden="true" />
            <span className="text-lg font-semibold">ParkReserve</span>
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to landing
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-8 px-6 py-10">
        <section>
          <h1 className="text-3xl font-semibold tracking-tight">How to use</h1>
          <p className="mt-2 text-text-muted">
            ParkReserve is a CITS 5506 prototype for a paid-facility parking
            operator. This page walks a grader (or a curious facility manager)
            through every flow the prototype supports end-to-end.
          </p>
        </section>

        <Section
          icon={Cpu}
          title="1. Hardware setup"
        >
          <p>
            Three ESP32-CAM bay nodes and one Raspberry Pi 5 gateway, wired as
            described in the project proposal (§5). The frontend has no
            hardware dependency; it talks to the backend, which mirrors the
            authoritative state owned by the Pi.
          </p>
          <p>
            For a software-only demo, the backend ships a mock Pi publisher:
          </p>
          <pre className="overflow-x-auto rounded-lg bg-surface-2 p-3 font-mono text-xs">
            cd ../backend{"\n"}.venv/bin/python scripts/mock_pi_publisher.py
          </pre>
        </Section>

        <Section icon={Wrench} title="2. Software installation">
          <p>Prerequisites:</p>
          <ul className="list-inside list-disc text-sm">
            <li>Node.js ≥ 20.10</li>
            <li>pnpm 9.x (via Node's `corepack` shim)</li>
            <li>Backend running on `:8000`</li>
          </ul>
          <pre className="overflow-x-auto rounded-lg bg-surface-2 p-3 font-mono text-xs">
            cd frontend{"\n"}
            corepack enable{"\n"}
            pnpm install{"\n"}
            cp .env.example .env{"\n"}
            pnpm dev
          </pre>
        </Section>

        <Section icon={PlaySquare} title="3. Driver flow (live demo)">
          <ol className="list-inside list-decimal space-y-1 text-sm">
            <li>
              <Link to="/register" className="text-brand hover:underline">
                Create a driver account
              </Link>{" "}
              (or sign in as the seeded driver).
            </li>
            <li>
              Bind a licence plate at{" "}
              <Link to="/app/plates" className="text-brand hover:underline">
                /app/plates
              </Link>
              . The backend rejects reservation creation without at least one
              bound plate.
            </li>
            <li>
              Pick an available bay on the home screen and click <em>Book this
              bay</em>. The wizard collects bay → time → mock card.
            </li>
            <li>
              Trigger the mock Pi publisher (Step 1) to push a vehicle-detected
              event, then click <em>Check in (manual)</em> in the cockpit.
            </li>
            <li>
              Cancel a reservation to see the deposit release on the payments
              ledger.
            </li>
          </ol>
        </Section>

        <Section icon={KeyRound} title="4. Admin flow">
          <ol className="list-inside list-decimal space-y-1 text-sm">
            <li>Sign in as the seeded admin user.</li>
            <li>
              The grid at <Link to="/admin/grid" className="text-brand hover:underline">
                /admin/grid
              </Link>{" "}
              shows every bay with live state, distance, and a 30-minute
              sparkline.
            </li>
            <li>
              When a conflict fires, the row appears in{" "}
              <Link to="/admin/conflicts" className="text-brand hover:underline">
                /admin/conflicts
              </Link>{" "}
              and the navigation badge increments. Open the row to view the
              evidence JPEG (strong-conflict only) and resolve.
            </li>
          </ol>
        </Section>

        <Section icon={ScrollText} title="5. State + payment cheat sheet">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-text-muted">Reserved</dt>
            <dd>Bay held for a driver, awaiting arrival.</dd>
            <dt className="text-text-muted">Pending check-in</dt>
            <dd>Vehicle detected; LPR didn't auto-match.</dd>
            <dt className="text-text-muted">Reserved + checked in</dt>
            <dd>Driver verified (auto-LPR or manual).</dd>
            <dt className="text-text-muted">Conflict (weak)</dt>
            <dd>Grace window expired with no check-in → penalty captured.</dd>
            <dt className="text-text-muted">Conflict (strong)</dt>
            <dd>LPR saw a plate not bound to the holder → full refund.</dd>
          </dl>
        </Section>

        <Section icon={ShieldAlert} title="6. Mock-payment notice">
          <p>
            The card form never reaches a real bank. Card numbers are validated
            against the seeded <code className="font-mono">mock_cards</code>{" "}
            table. The banner that appears on the booking wizard's payment step
            is permanent and cannot be dismissed.
          </p>
        </Section>
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto max-w-3xl px-6 py-6 text-xs text-text-muted">
          ParkReserve · CITS 5506 Group 29 · Mock-payment prototype.
        </div>
      </footer>
    </div>
  );
}

interface SectionProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}

function Section({ icon: Icon, title, children }: SectionProps) {
  return (
    <section className="space-y-3">
      <h2 className="inline-flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Icon className="h-5 w-5 text-brand" aria-hidden="true" />
        {title}
      </h2>
      <div className="space-y-3 text-sm text-text">{children}</div>
    </section>
  );
}

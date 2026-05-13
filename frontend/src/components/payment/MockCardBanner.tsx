/**
 * Sticky banner reminding the user that the card form is a mock and that
 * **no real bank network is contacted**. Wording is asserted by a unit
 * test (plan §6.3) so it can't regress.
 */
import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/cn";

export const MOCK_PAYMENT_BANNER_TEXT =
  "MOCK PAYMENT — DO NOT ENTER REAL CARD DETAILS";

interface Props {
  className?: string;
}

export function MockCardBanner({ className }: Props) {
  return (
    <div
      role="alert"
      data-testid="mock-card-banner"
      className={cn(
        "sticky top-0 z-10 flex items-start gap-3 rounded-lg border border-warn/50",
        "bg-warn/15 p-3 text-sm font-medium text-text",
        className,
      )}
    >
      <ShieldAlert
        aria-hidden="true"
        className="mt-0.5 h-4 w-4 shrink-0 text-warn"
      />
      <p className="leading-tight">
        <span className="font-semibold tracking-wide">
          {MOCK_PAYMENT_BANNER_TEXT}
        </span>
        <span className="mt-1 block font-normal text-text-muted">
          This prototype settles payments against an in-process mock-bank
          database. Any data you type here stays on the server you control.
        </span>
      </p>
    </div>
  );
}

/**
 * Mock card details form.
 *
 * Pure presentational — accepts an RHF `register` + `errors` from the
 * parent, since the parent owns the wider booking form (bay + time + card).
 * The seed migration's well-known card numbers are listed beneath the
 * inputs so a grader running the demo can pick one without leaving the
 * page. Mirror of [backend/scripts/seed.py](../../backend/scripts/seed.py).
 */
import type { FieldErrors, UseFormRegister, UseFormSetValue } from "react-hook-form";
import { CreditCard, User as UserIcon, Calendar, Hash } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { MockCardBanner } from "./MockCardBanner";

interface FormShape {
  card: {
    number: string;
    cvv: string;
    expiry_month: number;
    expiry_year: number;
    holder_name: string;
  };
}

interface Props<T extends FormShape> {
  register: UseFormRegister<T>;
  setValue: UseFormSetValue<T>;
  errors: FieldErrors<T>;
}

/**
 * Demo card numbers — verified against the migration that seeds
 * `mock_cards` (see `20260421_03_seed_mock_cards`). Listed here purely
 * to make the live demo painless.
 */
const DEMO_CARDS: ReadonlyArray<{
  label: string;
  number: string;
  cvv: string;
  holder_name: string;
  expiry_month: number;
  expiry_year: number;
  hint: string;
}> = [
  {
    label: "Valid",
    number: "4111111111111001",
    cvv: "123",
    holder_name: "Nyx Chen",
    expiry_month: 12,
    expiry_year: 2030,
    hint: "Successful booking",
  },
  {
    label: "Low funds",
    number: "4111111111111002",
    cvv: "234",
    holder_name: "Nyx Chen",
    expiry_month: 12,
    expiry_year: 2030,
    hint: "Insufficient funds",
  },
  {
    label: "Expired",
    number: "4333333333333002",
    cvv: "222",
    holder_name: "Yuan Cong",
    expiry_month: 1,
    expiry_year: 2024,
    hint: "Expired card",
  },
];

export function MockCardForm<T extends FormShape>({ register, setValue, errors }: Props<T>) {
  // The `as any` is unavoidable here: RHF's typed register signature
  // requires a literal path; with a generic constraint we surface the
  // path string the parent's schema produced.
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const r = register as any;
  const e = errors as any;
  const set = setValue as any;
  /* eslint-enable @typescript-eslint/no-explicit-any */

  const fillDemoCard = (card: (typeof DEMO_CARDS)[number]) => {
    const options = {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: true,
    };
    set("card.number", card.number, options);
    set("card.holder_name", card.holder_name, options);
    set("card.expiry_month", card.expiry_month, options);
    set("card.expiry_year", card.expiry_year, options);
    set("card.cvv", card.cvv, options);
  };

  return (
    <div className="flex flex-col gap-4">
      <MockCardBanner />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-text-muted">Demo quick fill:</span>
        {DEMO_CARDS.map((card) => (
          <Button
            key={card.number}
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => fillDemoCard(card)}
          >
            {card.label}
          </Button>
        ))}
      </div>

      <Field
        label="Card number"
        placeholder="4111 1111 1111 1111"
        autoComplete="off"
        inputMode="numeric"
        leadingIcon={<CreditCard className="h-4 w-4" aria-hidden="true" />}
        error={e?.card?.number?.message}
        required
        {...r("card.number")}
      />
      <Field
        label="Cardholder name"
        autoComplete="off"
        leadingIcon={<UserIcon className="h-4 w-4" aria-hidden="true" />}
        error={e?.card?.holder_name?.message}
        required
        {...r("card.holder_name")}
      />
      <div className="grid grid-cols-3 gap-3">
        <Field
          label="Month"
          type="number"
          inputMode="numeric"
          min={1}
          max={12}
          placeholder="MM"
          leadingIcon={<Calendar className="h-4 w-4" aria-hidden="true" />}
          error={e?.card?.expiry_month?.message}
          required
          {...r("card.expiry_month", { valueAsNumber: true })}
        />
        <Field
          label="Year"
          type="number"
          inputMode="numeric"
          min={2024}
          max={2099}
          placeholder="YYYY"
          error={e?.card?.expiry_year?.message}
          required
          {...r("card.expiry_year", { valueAsNumber: true })}
        />
        <Field
          label="CVV"
          type="password"
          autoComplete="off"
          inputMode="numeric"
          maxLength={4}
          placeholder="123"
          leadingIcon={<Hash className="h-4 w-4" aria-hidden="true" />}
          error={e?.card?.cvv?.message}
          required
          {...r("card.cvv")}
        />
      </div>

      <details className="rounded-lg border border-border bg-surface-2 p-3 text-sm">
        <summary className="cursor-pointer font-medium text-text">
          Demo card numbers (CITS 5506 graders)
        </summary>
        <ul className="mt-2 grid gap-1.5 font-mono text-xs">
          {DEMO_CARDS.map((c) => (
            <li key={c.number} className="flex justify-between gap-3">
              <span>
                {c.number}{" "}
                <span className="text-text-muted">
                  {c.holder_name} | {String(c.expiry_month).padStart(2, "0")}/
                  {c.expiry_year} | CVV {c.cvv}
                </span>
              </span>
              <span className="text-text-muted">{c.hint}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-text-muted">
          Use the quick-fill buttons above if you want the exact seeded values.
        </p>
      </details>
    </div>
  );
}

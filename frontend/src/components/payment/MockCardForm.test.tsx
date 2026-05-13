import { act, render, screen } from "@testing-library/react";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";

import { MockCardForm } from "./MockCardForm";

interface TestFormValues {
  card: {
    number: string;
    cvv: string;
    expiry_month: number;
    expiry_year: number;
    holder_name: string;
  };
}

function TestHarness() {
  const form = useForm<TestFormValues>({
    defaultValues: {
      card: {
        number: "",
        cvv: "",
        expiry_month: 1,
        expiry_year: 2030,
        holder_name: "",
      },
    },
  });

  return (
    <MockCardForm
      register={form.register}
      setValue={form.setValue}
      errors={form.formState.errors}
    />
  );
}

describe("MockCardForm", () => {
  it("quick-fills all card fields from the seeded demo cards", async () => {
    render(<TestHarness />);

    await act(async () => {
      screen.getByRole("button", { name: /^valid$/i }).click();
    });
    expect(screen.getByLabelText(/card number/i)).toHaveValue("4111111111111001");
    expect(screen.getByLabelText(/cardholder name/i)).toHaveValue("Nyx Chen");
    expect(screen.getByLabelText(/month/i)).toHaveValue(12);
    expect(screen.getByLabelText(/year/i)).toHaveValue(2030);
    expect(screen.getByLabelText(/cvv/i)).toHaveValue("123");

    await act(async () => {
      screen.getByRole("button", { name: /^low funds$/i }).click();
    });
    expect(screen.getByLabelText(/card number/i)).toHaveValue("4111111111111002");
    expect(screen.getByLabelText(/cardholder name/i)).toHaveValue("Nyx Chen");
    expect(screen.getByLabelText(/month/i)).toHaveValue(12);
    expect(screen.getByLabelText(/year/i)).toHaveValue(2030);
    expect(screen.getByLabelText(/cvv/i)).toHaveValue("234");

    await act(async () => {
      screen.getByRole("button", { name: /^expired$/i }).click();
    });
    expect(screen.getByLabelText(/card number/i)).toHaveValue("4333333333333002");
    expect(screen.getByLabelText(/cardholder name/i)).toHaveValue("Yuan Cong");
    expect(screen.getByLabelText(/month/i)).toHaveValue(1);
    expect(screen.getByLabelText(/year/i)).toHaveValue(2024);
    expect(screen.getByLabelText(/cvv/i)).toHaveValue("222");
  });
});

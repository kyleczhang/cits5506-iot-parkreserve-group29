import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Field } from "./Field";

describe("Field", () => {
  it("links label to input via htmlFor / id", () => {
    render(<Field label="Email" type="email" />);
    const input = screen.getByLabelText(/email/i);
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe("INPUT");
  });

  it("renders error with aria-invalid and role=alert", () => {
    render(<Field label="Email" error="invalid email" />);
    expect(screen.getByLabelText(/email/i)).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/invalid email/i);
  });

  it("propagates change events", () => {
    const onChange = vi.fn();
    render(<Field label="Name" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: "Ada" },
    });
    expect(onChange).toHaveBeenCalled();
  });
});

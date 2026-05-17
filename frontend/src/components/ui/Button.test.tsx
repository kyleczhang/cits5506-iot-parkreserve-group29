import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders children and fires onClick", () => {
    const handle = vi.fn();
    render(<Button onClick={handle}>Click me</Button>);
    fireEvent.click(screen.getByRole("button", { name: /click me/i }));
    expect(handle).toHaveBeenCalledTimes(1);
  });

  it("is disabled while loading and announces aria-busy", () => {
    const handle = vi.fn();
    render(
      <Button loading onClick={handle}>
        Saving
      </Button>,
    );
    const btn = screen.getByRole("button", { name: /saving/i });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
    fireEvent.click(btn);
    expect(handle).not.toHaveBeenCalled();
  });

  it("respects the explicit type attribute", () => {
    render(<Button type="submit">Go</Button>);
    expect(screen.getByRole("button", { name: /go/i })).toHaveAttribute(
      "type",
      "submit",
    );
  });
});

/**
 * CountdownPill behavioural tests.
 *
 * Uses Vitest's fake timers to advance the 1 s interval and assert:
 *   (a) `onExpire` fires exactly once when the timer crosses zero,
 *   (b) the rendered `mm:ss` reflects the remaining seconds.
 */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CountdownPill } from "./CountdownPill";

describe("CountdownPill", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-12T00:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the initial mm:ss for a future target", () => {
    const target = new Date("2026-05-12T00:01:30Z").toISOString();
    render(<CountdownPill target={target} label="left" />);
    // 1m30s should appear at mount.
    expect(screen.getByText(/01:30/)).toBeInTheDocument();
  });

  it("fires onExpire exactly once when crossing zero", () => {
    const onExpire = vi.fn();
    const target = new Date("2026-05-12T00:00:02Z").toISOString();
    render(<CountdownPill target={target} onExpire={onExpire} />);
    expect(onExpire).not.toHaveBeenCalled();
    // advance past the target
    act(() => {
      vi.advanceTimersByTime(3_000);
    });
    expect(onExpire).toHaveBeenCalledTimes(1);
    // continue ticking — should not fire again
    act(() => {
      vi.advanceTimersByTime(5_000);
    });
    expect(onExpire).toHaveBeenCalledTimes(1);
  });
});

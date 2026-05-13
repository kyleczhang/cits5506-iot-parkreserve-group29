import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReservationCockpit } from "./cockpit";
import {
  cancelReservation,
  getReservation,
} from "@/api/reservations";
import { qk } from "@/api/queryKeys";

vi.mock("@/api/reservations", () => ({
  cancelReservation: vi.fn(),
  checkInReservation: vi.fn(),
  getReservation: vi.fn(),
}));

const mockedGetReservation = vi.mocked(getReservation);
const mockedCancelReservation = vi.mocked(cancelReservation);

function renderCockpit() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  queryClient.setQueryData(qk.bays.list(), [
    {
      code: "A1",
      label: "Bay A1",
      state: "reserved",
      last_distance_cm: null,
      sensor_last_seen_at: null,
      current_reservation_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      current_reservation_arrival: "2026-05-12T10:30:00Z",
      check_in_grace_expires_at: null,
    },
  ]);
  queryClient.setQueryData(qk.bays.detail("A1"), {
    code: "A1",
    label: "Bay A1",
    state: "reserved",
    last_distance_cm: null,
    sensor_last_seen_at: null,
    current_reservation_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    current_reservation_arrival: "2026-05-12T10:30:00Z",
    check_in_grace_expires_at: null,
  });

  const renderResult = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/app/reservations/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"]}>
        <Routes>
          <Route
            path="/app/reservations/:id"
            element={<ReservationCockpit />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  return { ...renderResult, queryClient };
}

describe("ReservationCockpit", () => {
  beforeEach(() => {
    mockedGetReservation.mockResolvedValue({
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      bay_code: "A1",
      user_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      status: "active",
      expected_arrival_time: "2026-05-12T10:30:00Z",
      booked_at: "2026-05-12T10:00:00Z",
      check_in_grace_expires_at: null,
      checked_in_at: null,
      check_in_mechanism: null,
      cancelled_at: null,
      completed_at: null,
      payment: { deposit_cents: 1000 },
    });
    mockedCancelReservation.mockResolvedValue({
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      bay_code: "A1",
      user_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      status: "cancelled",
      expected_arrival_time: "2026-05-12T10:30:00Z",
      booked_at: "2026-05-12T10:00:00Z",
      check_in_grace_expires_at: null,
      checked_in_at: null,
      check_in_mechanism: null,
      cancelled_at: "2026-05-12T10:05:00Z",
      completed_at: null,
      payment: { deposit_cents: 1000 },
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("clears the cached bay reservation state after cancellation", async () => {
    const { queryClient } = renderCockpit();

    fireEvent.click(await screen.findByRole("button", { name: /cancel reservation/i }));

    await waitFor(() => expect(mockedCancelReservation).toHaveBeenCalledTimes(1));

    expect(queryClient.getQueryData(qk.bays.list())).toEqual([
      {
        code: "A1",
        label: "Bay A1",
        state: "available",
        last_distance_cm: null,
        sensor_last_seen_at: null,
        current_reservation_id: null,
        current_reservation_arrival: null,
        check_in_grace_expires_at: null,
      },
    ]);
    expect(queryClient.getQueryData(qk.bays.detail("A1"))).toEqual({
      code: "A1",
      label: "Bay A1",
      state: "available",
      last_distance_cm: null,
      sensor_last_seen_at: null,
      current_reservation_id: null,
      current_reservation_arrival: null,
      check_in_grace_expires_at: null,
    });
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BookingWizard } from "./booking";
import { listBays } from "@/api/bays";
import { createReservation } from "@/api/reservations";
import { listPlates } from "@/api/plates";
import { qk } from "@/api/queryKeys";

vi.mock("@/api/bays", () => ({
  listBays: vi.fn(),
}));

vi.mock("@/api/plates", () => ({
  listPlates: vi.fn(),
}));

vi.mock("@/api/reservations", () => ({
  createReservation: vi.fn(),
}));

const mockedListBays = vi.mocked(listBays);
const mockedListPlates = vi.mocked(listPlates);
const mockedCreateReservation = vi.mocked(createReservation);

function renderBooking(initialEntry = "/app/reservations/new?bay=A2") {
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

  const renderResult = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/app/reservations/new" element={<BookingWizard />} />
          <Route path="/app/reservations/:id" element={<div>Reservation detail</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  return { ...renderResult, queryClient };
}

describe("BookingWizard", () => {
  beforeEach(() => {
    mockedListBays.mockResolvedValue([
      {
        code: "A2",
        label: "Bay A2",
        state: "available",
        last_distance_cm: null,
        sensor_last_seen_at: null,
        current_reservation_id: null,
        current_reservation_arrival: null,
        check_in_grace_expires_at: null,
      },
    ]);
    mockedListPlates.mockResolvedValue([
      {
        id: "55555555-5555-4555-8555-555555555555",
        plate: "DEMO123",
        label: "Demo",
        created_at: "2026-05-12T10:00:00Z",
      },
    ]);
    mockedCreateReservation.mockResolvedValue({
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      bay_code: "A2",
      user_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      status: "active",
      expected_arrival_time: "2026-05-12T10:05:00Z",
      booked_at: "2026-05-12T10:00:00Z",
      payment: {
        deposit_cents: 1000,
      },
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("quick-fills the arrival time for demo shortcuts", async () => {
    renderBooking();

    const continueButton = await screen.findByRole("button", {
      name: /^continue$/i,
    });
    await waitFor(() => expect(continueButton).toBeEnabled());
    fireEvent.click(continueButton);

    const input = await screen.findByLabelText(/expected arrival time/i);
    expect(input).toHaveValue("");

    const parseArrivalMs = () => new Date((input as HTMLInputElement).value).getTime();

    fireEvent.click(screen.getByRole("button", { name: /^1 min$/i }));
    expect(parseArrivalMs() - Date.now()).toBeGreaterThan(0);
    expect(parseArrivalMs() - Date.now()).toBeLessThanOrEqual(60_000);

    fireEvent.click(screen.getByRole("button", { name: /^5 min$/i }));
    expect(parseArrivalMs() - Date.now()).toBeGreaterThan(240_000);
    expect(parseArrivalMs() - Date.now()).toBeLessThanOrEqual(300_000);

    fireEvent.click(screen.getByRole("button", { name: /^30 min$/i }));
    expect(parseArrivalMs() - Date.now()).toBeGreaterThan(1_740_000);
    expect(parseArrivalMs() - Date.now()).toBeLessThanOrEqual(1_800_000);
  });

  it("marks the booked bay reserved in the cached bay list after booking", async () => {
    const { queryClient } = renderBooking();

    const continueButton = await screen.findByRole("button", {
      name: /^continue$/i,
    });
    await waitFor(() => expect(continueButton).toBeEnabled());
    fireEvent.click(continueButton);

    fireEvent.click(await screen.findByRole("button", { name: /^5 min$/i }));
    fireEvent.click(screen.getByRole("button", { name: /continue to payment/i }));

    fireEvent.click(await screen.findByRole("button", { name: /^valid$/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirm reservation/i }));

    await waitFor(() => expect(mockedCreateReservation).toHaveBeenCalledTimes(1));

    const bays = queryClient.getQueryData<Array<{
      code: string;
      state: string;
      current_reservation_id: string | null;
      current_reservation_arrival: string | null;
    }>>(qk.bays.list());
    expect(bays).toBeDefined();
    expect(bays?.[0]).toMatchObject({
      code: "A2",
      state: "reserved",
      current_reservation_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      current_reservation_arrival: "2026-05-12T10:05:00Z",
    });
  });
});

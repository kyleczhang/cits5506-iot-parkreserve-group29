import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DriverHome } from "./home";
import { listBays } from "@/api/bays";
import { listReservations } from "@/api/reservations";
import { listPlates } from "@/api/plates";

vi.mock("@/api/bays", () => ({
  listBays: vi.fn(),
}));

vi.mock("@/api/reservations", () => ({
  listReservations: vi.fn(),
}));

vi.mock("@/api/plates", () => ({
  listPlates: vi.fn(),
}));

const mockedListBays = vi.mocked(listBays);
const mockedListReservations = vi.mocked(listReservations);
const mockedListPlates = vi.mocked(listPlates);

function renderHome() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DriverHome />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DriverHome", () => {
  it("shows only the 5 most recent reservations", async () => {
    mockedListBays.mockResolvedValue([]);
    mockedListPlates.mockResolvedValue([
      {
        id: "55555555-5555-4555-8555-555555555555",
        plate: "DEMO123",
        label: "Demo",
        created_at: "2026-05-12T10:00:00Z",
      },
    ]);
    mockedListReservations.mockResolvedValue([
      {
        id: "11111111-1111-4111-8111-111111111111",
        bay_code: "A1",
        user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        status: "active",
        expected_arrival_time: "2026-05-12T10:05:00Z",
        booked_at: "2026-05-12T10:01:00Z",
      },
      {
        id: "22222222-2222-4222-8222-222222222222",
        bay_code: "A2",
        user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        status: "active",
        expected_arrival_time: "2026-05-12T10:06:00Z",
        booked_at: "2026-05-12T10:06:00Z",
      },
      {
        id: "33333333-3333-4333-8333-333333333333",
        bay_code: "A3",
        user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        status: "active",
        expected_arrival_time: "2026-05-12T10:04:00Z",
        booked_at: "2026-05-12T10:04:00Z",
      },
      {
        id: "44444444-4444-4444-8444-444444444444",
        bay_code: "A4",
        user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        status: "active",
        expected_arrival_time: "2026-05-12T10:03:00Z",
        booked_at: "2026-05-12T10:03:00Z",
      },
      {
        id: "55555555-5555-4555-8555-555555555555",
        bay_code: "A5",
        user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        status: "active",
        expected_arrival_time: "2026-05-12T10:02:00Z",
        booked_at: "2026-05-12T10:02:00Z",
      },
      {
        id: "66666666-6666-4666-8666-666666666666",
        bay_code: "A6",
        user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        status: "active",
        expected_arrival_time: "2026-05-12T10:00:00Z",
        booked_at: "2026-05-12T10:00:00Z",
      },
    ]);

    renderHome();

    await waitFor(() => {
      expect(
        screen.getAllByRole("link", { name: /open reservation for bay/i }),
      ).toHaveLength(5);
    });

    const items = screen.getAllByRole("link", {
      name: /open reservation for bay/i,
    });
    expect(items.map((item) => item.getAttribute("aria-label"))).toEqual([
      "Open reservation for bay A2",
      "Open reservation for bay A3",
      "Open reservation for bay A4",
      "Open reservation for bay A5",
      "Open reservation for bay A1",
    ]);
    expect(
      screen.queryByRole("link", { name: /open reservation for bay A6/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/most recent 5/i)).toBeInTheDocument();
  });
});

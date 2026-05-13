/**
 * Route tree.
 *
 * Auth/role gating lives inside the route `element` via `<RequireRole>`
 * (auth state lives in React context — easier to consult than a router
 * loader). Unauthenticated routes: landing, login, register, help.
 * Driver routes: `/app/*`. Admin routes: `/admin/*`.
 */
import { createBrowserRouter } from "react-router-dom";

import { RequireRole } from "@/auth/RequireRole";
import { Landing } from "./landing";
import { LoginPage } from "./auth/login";
import { RegisterPage } from "./auth/register";
import { DriverLayout } from "./driver/layout";
import { DriverHome } from "./driver/home";
import { PlatesPage } from "./driver/plates";
import { BookingWizard } from "./driver/booking";
import { ReservationCockpit } from "./driver/cockpit";
import { PaymentsPage } from "./driver/payments";
import { AdminLayout } from "./admin/layout";
import { AdminGrid } from "./admin/grid";
import { BayDetailPage } from "./admin/bay-detail";
import { ConflictsPage } from "./admin/conflicts";
import { HelpPage } from "./help";
import { NotFoundPage } from "./errors/not-found";
import { ForbiddenPage } from "./errors/forbidden";

export const router = createBrowserRouter([
  { path: "/", element: <Landing /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/help", element: <HelpPage /> },
  {
    path: "/app",
    element: (
      <RequireRole>
        <DriverLayout />
      </RequireRole>
    ),
    children: [
      { index: true, element: <DriverHome /> },
      { path: "plates", element: <PlatesPage /> },
      { path: "reservations/new", element: <BookingWizard /> },
      { path: "reservations/:id", element: <ReservationCockpit /> },
      { path: "payments", element: <PaymentsPage /> },
    ],
  },
  {
    path: "/admin",
    element: (
      <RequireRole role="admin">
        <AdminLayout />
      </RequireRole>
    ),
    children: [
      { index: true, element: <AdminGrid /> },
      { path: "grid", element: <AdminGrid /> },
      { path: "bays/:code", element: <BayDetailPage /> },
      { path: "conflicts", element: <ConflictsPage /> },
    ],
  },
  { path: "/forbidden", element: <ForbiddenPage /> },
  { path: "*", element: <NotFoundPage /> },
]);

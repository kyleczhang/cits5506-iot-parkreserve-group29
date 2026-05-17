/**
 * Driver-shell layout (light theme).
 *
 * Mounts the realtime socket + bus (the socket lifecycle is bound to
 * this authenticated route per plan §8) and renders the top nav.
 */
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LogOut,
  ParkingCircle,
  ReceiptText,
  Car,
  Plus,
  HelpCircle,
} from "lucide-react";

import { applyTheme } from "@/lib/theme";
import { useEffect } from "react";

import { useAuth } from "@/auth/AuthProvider";
import { useRealtime } from "@/realtime/useRealtime";
import { Button } from "@/components/ui/Button";
import { ConnectionStatusDot } from "@/components/ui/ConnectionStatusDot";
import { cn } from "@/lib/cn";

export function DriverLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const conn = useRealtime(user?.id ?? null);

  useEffect(() => {
    applyTheme("driver");
  }, []);

  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
          <Link
            to="/app"
            className="inline-flex items-center gap-2 text-text"
            aria-label="ParkReserve driver home"
          >
            <ParkingCircle className="h-6 w-6 text-brand" aria-hidden="true" />
            <span className="text-base font-semibold">ParkReserve</span>
          </Link>

          <nav aria-label="Primary" className="hidden md:block">
            <ul className="flex items-center gap-1">
              <NavItem to="/app" icon={ParkingCircle} label="Home" end />
              <NavItem to="/app/plates" icon={Car} label="Plates" />
              <NavItem to="/app/payments" icon={ReceiptText} label="Payments" />
              <NavItem to="/help" icon={HelpCircle} label="Help" />
            </ul>
          </nav>

          <div className="flex items-center gap-3">
            <ConnectionStatusDot state={conn} />
            <span className="hidden text-sm text-text-muted md:inline">
              {user?.name}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                signOut();
                navigate("/");
              }}
              leadingIcon={<LogOut className="h-4 w-4" />}
            >
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8 pb-28 md:pb-8">
        <Outlet />
      </main>

      {/* Floating quick-action button — opens the booking wizard.
          On mobile it sits above the bottom tab bar; on ≥md it returns
          to the canonical corner position. */}
      <Link
        to="/app/reservations/new"
        aria-label="Book a bay"
        className={cn(
          "fixed right-4 bottom-20 md:right-6 md:bottom-6",
          "inline-flex h-14 w-14 items-center justify-center rounded-full",
          "bg-brand text-white shadow-card-hover hover:bg-brand/90",
          "transition-colors duration-150 cursor-pointer z-30",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
        )}
      >
        <Plus className="h-6 w-6" aria-hidden="true" />
      </Link>

      {/* Mobile bottom tab bar — mirrors the desktop primary nav. */}
      <nav
        aria-label="Primary"
        className={cn(
          "fixed inset-x-0 bottom-0 z-20 md:hidden",
          "border-t border-border bg-surface/95 backdrop-blur",
          "pb-[env(safe-area-inset-bottom)]",
        )}
      >
        <ul className="mx-auto grid max-w-6xl grid-cols-4">
          <TabItem to="/app" icon={ParkingCircle} label="Home" end />
          <TabItem to="/app/plates" icon={Car} label="Plates" />
          <TabItem to="/app/payments" icon={ReceiptText} label="Payments" />
          <TabItem to="/help" icon={HelpCircle} label="Help" />
        </ul>
      </nav>
    </div>
  );
}

interface NavItemProps {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  end?: boolean;
}

function NavItem({ to, icon: Icon, label, end }: NavItemProps) {
  return (
    <li>
      <NavLink
        to={to}
        end={end}
        className={({ isActive }) =>
          cn(
            "inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium",
            "transition-colors duration-150 hover:bg-surface-2",
            isActive ? "bg-surface-2 text-text" : "text-text-muted",
          )
        }
      >
        <Icon className="h-4 w-4" aria-hidden="true" />
        {label}
      </NavLink>
    </li>
  );
}

function TabItem({ to, icon: Icon, label, end }: NavItemProps) {
  return (
    <li className="contents">
      <NavLink
        to={to}
        end={end}
        className={({ isActive }) =>
          cn(
            "flex min-h-14 flex-col items-center justify-center gap-1 px-2 py-2",
            "text-xs font-medium transition-colors duration-150",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            isActive ? "text-brand" : "text-text-muted hover:text-text",
          )
        }
      >
        <Icon className="h-5 w-5" aria-hidden="true" />
        <span>{label}</span>
      </NavLink>
    </li>
  );
}

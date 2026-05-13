/**
 * Admin shell — `/admin/*`.
 *
 * Ops theme (dark) — applied via `data-theme="ops"` on the
 * `<html>` element. The sidebar carries the conflict-count badge
 * driven by the same `qk.conflicts.open()` cache slice the
 * conflicts page reads from.
 */
import { useEffect } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Layers,
  LogOut,
  ParkingCircle,
  ShieldAlert,
  HelpCircle,
} from "lucide-react";

import { useAuth } from "@/auth/AuthProvider";
import { useRealtime } from "@/realtime/useRealtime";
import { Button } from "@/components/ui/Button";
import { ConnectionStatusDot } from "@/components/ui/ConnectionStatusDot";
import { listOpenConflicts } from "@/api/conflicts";
import { qk } from "@/api/queryKeys";
import { applyTheme } from "@/lib/theme";
import { cn } from "@/lib/cn";

export function AdminLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const conn = useRealtime(user?.id ?? null);
  const conflicts = useQuery({
    queryKey: qk.conflicts.open(),
    queryFn: listOpenConflicts,
    staleTime: 10_000,
  });

  useEffect(() => {
    applyTheme("ops");
    return () => applyTheme("driver");
  }, []);

  const count = conflicts.data?.length ?? 0;

  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-3">
          <Link
            to="/admin/grid"
            className="inline-flex items-center gap-2 text-text"
            aria-label="ParkReserve admin home"
          >
            <ParkingCircle className="h-6 w-6 text-brand" aria-hidden="true" />
            <span className="text-base font-semibold">
              ParkReserve <span className="text-text-muted">/ Ops</span>
            </span>
          </Link>

          <nav aria-label="Admin navigation" className="hidden md:block">
            <ul className="flex items-center gap-1">
              <NavItem to="/admin/grid" icon={Layers} label="Grid" end />
              <NavItem
                to="/admin/conflicts"
                icon={ShieldAlert}
                label="Conflicts"
                badge={count}
              />
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

      <main className="mx-auto max-w-7xl px-6 py-8 pb-28 md:pb-8">
        <Outlet />
      </main>

      {/* Mobile bottom tab bar — mirrors the desktop admin nav. */}
      <nav
        aria-label="Admin navigation"
        className={cn(
          "fixed inset-x-0 bottom-0 z-20 md:hidden",
          "border-t border-border bg-surface/95 backdrop-blur",
          "pb-[env(safe-area-inset-bottom)]",
        )}
      >
        <ul className="mx-auto grid max-w-7xl grid-cols-3">
          <TabItem to="/admin/grid" icon={Layers} label="Grid" end />
          <TabItem
            to="/admin/conflicts"
            icon={ShieldAlert}
            label="Conflicts"
            badge={count}
          />
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
  badge?: number;
  end?: boolean;
}

function NavItem({ to, icon: Icon, label, badge, end }: NavItemProps) {
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
        {badge && badge > 0 ? (
          <span
            aria-label={`${badge} open`}
            className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-danger px-1 text-xs font-semibold text-white"
          >
            {badge}
          </span>
        ) : null}
      </NavLink>
    </li>
  );
}

function TabItem({ to, icon: Icon, label, badge, end }: NavItemProps) {
  return (
    <li className="contents">
      <NavLink
        to={to}
        end={end}
        className={({ isActive }) =>
          cn(
            "relative flex min-h-14 flex-col items-center justify-center gap-1 px-2 py-2",
            "text-xs font-medium transition-colors duration-150",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            isActive ? "text-brand" : "text-text-muted hover:text-text",
          )
        }
      >
        <span className="relative">
          <Icon className="h-5 w-5" aria-hidden="true" />
          {badge && badge > 0 ? (
            <span
              aria-label={`${badge} open`}
              className="absolute -right-2 -top-1 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white"
            >
              {badge}
            </span>
          ) : null}
        </span>
        <span>{label}</span>
      </NavLink>
    </li>
  );
}

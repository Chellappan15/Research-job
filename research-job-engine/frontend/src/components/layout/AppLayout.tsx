import {
  Activity,
  LayoutDashboard,
  Menu,
  Newspaper,
  Radio,
  Rss,
  X,
  MonitorPlay,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";

import { useHealth } from "../../hooks/queries";
import { cn } from "../../lib/cn";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/news", label: "News Feed", icon: Newspaper },
  { to: "/videos", label: "YouTube Videos", icon: MonitorPlay },
  { to: "/sources", label: "Sources", icon: Rss },
  { to: "/jobs", label: "Job Monitor", icon: Activity },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <span className="flex size-7 items-center justify-center rounded-md bg-accent-soft text-accent">
        <Radio className="size-4" aria-hidden />
      </span>
      <span className="text-[15px] font-semibold tracking-tight">TechPulse</span>
    </div>
  );
}

function ApiStatus() {
  const health = useHealth();
  const state = health.isPending ? "checking" : health.isSuccess ? "online" : "offline";
  return (
    <div className="flex items-center gap-2 px-2 text-xs text-fg-muted" aria-live="polite">
      <span
        aria-hidden
        className={cn(
          "size-2 rounded-full",
          state === "online" && "bg-ok",
          state === "offline" && "bg-bad",
          state === "checking" && "animate-pulse bg-fg-subtle",
        )}
      />
      API {state}
    </div>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium",
                isActive
                  ? "bg-elevated text-fg shadow-[inset_2px_0_0_var(--color-accent)]"
                  : "text-fg-muted hover:bg-hover hover:text-fg",
              )
            }
          >
            <Icon className="size-4 shrink-0" aria-hidden />
            {label}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

export function AppLayout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const menuButton = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLDivElement>(null);

  useEffect(() => setOpen(false), [location.pathname]);

  useEffect(() => {
    if (!open) return;
    drawer.current?.querySelector<HTMLElement>("a")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        menuButton.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-accent px-3 py-2 text-sm font-medium text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-line bg-surface px-3 py-4 lg:flex">
        <Brand />
        <nav aria-label="Main" className="mt-6 flex-1">
          <NavItems />
        </nav>
        <ApiStatus />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-surface/95 px-4 backdrop-blur lg:hidden">
        <Brand />
        <button
          ref={menuButton}
          type="button"
          aria-label={open ? "Close navigation" : "Open navigation"}
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
          className="rounded-md p-2 text-fg-muted hover:bg-hover hover:text-fg"
        >
          {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
        </button>
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            tabIndex={-1}
            className="absolute inset-0 bg-black/60"
            onClick={() => setOpen(false)}
          />
          <div
            ref={drawer}
            id="mobile-nav"
            className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-line bg-surface px-3 py-4"
          >
            <Brand />
            <nav aria-label="Main" className="mt-6 flex-1">
              <NavItems onNavigate={() => setOpen(false)} />
            </nav>
            <ApiStatus />
          </div>
        </div>
      )}

      <main id="main" tabIndex={-1} className="lg:pl-60 focus:outline-none">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

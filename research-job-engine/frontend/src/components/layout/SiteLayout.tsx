import { Radio, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router";

import { cn } from "../../lib/cn";

const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/news", label: "News" },
  { to: "/videos", label: "Videos" },
];

function HeaderSearch() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const location = useLocation();
  const current = location.pathname === "/search" ? (params.get("q") ?? "") : "";
  const [value, setValue] = useState(current);
  useEffect(() => setValue(current), [current]);
  return (
    <form
      role="search"
      className="relative w-full sm:w-64"
      onSubmit={(e) => {
        e.preventDefault();
        const q = value.trim();
        if (q) navigate(`/search?q=${encodeURIComponent(q)}`);
      }}
    >
      <label htmlFor="site-search" className="sr-only">
        Search articles and videos
      </label>
      <Search
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle"
        aria-hidden
      />
      <input
        id="site-search"
        type="search"
        value={value}
        maxLength={200}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search AI news…"
        className="h-9 w-full rounded-full border border-line-strong bg-canvas pr-3 pl-9 text-sm text-fg placeholder:text-fg-subtle hover:border-fg-subtle"
      />
    </form>
  );
}

/** Public, reader-facing layout: top navigation, content, footer. */
export function SiteLayout() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo?.({ top: 0 });
  }, [pathname]);

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-accent px-3 py-2 text-sm font-medium text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:flex-nowrap sm:px-6">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-accent-soft text-accent">
              <Radio className="size-4" aria-hidden />
            </span>
            <span className="text-base font-semibold tracking-tight">TechPulse</span>
          </Link>
          <nav aria-label="Main" className="order-3 w-full sm:order-none sm:w-auto">
            <ul className="flex gap-1">
              {NAV.map(({ to, label, end }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      cn(
                        "rounded-full px-3 py-1.5 text-sm font-medium",
                        isActive ? "bg-elevated text-fg" : "text-fg-muted hover:text-fg",
                      )
                    }
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className="ml-auto flex min-w-0 flex-1 justify-end sm:flex-none">
            <HeaderSearch />
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-6 text-sm text-fg-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>
            AI news and videos gathered from public feeds. Links go to the original publishers.
          </p>
          <nav aria-label="Footer" className="flex gap-4">
            <Link to="/about" className="hover:text-fg">
              About
            </Link>
            {/* <Link to="/admin" className="hover:text-fg">
              System status
            </Link> */}
          </nav>
        </div>
      </footer>
    </div>
  );
}

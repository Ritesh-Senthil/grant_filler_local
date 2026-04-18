import { Link, NavLink, Outlet } from "react-router-dom";
import { OrgBrandingProvider, useOrgBranding } from "./orgBranding";

function Nav() {
  const { headerName, bannerSrc } = useOrgBranding();

  return (
    <header className="border-b border-slate-200/80 dark:border-slate-700/80 bg-white/80 dark:bg-slate-900/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-5xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          {bannerSrc ? (
            <img
              src={bannerSrc}
              alt=""
              className="h-9 max-w-[160px] w-auto object-cover rounded-md border border-slate-200/90 dark:border-slate-600 shrink-0"
            />
          ) : null}
          <div className="min-w-0">
            <Link to="/" className="font-semibold text-lg text-slate-900 dark:text-white block truncate">
              GrantFiller
            </Link>
            {headerName ? (
              <p className="text-xs text-slate-500 dark:text-slate-400 truncate m-0">{headerName}</p>
            ) : null}
          </div>
        </div>
        <nav className="flex flex-wrap gap-4 text-sm">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive
                ? "text-blue-600 dark:text-blue-400 font-medium"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }
          >
            Grants
          </NavLink>
          <NavLink
            to="/org"
            className={({ isActive }) =>
              isActive
                ? "text-blue-600 dark:text-blue-400 font-medium"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }
          >
            Your organization
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              isActive
                ? "text-blue-600 dark:text-blue-400 font-medium"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }
          >
            Settings
          </NavLink>
        </nav>
      </div>
    </header>
  );
}

/** Shell layout for `createBrowserRouter` (`RouterProvider` in `main.tsx`). */
export function RootLayout() {
  return (
    <OrgBrandingProvider>
      <div className="min-h-screen">
        <Nav />
        <main className="max-w-5xl mx-auto px-4 py-8">
          <Outlet />
        </main>
      </div>
    </OrgBrandingProvider>
  );
}

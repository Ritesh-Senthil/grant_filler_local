import { Link, NavLink, Route, Routes } from "react-router-dom";
import { DashboardPage } from "./pages/DashboardPage";
import { GrantPage } from "./pages/GrantPage";
import { OrgPage } from "./pages/OrgPage";

function Nav() {
  return (
    <header className="border-b border-slate-200/80 dark:border-slate-700/80 bg-white/80 dark:bg-slate-900/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        <Link to="/" className="font-semibold text-lg text-slate-900 dark:text-white">
          GrantFiller
        </Link>
        <nav className="flex gap-4 text-sm">
          <NavLink
            to="/"
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
        </nav>
        <button
          type="button"
          onClick={() => document.documentElement.classList.toggle("dark")}
          className="text-xs px-2 py-1 rounded-md border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300"
        >
          Theme
        </button>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/org" element={<OrgPage />} />
          <Route path="/grants/:id" element={<GrantPage />} />
        </Routes>
      </main>
    </div>
  );
}

import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { RootLayout } from "./App";
import "./index.css";
import { initThemeFromStorage } from "./theme";
import { DashboardPage } from "./pages/DashboardPage";
import { GrantPage } from "./pages/GrantPage";
import { OrgPage } from "./pages/OrgPage";
import { SettingsPage } from "./pages/SettingsPage";

initThemeFromStorage();

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "org", element: <OrgPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "grants/:id", element: <GrantPage /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);

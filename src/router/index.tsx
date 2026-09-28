import { createBrowserRouter, redirect } from "react-router";
import LoginPage from "@/pages/login";
import { redirectIfLoggedIn, requireAdmin, requireUser } from "@/router/guards";

export const router = createBrowserRouter([
  {
    path: "/login",
    loader: redirectIfLoggedIn,
    element: <LoginPage />,
  },
  {
    path: "/register",
    loader: redirectIfLoggedIn,
    lazy: () => import("@/pages/register").then((m) => ({ Component: m.default })),
    HydrateFallback: () => null,
  },
  // 阅读端：书架与阅读页
  {
    path: "/",
    loader: requireUser,
    lazy: () => import("@/pages/stage/shelf").then((m) => ({ Component: m.default })),
    HydrateFallback: () => null,
  },
  {
    // 我的收藏（D55）：与书架同一个页面
    path: "/favorites",
    loader: requireUser,
    lazy: () =>
      import("@/pages/stage/shelf").then((m) => ({
        Component: () => <m.default mode="favorites" />,
      })),
    HydrateFallback: () => null,
  },
  {
    path: "/books/:id",
    loader: requireUser,
    lazy: () => import("@/pages/stage/reader").then((m) => ({ Component: m.default })),
    HydrateFallback: () => null,
  },
  // 管理后台单独打包，读者不会加载
  {
    path: "/admin",
    loader: requireAdmin,
    lazy: () => import("@/pages/admin/layout").then((m) => ({ Component: m.default })),
    HydrateFallback: () => null,
    children: [
      { index: true, loader: () => redirect("/admin/books") },
      {
        path: "books",
        lazy: () => import("@/pages/admin/books").then((m) => ({ Component: m.default })),
      },
      {
        path: "books/:id",
        lazy: () => import("@/pages/admin/book-detail").then((m) => ({ Component: m.default })),
      },
      {
        path: "invites",
        lazy: () => import("@/pages/admin/invites").then((m) => ({ Component: m.default })),
      },
      {
        path: "readers",
        lazy: () => import("@/pages/admin/readers").then((m) => ({ Component: m.default })),
      },
      {
        path: "ai",
        lazy: () => import("@/pages/admin/ai-settings").then((m) => ({ Component: m.default })),
      },
    ],
  },
  { path: "*", loader: () => redirect("/") },
]);

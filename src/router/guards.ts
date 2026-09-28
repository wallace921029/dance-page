import { redirect, type LoaderFunctionArgs } from "react-router";
import { meQuery } from "@/api/auth";
import { queryClient } from "@/lib/query-client";

function loginRedirect(request: Request) {
  const url = new URL(request.url);
  return redirect(`/login?next=${encodeURIComponent(url.pathname + url.search)}`);
}

/** 任意已登录用户 */
export async function requireUser({ request }: LoaderFunctionArgs) {
  const me = await queryClient.ensureQueryData(meQuery);
  if (!me) throw loginRedirect(request);
  return me;
}

/** 仅管理员；读者访问 /admin 时回到书架 */
export async function requireAdmin({ request }: LoaderFunctionArgs) {
  const me = await queryClient.ensureQueryData(meQuery);
  if (!me) throw loginRedirect(request);
  if (me.role !== "admin") throw redirect("/");
  return me;
}

/** 已登录时访问登录页，直接进入对应首页 */
export async function redirectIfLoggedIn() {
  const me = await queryClient.ensureQueryData(meQuery);
  if (me) throw redirect(me.role === "admin" ? "/admin/books" : "/");
  return null;
}

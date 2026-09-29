import { redirect, type LoaderFunctionArgs } from "react-router";
import { meQuery } from "@/api/auth";
import { queryClient } from "@/lib/query-client";
import { isFullAdmin, isStaff } from "@/lib/roles";

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

/** 管理员或小小管理员（能进管理后台的绘本模块）；读者访问 /admin 时回到书架 */
export async function requireStaff({ request }: LoaderFunctionArgs) {
  const me = await queryClient.ensureQueryData(meQuery);
  if (!me) throw loginRedirect(request);
  if (!isStaff(me.role)) throw redirect("/");
  return me;
}

/** 仅管理员（用户管理、AI 配置）；小小管理员访问时回到绘本模块 */
export async function requireAdmin({ request }: LoaderFunctionArgs) {
  const me = await queryClient.ensureQueryData(meQuery);
  if (!me) throw loginRedirect(request);
  if (!isFullAdmin(me.role)) throw redirect(isStaff(me.role) ? "/admin/books" : "/");
  return me;
}

/** 已登录时访问登录页，直接进入对应首页 */
export async function redirectIfLoggedIn() {
  const me = await queryClient.ensureQueryData(meQuery);
  // 小小管理员首先是读者，登录后先到书架；要管理绘本从头像里进管理后台
  if (me) throw redirect(me.role === "admin" ? "/admin/books" : "/");
  return null;
}

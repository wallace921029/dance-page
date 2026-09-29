import { Link, Outlet, useLocation, useMatch, useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Library, LogOut, Sparkles, Users } from "lucide-react";
import { MotionConfig, motion } from "motion/react";
import { cn } from "cn";
import "@fontsource/zcool-xiaowei";
import { meQuery, useLogout } from "@/api/auth";
import { APP_NAME } from "@/lib/app-info";
import { ROLE_LABELS, isFullAdmin } from "@/lib/roles";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "@/components/ui/navigation-menu";

// adminOnly：只有管理员能用；小小管理员只有"绘本"模块（D109）
const NAV_ITEMS = [
  { to: "/admin/books", label: "绘本", icon: BookOpen, adminOnly: false },
  { to: "/admin/users", label: "用户管理", icon: Users, adminOnly: true },
  { to: "/admin/ai", label: "AI 配置", icon: Sparkles, adminOnly: true },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { data: me } = useQuery(meQuery);
  const logout = useLogout();

  return (
    <div className="min-h-svh bg-muted/40">
      <header className="sticky top-0 z-20 border-b bg-background/95 pt-[env(safe-area-inset-top)] backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <Link
            to="/admin/books"
            aria-label={`${APP_NAME} 管理后台`}
            className="flex items-center gap-2.5 rounded-xl bg-stage-night py-1 pr-3.5 pl-1 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {/* 网站 logo：萤火虫照亮打开的书（同 favicon）。字标与读者首页一致（站酷小薇 + 舞台金），
                浅色顶栏上金色看不清，所以整体放在夜幕色的胶囊里；admin 小而淡，只是个提示 */}
            <img src="/favicon.svg" alt="" className="size-8 rounded-lg" />
            <span className="font-stage-title text-2xl leading-none tracking-[0.2em] text-stage-light">
              {APP_NAME}
            </span>
            <span className="self-end pb-1 text-[10px] leading-none tracking-[0.25em] text-stage-light/45 uppercase">
              admin
            </span>
          </Link>
          <NavigationMenu>
            <NavigationMenuList>
              {NAV_ITEMS.filter((item) => !item.adminOnly || isFullAdmin(me?.role)).map(
                ({ adminOnly: _adminOnly, ...item }) => (
                  <NavItem key={item.to} {...item} />
                ),
              )}
            </NavigationMenuList>
          </NavigationMenu>
          {me && (
            <div className="ml-auto flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                nativeButton={false}
                render={<Link to="/" />}
                aria-label="打开读者首页"
                title="打开读者首页"
                className="text-muted-foreground"
              >
                <Library />
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger
                  aria-label="账户"
                  render={<Button variant="ghost" size="icon" className="rounded-full" />}
                >
                  <Avatar>
                    <AvatarFallback>{me.username.slice(0, 1).toUpperCase()}</AvatarFallback>
                  </Avatar>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-40">
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>
                      {me.username}
                      {me.role === "sub_admin" && (
                        <span className="ml-1.5 font-normal text-muted-foreground">
                          {ROLE_LABELS.sub_admin}
                        </span>
                      )}
                    </DropdownMenuLabel>
                  </DropdownMenuGroup>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    disabled={logout.isPending}
                    onClick={() =>
                      logout.mutate(undefined, {
                        onSuccess: () => navigate("/login", { replace: true }),
                      })
                    }
                  >
                    <LogOut />
                    退出登录
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
        </div>
      </header>
      {/* "减少动态效果"时只保留淡入，去掉位移和缩放 */}
      <MotionConfig reducedMotion="user">
        {/* 切换页面时内容淡入；只看路径，同一页里翻页、筛选不重播 */}
        <motion.main
          // 用户管理里切换标签时只换标签下面的内容，标题和标签不跟着重新淡入
          key={pathname.startsWith("/admin/users") ? "/admin/users" : pathname}
          className="mx-auto max-w-6xl px-4 py-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
        >
          <Outlet />
        </motion.main>
      </MotionConfig>
    </div>
  );
}

function NavItem({ to, label, icon: Icon }: Omit<(typeof NAV_ITEMS)[number], "adminOnly">) {
  // 绘本详情页（/admin/books/:id）也算在"绘本"下
  const active = useMatch({ path: to, end: false }) !== null;
  return (
    <NavigationMenuItem>
      <NavigationMenuLink
        active={active}
        render={<Link to={to} />}
        className="px-3 py-1.5 text-muted-foreground data-active:font-medium data-active:text-foreground"
      >
        <Icon />
        {label}
      </NavigationMenuLink>
    </NavigationMenuItem>
  );
}

/** 页面标题行：左侧标题和说明，右侧操作按钮 */
export function PageHeader({
  title,
  description,
  children,
}: {
  /** 不给标题时只显示说明和右侧的操作按钮（用在带标签的页面里） */
  title?: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        {title && <h1 className="text-xl font-semibold">{title}</h1>}
        {description && (
          <p className={cn("text-sm text-muted-foreground", title && "mt-1")}>{description}</p>
        )}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}

import { Link, Outlet, useLocation, useMatch, useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, LogOut, Sparkles, Ticket, Users } from "lucide-react";
import { MotionConfig, motion } from "motion/react";
import { meQuery, useLogout } from "@/api/auth";
import { APP_NAME } from "@/lib/app-info";
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

const NAV_ITEMS = [
  { to: "/admin/books", label: "绘本", icon: BookOpen },
  { to: "/admin/invites", label: "邀请码", icon: Ticket },
  { to: "/admin/readers", label: "读者", icon: Users },
  { to: "/admin/ai", label: "AI 配置", icon: Sparkles },
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
          <span className="font-semibold">{APP_NAME} 管理后台</span>
          <NavigationMenu>
            <NavigationMenuList>
              {NAV_ITEMS.map((item) => (
                <NavItem key={item.to} {...item} />
              ))}
            </NavigationMenuList>
          </NavigationMenu>
          {me && (
            <div className="ml-auto">
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
                    <DropdownMenuLabel>{me.username}</DropdownMenuLabel>
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
          key={pathname}
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

function NavItem({ to, label, icon: Icon }: (typeof NAV_ITEMS)[number]) {
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
  title: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}

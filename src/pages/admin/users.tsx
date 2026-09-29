// 用户管理：把"邀请码"和"读者"两个模块合在一起，用标签切换。
// 标签对应子路由（/admin/users/invites、/admin/users/readers），刷新或分享链接时停在同一个标签
import { Outlet, useLocation, useNavigate } from "react-router";
import { Ticket, Users } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/pages/admin/layout";

const TABS = [
  { value: "invites", label: "邀请码", icon: Ticket },
  { value: "readers", label: "读者", icon: Users },
] as const;

export default function AdminUsersPage() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const active = pathname.endsWith("/readers") ? "readers" : "invites";

  return (
    <>
      <PageHeader title="用户管理" description="用邀请码邀请读者注册，并管理已注册的读者账号。" />
      <Tabs
        value={active}
        onValueChange={(value) => navigate(`/admin/users/${value}`)}
        className="gap-4"
      >
        <TabsList>
          {TABS.map(({ value, label, icon: Icon }) => (
            <TabsTrigger key={value} value={value} className="gap-1.5 px-3">
              <Icon />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={active}>
          <Outlet />
        </TabsContent>
      </Tabs>
    </>
  );
}

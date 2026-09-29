// 账号角色（D109）：admin = .env 里的初始管理员，拥有全部权限；
// sub_admin = 小小管理员，由管理员从读者里授予，只有"绘本"模块的权限；reader = 读者
import type { Role } from "@/api/types";

/** 能进管理后台（绘本模块）：管理员和小小管理员 */
export function isStaff(role: Role | undefined | null): boolean {
  return role === "admin" || role === "sub_admin";
}

/** 拥有全部管理权限：用户管理、AI 配置只有管理员能用 */
export function isFullAdmin(role: Role | undefined | null): boolean {
  return role === "admin";
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: "管理员",
  sub_admin: "小小管理员",
  reader: "小读者",
};

import { useState } from "react";
import { Copy, Plus, Ticket, Trash2 } from "lucide-react";
import { useCreateInvite, useDeleteInvite, useInvites, useRevokeInvite } from "@/api/invites";
import type { Invite, InviteStatus } from "@/api/types";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/api";
import { formatDateTime, formatInviteCode } from "@/lib/format";
import { PageHeader } from "@/pages/admin/layout";
import { AnimatedTableRow, Reveal } from "@/pages/admin/motion";
import { ErrorState, LoadingState } from "@/pages/admin/query-state";

const VALID_DAYS_ITEMS = [1, 3, 7, 30].map((days) => ({ value: days, label: `有效期 ${days} 天` }));

const STATUS_BADGES: Record<InviteStatus, React.ReactNode> = {
  unused: <Badge>未使用</Badge>,
  used: <Badge variant="secondary">已使用</Badge>,
  expired: <Badge variant="outline">已过期</Badge>,
  revoked: <Badge variant="outline">已作废</Badge>,
};

function registerLink(code: string) {
  return `${window.location.origin}/register?code=${code}`;
}

async function copyRegisterLink(invite: Invite) {
  try {
    await navigator.clipboard.writeText(registerLink(invite.code));
    toast.add({
      title: "注册链接已复制",
      description: `发给读者即可，邀请码 ${formatInviteCode(invite.code)}`,
      type: "success",
    });
  } catch {
    // 非 HTTPS 环境下浏览器可能不允许写剪贴板
    toast.add({
      title: "无法自动复制，请手动复制",
      description: registerLink(invite.code),
      type: "error",
    });
  }
}

export default function AdminInvitesPage() {
  const { data: invites, isPending, error } = useInvites();
  useDocumentTitle("用户管理 · 邀请码");
  const create = useCreateInvite();
  const [validDays, setValidDays] = useState(7);

  return (
    <>
      <PageHeader description="一个邀请码只能注册一个读者，过期或作废后不能再使用。">
        <Select
          items={VALID_DAYS_ITEMS}
          value={validDays}
          onValueChange={(value) => value !== null && setValidDays(value)}
        >
          <SelectTrigger aria-label="有效期">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {VALID_DAYS_ITEMS.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          disabled={create.isPending}
          onClick={() =>
            create.mutate(validDays, {
              onSuccess: (invite) => void copyRegisterLink(invite),
              onError: (err) =>
                toast.add({ title: "生成失败", description: getErrorMessage(err), type: "error" }),
            })
          }
        >
          {create.isPending ? <Spinner /> : <Plus />}
          生成邀请码
        </Button>
      </PageHeader>

      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : invites.length === 0 ? (
        <Reveal>
          <Empty className="border bg-background">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Ticket />
              </EmptyMedia>
              <EmptyTitle>还没有邀请码</EmptyTitle>
              <EmptyDescription>
                生成邀请码后，注册链接会自动复制，发给读者即可注册。
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </Reveal>
      ) : (
        <Reveal>
          <Card className="gap-0 py-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>邀请码</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>使用者</TableHead>
                  <TableHead>生成时间</TableHead>
                  <TableHead>过期时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invites.map((invite, index) => (
                  <AnimatedTableRow key={invite.id} index={index}>
                    <TableCell className="font-mono tracking-wider">
                      {formatInviteCode(invite.code)}
                    </TableCell>
                    <TableCell>{STATUS_BADGES[invite.status]}</TableCell>
                    <TableCell>{invite.used_by?.username ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground tabular-nums">
                      {formatDateTime(invite.created_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground tabular-nums">
                      {formatDateTime(invite.expires_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <InviteActions invite={invite} />
                    </TableCell>
                  </AnimatedTableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </Reveal>
      )}
    </>
  );
}

/** 一行邀请码的操作：未使用的可以复制链接、作废；没被用过的（未使用、已过期、已作废）都可以删除 */
function InviteActions({ invite }: { invite: Invite }) {
  const revoke = useRevokeInvite();
  return (
    <div className="flex justify-end gap-1">
      {invite.status === "unused" && (
        <>
          <Button size="sm" variant="ghost" onClick={() => void copyRegisterLink(invite)}>
            <Copy />
            复制注册链接
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-destructive hover:text-destructive"
            disabled={revoke.isPending}
            onClick={() =>
              revoke.mutate(invite.id, {
                onSuccess: () => toast.add({ title: "已作废", type: "success" }),
                onError: (err) =>
                  toast.add({
                    title: "作废失败",
                    description: getErrorMessage(err),
                    type: "error",
                  }),
              })
            }
          >
            作废
          </Button>
        </>
      )}
      {invite.status !== "used" && <DeleteInviteButton invite={invite} />}
    </div>
  );
}

function DeleteInviteButton({ invite }: { invite: Invite }) {
  const remove = useDeleteInvite();
  const [open, setOpen] = useState(false);
  const code = formatInviteCode(invite.code);
  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger
        render={
          <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" />
        }
      >
        <Trash2 />
        删除
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除邀请码 {code}？</AlertDialogTitle>
          <AlertDialogDescription>
            {invite.status === "unused"
              ? "这个邀请码还没有被使用，删除后已经发出去的注册链接会立即失效。"
              : "删除后从列表里消失，无法恢复。"}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(invite.id, {
                onSuccess: () => {
                  setOpen(false);
                  toast.add({ title: `已删除 ${code}`, type: "success" });
                },
                onError: (err) =>
                  toast.add({
                    title: "删除失败",
                    description: getErrorMessage(err),
                    type: "error",
                  }),
              })
            }
          >
            {remove.isPending && <Spinner />}
            删除
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

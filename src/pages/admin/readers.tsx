import { useState } from "react";
import { KeyRound, Users } from "lucide-react";
import { useReaders, useResetReaderPassword, useSetReaderDisabled } from "@/api/readers";
import type { Reader } from "@/api/types";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
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
import { formatDateTime } from "@/lib/format";
import { PageHeader } from "@/pages/admin/layout";
import { AnimatedTableRow, Reveal } from "@/pages/admin/motion";
import { ErrorState, LoadingState } from "@/pages/admin/query-state";

const PASSWORD_MIN_LENGTH = 6;

export default function AdminReadersPage() {
  const { data: readers, isPending, error } = useReaders();
  useDocumentTitle("用户管理 · 读者");

  return (
    <>
      <PageHeader description="读者通过邀请码自行注册。停用后立即退出登录且无法再登录；忘记密码时可在这里重置。" />
      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : readers.length === 0 ? (
        <Reveal>
          <Empty className="border bg-background">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Users />
              </EmptyMedia>
              <EmptyTitle>还没有读者</EmptyTitle>
              <EmptyDescription>在"邀请码"标签里生成邀请码，把注册链接发给读者。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        </Reveal>
      ) : (
        <Reveal>
          <Card className="gap-0 py-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用户名</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>注册时间</TableHead>
                  <TableHead>最近使用</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {readers.map((reader, index) => (
                  <AnimatedTableRow key={reader.id} index={index}>
                    <TableCell className="font-medium">{reader.username}</TableCell>
                    <TableCell>
                      {reader.is_disabled ? (
                        <Badge variant="outline">已停用</Badge>
                      ) : (
                        <Badge variant="secondary">正常</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground tabular-nums">
                      {formatDateTime(reader.created_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground tabular-nums">
                      {formatDateTime(reader.last_active_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <ResetPasswordButton reader={reader} />
                        <ToggleDisabledButton reader={reader} />
                      </div>
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

function ToggleDisabledButton({ reader }: { reader: Reader }) {
  const setDisabled = useSetReaderDisabled();
  const [open, setOpen] = useState(false);

  const apply = (disabled: boolean) =>
    setDisabled.mutate(
      { id: reader.id, disabled },
      {
        onSuccess: () => {
          setOpen(false);
          toast.add({
            title: disabled ? `已停用 ${reader.username}` : `已启用 ${reader.username}`,
            type: "success",
          });
        },
        onError: (err) =>
          toast.add({ title: "操作失败", description: getErrorMessage(err), type: "error" }),
      },
    );

  if (reader.is_disabled) {
    return (
      <Button
        size="sm"
        variant="ghost"
        disabled={setDisabled.isPending}
        onClick={() => apply(false)}
      >
        启用
      </Button>
    );
  }
  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger
        render={
          <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" />
        }
      >
        停用
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>停用 {reader.username}？</AlertDialogTitle>
          <AlertDialogDescription>
            该读者所有设备会立即退出登录，并且无法再登录。之后可以随时重新启用。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <Button
            variant="destructive"
            disabled={setDisabled.isPending}
            onClick={() => apply(true)}
          >
            {setDisabled.isPending && <Spinner />}
            停用
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ResetPasswordButton({ reader }: { reader: Reader }) {
  const reset = useResetReaderPassword();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const tooShort = password.length < PASSWORD_MIN_LENGTH;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    reset.mutate(
      { id: reader.id, password },
      {
        onSuccess: () => {
          setOpen(false);
          toast.add({
            title: `已重置 ${reader.username} 的密码`,
            description: "请把新密码告诉读者，所有设备需要用新密码重新登录。",
            type: "success",
          });
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setPassword("");
          reset.reset();
        }
      }}
    >
      <DialogTrigger render={<Button size="sm" variant="ghost" />}>
        <KeyRound />
        重置密码
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>重置 {reader.username} 的密码</DialogTitle>
            <DialogDescription>设置后该读者的所有设备都会退出登录。</DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="new-password">新密码</FieldLabel>
            <Input
              id="new-password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={`至少 ${PASSWORD_MIN_LENGTH} 位`}
            />
            {reset.isError && <FieldError>{getErrorMessage(reset.error)}</FieldError>}
          </Field>
          <DialogFooter>
            <Button type="submit" disabled={tooShort || reset.isPending}>
              {reset.isPending && <Spinner />}
              确认重置
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// 绘本的上架 / 下架与删除，列表页和详情页共用
import { useState } from "react";
import { Eye, EyeOff, Trash2 } from "lucide-react";
import { useDeleteBook, useUpdateBook } from "@/api/books";
import type { AdminBook } from "@/api/types";
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
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toast";
import { getErrorMessage } from "@/lib/api";

type ButtonSize = "default" | "sm";

/** 需要二次确认的操作：点击按钮先弹出确认框 */
function ConfirmButton({
  trigger,
  title,
  description,
  confirmLabel,
  destructive,
  pending,
  onConfirm,
}: {
  trigger: React.ReactElement;
  title: React.ReactNode;
  description: React.ReactNode;
  confirmLabel: string;
  destructive?: boolean;
  pending: boolean;
  /** 调用 done() 关闭确认框（操作成功后） */
  onConfirm: (done: () => void) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger render={trigger} />
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <Button
            variant={destructive ? "destructive" : "default"}
            disabled={pending}
            onClick={() => onConfirm(() => setOpen(false))}
          >
            {pending && <Spinner />}
            {confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** 已上架 → 下架（需确认）；已下架 → 上架（直接生效） */
export function VisibilityButton({
  book,
  size = "default",
  variant = "outline",
}: {
  book: AdminBook;
  size?: ButtonSize;
  variant?: "outline" | "ghost";
}) {
  const update = useUpdateBook(book.id);

  const setVisibility = (visibility: AdminBook["visibility"], done?: () => void) =>
    update.mutate(
      { visibility },
      {
        onSuccess: () => {
          done?.();
          toast.add({
            title: visibility === "listed" ? `已上架《${book.title}》` : `已下架《${book.title}》`,
            type: "success",
          });
        },
        onError: (err) =>
          toast.add({ title: "操作失败", description: getErrorMessage(err), type: "error" }),
      },
    );

  if (book.visibility === "unlisted") {
    return (
      <Button
        variant={variant}
        size={size}
        disabled={update.isPending}
        onClick={() => setVisibility("listed")}
      >
        <Eye />
        上架
      </Button>
    );
  }
  return (
    <ConfirmButton
      trigger={
        <Button variant={variant} size={size}>
          <EyeOff />
          下架
        </Button>
      }
      title={`下架《${book.title}》？`}
      description="下架后读者在书架上看不到这本书，正在阅读的读者也无法再打开。数据会保留，随时可以重新上架。"
      confirmLabel="确认下架"
      pending={update.isPending}
      onConfirm={(done) => setVisibility("unlisted", done)}
    />
  );
}

export function DeleteBookButton({
  book,
  size = "default",
  variant = "destructive",
  onDeleted,
}: {
  book: AdminBook;
  size?: ButtonSize;
  variant?: "destructive" | "ghost";
  onDeleted?: () => void;
}) {
  const remove = useDeleteBook();
  return (
    <ConfirmButton
      trigger={
        <Button
          variant={variant}
          size={size}
          className={variant === "ghost" ? "text-destructive hover:text-destructive" : undefined}
        >
          <Trash2 />
          删除
        </Button>
      }
      title={`删除《${book.title}》？`}
      description={
        book.visibility === "listed" && book.processing_status === "ready"
          ? "这本书正在书架上，删除后读者将无法再阅读。原始 PDF 和所有页面图片都会被删除，且无法恢复。如只是暂时不想让读者看到，可以选择“下架”。"
          : "原始 PDF 和所有页面图片都会被删除，且无法恢复。"
      }
      confirmLabel="确认删除"
      destructive
      pending={remove.isPending}
      onConfirm={(done) =>
        remove.mutate(book.id, {
          onSuccess: () => {
            done();
            toast.add({ title: `已删除《${book.title}》`, type: "success" });
            onDeleted?.();
          },
          onError: (err) =>
            toast.add({ title: "删除失败", description: getErrorMessage(err), type: "error" }),
        })
      }
    />
  );
}

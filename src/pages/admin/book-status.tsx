import type { AdminBook } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

export function BookStatusBadge({ book }: { book: AdminBook }) {
  if (book.processing_status === "processing") {
    const { done = 0, total = 0 } = book.progress ?? {};
    return <Badge variant="secondary">处理中 {total > 0 ? `${done} / ${total}` : "…"}</Badge>;
  }
  if (book.processing_status === "failed") return <Badge variant="destructive">处理失败</Badge>;
  return book.visibility === "listed" ? (
    <Badge>已上架</Badge>
  ) : (
    <Badge variant="outline">已下架</Badge>
  );
}

/** 拆页进度 */
export function ProcessingProgress({ book, children }: { book: AdminBook; children?: React.ReactNode }) {
  const { done = 0, total = 0 } = book.progress ?? {};
  return (
    <Progress value={total > 0 ? (done / total) * 100 : 0} aria-label="拆页进度">
      {children}
    </Progress>
  );
}

import type { AdminBook } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "cn";
import { Film, Sparkles, Volume2 } from "lucide-react";

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

/** 绘本的 3 个 AI 就绪状态图标（封面动画、Dance Ready、Voice Ready） */
export function BookAiStatusIcons({ book }: { book: AdminBook }) {
  const items = [
    {
      key: "cover-video",
      name: "封面动画",
      ready: book.cover_video_ready,
      icon: Film,
      readyClass: "text-sky-500 dark:text-sky-400",
    },
    {
      key: "dance",
      name: "Dance Ready",
      ready: book.dance_ready,
      icon: Sparkles,
      readyClass: "text-amber-500 dark:text-amber-400",
    },
    {
      key: "voice",
      name: "Voice Ready",
      ready: book.voice_ready,
      icon: Volume2,
      readyClass: "text-emerald-500 dark:text-emerald-400",
    },
  ];

  return (
    <div className="flex items-center gap-1" aria-label="AI 状态">
      {items.map((item) => {
        const Icon = item.icon;
        const text = `${item.name}：${item.ready ? "已就绪" : "未就绪"}`;
        return (
          <Tooltip key={item.key}>
            <TooltipTrigger
              render={
                <span
                  tabIndex={0}
                  className={cn(
                    "inline-flex size-6 items-center justify-center rounded-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                    item.ready ? item.readyClass : "text-muted-foreground/35",
                  )}
                  aria-label={text}
                  title={text}
                >
                  <Icon className="size-3.5" />
                  <span className="sr-only">{text}</span>
                </span>
              }
            />
            <TooltipContent side="top">{text}</TooltipContent>
          </Tooltip>
        );
      })}
    </div>
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


// 书架标题右侧的搜索（D54、D119）：点手绘放大镜弹出一个手绘风格的小弹窗（与头像弹窗同一套），
// 在里面输入书名，点"找一找"（或回车）后弹窗收起、书架只显示匹配的绘本。
// 有搜索词时放大镜亮着，再点开可以改或清除
import { useImperativeHandle, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { stageSubmitButtonClass } from "@/pages/stage/common";
import { DoodleSearch } from "@/pages/stage/doodle-search";

export type ShelfSearchHandle = {
  /** 清空搜索词（与在弹窗里点"清除"相同） */
  clear: () => void;
};

export function ShelfSearch({
  value,
  onChange,
  ref,
}: {
  /** 当前生效的搜索词（在地址里） */
  value: string;
  onChange: (value: string) => void;
  ref?: React.Ref<ShelfSearchHandle>;
}) {
  const [open, setOpen] = useState(false);
  // 弹窗里正在输入的文字（包括输入法组字中的文字），点"找一找"才写入搜索词
  const [text, setText] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const active = value.trim() !== "";

  useImperativeHandle(ref, () => ({
    clear: () => {
      setText("");
      onChange("");
    },
  }));

  const changeOpen = (next: boolean) => {
    // 每次打开都从当前生效的搜索词开始，上次没提交的文字不保留
    if (next) setText(value);
    setOpen(next);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onChange(text.trim());
    setOpen(false);
  };

  const clear = () => {
    setText("");
    onChange("");
    setOpen(false);
  };

  const label = active ? `搜索绘本（正在找"${value.trim()}"）` : "搜索绘本";

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon-lg"
            aria-label={label}
            title={label}
            className={cn(
              "size-11 rotate-3 rounded-full bg-transparent p-1 transition-transform hover:scale-110 hover:bg-transparent focus-visible:ring-stage-spot/60 active:scale-95 motion-reduce:transition-none dark:hover:bg-transparent [&_svg:not([class*='size-'])]:size-full",
              // 有搜索词时像被点亮的贴纸：微微歪着、带一圈暖光（与收藏页的爱心同一做法）
              active && "-rotate-12 bg-white/15 ring-2 ring-stage-spot/60",
            )}
          />
        }
      >
        <DoodleSearch className="size-full drop-shadow-[0_2px_2px_rgba(30,20,50,.35)]" />
      </DialogTrigger>
      {/* 弹窗渲染在书架之外，不继承书架主题，所以自己带上深色配色（与 account-dialog.tsx 一致）。
          靠上放，iPad 上键盘弹出来时不会盖住输入框 */}
      <DialogContent
        initialFocus={inputRef}
        className="dark top-[8vh] max-w-80 -translate-y-0 gap-5 rounded-3xl border-2 border-dashed border-stage-light/45 bg-stage-night p-6 font-stage text-stage-light shadow-[0_0_60px_rgba(255,214,107,0.16)] ring-0 sm:max-w-80 [&_[data-slot=dialog-close]]:text-stage-light/80 [&_[data-slot=dialog-close]]:hover:bg-white/10 [&_[data-slot=dialog-close]]:hover:text-stage-light"
      >
        <div className="flex flex-col items-center gap-1.5 text-center">
          <DoodleSearch className="size-16 -rotate-6 drop-shadow-[0_3px_3px_rgba(0,0,0,.4)]" />
          <DialogTitle className="mt-1 font-stage-title text-2xl tracking-wider text-stage-light">
            找一本绘本
          </DialogTitle>
          <DialogDescription className="text-xs text-stage-light/70">
            输入书名的一部分就行
          </DialogDescription>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <Input
            ref={inputRef}
            type="search"
            enterKeyHint="search"
            autoComplete="off"
            autoCapitalize="none"
            placeholder="书名"
            aria-label="搜索绘本"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="h-12 rounded-2xl border-2 border-dashed border-stage-light/45 bg-white/5 px-4 text-base text-stage-light placeholder:text-stage-light/50 focus-visible:border-stage-spot focus-visible:ring-stage-spot/40 dark:bg-white/5 [&::-webkit-search-cancel-button]:hidden"
          />
          <Button
            type="submit"
            size="lg"
            className={cn(
              stageSubmitButtonClass,
              "h-12 rounded-2xl font-stage-title text-lg tracking-wider",
            )}
          >
            找一找
          </Button>
          {(active || text !== "") && (
            <Button
              type="button"
              variant="ghost"
              onClick={clear}
              className="h-11 rounded-2xl border-2 border-dashed border-stage-light/40 bg-white/5 font-stage-title text-base tracking-wider text-stage-light hover:bg-white/12 hover:text-stage-light focus-visible:ring-stage-spot/50"
            >
              清除
            </Button>
          )}
        </form>
      </DialogContent>
    </Dialog>
  );
}

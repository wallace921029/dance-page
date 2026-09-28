import { useEffect, useRef, useState } from "react";
import {
  AudioLines,
  BadgeCheck,
  BookOpen,
  CircleAlert,
  Combine,
  Edit2,
  Film,
  Maximize2,
  MoreHorizontal,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
  Split,
  Square,
  Trash2,
  Volume2,
  Wand2,
} from "lucide-react";
import { cn } from "cn";
import {
  useAnalyzeBook,
  useBookAi,
  useCreateCharacter,
  useDeleteCharacter,
  useDesignVoice,
  useDraftAiUnit,
  useGenerateAllAudio,
  useGenerateCoverVideo,
  useGenerateSpreadAudio,
  useGenerateUnitAudio,
  useSetCoverVideoEnabled,
  useSetVoiceReady,
  useUpdateSpreadSwitches,
  useUpdateAiUnit,
  useUpdateBookAi,
  useUpdateCharacter,
  useUpdateSpreadMode,
} from "@/api/ai";
import type {
  AdminBookDetail,
  AiLineItem,
  AiUnit,
  BookAi,
  BookPage,
  Character,
  CoverVideo,
  Spread,
} from "@/api/types";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
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
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { getErrorMessage } from "@/lib/api";

/** 对开时"分别生成"的两页的朗读顺序（D69） */
const READ_ORDER_ITEMS = [
  { value: "left_first", label: "先左后右" },
  { value: "right_first", label: "先右后左" },
];

interface AiWorkbenchProps {
  book: AdminBookDetail;
  onSetCover: (index: number) => void;
  isSettingCover: boolean;
}

export function AiWorkbench({ book, onSetCover, isSettingCover }: AiWorkbenchProps) {
  const { data: bookAi, isPending, error } = useBookAi(book.id);

  if (isPending) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-16">
          <Spinner className="size-6 text-muted-foreground" />
          <span className="ml-3 text-sm text-muted-foreground">正在加载 AI 工作台…</span>
        </CardContent>
      </Card>
    );
  }

  if (error || !bookAi) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-destructive">
          无法加载 AI 工作台数据：{getErrorMessage(error)}
        </CardContent>
      </Card>
    );
  }

  const analyzed = bookAi.spreads.some((s) => s.units.length > 0);

  return (
    <div className="space-y-6">
      {/* 顶部：流程说明 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="size-5 text-amber-500" />
            页面与 AI 工作台
          </CardTitle>
          <CardDescription>
            {book.page_count} 页 · 先分析整本故事并校对台词，为角色生成音色，再生成朗读并确认 Voice
            Ready。
          </CardDescription>
        </CardHeader>
        {!analyzed && (
          <CardContent>
            <p className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
              还没有分析故事。在下方「故事与角色」里点「分析整本故事」开始。
            </p>
          </CardContent>
        )}
      </Card>

      {/* 故事与角色卡片 */}
      <StoryAndCharactersCard bookId={book.id} bookAi={bookAi} />

      {/* 封面动画（D96）：与朗读、开页动画相互独立 */}
      <CoverAnimationCard book={book} bookAi={bookAi} />

      {/* 各类 AI 产物的进度和一键操作，是下方开页列表的总览（A4 在这里加"动画"一行） */}
      {analyzed && (
        <Card>
          <CardContent>
            <AudioPipelineRow bookId={book.id} bookAi={bookAi} />
          </CardContent>
        </Card>
      )}

      {/* 开页列表 */}
      <div className="space-y-6">
        {bookAi.spreads.map((spread) => (
          <SpreadCard
            key={spread.index}
            bookId={book.id}
            book={book}
            spread={spread}
            characters={bookAi.characters}
            onSetCover={onSetCover}
            isSettingCover={isSettingCover}
          />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// 朗读：进度 + 全部生成 + Voice Ready + 朗读设置
// ============================================================================

function AudioPipelineRow({ bookId, bookAi }: { bookId: string; bookAi: BookAi }) {
  const generateAll = useGenerateAllAudio(bookId);
  const updateAi = useUpdateBookAi(bookId);

  const allUnits = bookAi.spreads.flatMap((s) => s.units);
  const spoken = allUnits.filter((u) => u.lines.some((l) => l.text.trim()));
  const units = spoken.filter((u) => u.audio_enabled);
  const ready = units.filter((u) => u.audio_url).length;
  const outdated = units.filter((u) => u.audio_url && u.audio_outdated).length;
  const running = units.filter(
    (u) => u.audio_status === "queued" || u.audio_status === "running",
  ).length;
  const failed = units.filter((u) => u.audio_status === "failed").length;
  const disabled = spoken.length - units.length;

  const summary = [
    `已生成 ${ready} / ${units.length} 个单元`,
    running && `${running} 个生成中`,
    outdated && `${outdated} 个需要重新生成`,
    failed && `${failed} 个失败`,
    disabled && `${disabled} 个已关闭朗读`,
  ].filter(Boolean);

  const handleGenerateAll = () => {
    generateAll.mutate(undefined, {
      onSuccess: ({ queued }) =>
        toast.add(
          queued
            ? {
                title: `已加入 ${queued} 个单元`,
                description: "正在逐个生成朗读，每个单元约需十几秒…",
                type: "success",
              }
            : { title: "所有朗读都已是最新", type: "success" },
        ),
      onError: (err) =>
        toast.add({ title: "全部生成朗读失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  const handleReadOrderChange = (value: string) => {
    if (value !== "left_first" && value !== "right_first") return;
    updateAi.mutate(
      { read_order: value },
      {
        onSuccess: () => toast.add({ title: "已更新朗读顺序", type: "success" }),
        onError: (err) =>
          toast.add({ title: "更新朗读顺序失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted">
          <Volume2 className="size-4 text-muted-foreground" />
        </div>
        <Progress
          value={units.length ? (ready / units.length) * 100 : 0}
          aria-label="朗读生成进度"
          className="min-w-0 flex-1 gap-1.5"
        >
          <div className="flex w-full flex-wrap items-baseline gap-x-2 text-sm">
            <span className="font-medium">朗读</span>
            <span className="text-xs text-muted-foreground">{summary.join(" · ")}</span>
          </div>
        </Progress>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant="outline"
          onClick={handleGenerateAll}
          disabled={generateAll.isPending || running > 0}
          title="为未生成、失败或台词 / 音色已修改的单元生成朗读；关闭了朗读的开页跳过"
        >
          {running > 0 || generateAll.isPending ? (
            <Spinner className="size-4" />
          ) : (
            <Volume2 className="size-4" />
          )}
          {running > 0 ? "生成中…" : "全部生成"}
        </Button>
        <VoiceReadyControl bookId={bookId} bookAi={bookAi} />
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="icon" aria-label="朗读设置" title="朗读设置" />
            }
          >
            <MoreHorizontal />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuGroup>
              <DropdownMenuLabel>对开时的朗读顺序</DropdownMenuLabel>
              <DropdownMenuRadioGroup
                value={bookAi.read_order}
                onValueChange={handleReadOrderChange}
              >
                {READ_ORDER_ITEMS.map((item) => (
                  <DropdownMenuRadioItem key={item.value} value={item.value} closeOnClick>
                    {item.label}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

// ============================================================================
// Voice Ready 确认
// ============================================================================

function VoiceReadyControl({ bookId, bookAi }: { bookId: string; bookAi: BookAi }) {
  const setVoiceReady = useSetVoiceReady(bookId);
  const [open, setOpen] = useState(false);
  const isReady = bookAi.voice_ready_at !== null;

  const units = bookAi.spreads.flatMap((s) => s.units).filter((u) => u.audio_enabled);
  const withAudio = units.filter((u) => u.audio_url).length;
  const missing = units.filter((u) => !u.audio_url && u.lines.some((l) => l.text.trim())).length;
  const outdated = units.filter((u) => u.audio_url && u.audio_outdated).length;

  const handleConfirm = () => {
    setOpen(false);
    setVoiceReady.mutate(!isReady, {
      onSuccess: () =>
        toast.add({
          title: isReady ? "已取消 Voice Ready" : "已确认 Voice Ready",
          description: isReady ? "读者暂时听不到这本书的朗读" : "读者现在可以听这本书的朗读了",
          type: "success",
        }),
      onError: (err) =>
        toast.add({ title: "操作失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger
        render={
          isReady ? (
            <Button
              variant="outline"
              className="border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 hover:text-emerald-800"
              disabled={setVoiceReady.isPending}
            >
              <BadgeCheck className="size-4" />
              Voice Ready
            </Button>
          ) : (
            <Button
              variant="outline"
              disabled={setVoiceReady.isPending || withAudio === 0}
              title={withAudio === 0 ? "还没有生成任何朗读" : undefined}
            >
              <BadgeCheck className="size-4" />
              确认 Voice Ready
            </Button>
          )
        }
      />
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{isReady ? "取消 Voice Ready？" : "确认 Voice Ready？"}</AlertDialogTitle>
          <AlertDialogDescription>
            {isReady
              ? "取消后读者听不到这本书的朗读，书架上的音乐符号也会去掉；已生成的朗读会保留，可以随时再确认。"
              : `确认后，读者在书架上会看到音乐符号，阅读时有朗读的页面会出现小喇叭。已生成朗读的单元：${withAudio} 个。`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {!isReady && (missing > 0 || outdated > 0) && (
          <Alert className="text-xs">
            <CircleAlert />
            <AlertDescription className="text-xs">
              {missing > 0 && <p>还有 {missing} 个有台词的单元没有生成朗读，这些页面不会出现小喇叭。</p>}
              {outdated > 0 && (
                <p>{outdated} 个单元的台词或音色改过但还没重新生成，读者听到的是旧版朗读。</p>
              )}
            </AlertDescription>
          </Alert>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>{isReady ? "保留" : "再看看"}</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            variant={isReady ? "destructive" : "default"}
          >
            {isReady ? "取消 Voice Ready" : "确认"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// ============================================================================
// 封面动画（D96）：像魔法报纸上的照片，封面里的角色轻轻动
// ============================================================================

function CoverAnimationCard({ book, bookAi }: { book: AdminBookDetail; bookAi: BookAi }) {
  const cover = bookAi.cover;
  const updateAi = useUpdateBookAi(book.id);
  const generate = useGenerateCoverVideo(book.id);
  const setEnabled = useSetCoverVideoEnabled(book.id);
  const [motion, setMotion] = useState(cover.motion_prompt ?? "");
  const [savedMotion, setSavedMotion] = useState(cover.motion_prompt ?? "");
  // 服务器上的描述变了（如分析整本故事填了草稿）时，同步到输入框
  if ((cover.motion_prompt ?? "") !== savedMotion) {
    setSavedMotion(cover.motion_prompt ?? "");
    setMotion(cover.motion_prompt ?? "");
  }
  const isDirty = motion.trim() !== savedMotion.trim();
  const isBusy = generate.isPending || cover.status === "queued" || cover.status === "running";
  const hasVideo = cover.video_url !== null;
  const isEnabled = cover.enabled_at !== null;

  const handleSave = () => {
    updateAi.mutate(
      { cover_motion_prompt: motion.trim() },
      {
        onSuccess: () => toast.add({ title: "已保存动作描述", type: "success" }),
        onError: (err) =>
          toast.add({ title: "保存失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  const handleGenerate = () => {
    generate.mutate(undefined, {
      onSuccess: () =>
        toast.add({
          title: "封面动画已提交",
          description: "服务商生成一段 5 秒的视频，约需 1–3 分钟…",
          type: "success",
        }),
      onError: (err) =>
        toast.add({ title: "提交封面动画失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  const handleEnabled = (enabled: boolean) => {
    setEnabled.mutate(enabled, {
      onSuccess: () =>
        toast.add({
          title: enabled ? "已启用封面动画" : "已停用封面动画",
          description: enabled ? "读者在书架和阅读页封面上会看到它" : undefined,
          type: "success",
        }),
      onError: (err) =>
        toast.add({ title: "操作失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Wand2 className="size-4 text-primary" />
          封面动画
        </CardTitle>
        <CardDescription>
          像魔法报纸上会动的照片：封面里的角色轻轻眨眼、呼吸，画面其余部分不变，循环播放。
        </CardDescription>
        <CardAction>
          <Button
            size="sm"
            variant={hasVideo ? "outline" : "default"}
            onClick={handleGenerate}
            disabled={isBusy || isDirty || book.processing_status !== "ready"}
            title={isDirty ? "请先保存动作描述" : undefined}
          >
            {isBusy ? <Spinner className="size-4" /> : <Wand2 className="size-4" />}
            {isBusy ? "生成中…" : hasVideo ? "重新生成" : "生成封面动画"}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 sm:flex-row">
        {/* 预览：生成后循环播放，否则显示静态封面 */}
        <div className="w-48 shrink-0 space-y-1.5 self-center sm:self-start">
          {hasVideo ? (
            <>
              <div className="relative">
                <video
                  key={cover.video_url}
                  src={cover.video_url!}
                  poster={book.cover_url ?? undefined}
                  className="w-full rounded-md bg-muted ring-1 ring-border"
                  autoPlay
                  loop
                  muted
                  playsInline
                />
                <Badge className="pointer-events-none absolute top-1.5 left-1.5 bg-black/60 text-[10px] text-white">
                  <Play className="size-2.5" />
                  循环播放中
                </Badge>
              </div>
              <CoverVideoDialog url={cover.video_url!} poster={book.cover_url} />
            </>
          ) : book.cover_url ? (
            <img
              src={book.cover_url}
              alt="封面"
              className="w-full rounded-md bg-muted ring-1 ring-border"
            />
          ) : null}
        </div>

        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-xs font-medium">动作描述（画面里谁、怎样轻轻动）</span>
              {isDirty && (
                <Button size="xs" onClick={handleSave} disabled={updateAi.isPending}>
                  {updateAi.isPending && <Spinner className="size-3" />}
                  保存
                </Button>
              )}
            </div>
            <Textarea
              value={motion}
              onChange={(e) => setMotion(e.target.value)}
              placeholder="留空则由 AI 看封面自动写。例如：兔子波西眨眨眼、手指轻挠下巴，小老鼠皮普的尾巴轻轻摆动"
              className="min-h-[60px] resize-y text-xs"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <CoverStatusBadge status={cover.status} />
            {hasVideo && cover.resolution && (
              <span className="text-xs text-muted-foreground">5 秒 · {cover.resolution}</span>
            )}
            {hasVideo && cover.frame_changed && (
              <Badge
                variant="outline"
                className="border-amber-200 bg-amber-50 text-[10px] text-amber-700"
              >
                封面已更换，需要重新生成
              </Badge>
            )}
            {hasVideo && !cover.frame_changed && cover.outdated && (
              <Badge
                variant="outline"
                className="border-amber-200 bg-amber-50 text-[10px] text-amber-700"
                title="动作描述、模型或清晰度在生成之后改过"
              >
                需要重新生成
              </Badge>
            )}
          </div>

          {cover.status === "failed" && cover.error && (
            <Alert variant="destructive" className="px-2 py-1.5 text-xs">
              <CircleAlert />
              <AlertDescription className="text-xs">{cover.error}</AlertDescription>
            </Alert>
          )}

          <label
            className={cn(
              "flex w-fit items-center gap-2 text-sm",
              hasVideo && !cover.frame_changed ? "cursor-pointer" : "text-muted-foreground",
            )}
          >
            <Switch
              checked={isEnabled}
              onCheckedChange={handleEnabled}
              disabled={
                setEnabled.isPending || (!isEnabled && (!hasVideo || cover.frame_changed))
              }
            />
            在书架和阅读页封面上播放
          </label>
        </div>
      </CardContent>
    </Card>
  );
}

/** 放大预览封面动画（带播放控制），小图里不容易看清动作 */
function CoverVideoDialog({ url, poster }: { url: string; poster: string | null }) {
  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button size="xs" variant="outline" className="w-full">
            <Maximize2 className="size-3" />
            放大预览
          </Button>
        }
      />
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>封面动画预览</DialogTitle>
          <DialogDescription>5 秒一段循环播放；首尾帧就是封面原图，所以接缝处看不出跳变。</DialogDescription>
        </DialogHeader>
        <video
          src={url}
          poster={poster ?? undefined}
          className="max-h-[70vh] w-full rounded-md bg-muted object-contain"
          autoPlay
          loop
          muted
          playsInline
          controls
        />
      </DialogContent>
    </Dialog>
  );
}

function CoverStatusBadge({ status }: { status: CoverVideo["status"] }) {
  if (status === "queued" || status === "running") {
    return (
      <Badge variant="outline" className="border-amber-200 bg-amber-50 text-[10px] text-amber-700">
        {status === "queued" ? "排队中" : "生成中，约需 1–3 分钟"}
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge variant="destructive" className="text-[10px]">
        生成失败
      </Badge>
    );
  }
  if (status === "ready") {
    return (
      <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-[10px] text-emerald-700">
        已生成
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-[10px] text-muted-foreground">
      未生成
    </Badge>
  );
}

// ============================================================================
// 分析整本故事（放在"故事与角色"卡片右上角：它生成的就是故事、角色和全部草稿）
// ============================================================================

function AnalyzeBookButton({ bookId, bookAi }: { bookId: string; bookAi: BookAi }) {
  const analyze = useAnalyzeBook(bookId);
  const [open, setOpen] = useState(false);
  const isAnalyzing =
    analyze.isPending || bookAi.running_jobs.some((j) => j.type === "ai_analyze_book");
  const analyzed = bookAi.spreads.some((s) => s.units.length > 0);

  const handleStart = () => {
    setOpen(false);
    analyze.mutate(undefined, {
      onSuccess: () =>
        toast.add({
          title: "故事分析任务已提交",
          description: "正在由视觉大模型通读全部页面，约需几分钟…",
          type: "success",
        }),
      onError: (err) =>
        toast.add({ title: "提交分析任务失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger
        render={
          <Button size="sm" variant={analyzed ? "outline" : "default"} disabled={isAnalyzing}>
            {isAnalyzing ? <Spinner className="size-4" /> : <Sparkles className="size-4" />}
            {isAnalyzing ? "分析故事中…" : analyzed ? "重新分析整本故事" : "分析整本故事"}
          </Button>
        }
      />
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{analyzed ? "重新分析整本故事？" : "分析整本故事？"}</AlertDialogTitle>
          <AlertDialogDescription>
            视觉大模型将通读全书所有页面，提取故事梗概、角色设定、逐页朗读稿（保留原文并适度补充）和微动作草稿，约需几分钟。
            {analyzed && "已有的草稿会被覆盖，角色已生成的音色和朗读也会一并清除。"}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction onClick={handleStart}>开始分析</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// ============================================================================
// 故事与角色管理卡片
// ============================================================================

function StoryAndCharactersCard({ bookId, bookAi }: { bookId: string; bookAi: BookAi }) {
  const updateAi = useUpdateBookAi(bookId);
  const [story, setStory] = useState(bookAi.story || "");
  const [isAddingChar, setIsAddingChar] = useState(false);

  useEffect(() => {
    setStory(bookAi.story || "");
  }, [bookAi.story]);

  const handleSaveStory = () => {
    updateAi.mutate(
      { story },
      {
        onSuccess: () => toast.add({ title: "故事大纲已保存", type: "success" }),
        onError: (err) =>
          toast.add({ title: "保存故事大纲失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  const isStoryDirty = story !== (bookAi.story || "");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BookOpen className="size-4 text-primary" />
          故事与角色
        </CardTitle>
        <CardDescription>
          故事整体背景和大纲，以及提取出的说话角色。台词识别与朗读合成将参考此设定。
        </CardDescription>
        <CardAction>
          <AnalyzeBookButton bookId={bookId} bookAi={bookAi} />
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 故事大纲 */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">故事大纲</span>
            {isStoryDirty && (
              <Button size="xs" onClick={handleSaveStory} disabled={updateAi.isPending}>
                {updateAi.isPending && <Spinner className="size-3" />}
                保存大纲
              </Button>
            )}
          </div>
          <Textarea
            value={story}
            onChange={(e) => setStory(e.target.value)}
            placeholder="点击上方【分析整本故事】自动提取故事梗概，或在此手动输入…"
            className="min-h-[80px] resize-y text-sm"
          />
        </div>

        {/* 角色表 */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium">故事角色（{bookAi.characters.length}）</span>
            <CharacterCreateDialog
              bookId={bookId}
              open={isAddingChar}
              onOpenChange={setIsAddingChar}
            />
          </div>

          {bookAi.characters.length === 0 ? (
            <p className="rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
              尚未提取角色。分析整本故事后将自动列出所有出场角色。
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
              {bookAi.characters.map((char) => (
                <CharacterItem key={char.id} bookId={bookId} character={char} />
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function CharacterItem({ bookId, character }: { bookId: string; character: Character }) {
  const deleteChar = useDeleteCharacter(bookId);
  const [isEditing, setIsEditing] = useState(false);

  return (
    <div className="flex flex-col justify-between rounded-lg border bg-card p-3 shadow-xs">
      <div>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{character.name}</span>
            {character.is_narrator && (
              <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
                旁白
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              size="icon-xs"
              variant="ghost"
              onClick={() => setIsEditing(true)}
              title="编辑角色"
            >
              <Edit2 className="size-3" />
            </Button>
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    className="text-muted-foreground hover:text-destructive"
                    title="删除角色"
                  >
                    <Trash2 className="size-3" />
                  </Button>
                }
              />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>删除角色「{character.name}」？</AlertDialogTitle>
                  <AlertDialogDescription>
                    已分配给该角色的台词将改由旁白朗读，该角色的音色也会一并删除。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() =>
                      deleteChar.mutate(character.id, {
                        onSuccess: () => toast.add({ title: "已删除角色", type: "success" }),
                        onError: (err) =>
                          toast.add({
                            title: "删除角色失败",
                            description: getErrorMessage(err),
                            type: "error",
                          }),
                      })
                    }
                  >
                    删除
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
          {character.voice_prompt || "（无音色描述）"}
        </p>
      </div>

      <CharacterVoicePanel bookId={bookId} character={character} />

      <CharacterEditDialog
        bookId={bookId}
        character={character}
        open={isEditing}
        onOpenChange={setIsEditing}
      />
    </div>
  );
}

// 同一时间只播放一段试听
let playingPreview: HTMLAudioElement | null = null;

function CharacterVoicePanel({ bookId, character }: { bookId: string; character: Character }) {
  const designVoice = useDesignVoice(bookId);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { voice, voice_status: status } = character;
  const isBusy = status === "queued" || status === "running" || designVoice.isPending;
  const hasPrompt = Boolean(character.voice_prompt?.trim());

  const handleDesign = () => {
    setConfirmOpen(false);
    designVoice.mutate(character.id, {
      onSuccess: () =>
        toast.add({
          title: "音色生成任务已提交",
          description: `正在为「${character.name}」设计音色，约需十几秒…`,
          type: "success",
        }),
      onError: (err) =>
        toast.add({ title: "提交音色任务失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  const designButton = (
    <Button
      size="xs"
      variant="outline"
      disabled={isBusy || !hasPrompt}
      title={hasPrompt ? undefined : "请先填写音色描述"}
      onClick={voice ? undefined : handleDesign}
    >
      {isBusy ? <Spinner className="size-3" /> : <AudioLines className="size-3" />}
      {voice ? "重新生成" : "生成音色"}
    </Button>
  );

  return (
    <div className="mt-3 space-y-2 border-t pt-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1">
          <VoiceStatusBadge status={status} />
          {voice && character.voice_outdated && status !== "queued" && status !== "running" && (
            <Badge
              variant="outline"
              className="border-amber-200 bg-amber-50 text-[10px] text-amber-700"
              title="音色描述在生成音色后改过，重新生成后才会生效"
            >
              描述已修改
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          {voice && (
            <AudioPreviewButton url={voice.preview_url} label={`「${character.name}」的音色`} />
          )}
          {voice ? (
            <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
              <AlertDialogTrigger render={designButton} />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>重新生成「{character.name}」的音色？</AlertDialogTitle>
                  <AlertDialogDescription>
                    将按当前的音色描述重新设计，新音色会替换现在的音色；已经生成的朗读不受影响，重新生成朗读时才会用上新音色。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction onClick={handleDesign}>重新生成</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : (
            designButton
          )}
        </div>
      </div>
      {status === "failed" && character.voice_error && (
        <Alert variant="destructive" className="px-2 py-1.5 text-xs">
          <CircleAlert />
          <AlertDescription className="text-xs">{character.voice_error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}

function VoiceStatusBadge({ status }: { status: Character["voice_status"] }) {
  if (status === "ready") {
    return (
      <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-[10px] text-emerald-700">
        音色已就绪
      </Badge>
    );
  }
  if (status === "queued" || status === "running") {
    return (
      <Badge variant="outline" className="border-amber-200 bg-amber-50 text-[10px] text-amber-700">
        {status === "queued" ? "音色排队中" : "音色生成中"}
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge variant="destructive" className="text-[10px]">
        音色生成失败
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-[10px] text-muted-foreground">
      未生成音色
    </Badge>
  );
}

function AudioPreviewButton({ url, label }: { url: string; label: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // 地址变了（重新生成）或卸载时停止播放
  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, [url]);

  const toggle = () => {
    if (isPlaying) {
      audioRef.current?.pause();
      return;
    }
    if (!audioRef.current) {
      const audio = new Audio(url);
      audio.onplay = () => setIsPlaying(true);
      audio.onpause = () => setIsPlaying(false);
      audio.onended = () => setIsPlaying(false);
      audioRef.current = audio;
    }
    const audio = audioRef.current;
    if (playingPreview && playingPreview !== audio) playingPreview.pause();
    playingPreview = audio;
    audio.currentTime = 0;
    audio.play().catch((err) => {
      setIsPlaying(false);
      toast.add({ title: "无法播放试听", description: getErrorMessage(err), type: "error" });
    });
  };

  return (
    <Button
      size="icon-xs"
      variant="ghost"
      onClick={toggle}
      title={isPlaying ? "停止试听" : `试听${label}`}
    >
      {isPlaying ? <Square className="size-3" /> : <Play className="size-3" />}
    </Button>
  );
}

function CharacterCreateDialog({
  bookId,
  open,
  onOpenChange,
}: {
  bookId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createChar = useCreateCharacter(bookId);
  const [name, setName] = useState("");
  const [voicePrompt, setVoicePrompt] = useState("");
  const [isNarrator, setIsNarrator] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    createChar.mutate(
      { name: name.trim(), voice_prompt: voicePrompt.trim() || null, is_narrator: isNarrator },
      {
        onSuccess: () => {
          toast.add({ title: "已添加角色", type: "success" });
          setName("");
          setVoicePrompt("");
          setIsNarrator(false);
          onOpenChange(false);
        },
        onError: (err) =>
          toast.add({ title: "添加角色失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger
        render={
          <Button size="xs" variant="outline">
            <Plus className="size-3" />
            添加角色
          </Button>
        }
      />
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>添加新角色</DialogTitle>
            <DialogDescription>为绘本添加故事角色，用于分配台词和设计朗读音色。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Field>
              <FieldLabel>角色名称</FieldLabel>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：波西、大怪兽"
                required
              />
            </Field>
            <Field>
              <FieldLabel>音色描述提示词</FieldLabel>
              <Textarea
                value={voicePrompt}
                onChange={(e) => setVoicePrompt(e.target.value)}
                placeholder="例如：5岁左右的小女孩，声音清脆软糯，语速稍慢"
                className="text-sm"
              />
            </Field>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={createChar.isPending}
            >
              取消
            </Button>
            <Button type="submit" disabled={!name.trim() || createChar.isPending}>
              {createChar.isPending && <Spinner className="size-3" />}
              添加
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CharacterEditDialog({
  bookId,
  character,
  open,
  onOpenChange,
}: {
  bookId: string;
  character: Character;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const updateChar = useUpdateCharacter(bookId);
  const [name, setName] = useState(character.name);
  const [voicePrompt, setVoicePrompt] = useState(character.voice_prompt || "");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    updateChar.mutate(
      { id: character.id, name: name.trim(), voice_prompt: voicePrompt.trim() || null },
      {
        onSuccess: () => {
          toast.add({ title: "已更新角色", type: "success" });
          onOpenChange(false);
        },
        onError: (err) =>
          toast.add({ title: "更新角色失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>编辑角色「{character.name}」</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Field>
              <FieldLabel>角色名称</FieldLabel>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </Field>
            <Field>
              <FieldLabel>音色描述提示词</FieldLabel>
              <Textarea
                value={voicePrompt}
                onChange={(e) => setVoicePrompt(e.target.value)}
                className="text-sm"
              />
            </Field>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={updateChar.isPending}
            >
              取消
            </Button>
            <Button type="submit" disabled={!name.trim() || updateChar.isPending}>
              {updateChar.isPending && <Spinner className="size-3" />}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// 开页与生成单元卡片
// ============================================================================

interface SpreadCardProps {
  bookId: string;
  book: AdminBookDetail;
  spread: Spread;
  characters: Character[];
  onSetCover: (index: number) => void;
  isSettingCover: boolean;
}

function SpreadCard({
  bookId,
  book,
  spread,
  characters,
  onSetCover,
  isSettingCover,
}: SpreadCardProps) {
  const updateSpreadMode = useUpdateSpreadMode(bookId);
  const updateSwitches = useUpdateSpreadSwitches(bookId);
  const generateSpreadAudio = useGenerateSpreadAudio(bookId);
  const hasTwoPages = spread.left_page_index !== null && spread.right_page_index !== null;
  // 开页的第一页：接口用它指代开页
  const firstPage = (spread.left_page_index ?? spread.right_page_index)!;
  const hasUnits = spread.units.length > 0;

  const spokenUnits = spread.units.filter((u) => u.lines.some((l) => l.text.trim()));
  const spreadMissingVoices = [
    ...new Set(spokenUnits.flatMap((u) => missingVoiceNames(u, characters))),
  ];
  const isSpreadAudioBusy =
    generateSpreadAudio.isPending ||
    spread.units.some((u) => u.audio_status === "queued" || u.audio_status === "running");

  const handleSwitch = (field: "audio_enabled" | "video_enabled", enabled: boolean) => {
    const label = field === "audio_enabled" ? "朗读" : "动画";
    updateSwitches.mutate(
      { firstPage, [field]: enabled },
      {
        onSuccess: () =>
          toast.add({
            title: enabled ? `已打开这个开页的${label}` : `已关闭这个开页的${label}`,
            description: enabled
              ? undefined
              : `一键生成时会跳过，阅读时也不${label === "朗读" ? "朗读" : "播放动画"}；已生成的内容保留。`,
            type: "success",
          }),
        onError: (err) =>
          toast.add({ title: "设置失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  const handleGenerateSpreadAudio = () => {
    generateSpreadAudio.mutate(firstPage, {
      onError: (err) =>
        toast.add({ title: "生成本开页朗读失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  const handleToggleMode = (mode: "separate" | "merged") => {
    if (!hasTwoPages || mode === spread.mode) return;
    updateSpreadMode.mutate(
      { firstPage: spread.left_page_index!, mode },
      {
        onSuccess: () =>
          toast.add({
            title: mode === "merged" ? "已切换为合并生成" : "已切换为分别生成",
            type: "success",
          }),
        onError: (err) =>
          toast.add({ title: "切换失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  const getPageObj = (pageIndex: number | null) => {
    if (pageIndex === null) return null;
    return book.pages.find((p) => p.index === pageIndex);
  };

  const leftPage = getPageObj(spread.left_page_index);
  const rightPage = getPageObj(spread.right_page_index);

  // 标示开页名
  let spreadTitle = `开页 ${spread.index + 1}`;
  if (spread.left_page_index === null && spread.right_page_index === 0) {
    spreadTitle += "（封面）";
  } else if (hasTwoPages) {
    spreadTitle += `（第 ${spread.left_page_index! + 1}–${spread.right_page_index! + 1} 页）`;
  } else {
    const singleIndex = (spread.left_page_index ?? spread.right_page_index)! + 1;
    spreadTitle += `（第 ${singleIndex} 页）`;
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 border-b bg-muted/40 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-semibold text-sm">{spreadTitle}</span>
          {spread.mode === "merged" && (
            <Badge variant="outline" className="bg-background text-xs">
              <Combine className="mr-1 size-3 text-primary" />
              左右合并生成
            </Badge>
          )}
          {hasUnits && (
            <div className="flex items-center gap-3 text-xs">
              <label className="flex cursor-pointer items-center gap-1.5">
                <Switch
                  size="sm"
                  checked={spread.audio_enabled}
                  onCheckedChange={(checked) => handleSwitch("audio_enabled", checked)}
                  disabled={updateSwitches.isPending}
                />
                <Volume2 className="size-3.5 text-muted-foreground" />
                朗读
              </label>
              <label
                className="flex cursor-pointer items-center gap-1.5"
                title="关闭后不生成动画（动画功能开发中）"
              >
                <Switch
                  size="sm"
                  checked={spread.video_enabled}
                  onCheckedChange={(checked) => handleSwitch("video_enabled", checked)}
                  disabled={updateSwitches.isPending}
                />
                <Film className="size-3.5 text-muted-foreground" />
                动画
              </label>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {spread.audio_enabled && spokenUnits.length > 0 && (
            <Button
              size="xs"
              variant="outline"
              className="h-7 bg-background"
              onClick={handleGenerateSpreadAudio}
              disabled={isSpreadAudioBusy || spreadMissingVoices.length > 0}
              title={
                spreadMissingVoices.length > 0
                  ? `请先为「${spreadMissingVoices.join("」「")}」生成音色`
                  : "为这个开页的所有单元生成朗读（使用已保存的台词）"
              }
            >
              {isSpreadAudioBusy ? <Spinner className="size-3" /> : <Volume2 className="size-3" />}
              {spread.units.some((u) => u.audio_url) ? "重新生成本开页朗读" : "生成本开页朗读"}
            </Button>
          )}

          {hasTwoPages && (
            <div className="flex items-center rounded-lg border bg-background p-0.5 shadow-2xs">
              <Button
                size="xs"
                variant={spread.mode === "separate" ? "secondary" : "ghost"}
                className="h-7 px-2.5 text-xs"
                onClick={() => handleToggleMode("separate")}
                disabled={updateSpreadMode.isPending}
              >
                <Split className="mr-1 size-3" />
                分别生成
              </Button>
              <Button
                size="xs"
                variant={spread.mode === "merged" ? "secondary" : "ghost"}
                className="h-7 px-2.5 text-xs"
                onClick={() => handleToggleMode("merged")}
                disabled={updateSpreadMode.isPending}
              >
                <Combine className="mr-1 size-3" />
                合并生成
              </Button>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="grid grid-cols-1 gap-6 p-4 md:grid-cols-12 md:p-6">
        {/* 左侧：画面缩略图 */}
        <div className="md:col-span-4 lg:col-span-3">
          <div className="grid grid-cols-2 gap-2">
            {/* 左页 */}
            {spread.left_page_index === null ? (
              <div className="aspect-[3/4] rounded-sm border border-dashed bg-muted/20" />
            ) : leftPage ? (
              <PageThumb
                page={leftPage}
                isCover={leftPage.index === book.cover_page_index}
                disabled={isSettingCover}
                onSetCover={() => onSetCover(leftPage.index)}
              />
            ) : null}

            {/* 右页 */}
            {rightPage ? (
              <PageThumb
                page={rightPage}
                isCover={rightPage.index === book.cover_page_index}
                disabled={isSettingCover}
                onSetCover={() => onSetCover(rightPage.index)}
              />
            ) : (
              <div className="aspect-[3/4] rounded-sm border border-dashed bg-muted/20" />
            )}
          </div>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            {spread.mode === "merged" ? "左右两页拼为同一场景" : "单页独立预览"}
          </p>
        </div>

        {/* 右侧：生成单元草稿区 */}
        <div className="space-y-4 md:col-span-8 lg:col-span-9">
          {spread.units.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
              <Sparkles className="size-8 text-muted-foreground/60" />
              <p className="mt-2 text-sm text-muted-foreground">该开页暂无生成单元草稿</p>
              <p className="mt-1 text-xs text-muted-foreground">
                点击上方【分析整本故事】即可自动生成全书草稿
              </p>
            </div>
          ) : (
            spread.units.map((unit) => (
              <UnitDraftEditor
                key={unit.id}
                bookId={bookId}
                unit={unit}
                characters={characters}
                spread={spread}
              />
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// 单个单元草稿编辑组件
// ============================================================================

interface UnitDraftEditorProps {
  bookId: string;
  unit: AiUnit;
  characters: Character[];
  spread: Spread;
}

function UnitDraftEditor({ bookId, unit, characters, spread }: UnitDraftEditorProps) {
  const updateUnit = useUpdateAiUnit(bookId);
  const draftUnit = useDraftAiUnit(bookId);

  const [lines, setLines] = useState<AiLineItem[]>(unit.lines || []);
  const [motionPrompt, setMotionPrompt] = useState(unit.motion_prompt || "");

  useEffect(() => {
    setLines(unit.lines || []);
    setMotionPrompt(unit.motion_prompt || "");
  }, [unit.lines, unit.motion_prompt]);

  const isLinesDirty = JSON.stringify(lines) !== JSON.stringify(unit.lines || []);
  const isPromptDirty = (motionPrompt || "") !== (unit.motion_prompt || "");
  const isDirty = isLinesDirty || isPromptDirty;

  const handleSave = () => {
    updateUnit.mutate(
      { unitId: unit.id, lines, motion_prompt: motionPrompt.trim() || null },
      {
        onSuccess: () => toast.add({ title: "已保存草稿", type: "success" }),
        onError: (err) =>
          toast.add({ title: "保存草稿失败", description: getErrorMessage(err), type: "error" }),
      },
    );
  };

  const handleRedraft = () => {
    draftUnit.mutate(unit.id, {
      onSuccess: () =>
        toast.add({
          title: "重写任务已提交",
          description: "大模型正在根据全书背景重新构思该单元…",
          type: "success",
        }),
      onError: (err) =>
        toast.add({ title: "提交重写失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  const narratorId = characters.find((c) => c.is_narrator)?.id ?? null;
  const speakerItems = characters.map((c) => ({ value: c.id, label: c.name }));

  const handleAddLine = () => {
    const defaultSpeaker =
      characters.find((c) => c.is_narrator)?.id ?? (characters[0]?.id ?? null);
    setLines([...lines, { character_id: defaultSpeaker, text: "", added: true }]);
  };

  const handleLineChange = (index: number, field: keyof AiLineItem, val: any) => {
    const next = [...lines];
    next[index] = { ...next[index], [field]: val };
    setLines(next);
  };

  const handleDeleteLine = (index: number) => {
    setLines(lines.filter((_, i) => i !== index));
  };

  // 单元标签
  let unitLabel = `单元`;
  if (unit.page_count === 2) {
    unitLabel += `（合并对开）`;
  } else if (unit.first_page_index === spread.left_page_index) {
    unitLabel += `（左页 · 第 ${unit.first_page_index + 1} 页）`;
  } else {
    unitLabel += `（右页 · 第 ${unit.first_page_index + 1} 页）`;
  }

  return (
    <div className="rounded-lg border bg-muted/20 p-4">
      {/* 单元头部 */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b pb-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-xs text-foreground/90">{unitLabel}</span>
          <div className="flex items-center gap-1.5">
            <VideoStatusBadge status={unit.video_status} />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="xs"
            variant="outline"
            onClick={handleRedraft}
            disabled={draftUnit.isPending}
            title="让大模型针对本单元重新编写台词与动作"
          >
            {draftUnit.isPending ? (
              <Spinner className="size-3" />
            ) : (
              <RefreshCw className="size-3" />
            )}
            重新写草稿
          </Button>

          {isDirty && (
            <Button size="xs" onClick={handleSave} disabled={updateUnit.isPending}>
              {updateUnit.isPending && <Spinner className="size-3" />}
              保存草稿
            </Button>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {/* 台词编辑 */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5 font-medium text-xs">
              <Volume2 className="size-3.5 text-muted-foreground" />
              台词与说话人（逐行分配音色）
            </span>
            <Button size="xs" variant="ghost" onClick={handleAddLine} className="h-6 text-[11px]">
              <Plus className="mr-0.5 size-3" />
              添加一行
            </Button>
          </div>

          {lines.length === 0 ? (
            <p className="rounded-sm border border-dashed py-2 text-center text-xs text-muted-foreground">
              （画面无文字，不生成朗读）
            </p>
          ) : (
            <div className="space-y-2">
              {lines.map((line, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <Select
                    items={speakerItems}
                    // 没指定说话人的行由旁白读（与后端生成朗读时一致）
                    value={line.character_id ?? narratorId}
                    onValueChange={(val) => handleLineChange(idx, "character_id", val)}
                  >
                    <SelectTrigger className="w-[110px] shrink-0 text-xs">
                      <SelectValue placeholder="说话人" />
                    </SelectTrigger>
                    <SelectContent>
                      {speakerItems.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {line.added && (
                    <Badge
                      variant="secondary"
                      className="shrink-0 px-1.5 text-[10px]"
                      title="书上原文之外补充的内容"
                    >
                      补充
                    </Badge>
                  )}
                  <Input
                    value={line.text}
                    onChange={(e) => handleLineChange(idx, "text", e.target.value)}
                    placeholder="输入该行台词…"
                    className="h-8 text-xs"
                  />

                  <Button
                    size="icon-xs"
                    variant="ghost"
                    onClick={() => handleDeleteLine(idx)}
                    className="shrink-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 朗读 */}
        <UnitAudioRow bookId={bookId} unit={unit} characters={characters} isDirty={isDirty} />

        {/* 动作描述编辑 */}
        <div>
          <span className="mb-1.5 flex items-center gap-1.5 font-medium text-xs">
            <Film className="size-3.5 text-muted-foreground" />
            动作描述（循环动画提示词）
          </span>
          <Textarea
            value={motionPrompt}
            onChange={(e) => setMotionPrompt(e.target.value)}
            placeholder="例如：大怪兽慢慢眨眼，尾巴轻轻摆动，动作轻柔缓慢，最后回到初始姿态…"
            className="min-h-[60px] resize-y text-xs"
          />
        </div>
      </div>
    </div>
  );
}

function UnitAudioRow({
  bookId,
  unit,
  characters,
  isDirty,
}: {
  bookId: string;
  unit: AiUnit;
  characters: Character[];
  isDirty: boolean;
}) {
  const generateAudio = useGenerateUnitAudio(bookId);
  const isBusy =
    unit.audio_status === "queued" || unit.audio_status === "running" || generateAudio.isPending;

  const missingVoices = missingVoiceNames(unit, characters);
  const hasLines = unit.lines.some((line) => line.text.trim());

  let blockedReason: string | null = null;
  if (!hasLines) blockedReason = "没有台词，不需要朗读";
  else if (isDirty) blockedReason = "请先保存草稿";
  else if (missingVoices.length) blockedReason = `请先为「${missingVoices.join("」「")}」生成音色`;

  const handleGenerate = () => {
    generateAudio.mutate(unit.id, {
      onError: (err) =>
        toast.add({ title: "提交朗读任务失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  if (!hasLines && !unit.audio_url) return null;

  if (!unit.audio_enabled) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
        <Volume2 className="size-3.5" />
        这个开页已关闭朗读：一键生成时跳过，阅读时也不朗读
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-background px-3 py-2">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="flex items-center gap-1.5 font-medium">
            <Volume2 className="size-3.5 text-muted-foreground" />
            朗读
          </span>
          <AudioStatusBadge status={unit.audio_status} outdated={unit.audio_outdated} />
          {unit.audio_url && unit.audio_duration_ms !== null && (
            <span className="text-muted-foreground tabular-nums">
              {(unit.audio_duration_ms / 1000).toFixed(1)} 秒
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {unit.audio_url && <AudioPreviewButton url={unit.audio_url} label="朗读" />}
          <Button
            size="xs"
            variant="outline"
            onClick={handleGenerate}
            disabled={isBusy || blockedReason !== null}
            title={blockedReason ?? undefined}
          >
            {isBusy ? <Spinner className="size-3" /> : <Volume2 className="size-3" />}
            {unit.audio_url ? "重新生成朗读" : "生成朗读"}
          </Button>
        </div>
      </div>
      {blockedReason && hasLines && !isBusy && (
        <p className="text-xs text-muted-foreground">{blockedReason}</p>
      )}
      {unit.audio_status === "failed" && unit.audio_error && (
        <Alert variant="destructive" className="px-2 py-1.5 text-xs">
          <CircleAlert />
          <AlertDescription className="text-xs">{unit.audio_error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}

/** 单元里还没有音色的说话人（与后端一致：没指定或已删除的说话人由旁白读，空行跳过） */
function missingVoiceNames(unit: AiUnit, characters: Character[]) {
  const narrator = characters.find((c) => c.is_narrator);
  const names = unit.lines
    .filter((line) => line.text.trim())
    .map((line) => characters.find((c) => c.id === line.character_id) ?? narrator)
    .filter((c): c is Character => c !== undefined && !c.voice)
    .map((c) => c.name);
  return [...new Set(names)];
}

function AudioStatusBadge({ status, outdated }: { status: AiUnit["audio_status"]; outdated: boolean }) {
  if (status === "queued" || status === "running") {
    return (
      <Badge variant="outline" className="border-amber-200 bg-amber-50 text-[10px] text-amber-700">
        {status === "queued" ? "排队中" : "生成中"}
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge variant="destructive" className="text-[10px]">
        生成失败
      </Badge>
    );
  }
  if (status === "ready" && outdated) {
    return (
      <Badge
        variant="outline"
        className="border-amber-200 bg-amber-50 text-[10px] text-amber-700"
        title="台词或音色在生成朗读之后改过"
      >
        需要重新生成
      </Badge>
    );
  }
  if (status === "ready") {
    return (
      <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-[10px] text-emerald-700">
        已就绪
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-[10px] text-muted-foreground">
      未生成
    </Badge>
  );
}

function VideoStatusBadge({ status }: { status: string }) {
  if (status === "ready") {
    return (
      <Badge variant="outline" className="border-blue-200 bg-blue-50 text-[10px] text-blue-700">
        动画已就绪
      </Badge>
    );
  }
  if (status === "running" || status === "queued") {
    return (
      <Badge variant="outline" className="border-amber-200 bg-amber-50 text-[10px] text-amber-700">
        动画生成中
      </Badge>
    );
  }
  return null;
}

function PageThumb({
  page,
  isCover,
  disabled,
  onSetCover,
}: {
  page: BookPage;
  isCover: boolean;
  disabled: boolean;
  onSetCover: () => void;
}) {
  return (
    <figure className="group/thumb relative self-start">
      <img
        src={page.url}
        alt={`第 ${page.index + 1} 页`}
        loading="lazy"
        className={cn(
          "w-full rounded-sm bg-muted ring-1 ring-border",
          isCover && "ring-2 ring-primary",
        )}
        style={{ aspectRatio: `${page.width} / ${page.height}` }}
      />
      {isCover ? (
        <Badge className="absolute top-1.5 left-1.5 text-[10px]">封面</Badge>
      ) : (
        <Button
          size="xs"
          variant="secondary"
          disabled={disabled}
          onClick={onSetCover}
          className="absolute top-1.5 left-1.5 opacity-0 shadow-xs transition-opacity group-hover/thumb:opacity-100 focus-visible:opacity-100"
        >
          设为封面
        </Button>
      )}
      <figcaption className="mt-1 text-center text-xs text-muted-foreground tabular-nums">
        {page.index + 1}
      </figcaption>
    </figure>
  );
}

import { useEffect, useState } from "react";
import {
  BookOpen,
  Combine,
  Edit2,
  Film,
  Plus,
  RefreshCw,
  Sparkles,
  Split,
  Trash2,
  Volume2,
} from "lucide-react";
import { cn } from "cn";
import {
  useAnalyzeBook,
  useBookAi,
  useCreateCharacter,
  useDeleteCharacter,
  useDraftAiUnit,
  useUpdateAiUnit,
  useUpdateBookAi,
  useUpdateCharacter,
  useUpdateSpreadMode,
} from "@/api/ai";
import type {
  AdminBookDetail,
  AiLineItem,
  AiUnit,
  BookPage,
  Character,
  Spread,
} from "@/api/types";
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
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { getErrorMessage } from "@/lib/api";

interface AiWorkbenchProps {
  book: AdminBookDetail;
  onSetCover: (index: number) => void;
  isSettingCover: boolean;
}

export function AiWorkbench({ book, onSetCover, isSettingCover }: AiWorkbenchProps) {
  const { data: bookAi, isPending, error } = useBookAi(book.id);
  const analyze = useAnalyzeBook(book.id);
  const updateAi = useUpdateBookAi(book.id);

  const isAnalyzing = Boolean(
    bookAi?.running_jobs?.some((j) => j.type === "ai_analyze_book" && j.status !== "failed"),
  );
  const [analyzeOpen, setAnalyzeOpen] = useState(false);

  const handleStartAnalysis = () => {
    setAnalyzeOpen(false);
    analyze.mutate(undefined, {
      onSuccess: () =>
        toast.add({
          title: "故事分析任务已提交",
          description: "正在由视觉大模型通读全部页面，约需 1–2 分钟…",
          type: "success",
        }),
      onError: (err) =>
        toast.add({ title: "提交分析任务失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  const handleReadOrderChange = (value: string | null) => {
    if (value === "left_first" || value === "right_first") {
      updateAi.mutate(
        { read_order: value },
        {
          onSuccess: () => toast.add({ title: "已更新朗读顺序", type: "success" }),
          onError: (err) =>
            toast.add({
              title: "更新朗读顺序失败",
              description: getErrorMessage(err),
              type: "error",
            }),
        },
      );
    }
  };

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

  return (
    <div className="space-y-6">
      {/* 顶部工具栏 */}
      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="size-5 text-amber-500" />
              页面与 AI 工作台（{book.page_count} 页）
            </CardTitle>
            <CardDescription className="mt-1">
              通读全书分析角色与大纲，按开页分别/合并生成台词与微动作草稿。
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">朗读顺序：</span>
              <Select
                value={bookAi.read_order}
                onValueChange={handleReadOrderChange}
                disabled={updateAi.isPending}
              >
                <SelectTrigger className="w-[120px] text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="left_first">先左后右</SelectItem>
                  <SelectItem value="right_first">先右后左</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <AlertDialog open={analyzeOpen} onOpenChange={setAnalyzeOpen}>
              <AlertDialogTrigger
                render={
                  <Button variant="default" disabled={isAnalyzing || analyze.isPending}>
                    {isAnalyzing || analyze.isPending ? (
                      <>
                        <Spinner className="size-4" />
                        分析故事中…
                      </>
                    ) : (
                      <>
                        <Sparkles className="size-4" />
                        分析整本故事
                      </>
                    )}
                  </Button>
                }
              />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>分析整本故事？</AlertDialogTitle>
                  <AlertDialogDescription>
                    视觉大模型将通读全书所有页面，重新提取故事梗概、角色设定、逐页台词和微动作草稿。已有草稿将被覆盖重置。约需
                    1–2 分钟。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction onClick={handleStartAnalysis}>开始分析</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardHeader>
      </Card>

      {/* 故事与角色卡片 */}
      <StoryAndCharactersCard bookId={book.id} bookAi={bookAi} />

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
// 故事与角色管理卡片
// ============================================================================

function StoryAndCharactersCard({ bookId, bookAi }: { bookId: string; bookAi: any }) {
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
              {bookAi.characters.map((char: Character) => (
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
                    已分配给该角色的台词说话人将被重置为空，音色也将被移除。
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

      <CharacterEditDialog
        bookId={bookId}
        character={character}
        open={isEditing}
        onOpenChange={setIsEditing}
      />
    </div>
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
  const hasTwoPages = spread.left_page_index !== null && spread.right_page_index !== null;

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
      <CardHeader className="flex flex-row items-center justify-between border-b bg-muted/40 py-3">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-sm">{spreadTitle}</span>
          {spread.mode === "merged" && (
            <Badge variant="outline" className="bg-background text-xs">
              <Combine className="mr-1 size-3 text-primary" />
              左右合并生成
            </Badge>
          )}
        </div>

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

  const handleAddLine = () => {
    const defaultSpeaker =
      characters.find((c) => c.is_narrator)?.id ?? (characters[0]?.id ?? null);
    setLines([...lines, { character_id: defaultSpeaker, text: "" }]);
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
            <AudioStatusBadge status={unit.audio_status} />
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
                    value={line.character_id !== null ? String(line.character_id) : "narrator"}
                    onValueChange={(val) =>
                      handleLineChange(
                        idx,
                        "character_id",
                        val === "narrator" ? null : Number(val),
                      )
                    }
                  >
                    <SelectTrigger className="w-[110px] shrink-0 text-xs">
                      <SelectValue placeholder="说话人" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="narrator">旁白</SelectItem>
                      {characters
                        .filter((c) => !c.is_narrator)
                        .map((c) => (
                          <SelectItem key={c.id} value={String(c.id)}>
                            {c.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>

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

function AudioStatusBadge({ status }: { status: string }) {
  if (status === "ready") {
    return (
      <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-[10px] text-emerald-700">
        朗读已就绪
      </Badge>
    );
  }
  if (status === "running" || status === "queued") {
    return (
      <Badge variant="outline" className="border-amber-200 bg-amber-50 text-[10px] text-amber-700">
        朗读生成中
      </Badge>
    );
  }
  return null;
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

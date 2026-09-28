import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ArrowLeft, CircleAlert } from "lucide-react";
import { useAdminBook, useUpdateBook } from "@/api/books";
import { AiWorkbench } from "@/pages/admin/ai-workbench";
import type {
  AdminBookDetail,
  BookUpdate,
  Language,
  Orientation,
  SpreadStartPage,
} from "@/api/types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ProgressLabel } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toast";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/api";
import { formatDateTime, formatFileSize } from "@/lib/format";
import { DeleteBookButton, VisibilityButton } from "@/pages/admin/book-actions";
import { BookStatusBadge, ProcessingProgress } from "@/pages/admin/book-status";
import { PageHeader } from "@/pages/admin/layout";
import { Reveal } from "@/pages/admin/motion";
import { ErrorState, LoadingState } from "@/pages/admin/query-state";

export default function AdminBookDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { data: book, isPending, error } = useAdminBook(id);
  const coverUpdate = useUpdateBook(id);
  useDocumentTitle(book?.title ?? "绘本管理");

  if (isPending) return <LoadingState />;
  if (error) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorState error={error} title="无法打开这本绘本" />
      </div>
    );
  }

  const ready = book.processing_status === "ready";
  const handleSetCover = (index: number) =>
    coverUpdate.mutate(
      { cover_page_index: index },
      {
        onSuccess: () => toast.add({ title: `已将第 ${index + 1} 页设为封面`, type: "success" }),
        onError: (err) =>
          toast.add({ title: "设置封面失败", description: getErrorMessage(err), type: "error" }),
      },
    );

  return (
    <>
      <BackLink />
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            {book.title}
            <BookStatusBadge book={book} />
          </span>
        }
        description={`${book.original_filename} · ${formatFileSize(book.file_size)} · 上传于 ${formatDateTime(book.created_at)}`}
      >
        {ready && <VisibilityButton book={book} />}
        <DeleteBookButton
          book={book}
          onDeleted={() => navigate("/admin/books", { replace: true })}
        />
      </PageHeader>

      {book.processing_status === "processing" && (
        <Reveal>
          <Card className="mb-6">
            <CardContent>
              <ProcessingProgress book={book}>
                <ProgressLabel>
                  正在拆页
                  {book.progress?.total ? `：${book.progress.done} / ${book.progress.total}` : "…"}
                </ProgressLabel>
              </ProcessingProgress>
            </CardContent>
          </Card>
        </Reveal>
      )}
      {book.processing_status === "failed" && (
        <Reveal>
          <Alert variant="destructive" className="mb-6">
            <CircleAlert />
            <AlertTitle>处理失败：{book.processing_error}</AlertTitle>
            <AlertDescription>请删除这本绘本后重新上传。</AlertDescription>
          </Alert>
        </Reveal>
      )}

      <Reveal index={1}>
        <InfoForm key={`${book.id}-${book.updated_at}`} book={book} />
      </Reveal>
      {ready && (
        <Reveal index={2}>
          <AiWorkbench
            book={book}
            onSetCover={handleSetCover}
            isSettingCover={coverUpdate.isPending}
          />
        </Reveal>
      )}
    </>
  );
}

function BackLink() {
  return (
    <Button
      variant="ghost"
      size="sm"
      nativeButton={false}
      render={<Link to="/admin/books" />}
      className="mb-3 -ml-2 text-muted-foreground"
    >
      <ArrowLeft />
      全部绘本
    </Button>
  );
}

// ---------- 基本信息 ----------

const SPREAD_LABELS: Record<SpreadStartPage, string> = {
  2: "从第 2 页开始配对（2+3、4+5…）",
  3: "从第 3 页开始配对（3+4、5+6…）",
};

// 传给 Select 的 items：选择框里显示选项名称而不是原始值
const LANGUAGE_ITEMS: { value: Language | ""; label: string }[] = [
  { value: "", label: "未设置" },
  { value: "zh", label: "中文" },
  { value: "en", label: "英文" },
];
const ORIENTATION_ITEMS: { value: Orientation; label: string }[] = [
  { value: "portrait", label: "竖版（平板横屏时对开显示）" },
  { value: "landscape", label: "横版（始终单页显示）" },
];
const SPREAD_ITEMS: { value: "auto" | `${SpreadStartPage}`; label: string }[] = [
  { value: "auto", label: "自动" },
  { value: "2", label: SPREAD_LABELS[2] },
  { value: "3", label: SPREAD_LABELS[3] },
];

function InfoForm({ book }: { book: AdminBookDetail }) {
  const update = useUpdateBook(book.id);
  const [title, setTitle] = useState(book.title);
  const [language, setLanguage] = useState<Language | "">(book.language ?? "");
  const [orientation, setOrientation] = useState<Orientation | "">(book.orientation ?? "");
  const [spread, setSpread] = useState<"auto" | `${SpreadStartPage}`>(
    book.spread_start_override ? `${book.spread_start_override}` : "auto",
  );

  const changes: BookUpdate = {};
  if (title.trim() !== book.title) changes.title = title.trim();
  if ((language || null) !== book.language) changes.language = language || null;
  if (orientation && orientation !== book.orientation) changes.orientation = orientation;
  const spreadOverride = spread === "auto" ? null : (Number(spread) as SpreadStartPage);
  if (spreadOverride !== book.spread_start_override) changes.spread_start_override = spreadOverride;
  const dirty = Object.keys(changes).length > 0;

  const detected = book.spread_start_detected
    ? `检测结果：${SPREAD_LABELS[book.spread_start_detected]}`
    : book.processing_status === "ready"
      ? "未检测出跨页大图，按从第 2 页开始配对"
      : "拆页完成后自动检测";

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    update.mutate(changes, {
      onSuccess: () => toast.add({ title: "已保存", type: "success" }),
      onError: (err) =>
        toast.add({ title: "保存失败", description: getErrorMessage(err), type: "error" }),
    });
  };

  return (
    <Card className="mb-6">
      <form onSubmit={save} className="contents">
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent>
          <FieldGroup className="grid gap-4 sm:grid-cols-2">
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="title">书名</FieldLabel>
              <Input
                id="title"
                value={title}
                maxLength={100}
                onChange={(e) => setTitle(e.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="language">语言</FieldLabel>
              <Select
                items={LANGUAGE_ITEMS}
                value={language}
                onValueChange={(value) => value !== null && setLanguage(value)}
              >
                <SelectTrigger id="language" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGE_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="orientation">版式</FieldLabel>
              <Select
                items={ORIENTATION_ITEMS}
                value={orientation || null}
                disabled={!book.orientation}
                onValueChange={(value) => value !== null && setOrientation(value)}
              >
                <SelectTrigger id="orientation" className="w-full">
                  <SelectValue placeholder="拆页后自动识别" />
                </SelectTrigger>
                <SelectContent>
                  {ORIENTATION_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="spread">对开配对</FieldLabel>
              <Select
                items={SPREAD_ITEMS}
                value={spread}
                onValueChange={(value) => value !== null && setSpread(value)}
              >
                <SelectTrigger id="spread" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SPREAD_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FieldDescription>
                {detected}。仅影响竖版书在平板横屏时的对开显示，让跨页大图的左右两半拼在一起。
              </FieldDescription>
            </Field>
          </FieldGroup>
        </CardContent>
        <CardFooter className="justify-end">
          <Button type="submit" disabled={!dirty || update.isPending}>
            {update.isPending && <Spinner />}
            保存
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

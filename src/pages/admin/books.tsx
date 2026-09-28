import { Fragment, useEffect, useRef, useState, type MouseEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, ImageOff, Upload } from "lucide-react";
import { adminBookKeys, uploadBook, useAdminBooks } from "@/api/books";
import type { AdminBook } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { Progress, ProgressLabel } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
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
import { formatDateTime, formatFileSize } from "@/lib/format";
import { DeleteBookButton, VisibilityButton } from "@/pages/admin/book-actions";
import { BookStatusBadge, ProcessingProgress } from "@/pages/admin/book-status";
import { PageHeader } from "@/pages/admin/layout";
import { ErrorState, LoadingState } from "@/pages/admin/query-state";

const MAX_UPLOAD_MB = 200;
const PAGE_SIZE = 10;

type UploadTask = { id: number; name: string; progress: number };

function searchParamsForPage(searchParams: URLSearchParams, page: number) {
  const params = new URLSearchParams(searchParams);
  if (page === 1) params.delete("page");
  else params.set("page", String(page));
  return params;
}

export default function AdminBooksPage() {
  const { data: books, isPending, error } = useAdminBooks();
  useDocumentTitle("绘本管理");
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<UploadTask[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const pageParam = searchParams.get("page");
  const parsedPage = Number(pageParam);
  const requestedPage =
    pageParam !== null && Number.isSafeInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const pageCount = Math.max(1, Math.ceil((books?.length ?? 0) / PAGE_SIZE));
  const page = Math.min(requestedPage, pageCount);
  const pageBooks = books?.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const pageNumbers =
    pageCount <= 7
      ? Array.from({ length: pageCount }, (_, i) => i + 1)
      : [...new Set([1, page - 1, page, page + 1, pageCount])]
          .filter((number) => number >= 1 && number <= pageCount)
          .sort((a, b) => a - b);

  useEffect(() => {
    if (books && pageParam !== null && pageParam !== (page === 1 ? "1" : String(page))) {
      setSearchParams((current) => searchParamsForPage(current, page), { replace: true });
    }
  }, [books, pageParam, page, setSearchParams]);

  const pageHref = (target: number) => {
    const params = searchParamsForPage(searchParams, target).toString();
    return `/admin/books${params ? `?${params}` : ""}`;
  };
  const changePage = (target: number) => (event: MouseEvent<HTMLAnchorElement>) => {
    if (target < 1 || target > pageCount) {
      event.preventDefault();
      return;
    }
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    setSearchParams((current) => searchParamsForPage(current, target));
  };

  // 多个文件依次上传，避免同时占满带宽
  const uploadFiles = async (files: File[]) => {
    const tasks = files.map((file, i) => ({ id: Date.now() + i, name: file.name, progress: 0 }));
    setUploads((current) => [...current, ...tasks]);
    for (const [i, file] of files.entries()) {
      const task = tasks[i];
      const update = (progress: number) =>
        setUploads((current) => current.map((t) => (t.id === task.id ? { ...t, progress } : t)));
      // 超限的文件在本地就拦下，不必上传完才被服务器拒绝
      const result =
        file.size > MAX_UPLOAD_MB * 1024 * 1024
          ? { error: `文件超过 ${MAX_UPLOAD_MB}MB 上限` }
          : await uploadBook(file, update).then(
              (book) => ({ book }),
              (e: unknown) => ({ error: getErrorMessage(e) }),
            );
      setUploads((current) => current.filter((t) => t.id !== task.id));
      if ("book" in result) {
        toast.add({ title: `《${result.book.title}》上传完成，正在处理`, type: "success" });
        setSearchParams((current) => searchParamsForPage(current, 1));
        queryClient.invalidateQueries({ queryKey: adminBookKeys.all, exact: true });
      } else {
        toast.add({ title: `${file.name} 上传失败`, description: result.error, type: "error" });
      }
    }
  };

  return (
    <>
      <PageHeader title="绘本" description="上传 PDF 后会自动拆页，处理完成即上架，读者可在书架上看到。">
        <Input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            e.target.value = "";
            if (files.length) void uploadFiles(files);
          }}
        />
        <Button onClick={() => fileInput.current?.click()}>
          <Upload />
          上传 PDF
        </Button>
      </PageHeader>

      {uploads.length > 0 && (
        <Card className="mb-4">
          <CardContent className="space-y-4">
            {uploads.map((task) => (
              <Progress key={task.id} value={task.progress * 100}>
                <ProgressLabel className="min-w-0 flex-1 truncate">{task.name}</ProgressLabel>
                <span className="shrink-0 text-sm text-muted-foreground">
                  {task.progress < 1 ? `上传中 ${Math.round(task.progress * 100)}%` : "等待服务器保存…"}
                </span>
              </Progress>
            ))}
          </CardContent>
        </Card>
      )}

      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : books.length === 0 ? (
        <Empty className="border bg-background">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <BookOpen />
            </EmptyMedia>
            <EmptyTitle>还没有绘本</EmptyTitle>
            <EmptyDescription>点击右上角"上传 PDF"添加第一本绘本，单个文件不超过 200MB。</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <Card className="gap-0 py-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">封面</TableHead>
                <TableHead>书名</TableHead>
                <TableHead className="w-40">状态</TableHead>
                <TableHead className="w-16 text-right">页数</TableHead>
                <TableHead className="w-24 text-right">大小</TableHead>
                <TableHead className="w-40">上传时间</TableHead>
                <TableHead className="w-44 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageBooks?.map((book) => (
                <BookRow key={book.id} book={book} />
              ))}
            </TableBody>
          </Table>
          {pageCount > 1 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
              <span className="text-sm text-muted-foreground">
                第 {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, books.length)} 条，共{" "}
                {books.length} 本
              </span>
              <Pagination aria-label="绘本列表分页" className="mx-0 w-auto max-w-full overflow-x-auto">
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      href={page > 1 ? pageHref(page - 1) : undefined}
                      onClick={changePage(page - 1)}
                      aria-label="上一页"
                      aria-disabled={page === 1}
                      tabIndex={page === 1 ? -1 : undefined}
                      className={page === 1 ? "pointer-events-none opacity-50" : undefined}
                      text="上一页"
                    />
                  </PaginationItem>
                  {pageNumbers.map((number, index) => (
                    <Fragment key={number}>
                      {index > 0 && number > pageNumbers[index - 1] + 1 && (
                        <PaginationItem>
                          <PaginationEllipsis />
                        </PaginationItem>
                      )}
                      <PaginationItem>
                        <PaginationLink
                          href={pageHref(number)}
                          onClick={changePage(number)}
                          isActive={number === page}
                          aria-label={`第 ${number} 页`}
                        >
                          {number}
                        </PaginationLink>
                      </PaginationItem>
                    </Fragment>
                  ))}
                  <PaginationItem>
                    <PaginationNext
                      href={page < pageCount ? pageHref(page + 1) : undefined}
                      onClick={changePage(page + 1)}
                      aria-label="下一页"
                      aria-disabled={page === pageCount}
                      tabIndex={page === pageCount ? -1 : undefined}
                      className={page === pageCount ? "pointer-events-none opacity-50" : undefined}
                      text="下一页"
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </Card>
      )}
    </>
  );
}

function BookRow({ book }: { book: AdminBook }) {
  return (
    <TableRow>
      <TableCell>
        <Link to={`/admin/books/${book.id}`} aria-label={book.title}>
          <Cover book={book} />
        </Link>
      </TableCell>
      <TableCell className="max-w-0">
        <Button
          variant="link"
          nativeButton={false}
          render={<Link to={`/admin/books/${book.id}`} />}
          className="h-auto max-w-full p-0 font-medium text-foreground"
        >
          <span className="truncate">{book.title}</span>
        </Button>
        {book.processing_status === "failed" && (
          <p className="truncate text-xs text-destructive">{book.processing_error}</p>
        )}
      </TableCell>
      <TableCell>
        <div className="space-y-1.5">
          <BookStatusBadge book={book} />
          {book.processing_status === "processing" && <ProcessingProgress book={book} />}
        </div>
      </TableCell>
      <TableCell className="text-right tabular-nums">{book.page_count || "—"}</TableCell>
      <TableCell className="text-right text-muted-foreground tabular-nums">
        {formatFileSize(book.file_size)}
      </TableCell>
      <TableCell className="text-muted-foreground tabular-nums">
        {formatDateTime(book.created_at)}
      </TableCell>
      <TableCell>
        <div className="flex justify-end gap-1">
          {book.processing_status === "ready" && (
            <VisibilityButton book={book} size="sm" variant="ghost" />
          )}
          <DeleteBookButton book={book} size="sm" variant="ghost" />
        </div>
      </TableCell>
    </TableRow>
  );
}

function Cover({ book }: { book: AdminBook }) {
  if (book.cover_url) {
    return (
      <img
        src={book.cover_url}
        alt=""
        loading="lazy"
        className="h-14 w-11 rounded-sm object-cover ring-1 ring-border"
      />
    );
  }
  if (book.processing_status === "processing") return <Skeleton className="h-14 w-11 rounded-sm" />;
  return (
    <div className="flex h-14 w-11 items-center justify-center rounded-sm bg-muted text-muted-foreground">
      <ImageOff className="size-4" />
    </div>
  );
}

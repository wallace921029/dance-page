import { Fragment, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, ImageOff, Search, Upload, X } from "lucide-react";
import { adminBookKeys, uploadBook, useAdminBooks } from "@/api/books";
import type { AdminBook } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
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
import { formatDateTime, formatFileSize, titleFromFilename } from "@/lib/format";
import { DeleteBookButton, VisibilityButton } from "@/pages/admin/book-actions";
import { BookAiStatusIcons, BookStatusBadge, ProcessingProgress } from "@/pages/admin/book-status";
import { PageHeader } from "@/pages/admin/layout";
import { AnimatedTableRow, Reveal } from "@/pages/admin/motion";
import { ErrorState, LoadingState } from "@/pages/admin/query-state";

const MAX_UPLOAD_MB = 200;
const PAGE_SIZE = 10;

type UploadTask = { id: number; name: string; progress: number };

/** 搜索与比对时忽略大小写和所有空格 */
function normalizeText(text: string) {
  return text.toLowerCase().replace(/\s+/g, "");
}

/** 去除书名两端可能带有的书名号或尖括号 */
function stripBookMarks(text: string) {
  return text.replace(/^[《<]/, "").replace(/[》>]$/, "").trim();
}

/** 预查重判断：书名或原始文件名一致则视为重复绘本 */
function isDuplicateBook(
  candidateTitle: string,
  filename: string,
  existingBook: { title: string; original_filename: string },
) {
  const normCandidateTitle = normalizeText(stripBookMarks(candidateTitle));
  const normExistingTitle = normalizeText(stripBookMarks(existingBook.title));
  if (normCandidateTitle && normExistingTitle && normCandidateTitle === normExistingTitle) {
    return true;
  }

  const normCandidateFilename = normalizeText(filename);
  const normExistingFilename = normalizeText(existingBook.original_filename);
  if (
    normCandidateFilename &&
    normExistingFilename &&
    normCandidateFilename === normExistingFilename
  ) {
    return true;
  }

  return false;
}

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
  const query = searchParams.get("q") ?? "";

  const updateQuery = (nextQuery: string) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (nextQuery.trim()) next.set("q", nextQuery.trim());
        else next.delete("q");
        next.delete("page"); // 搜索关键词变动时切回第 1 页
        return next;
      },
      { replace: true },
    );
  };

  const filteredBooks = useMemo(() => {
    const norm = normalizeText(query);
    if (!norm) return books;
    return books?.filter(
      (b) =>
        normalizeText(b.title).includes(norm) ||
        normalizeText(b.original_filename).includes(norm),
    );
  }, [books, query]);

  const pageParam = searchParams.get("page");
  const parsedPage = Number(pageParam);
  const requestedPage =
    pageParam !== null && Number.isSafeInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const pageCount = Math.max(1, Math.ceil((filteredBooks?.length ?? 0) / PAGE_SIZE));
  const page = Math.min(requestedPage, pageCount);
  const pageBooks = filteredBooks?.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const pageNumbers =
    pageCount <= 7
      ? Array.from({ length: pageCount }, (_, i) => i + 1)
      : [...new Set([1, page - 1, page, page + 1, pageCount])]
          .filter((number) => number >= 1 && number <= pageCount)
          .sort((a, b) => a - b);

  useEffect(() => {
    if (
      filteredBooks &&
      pageParam !== null &&
      pageParam !== (page === 1 ? "1" : String(page))
    ) {
      setSearchParams((current) => searchParamsForPage(current, page), { replace: true });
    }
  }, [filteredBooks, pageParam, page, setSearchParams]);

  const pageHref = (target: number) => {
    const params = searchParamsForPage(searchParams, target).toString();
    return `/admin/books${params ? `?${params}` : ""}`;
  };
  const changePage = (target: number) => (event: MouseEvent<HTMLAnchorElement>) => {
    if (target < 1 || target > pageCount) {
      event.preventDefault();
      return;
    }
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
      return;
    event.preventDefault();
    setSearchParams((current) => searchParamsForPage(current, target));
  };

  // 多个文件依次上传，上传前预查重并避免同时占满带宽
  const uploadFiles = async (files: File[]) => {
    // 1. 预查重：对比已存在的绘本及本次选中的其他文件
    const toUpload: File[] = [];
    const seenBatchTitles: string[] = [];

    for (const file of files) {
      const candidateTitle = titleFromFilename(file.name);
      const existing = books?.find((b) => isDuplicateBook(candidateTitle, file.name, b));
      const duplicateInBatch = seenBatchTitles.some(
        (t) => normalizeText(stripBookMarks(t)) === normalizeText(stripBookMarks(candidateTitle)),
      );

      if (existing || duplicateInBatch) {
        const matchName = existing?.title || candidateTitle;
        const formattedTitle =
          matchName.startsWith("《") && matchName.endsWith("》")
            ? matchName
            : `《${matchName}》`;
        toast.add({
          title: `${formattedTitle} 绘本已经存在`,
          description: "已自动忽略上传",
          type: "warning",
        });
        continue;
      }

      seenBatchTitles.push(candidateTitle);
      toUpload.push(file);
    }

    if (toUpload.length === 0) return;

    // 2. 依次执行上传
    const tasks = toUpload.map((file, i) => ({ id: Date.now() + i, name: file.name, progress: 0 }));
    setUploads((current) => [...current, ...tasks]);
    for (const [i, file] of toUpload.entries()) {
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
      <PageHeader
        title="绘本"
        description="上传 PDF 后会自动拆页，处理完成即上架，读者可在书架上看到。"
      >
        <InputGroup className="w-48 sm:w-64">
          <InputGroupAddon align="inline-start">
            <Search className="size-4" />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            placeholder="搜索绘本..."
            value={query}
            onChange={(e) => updateQuery(e.target.value)}
          />
          {query && (
            <InputGroupAddon align="inline-end">
              <InputGroupButton
                size="icon-xs"
                aria-label="清空搜索"
                onClick={() => updateQuery("")}
              >
                <X className="size-3.5" />
              </InputGroupButton>
            </InputGroupAddon>
          )}
        </InputGroup>
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
        <Reveal className="mb-4">
          <Card>
            <CardContent className="space-y-4">
              {uploads.map((task) => (
                <Progress key={task.id} value={task.progress * 100}>
                  <ProgressLabel className="min-w-0 flex-1 truncate">{task.name}</ProgressLabel>
                  <span className="shrink-0 text-sm text-muted-foreground">
                    {task.progress < 1
                      ? `上传中 ${Math.round(task.progress * 100)}%`
                      : "等待服务器保存…"}
                  </span>
                </Progress>
              ))}
            </CardContent>
          </Card>
        </Reveal>
      )}

      {isPending ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : books.length === 0 ? (
        <Reveal>
          <Empty className="border bg-background">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <BookOpen />
              </EmptyMedia>
              <EmptyTitle>还没有绘本</EmptyTitle>
              <EmptyDescription>
                点击右上角"上传 PDF"添加第一本绘本，单个文件不超过 200MB。
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </Reveal>
      ) : filteredBooks && filteredBooks.length === 0 ? (
        <Reveal>
          <Empty className="border bg-background">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Search />
              </EmptyMedia>
              <EmptyTitle>未找到匹配的绘本</EmptyTitle>
              <EmptyDescription>
                没有找到与“{query.trim()}”相关的绘本，换个关键词试试？
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button variant="outline" size="sm" onClick={() => updateQuery("")}>
                清除搜索
              </Button>
            </EmptyContent>
          </Empty>
        </Reveal>
      ) : (
        <Reveal>
          <Card className="gap-0 py-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">封面</TableHead>
                  <TableHead>书名</TableHead>
                  <TableHead className="w-48">状态</TableHead>
                  <TableHead className="w-16 text-right">页数</TableHead>
                  <TableHead className="w-24 text-right">大小</TableHead>
                  <TableHead className="w-40">上传时间</TableHead>
                  <TableHead className="w-44 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageBooks?.map((book, index) => (
                  <BookRow key={book.id} book={book} index={index} />
                ))}
              </TableBody>
            </Table>
            {(pageCount > 1 || query.trim() !== "") && (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
                <span className="text-sm text-muted-foreground">
                  {query.trim() ? (
                    <>
                      第 {(page - 1) * PAGE_SIZE + 1}–
                      {Math.min(page * PAGE_SIZE, filteredBooks?.length ?? 0)} 条，找到{" "}
                      {filteredBooks?.length ?? 0} 本（共 {books.length} 本）
                    </>
                  ) : (
                    <>
                      第 {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, books.length)}{" "}
                      条，共 {books.length} 本
                    </>
                  )}
                </span>
                <Pagination
                  aria-label="绘本列表分页"
                  className="mx-0 w-auto max-w-full overflow-x-auto"
                >
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
                        className={
                          page === pageCount ? "pointer-events-none opacity-50" : undefined
                        }
                        text="下一页"
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            )}
          </Card>
        </Reveal>
      )}
    </>
  );
}

function BookRow({ book, index }: { book: AdminBook; index: number }) {
  return (
    <AnimatedTableRow index={index}>
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
          <div className="flex items-center gap-2">
            <BookStatusBadge book={book} />
            <BookAiStatusIcons book={book} />
          </div>
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
    </AnimatedTableRow>
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

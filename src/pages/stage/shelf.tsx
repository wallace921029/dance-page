import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  LogOut,
  Palette,
  Settings,
  Sparkles,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { cn } from "cn";
import { meQuery, useLogout } from "@/api/auth";
import { useShelf } from "@/api/shelf";
import type { ShelfBook } from "@/api/types";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/api";
import { StageBrand, StageRoundButton } from "@/pages/stage/common";
import { DoodleArrow } from "@/pages/stage/doodle-arrow";
import { DoodleHeart } from "@/pages/stage/doodle-heart";
import { ShelfBackdrop } from "@/pages/stage/shelf-backdrop";
import { ShelfItem } from "@/pages/stage/shelf-item";
import { ShelfSearch, type ShelfSearchHandle } from "@/pages/stage/shelf-search";
import {
  SHELF_THEME_ORDER,
  SHELF_THEMES,
  type ShelfTheme,
  type ShelfThemeId,
  useShelfTheme,
} from "@/pages/stage/shelf-themes";
import {
  ENTRANCE_MAX_ITEMS,
  useEntranceOnce,
  useShelfFirefly,
  useShelfMotion,
} from "@/pages/stage/shelf-motion";

const BOOKS_PER_PAGE = 8;

function shelfPageParams(current: URLSearchParams, page: number) {
  const next = new URLSearchParams(current);
  if (page === 1) next.delete("page");
  else next.set("page", String(page));
  return next;
}

/** 搜索时忽略大小写和空格 */
function normalize(text: string) {
  return text.toLowerCase().replace(/\s+/g, "");
}

function useLandscapeRows(
  mainRef: React.RefObject<HTMLElement | null>,
  books: ShelfBook[] | undefined,
  page: number,
  plank: boolean,
) {
  const [layout, setLayout] = useState<{ height: number; rows: number[] } | null>(null);

  useLayoutEffect(() => {
    const main = mainRef.current;
    if (!main || !books?.length) return;

    const update = () => {
      const wide = window.matchMedia("(min-width: 640px)").matches;
      // 与网格列距、木书架内边距及书名最多两行的尺寸一致
      const columnGap = plank ? 0 : wide ? 40 : 24;
      const bookInset = plank ? (wide ? 40 : 24) : 0;
      const coverWidth = Math.max(0, (main.clientWidth - 3 * columnGap) / 4 - bookInset);
      const titleRoom = (wide ? 40 : 17) + (plank ? 20 : 12);
      const rowGap = wide ? 12 : 8;
      const pageBooks = books.slice((page - 1) * BOOKS_PER_PAGE, page * BOOKS_PER_PAGE);
      const rows = Array.from({ length: Math.ceil(pageBooks.length / 4) }, (_, row) =>
        Math.max(
          ...pageBooks
            .slice(row * 4, row * 4 + 4)
            .map((book) => coverWidth / book.cover_aspect + titleRoom),
        ),
      );
      const style = getComputedStyle(main);
      const available = Math.max(
        0,
        main.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom),
      );
      const gaps = (rows.length - 1) * rowGap;
      const scale = Math.min(
        1,
        Math.max(0, available - gaps) / rows.reduce((sum, height) => sum + height, 0),
      );
      const fittedRows = rows.map((height) => height * scale);
      const height = fittedRows.reduce((sum, row) => sum + row, gaps);
      setLayout((current) =>
        current?.height === height &&
        current.rows.length === fittedRows.length &&
        current.rows.every((row, index) => row === fittedRows[index])
          ? current
          : { height, rows: fittedRows },
      );
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(main);
    return () => observer.disconnect();
  }, [mainRef, books, page, plank]);

  return layout;
}

/** 书架页。mode="favorites" 时为"我的收藏"（D55），展示方式与首页相同 */
export default function ShelfPage({ mode = "all" }: { mode?: "all" | "favorites" }) {
  const favoritesMode = mode === "favorites";
  const { data: allBooks, isPending, error } = useShelf();
  const { data: me } = useQuery(meQuery);
  const [theme, setTheme] = useShelfTheme();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  // 搜索词放在地址里（D54），从阅读页返回时保留
  const query = searchParams.get("q") ?? "";
  const shelfBooks = useMemo(
    () =>
      favoritesMode
        ? allBooks
            ?.filter((b) => b.is_favorite)
            // 最近收藏的在前
            .sort((a, b) => (b.favorited_at ?? "").localeCompare(a.favorited_at ?? ""))
        : allBooks,
    [allBooks, favoritesMode],
  );
  const books = useMemo(
    () =>
      query.trim()
        ? shelfBooks?.filter((b) => normalize(b.title).includes(normalize(query)))
        : shelfBooks,
    [shelfBooks, query],
  );
  const pageParam = searchParams.get("page");
  const requestedPage = Number(pageParam);
  const pageCount = Math.max(1, Math.ceil((books?.length ?? 0) / BOOKS_PER_PAGE));
  const page =
    pageParam !== null && Number.isSafeInteger(requestedPage) && requestedPage > 0
      ? Math.min(requestedPage, pageCount)
      : 1;
  const [direction, setDirection] = useState(1);
  const reducedMotion = useReducedMotion();
  // 书本动效（D52）：进场、点按与翻开、萤火虫
  const shelfMotion = useShelfMotion();
  const playEntrance = useEntranceOnce(
    shelfMotion.enabled,
    Boolean(books && books.length > 0 && !error),
  );
  const mainRef = useRef<HTMLElement>(null);
  const landscapeRows = useLandscapeRows(mainRef, books, page, Boolean(theme.plank));
  const landscapeStyle: React.CSSProperties & {
    "--compact-height"?: string;
    "--compact-rows"?: string;
  } | undefined = landscapeRows
    ? {
        "--compact-height": `${landscapeRows.height}px`,
        "--compact-rows": landscapeRows.rows.map((height) => `${height}px`).join(" "),
      }
    : undefined;
  const searchRef = useRef<ShelfSearchHandle>(null);
  const setQuery = (value: string) =>
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set("q", value);
        else next.delete("q");
        next.delete("page"); // 搜索词变化后回到第 1 页
        return next;
      },
      { replace: true, preventScrollReset: true },
    );
  // 点按光点、萤火虫所在的定位层，铺满整个书架页、随页面滚动
  const effectsRef = useRef<HTMLDivElement>(null);
  useShelfFirefly(effectsRef, shelfMotion.enabled && Boolean(theme.fireflies));
  useDocumentTitle(favoritesMode ? "我的收藏" : undefined);

  useEffect(() => {
    if (!books || pageParam === null || pageParam === String(page)) return;
    setSearchParams(
      (current) => shelfPageParams(current, page),
      { replace: true, preventScrollReset: true },
    );
  }, [books, pageParam, page, setSearchParams]);

  const goToPage = (target: number) => {
    setDirection(target > page ? 1 : -1);
    setSearchParams(
      (current) => shelfPageParams(current, target),
      { preventScrollReset: true },
    );
  };

  const slideVariants = {
    enter: (slideDirection: number) => ({
      x: reducedMotion ? 0 : slideDirection * 64,
      opacity: reducedMotion ? 1 : 0,
    }),
    center: { x: 0, opacity: 1 },
    exit: (slideDirection: number) => ({
      x: reducedMotion ? 0 : -slideDirection * 64,
      opacity: reducedMotion ? 1 : 0,
    }),
  };

  return (
    <div
      className={cn(
        // 书架固定一屏高，不出现滚动条：书格按剩余空间缩放
        "relative isolate flex h-dvh flex-col overflow-hidden font-stage",
        // 从主屏幕打开时让出状态栏和刘海（底部由 main 和翻页按钮各自让出）
        "pt-[env(safe-area-inset-top)] pr-[env(safe-area-inset-right)] pl-[env(safe-area-inset-left)]",
        theme.dark && "dark",
        theme.text,
      )}
    >
      <ShelfBackdrop theme={theme} />
      <div
        ref={effectsRef}
        aria-hidden
        className="pointer-events-none absolute inset-0 z-10 overflow-hidden"
      />

      <div className="relative mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col px-6 md:px-12">
        <header className="flex h-16 shrink-0 items-center justify-between gap-3 sm:h-20">
          <div className="flex min-w-0 items-center gap-3 sm:gap-5">
            {favoritesMode ? (
              <>
                <StageRoundButton
                  label="返回书架"
                  nativeButton={false}
                  render={<Link to="/" />}
                  className={theme.avatar}
                >
                  <ArrowLeft />
                </StageRoundButton>
                <h1 className="flex shrink-0 items-center gap-2 font-stage-title text-2xl tracking-wider sm:text-3xl">
                  <DoodleHeart filled className="size-7 -rotate-12 sm:size-8" />
                  我的收藏
                </h1>
              </>
            ) : (
              <StageBrand className="shrink-0 text-3xl" />
            )}
            <ShelfSearch
              // 切换"全部 / 收藏"时重新挂载，按新页面的搜索词决定是否展开
              key={mode}
              ref={searchRef}
              value={query}
              onChange={setQuery}
              enableMotion={shelfMotion.enabled}
              buttonClassName={theme.avatar}
            />
          </div>
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <FavoritesButton favoritesMode={favoritesMode} />
            {me && (
              <UserMenu
                username={me.username}
                isAdmin={me.role === "admin"}
                theme={theme}
                onThemeChange={setTheme}
                shelfMotion={shelfMotion}
              />
            )}
          </div>
        </header>

        <main
          ref={mainRef}
          className={cn(
            "flex min-h-0 flex-1 flex-col pt-2",
            // 底部给固定的翻页按钮留出位置
            pageCount > 1
              ? "pb-[calc(6.5rem+env(safe-area-inset-bottom))] sm:pb-[calc(7rem+env(safe-area-inset-bottom))]"
              : "pb-[calc(1.5rem+env(safe-area-inset-bottom))]",
          )}
        >
          {isPending || (!books && !error) ? (
            <div className="flex justify-center py-32">
              <Spinner className="size-6" />
            </div>
          ) : error || !books || books.length === 0 ? (
            <ShelfEmpty
              error={error}
              favoritesMode={favoritesMode}
              query={query}
              hasShelfBooks={(shelfBooks?.length ?? 0) > 0}
              isAdmin={me?.role === "admin"}
              onClearQuery={() => searchRef.current?.clear()}
            />
          ) : (
            <AnimatePresence initial={false} mode="wait" custom={direction}>
              <motion.ul
                key={page}
                id="shelf-books"
                style={landscapeStyle}
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{
                  duration: reducedMotion ? 0 : 0.24,
                  ease: [0.22, 1, 0.36, 1],
                }}
                className={cn(
                  // 横屏按封面比例收紧两排，空间不足时等比缩放；竖屏仍填满剩余空间
                  "grid min-h-0 flex-1 grid-cols-2 grid-rows-4 gap-y-4 landscape:my-auto landscape:h-[var(--compact-height,100%)] landscape:flex-none landscape:grid-cols-4 landscape:grid-rows-[var(--compact-rows,repeat(2,minmax(0,1fr)))] landscape:gap-y-2 sm:gap-y-6 sm:landscape:gap-y-3 sm:portrait:grid-cols-3 sm:portrait:grid-rows-3",
                  // 木书架要连成一整条，列之间不留空隙，间距放到每本书内部
                  theme.plank ? "gap-x-0" : "gap-x-6 sm:gap-x-10",
                )}
              >
                {books
                  .slice((page - 1) * BOOKS_PER_PAGE, page * BOOKS_PER_PAGE)
                  .map((book, index) => (
                    <li key={book.id} className={cn("min-h-0", theme.plank && "px-3 sm:px-5")}>
                      <ShelfItem
                        book={book}
                        theme={theme}
                        shelfPath={location.pathname + location.search}
                        entranceIndex={playEntrance && index < ENTRANCE_MAX_ITEMS ? index : null}
                        motionEnabled={shelfMotion.enabled}
                        effectsRef={effectsRef}
                      />
                    </li>
                  ))}
              </motion.ul>
            </AnimatePresence>
          )}
        </main>
      </div>
      {!isPending && !error && pageCount > 1 && (
        <nav
          aria-label="书架翻页"
          className="pointer-events-none fixed inset-x-0 bottom-[calc(1.5rem+env(safe-area-inset-bottom))] z-20 flex items-center justify-center gap-5 sm:gap-8"
        >
          <ShelfPageButton
            direction="previous"
            disabled={page === 1}
            enableMotion={shelfMotion.enabled}
            onClick={() => goToPage(page - 1)}
          />
          <span
            aria-live="polite"
            className="relative min-w-16 pb-1.5 text-center font-stage-title text-lg tabular-nums"
          >
            {page} / {pageCount}
            {/* 手画的波浪下划线，颜色跟随主题文字 */}
            <svg
              viewBox="0 0 60 8"
              preserveAspectRatio="none"
              aria-hidden
              className="absolute inset-x-1 bottom-0 h-1.5 w-[calc(100%-0.5rem)] opacity-70"
            >
              <path
                d="M2 5C8 2 12 7 18 4S28 2 33 5 43 7 48 4 56 3 58 4"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <ShelfPageButton
            direction="next"
            disabled={page === pageCount}
            enableMotion={shelfMotion.enabled}
            onClick={() => goToPage(page + 1)}
          />
        </nav>
      )}
    </div>
  );
}

/**
 * 头像左侧的"我的收藏"入口（D58）：手绘爱心。
 * 在收藏页显示为选中状态，再点一下回到全部绘本
 */
function FavoritesButton({ favoritesMode }: { favoritesMode: boolean }) {
  const label = favoritesMode ? "返回全部绘本" : "我的收藏";
  return (
    <Button
      variant="ghost"
      size="icon-lg"
      nativeButton={false}
      render={<Link to={favoritesMode ? "/" : "/favorites"} />}
      aria-label={label}
      aria-current={favoritesMode ? "page" : undefined}
      title={label}
      className={cn(
        "size-11 rounded-full bg-transparent p-1 transition-transform hover:scale-110 hover:bg-transparent focus-visible:ring-stage-spot/60 active:scale-95 motion-reduce:transition-none dark:hover:bg-transparent [&_svg:not([class*='size-'])]:size-full",
        // 选中时微微歪着、带一圈暖光，像被点亮的贴纸
        favoritesMode ? "-rotate-12 bg-white/15 ring-2 ring-[#FF6F91]/60" : "rotate-6",
      )}
    >
      <DoodleHeart filled className="size-full drop-shadow-[0_2px_2px_rgba(30,20,50,.35)]" />
    </Button>
  );
}

/** 手绘涂鸦风格的上一页 / 下一页按钮（D57） */
function ShelfPageButton({
  direction,
  disabled,
  enableMotion,
  onClick,
}: {
  direction: "previous" | "next";
  disabled: boolean;
  enableMotion: boolean;
  onClick: () => void;
}) {
  const previous = direction === "previous";
  const label = previous ? "上一页" : "下一页";
  const iconRef = useRef<SVGSVGElement>(null);
  return (
    <Button
      variant="ghost"
      size="icon-lg"
      aria-label={label}
      aria-controls="shelf-books"
      title={label}
      disabled={disabled}
      onClick={() => {
        onClick();
        // 箭头朝翻页方向轻轻推一下
        const arrow = iconRef.current?.querySelector('[data-part="arrow"]');
        if (enableMotion && arrow) {
          const shift = previous ? -4 : 4;
          arrow.animate(
            [
              { translate: "0 0" },
              { translate: `${shift}px 0`, offset: 0.4 },
              { translate: "0 0" },
            ],
            { duration: 320, easing: "cubic-bezier(.3,.7,.4,1)" },
          );
        }
      }}
      className={cn(
        "pointer-events-auto size-12 rounded-full bg-transparent p-0 transition-transform hover:scale-110 hover:bg-transparent focus-visible:ring-stage-spot/60 active:scale-95 motion-reduce:transition-none sm:size-14 dark:hover:bg-transparent [&_svg:not([class*='size-'])]:size-full",
        previous ? "hover:-rotate-6" : "hover:rotate-6",
        // 翻不了时变淡变灰
        "disabled:opacity-35 disabled:grayscale",
      )}
    >
      <DoodleArrow
        ref={iconRef}
        direction={direction}
        className="size-full drop-shadow-[0_2px_2px_rgba(30,20,50,.35)]"
      />
    </Button>
  );
}

function UserMenu({
  username,
  isAdmin,
  theme,
  onThemeChange,
  shelfMotion,
}: {
  username: string;
  isAdmin: boolean;
  theme: ShelfTheme;
  onThemeChange: (id: ShelfThemeId) => void;
  shelfMotion: ReturnType<typeof useShelfMotion>;
}) {
  const navigate = useNavigate();
  const logout = useLogout();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="账户"
        render={<Button variant="ghost" size="icon-lg" className="size-11 rounded-full p-0" />}
      >
        <Avatar className="size-11">
          <AvatarFallback className={cn("text-lg", theme.avatar)}>
            {username.slice(0, 1).toUpperCase()}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-44">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{username}</DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex items-center gap-1.5">
            <Palette className="size-3.5" />
            书架主题
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={theme.id}
            onValueChange={(value) => onThemeChange(value as ShelfThemeId)}
          >
            {SHELF_THEME_ORDER.map((id) => (
              <DropdownMenuRadioItem key={id} value={id} closeOnClick>
                <span
                  aria-hidden
                  className="size-4 rounded-full ring-1 ring-foreground/15"
                  style={{ background: SHELF_THEMES[id].swatch }}
                />
                {SHELF_THEMES[id].name}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
          <DropdownMenuCheckboxItem
            checked={shelfMotion.preference && !shelfMotion.reduced}
            disabled={shelfMotion.reduced}
            onCheckedChange={(checked) => shelfMotion.setPreference(checked)}
            closeOnClick={false}
          >
            <Sparkles />
            {shelfMotion.reduced ? "书本动效（系统已减少动态效果）" : "书本动效"}
          </DropdownMenuCheckboxItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        {isAdmin && (
          <DropdownMenuItem onClick={() => navigate("/admin/books")}>
            <Settings />
            管理后台
          </DropdownMenuItem>
        )}
        <DropdownMenuItem
          onClick={() =>
            logout.mutate(undefined, { onSuccess: () => navigate("/login", { replace: true }) })
          }
        >
          <LogOut />
          退出登录
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** 书架的各种空状态：出错、书架上没书、还没有收藏、搜不到 */
function ShelfEmpty({
  error,
  favoritesMode,
  query,
  hasShelfBooks,
  isAdmin,
  onClearQuery,
}: {
  error: unknown;
  favoritesMode: boolean;
  query: string;
  hasShelfBooks: boolean;
  isAdmin: boolean;
  onClearQuery: () => void;
}) {
  let title: string;
  let description: string | null = null;
  let action: React.ReactNode = null;
  if (error) {
    title = getErrorMessage(error);
  } else if (hasShelfBooks && query) {
    title = `没有找到"${query.trim()}"`;
    description = "换个词试试，或者看看全部绘本。";
    action = (
      <Button variant="link" onClick={onClearQuery} className="text-current">
        清除搜索
      </Button>
    );
  } else if (favoritesMode) {
    title = "还没有收藏的绘本";
    description = "点一下封面左上角的小爱心，喜欢的绘本就会放到这里。";
    action = (
      <Button variant="link" nativeButton={false} render={<Link to="/" />} className="text-current">
        去书架看看
      </Button>
    );
  } else {
    title = "书架上还没有绘本";
    if (isAdmin) {
      action = (
        <Button
          variant="link"
          nativeButton={false}
          render={<Link to="/admin/books" />}
          className="text-current"
        >
          去管理后台上传
        </Button>
      );
    }
  }
  return (
    <Empty className="flex-1">
      <EmptyHeader>
        <EmptyTitle className="font-stage-title text-2xl">{title}</EmptyTitle>
        {description && (
          <EmptyDescription className="text-current opacity-75">{description}</EmptyDescription>
        )}
      </EmptyHeader>
      {action && <EmptyContent>{action}</EmptyContent>}
    </Empty>
  );
}

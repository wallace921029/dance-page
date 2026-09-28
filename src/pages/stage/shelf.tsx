import { Link, useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { LogOut, Palette, Settings } from "lucide-react";
import { cn } from "cn";
import { meQuery, useLogout } from "@/api/auth";
import { useShelf } from "@/api/shelf";
import type { ShelfBook } from "@/api/types";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Empty, EmptyContent, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { getErrorMessage } from "@/lib/api";
import { StageBrand } from "@/pages/stage/common";
import { ShelfBackdrop } from "@/pages/stage/shelf-backdrop";
import {
  SHELF_THEME_ORDER,
  SHELF_THEMES,
  type ShelfTheme,
  type ShelfThemeId,
  useShelfTheme,
} from "@/pages/stage/shelf-themes";

export default function ShelfPage() {
  const { data: books, isPending, error } = useShelf();
  const { data: me } = useQuery(meQuery);
  const [theme, setTheme] = useShelfTheme();
  useDocumentTitle();

  return (
    <div className={cn("relative isolate min-h-svh font-stage", theme.dark && "dark", theme.text)}>
      <ShelfBackdrop theme={theme} />

      <div className="relative mx-auto max-w-6xl px-6 md:px-12">
        <header className="flex h-20 items-center justify-between">
          <StageBrand className="text-3xl" />
          {me && (
            <UserMenu
              username={me.username}
              isAdmin={me.role === "admin"}
              theme={theme}
              onThemeChange={setTheme}
            />
          )}
        </header>

        <main className="pt-4 pb-40">
          {isPending ? (
            <div className="flex justify-center py-32">
              <Spinner className="size-6" />
            </div>
          ) : error || books.length === 0 ? (
            <Empty className="py-32">
              <EmptyHeader>
                <EmptyTitle className="font-stage-title text-2xl">
                  {error ? getErrorMessage(error) : "书架上还没有绘本"}
                </EmptyTitle>
              </EmptyHeader>
              {!error && me?.role === "admin" && (
                <EmptyContent>
                  <Button
                    variant="link"
                    nativeButton={false}
                    render={<Link to="/admin/books" />}
                    className="text-current"
                  >
                    去管理后台上传
                  </Button>
                </EmptyContent>
              )}
            </Empty>
          ) : (
            <ul
              className={cn(
                "grid grid-cols-2 gap-y-14 md:grid-cols-3 xl:grid-cols-4",
                // 木书架要连成一整条，列之间不留空隙，间距放到每本书内部
                theme.plank ? "gap-x-0" : "gap-x-10",
              )}
            >
              {books.map((book) => (
                <li key={book.id} className={cn(theme.plank && "px-5")}>
                  <ShelfItem book={book} theme={theme} />
                </li>
              ))}
            </ul>
          )}
        </main>
      </div>
    </div>
  );
}

function ShelfItem({ book, theme }: { book: ShelfBook; theme: ShelfTheme }) {
  return (
    <Link
      to={`/books/${book.id}`}
      className="group flex flex-col items-center outline-none"
      aria-label={book.title}
    >
      {/* 封面底部对齐，像立在台面上 */}
      <div className="relative flex h-[clamp(160px,32vh,320px)] w-full items-end justify-center">
        {theme.lightPool && (
          <div
            aria-hidden
            className="absolute -bottom-5 left-1/2 h-10 w-[120%] -translate-x-1/2 bg-[radial-gradient(ellipse_at_center,rgba(255,214,107,.34),transparent_70%)]"
          />
        )}
        {theme.plank && (
          <div
            aria-hidden
            className="absolute top-full -right-5 -left-5 h-3 bg-linear-to-b from-[#E6BD84] to-[#CF9A5C] shadow-[0_10px_14px_rgba(120,80,30,.22)]"
          />
        )}
        <img
          src={book.cover_url}
          alt=""
          loading="lazy"
          className={cn(
            "relative max-h-full max-w-full rounded-md transition-transform duration-300 group-hover:-translate-y-1.5 group-focus-visible:-translate-y-1.5 group-focus-visible:outline-3 group-focus-visible:outline-offset-4 group-focus-visible:outline-stage-spot group-active:scale-[.98]",
            theme.cover,
          )}
        />
      </div>
      <p
        className={cn(
          "line-clamp-2 text-center text-sm leading-snug",
          theme.plank ? "mt-8" : "mt-7",
          theme.caption,
        )}
      >
        {book.title}
      </p>
    </Link>
  );
}

function UserMenu({
  username,
  isAdmin,
  theme,
  onThemeChange,
}: {
  username: string;
  isAdmin: boolean;
  theme: ShelfTheme;
  onThemeChange: (id: ShelfThemeId) => void;
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

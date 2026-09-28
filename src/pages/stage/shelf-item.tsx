// 书架上的一本书：封面（点击打开）+ 左上角的收藏按钮 + 书名
import { useRef } from "react";
import { Link, useNavigate } from "react-router";
import { cn } from "cn";
import { useToggleFavorite } from "@/api/shelf";
import type { ShelfBook } from "@/api/types";
import { Button } from "@/components/ui/button";
import { isBookOpening, startBookOpening } from "@/pages/stage/book-opening";
import { DoodleHeart } from "@/pages/stage/doodle-heart";
import { DoodleNote } from "@/pages/stage/doodle-note";
import { coverRectInReader } from "@/pages/stage/reader-layout";
import type { ShelfTheme } from "@/pages/stage/shelf-themes";
import { unlockStoryAudio } from "@/pages/stage/story-audio";
import {
  ENTRANCE_STAGGER_MS,
  PRESS_BOUNCE_MS,
  playFavoriteFeedback,
  playPressFeedback,
  playUnfavoriteFeedback,
} from "@/pages/stage/shelf-motion";

export function ShelfItem({
  book,
  theme,
  shelfPath,
  entranceIndex,
  motionEnabled,
  effectsRef,
}: {
  book: ShelfBook;
  theme: ShelfTheme;
  /** 当前书架地址（含页码、搜索词），从阅读页返回时回到这里 */
  shelfPath: string;
  /** 进场动画中的顺序；null 表示不播放进场动画 */
  entranceIndex: number | null;
  motionEnabled: boolean;
  effectsRef: React.RefObject<HTMLDivElement | null>;
}) {
  const navigate = useNavigate();
  const imageRef = useRef<HTMLImageElement>(null);

  // 点书：回弹 + 光点，然后封面飞到阅读页上封面的位置，再进入阅读页（D52）
  const onOpen = (e: React.MouseEvent) => {
    // 借这次点击解锁声音，进入阅读页后自动朗读才能直接播放（iPad Safari 的限制）
    if (book.voice_ready) unlockStoryAudio();
    const image = imageRef.current;
    // 按住修饰键时保留浏览器默认行为（如新标签页打开）
    if (!motionEnabled || !image || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    if (isBookOpening()) return;
    const from = image.getBoundingClientRect();
    const to = coverRectInReader(
      window.innerWidth,
      window.innerHeight,
      book.cover_aspect,
      book.orientation,
    );
    playPressFeedback(image, effectsRef.current);
    window.setTimeout(() => {
      void startBookOpening(image, from, to).then(() =>
        navigate(`/books/${book.id}`, { state: { shelfPath, opening: true } }),
      );
    }, PRESS_BOUNCE_MS * 0.7);
  };

  return (
    <div
      className={cn(
        "flex h-full min-h-0 flex-col items-center",
        entranceIndex !== null && "animate-shelf-hop motion-reduce:animate-none",
      )}
      style={
        entranceIndex !== null
          ? { animationDelay: `${entranceIndex * ENTRANCE_STAGGER_MS}ms` }
          : undefined
      }
    >
      {/* 封面区域：封面框按宽高比在其中取最大，底部对齐，像立在台面上 */}
      <div className="relative flex min-h-0 w-full flex-1 items-end justify-center [container-type:size]">
        {theme.lightPool && (
          <div
            aria-hidden
            className="absolute -bottom-5 left-1/2 h-10 w-[120%] -translate-x-1/2 bg-[radial-gradient(ellipse_at_center,rgba(255,214,107,.34),transparent_70%)]"
          />
        )}
        {theme.plank && (
          <div
            aria-hidden
            className="absolute top-full -right-3 -left-3 h-3 bg-linear-to-b from-[#E6BD84] to-[#CF9A5C] shadow-[0_10px_14px_rgba(120,80,30,.22)] sm:-right-5 sm:-left-5"
          />
        )}
        <div
          className="relative"
          style={{
            width: `min(100cqw, 100cqh * ${book.cover_aspect})`,
            aspectRatio: book.cover_aspect,
          }}
        >
          <Link
            to={`/books/${book.id}`}
            state={{ shelfPath }}
            onClick={onOpen}
            aria-label={book.title}
            className="group block size-full rounded-md outline-none"
          >
            <img
              ref={imageRef}
              data-shelf-cover
              src={book.cover_url}
              alt=""
              loading="lazy"
              className={cn(
                "size-full rounded-md object-cover transition-transform duration-300 group-hover:-translate-y-1.5 group-focus-visible:-translate-y-1.5 group-focus-visible:outline-3 group-focus-visible:outline-offset-4 group-focus-visible:outline-stage-spot group-active:scale-[.98]",
                theme.cover,
              )}
            />
          </Link>
          <FavoriteButton book={book} motionEnabled={motionEnabled} />
        </div>
      </div>
      <p
        className={cn(
          "line-clamp-1 shrink-0 text-center text-xs leading-snug sm:line-clamp-2 sm:text-sm",
          theme.plank ? "mt-5" : "mt-3",
          theme.caption,
        )}
      >
        {book.voice_ready && (
          <>
            <DoodleNote className="mr-1 inline-block size-[1.15em] -translate-y-[0.12em] align-middle" />
            <span className="sr-only">（有朗读）</span>
          </>
        )}
        {book.title}
      </p>
    </div>
  );
}

/** 封面左上角的手绘小爱心：点一下收藏 / 取消收藏（D55、D56） */
function FavoriteButton({ book, motionEnabled }: { book: ShelfBook; motionEnabled: boolean }) {
  const toggle = useToggleFavorite();
  const heartRef = useRef<SVGSVGElement>(null);
  const favorite = book.is_favorite;
  const label = favorite ? `取消收藏《${book.title}》` : `收藏《${book.title}》`;

  const onClick = () => {
    toggle.mutate({ id: book.id, favorite: !favorite });
    const heart = heartRef.current;
    if (!motionEnabled || !heart) return;
    if (favorite) playUnfavoriteFeedback(heart);
    else playFavoriteFeedback(heart);
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={label}
      aria-pressed={favorite}
      title={favorite ? "取消收藏" : "收藏"}
      onClick={onClick}
      // 像一张歪贴在封面角上的贴纸
      className="absolute -top-3.5 -left-3.5 z-10 size-10 -rotate-12 rounded-full bg-transparent p-0 transition-transform hover:scale-110 hover:bg-transparent focus-visible:ring-stage-spot/60 active:scale-95 motion-reduce:transition-none sm:size-11 dark:hover:bg-transparent [&_svg:not([class*='size-'])]:size-full"
    >
      <DoodleHeart
        ref={heartRef}
        filled={favorite}
        className="size-full drop-shadow-[0_2px_2px_rgba(30,20,50,.35)]"
      />
    </Button>
  );
}

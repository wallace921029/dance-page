import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { ArrowLeft, BookOpen, Maximize, Minimize } from "lucide-react";
import { useReaderBook } from "@/api/shelf";
import type { ReaderUnit } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Item, ItemActions, ItemContent, ItemTitle } from "@/components/ui/item";
import { Spinner } from "@/components/ui/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { useFullscreen } from "@/hooks/use-fullscreen";
import { getErrorMessage } from "@/lib/api";
import { READER_BACKGROUND, StageRoundButton, stageSubmitButtonClass } from "@/pages/stage/common";
import { finishBookOpening } from "@/pages/stage/book-opening";
import { FlipBook, type FlipBookHandle } from "@/pages/stage/flip-book";
import { CoverVideo } from "@/pages/stage/cover-video";
import { AutoReadToggle, ReadAloudSpeakers } from "@/pages/stage/read-aloud";
import { useReadAloud } from "@/pages/stage/use-read-aloud";

const NO_UNITS: ReaderUnit[] = [];

/** 从书架"翻开进入阅读"时，过渡层撤掉后等这么久再自动翻开封面 */
const AUTO_OPEN_DELAY_MS = 300;

export default function ReaderPage() {
  const { id = "" } = useParams();
  const location = useLocation();
  // 返回书架时回到打开这本书的地方（首页或我的收藏，含页码和搜索词）
  const shelfPath: unknown = location.state?.shelfPath;
  const shelfHref =
    typeof shelfPath === "string" && shelfPath.startsWith("/") && !shelfPath.startsWith("//")
      ? shelfPath
      : "/";
  const navigate = useNavigate();
  // 从书架点书进来且开启了书本动效：书架的过渡层还盖在上面（D52）
  const opening = location.state?.opening === true;
  const { data: book, isPending, error } = useReaderBook(id);
  const flipRef = useRef<FlipBookHandle>(null);
  const [visible, setVisible] = useState<number[]>([0]);
  // 各位置上的页码（单页 1 项，对开 [左, 右]）；排版前为 null
  const [slots, setSlots] = useState<(number | null)[] | null>(null);
  const [flipping, setFlipping] = useState(false);
  const [closing, setClosing] = useState(false);
  const units = book?.units ?? NO_UNITS;
  const hasAudio = units.some((u) => u.audio_url);
  // 封面动画（D96）：阅读页的第 1 页就是书架封面时，封面翻开前也在动
  const coverVideoUrl =
    book?.cover_video_url && book.cover_page_index === 0 ? book.cover_video_url : null;
  const coverSlot = slots?.indexOf(0) ?? -1;
  const readAloud = useReadAloud({
    units,
    readOrder: book?.read_order ?? "left_first",
    slots,
    flipping,
    skipFirstAutoRead: opening,
  });

  useDocumentTitle(book?.title);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") flipRef.current?.flipNext();
      if (e.key === "ArrowLeft") flipRef.current?.flipPrev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // 加载失败时也要撤掉书架的过渡层
  useEffect(() => {
    if (error) finishBookOpening();
  }, [error]);

  // 封面已在过渡层下就位：撤掉过渡层，再用真实的翻页动画翻开封面
  const onReady = () => {
    if (!opening) return;
    finishBookOpening();
    window.setTimeout(() => flipRef.current?.flipNext(), AUTO_OPEN_DELAY_MS);
    // 去掉 opening 标记，刷新页面时不再自动翻开；保留返回书架用的页码
    navigate(location.pathname, { replace: true, state: { shelfPath } });
  };

  const onVisibleChange = (pages: number[], pageSlots: (number | null)[]) => {
    setVisible(pages);
    setSlots(pageSlots);
    if (pages.includes(0)) setClosing(false);
  };

  const atEnd = book !== undefined && !closing && visible.includes(book.pages.length - 1);

  return (
    <div
      className="fixed inset-0 touch-none overflow-hidden overscroll-none font-stage text-stage-light select-none"
      style={{ background: READER_BACKGROUND }}
    >
      {book && (
        <FlipBook
          key={book.id}
          ref={flipRef}
          pages={book.pages}
          orientation={book.orientation}
          spreadStartPage={book.spread_start_page}
          background={READER_BACKGROUND}
          onVisibleChange={onVisibleChange}
          onFlippingChange={setFlipping}
          onReady={onReady}
          overlay={
            hasAudio || coverVideoUrl
              ? (layout) => (
                  <>
                    {coverVideoUrl && coverSlot !== -1 && (
                      <CoverVideo
                        src={coverVideoUrl}
                        active={!flipping}
                        className="absolute top-0 h-full object-cover"
                        style={{ left: coverSlot * layout.pageWidth, width: layout.pageWidth }}
                      />
                    )}
                    {hasAudio && (
                      <ReadAloudSpeakers
                        layout={layout}
                        units={units}
                        slots={slots}
                        flipping={flipping}
                      />
                    )}
                  </>
                )
              : undefined
          }
        />
      )}

      <div className="absolute top-[calc(0.75rem+env(safe-area-inset-top))] left-[calc(1rem+env(safe-area-inset-left))] z-10">
        <StageRoundButton label="返回书架" nativeButton={false} render={<Link to={shelfHref} />}>
          <ArrowLeft />
        </StageRoundButton>
      </div>
      <div className="absolute top-[calc(0.75rem+env(safe-area-inset-top))] right-[calc(1rem+env(safe-area-inset-right))] z-10 flex items-center gap-2">
        {hasAudio && <AutoReadToggle on={readAloud.autoRead} onToggle={readAloud.toggleAutoRead} />}
        <FullscreenButton />
      </div>

      {isPending ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <Spinner className="size-6" />
        </div>
      ) : error ? (
        <Empty className="dark absolute inset-0">
          <EmptyHeader>
            <EmptyTitle className="font-stage-title text-2xl text-stage-light">
              {getErrorMessage(error, "这本书暂时打不开")}
            </EmptyTitle>
          </EmptyHeader>
          <EmptyContent>
            <Button
              variant="link"
              nativeButton={false}
              render={<Link to={shelfHref} />}
              className="text-stage-light"
            >
              回到书架
            </Button>
          </EmptyContent>
        </Empty>
      ) : atEnd ? (
        <EndHint
          onClose={() => {
            setClosing(true);
            flipRef.current?.closeBook();
          }}
        />
      ) : (
        <div className="pointer-events-none absolute inset-x-0 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] text-center font-stage-title text-xl tracking-widest tabular-nums">
          {visible.map((p) => p + 1).join("–")} / {book.pages.length}
        </div>
      )}
    </div>
  );
}

function FullscreenButton() {
  const fullscreen = useFullscreen();
  if (!fullscreen.supported) return null;
  return (
    <StageRoundButton
      label={fullscreen.active ? "退出全屏" : "全屏"}
      onClick={fullscreen.toggle}
    >
      {fullscreen.active ? <Minimize /> : <Maximize />}
    </StageRoundButton>
  );
}

/** 翻到最后一页时的读完提示（D41） */
function EndHint({ onClose }: { onClose: () => void }) {
  return (
    <div className="absolute inset-x-0 bottom-[calc(0.5rem+env(safe-area-inset-bottom))] z-10 flex justify-center">
      <Item
        variant="outline"
        size="sm"
        className="w-auto animate-in gap-3 rounded-full border-stage-spot/40 bg-stage-night/80 py-1.5 pr-1.5 pl-5 shadow-[0_0_24px_rgba(255,214,107,0.25)] backdrop-blur fade-in slide-in-from-bottom-2 duration-500"
      >
        <ItemContent>
          <ItemTitle className="font-stage-title text-lg tracking-wider text-stage-light">
            故事讲完啦！
          </ItemTitle>
        </ItemContent>
        <ItemActions>
          <Button size="lg" onClick={onClose} className={`${stageSubmitButtonClass} rounded-full px-4`}>
            <BookOpen />
            合上书本
          </Button>
        </ItemActions>
      </Item>
    </div>
  );
}

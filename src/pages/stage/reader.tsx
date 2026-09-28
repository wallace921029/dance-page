import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, BookOpen, Maximize, Minimize } from "lucide-react";
import { useReaderBook } from "@/api/shelf";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Item, ItemActions, ItemContent, ItemTitle } from "@/components/ui/item";
import { Spinner } from "@/components/ui/spinner";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { useFullscreen } from "@/hooks/use-fullscreen";
import { getErrorMessage } from "@/lib/api";
import { READER_BACKGROUND, StageRoundButton, stageSubmitButtonClass } from "@/pages/stage/common";
import { FlipBook, type FlipBookHandle } from "@/pages/stage/flip-book";

// 书四周留出的空间：上方放按钮，下方放页码
const BOOK_PADDING = { top: 68, bottom: 56, x: 24 };

export default function ReaderPage() {
  const { id = "" } = useParams();
  const { data: book, isPending, error } = useReaderBook(id);
  const flipRef = useRef<FlipBookHandle>(null);
  const [visible, setVisible] = useState<number[]>([0]);
  const [closing, setClosing] = useState(false);

  useDocumentTitle(book?.title);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") flipRef.current?.flipNext();
      if (e.key === "ArrowLeft") flipRef.current?.flipPrev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const onVisibleChange = (pages: number[]) => {
    setVisible(pages);
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
          padding={BOOK_PADDING}
          onVisibleChange={onVisibleChange}
        />
      )}

      <div className="absolute top-3 left-4 z-10">
        <StageRoundButton label="返回书架" nativeButton={false} render={<Link to="/" />}>
          <ArrowLeft />
        </StageRoundButton>
      </div>
      <div className="absolute top-3 right-4 z-10">
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
            <Button variant="link" nativeButton={false} render={<Link to="/" />} className="text-stage-light">
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
        <div className="pointer-events-none absolute inset-x-0 bottom-3 text-center font-stage-title text-xl tracking-widest tabular-nums">
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
    <div className="absolute inset-x-0 bottom-2 z-10 flex justify-center">
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

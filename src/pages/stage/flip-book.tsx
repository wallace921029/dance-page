// 仿真翻页（page-flip / StPageFlip，HTML 模式）。M0 验证过的要点见 docs/progress.md。
import { useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";
import { PageFlip } from "page-flip";
import type { BookPage, Orientation, SpreadStartPage } from "@/api/types";
import { BOOK_PADDING_CSS, computeBookLayout } from "@/pages/stage/reader-layout";

// 只给当前页前后这么多页设置图片地址，其余页释放图片以节省平板内存（封面始终保留，合上书时要用）
const LOAD_WINDOW = 4;
const BLANK_PAGE_COLOR = "#fdfbf5";
const FLIPPING_TIME_MS = 800;

export type FlipBookHandle = {
  flipNext: () => void;
  flipPrev: () => void;
  /** 合上书本：用一次翻页动画直接翻回封面 */
  closeBook: () => void;
};

type FlipBookProps = {
  pages: BookPage[];
  orientation: Orientation;
  spreadStartPage: SpreadStartPage;
  /** 舞台背景，舞台页里会画一块与它对齐的背景 */
  background: string;
  /**
   * 当前可见的页码（从 0 开始）。slots 按位置给出：单页时 1 项，对开时 [左, 右]；
   * 舞台页、空白页为 null（如对开时封面在右半边，slots 为 [null, 0]）
   */
  onVisibleChange: (pages: number[], slots: (number | null)[]) => void;
  /** 开始拖动或翻页时为 true，翻页停稳后为 false */
  onFlippingChange?: (flipping: boolean) => void;
  /** 叠在书上方、与书同尺寸的一层（如朗读按钮）；翻页库不管理这一层 */
  overlay?: (layout: BookOverlayLayout) => React.ReactNode;
  /** 首次排版完成且封面图片加载好时调用一次 */
  onReady?: () => void;
  ref?: React.Ref<FlipBookHandle>;
};

/**
 * 翻页组件里的每一项：
 * - 数字：页码（从 0 开始）
 * - "blank"：为对齐跨页大图插入的空白纸页
 * - "stage"：封面左边的"舞台页"，内容是与舞台背景对齐的一块背景，看起来是空的
 */
type BookItem = number | "blank" | "stage";

export interface BookOverlayLayout {
  isDouble: boolean;
  pageWidth: number;
  pageHeight: number;
}

function buildItems(pageCount: number, isDouble: boolean, spreadStartPage: SpreadStartPage) {
  const pages: BookItem[] = Array.from({ length: pageCount }, (_, i) => i);
  if (!isDouble) return pages;
  // 对开时按 (0,1)(2,3)… 配对，封面左边放舞台页，让封面单独显示在右半边。
  // 不用 page-flip 自带的 showCover：它会把封面设成硬页（没有卷页效果），而且封面前面没有页，
  // 往回翻到封面时左侧被掀开的区域会一直露出当前左页，直到动画结束。
  const items: BookItem[] = ["stage", ...pages];
  // 跨页大图从第 3 页开始配对（3+4、5+6…）的书，在封面后插入一张空白页来对齐（D43）
  if (spreadStartPage === 3 && pageCount > 1) items.splice(2, 0, "blank");
  return items;
}

/** index 为对开左页（单页模式下为当前页）在 items 中的位置；返回各位置上的页码 */
function visibleSlots(items: BookItem[], index: number, isDouble: boolean) {
  return items
    .slice(index, index + (isDouble ? 2 : 1))
    .map((item) => (typeof item === "number" ? item : null));
}

function useElementSize(ref: React.RefObject<HTMLElement | null>) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width: Math.floor(width), height: Math.floor(height) });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return size;
}

export function FlipBook({
  pages,
  orientation,
  spreadStartPage,
  background,
  onVisibleChange,
  onFlippingChange,
  onReady,
  overlay,
  ref,
}: FlipBookProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const flipRef = useRef<PageFlip | null>(null);
  // 重建翻页组件（旋转屏幕等）时保持在同一页
  const currentPageRef = useRef(0);
  const coverIndexRef = useRef(0);
  // 回调放进 ref，避免父组件每次渲染传入新函数时重建整个翻页组件
  const onVisibleChangeRef = useRef(onVisibleChange);
  const onFlippingChangeRef = useRef(onFlippingChange);
  const onReadyRef = useRef(onReady);
  useLayoutEffect(() => {
    onVisibleChangeRef.current = onVisibleChange;
    onFlippingChangeRef.current = onFlippingChange;
    onReadyRef.current = onReady;
  });
  const readyFiredRef = useRef(false);
  // 内边距以内的可用区域（ResizeObserver 的 contentRect 不含内边距）
  const { width, height } = useElementSize(hostRef);

  const ratio = pages[0].width / pages[0].height;
  const { isDouble, pageWidth, pageHeight } = computeBookLayout(width, height, ratio, orientation);

  useImperativeHandle(ref, () => ({
    flipNext: () => flipRef.current?.flipNext(),
    flipPrev: () => flipRef.current?.flipPrev(),
    closeBook: () => flipRef.current?.flip(coverIndexRef.current),
  }));

  useEffect(() => {
    const host = hostRef.current;
    if (!host || pageWidth < 50) return;

    const items = buildItems(pages.length, isDouble, spreadStartPage);
    // page-flip 会把根元素宽度设成 100%，所以外面再套一层定宽容器来控制书的尺寸；
    // 根元素本身由这里创建，因为 pageFlip.destroy() 会把它从 DOM 中删掉
    const sizer = document.createElement("div");
    sizer.style.cssText = `flex:none;width:${pageWidth * (isDouble ? 2 : 1)}px`;
    const block = document.createElement("div");
    sizer.appendChild(block);
    host.appendChild(sizer);

    const images: (HTMLImageElement | null)[] = [];
    const stageBackdrops: HTMLDivElement[] = [];
    const elements = items.map((item) => {
      const el = document.createElement("div");
      // page-flip 绘制时会用 style.cssText 覆盖页面元素自身的内联样式，所以底色等样式放在内层元素上
      const paper = document.createElement("div");
      paper.style.cssText = "position:relative;width:100%;height:100%;overflow:hidden";
      el.appendChild(paper);
      if (item === "stage") {
        const backdrop = document.createElement("div");
        backdrop.style.cssText = `position:absolute;background:${background}`;
        paper.appendChild(backdrop);
        stageBackdrops.push(backdrop);
        images.push(null);
        return el;
      }
      paper.style.background = BLANK_PAGE_COLOR;
      if (item === "blank") {
        images.push(null);
        return el;
      }
      const img = document.createElement("img");
      img.alt = `第 ${item + 1} 页`;
      img.draggable = false;
      img.decoding = "async";
      img.style.cssText = "width:100%;height:100%;display:block;pointer-events:none";
      img.dataset.src = pages[item].url;
      paper.appendChild(img);
      images.push(img);
      return el;
    });

    const coverIndex = items.indexOf(0);
    const loadAround = (index: number) => {
      images.forEach((img, i) => {
        if (!img) return;
        const near = i === coverIndex || Math.abs(i - index) <= LOAD_WINDOW;
        if (near && !img.getAttribute("src")) img.src = img.dataset.src!;
        if (!near && img.getAttribute("src")) img.removeAttribute("src");
      });
    };

    const found = items.indexOf(currentPageRef.current);
    const startPage = found === -1 ? 0 : found;
    loadAround(startPage);

    // 封面图片加载好后通知一次（书架的"翻开进入阅读"过渡要等封面出现再撤掉）
    const coverImage = images[coverIndex];
    const fireReady = () => {
      if (readyFiredRef.current) return;
      readyFiredRef.current = true;
      onReadyRef.current?.();
    };
    if (!coverImage || coverImage.complete) requestAnimationFrame(fireReady);
    else {
      coverImage.addEventListener("load", fireReady, { once: true });
      coverImage.addEventListener("error", fireReady, { once: true });
    }

    // page-flip 在根元素宽度 < minWidth * 2 时切成单页模式；
    // 这里 minWidth = maxWidth = 页宽，由根元素宽度（1 倍或 2 倍页宽）决定单页还是对开
    const pageFlip = new PageFlip(block, {
      size: "stretch",
      width: pages[0].width,
      height: pages[0].height,
      minWidth: pageWidth,
      maxWidth: pageWidth,
      minHeight: 100,
      maxHeight: Math.max(pageHeight, 100),
      usePortrait: true,
      startPage,
      flippingTime: FLIPPING_TIME_MS,
      maxShadowOpacity: 0.5,
      mobileScrollSupport: true,
    });
    pageFlip.loadFromHTML(elements);
    // 对开时落单的最后一页会被设成硬页（整张翻转、没有卷页效果），全部改回软页，让动效一致
    for (let i = 0; i < pageFlip.getPageCount(); i++) pageFlip.getPage(i).setDensity("soft");

    // 舞台页里的背景与舞台（和 host 同尺寸）对齐。舞台页总在左页位置，即书的左上角
    const alignStageBackdrops = () => {
      const hostRect = host.getBoundingClientRect();
      const bookRect = block.getBoundingClientRect();
      for (const backdrop of stageBackdrops) {
        backdrop.style.left = `${hostRect.left - bookRect.left}px`;
        backdrop.style.top = `${hostRect.top - bookRect.top}px`;
        backdrop.style.width = `${hostRect.width}px`;
        backdrop.style.height = `${hostRect.height}px`;
      }
    };
    alignStageBackdrops();
    window.addEventListener("resize", alignStageBackdrops);

    const onFlip = (index: number) => {
      const slots = visibleSlots(items, index, isDouble);
      const visible = slots.filter((page): page is number => page !== null);
      currentPageRef.current = visible[0] ?? 0;
      onVisibleChangeRef.current(visible, slots);
      loadAround(index);
    };
    pageFlip.on("flip", (e) => onFlip(e.data));
    // 状态：read（停稳）、fold_corner（鼠标移到角上卷起一点）、user_fold（拖动中）、flipping（翻页动画）
    pageFlip.on("changeState", (e) =>
      onFlippingChangeRef.current?.(e.data === "user_fold" || e.data === "flipping"),
    );
    onFlip(startPage);
    flipRef.current = pageFlip;
    coverIndexRef.current = coverIndex;

    return () => {
      window.removeEventListener("resize", alignStageBackdrops);
      flipRef.current = null;
      pageFlip.destroy();
      sizer.remove();
    };
  }, [pages, isDouble, spreadStartPage, background, pageWidth, pageHeight]);

  return (
    <>
      <div
        ref={hostRef}
        className="absolute inset-0 flex items-center justify-center"
        style={{ padding: BOOK_PADDING_CSS }}
      />
      {overlay && pageWidth >= 50 && (
        // 与 host 相同的排版，中间放一个与书同尺寸的框；框外不拦截触摸，翻页照常
        <div
          className="pointer-events-none absolute inset-0 flex items-center justify-center"
          style={{ padding: BOOK_PADDING_CSS }}
        >
          <div
            className="relative flex-none"
            style={{ width: pageWidth * (isDouble ? 2 : 1), height: pageHeight }}
          >
            {overlay({ isDouble, pageWidth, pageHeight })}
          </div>
        </div>
      )}
    </>
  );
}

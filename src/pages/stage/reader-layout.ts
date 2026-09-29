// 阅读页的排版计算。书架的"翻开进入阅读"过渡也用它算出封面在阅读页上的落点，两边必须一致
import type { Orientation } from "@/api/types";

/** 书四周留出的空间：上方放按钮，下方放页码 */
const BASE_PADDING = { top: 68, bottom: 56, x: 24 };

/**
 * 阅读页书本区域的内边距（CSS）：在基础留白上再让出设备安全区。
 * 从主屏幕打开时页面会延伸到状态栏和底部横条下面（D59），平时安全区为 0
 */
export const BOOK_PADDING_CSS = [
  `calc(${BASE_PADDING.top}px + env(safe-area-inset-top))`,
  `calc(${BASE_PADDING.x}px + env(safe-area-inset-right))`,
  `calc(${BASE_PADDING.bottom}px + env(safe-area-inset-bottom))`,
  `calc(${BASE_PADDING.x}px + env(safe-area-inset-left))`,
].join(" ");

/** 把 BOOK_PADDING_CSS 换算成像素（安全区只能由浏览器算出来） */
function readBookPadding() {
  const probe = document.createElement("div");
  probe.style.cssText = `position:fixed;top:0;left:0;visibility:hidden;pointer-events:none;padding:${BOOK_PADDING_CSS}`;
  document.body.appendChild(probe);
  const style = getComputedStyle(probe);
  const padding = {
    top: parseFloat(style.paddingTop),
    right: parseFloat(style.paddingRight),
    bottom: parseFloat(style.paddingBottom),
    left: parseFloat(style.paddingLeft),
  };
  probe.remove();
  return padding;
}

export interface BookLayout {
  /** 竖版书在横屏时对开，其余情况单页（02-reader） */
  isDouble: boolean;
  pageWidth: number;
  pageHeight: number;
}

/** availWidth / availHeight 为留白以内可以放书的区域，ratio 为页面宽高比 */
export function computeBookLayout(
  availWidth: number,
  availHeight: number,
  ratio: number,
  orientation: Orientation,
): BookLayout {
  const isDouble = orientation === "portrait" && availWidth > availHeight;
  const pageWidth = Math.floor(Math.min(availWidth / (isDouble ? 2 : 1), availHeight * ratio));
  return { isDouble, pageWidth, pageHeight: Math.round(pageWidth / ratio) };
}

/** 刚打开绘本时封面在视口中的位置：对开时在右半边（左边是舞台页），单页时居中 */
export function coverRectInReader(
  width: number,
  height: number,
  ratio: number,
  orientation: Orientation,
) {
  const padding = readBookPadding();
  const availWidth = width - padding.left - padding.right;
  const availHeight = height - padding.top - padding.bottom;
  const { isDouble, pageWidth, pageHeight } = computeBookLayout(
    availWidth,
    availHeight,
    ratio,
    orientation,
  );
  const bookWidth = pageWidth * (isDouble ? 2 : 1);
  const bookLeft = padding.left + (availWidth - bookWidth) / 2;
  return {
    left: bookLeft + (isDouble ? pageWidth : 0),
    top: padding.top + (availHeight - pageHeight) / 2,
    width: pageWidth,
    height: pageHeight,
  };
}

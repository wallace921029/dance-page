// 阅读页的排版计算。书架的"翻开进入阅读"过渡也用它算出封面在阅读页上的落点，两边必须一致
import type { Orientation } from "@/api/types";

/** 书四周留出的空间：上方放按钮，下方放页码 */
export const BOOK_PADDING = { top: 68, bottom: 56, x: 24 };

export interface BookLayout {
  /** 竖版书在横屏时对开，其余情况单页（02-reader） */
  isDouble: boolean;
  pageWidth: number;
  pageHeight: number;
}

/** width / height 为阅读页可用区域（整个视口）的尺寸，ratio 为页面宽高比 */
export function computeBookLayout(
  width: number,
  height: number,
  ratio: number,
  orientation: Orientation,
): BookLayout {
  const isDouble = orientation === "portrait" && width > height;
  const availWidth = width - BOOK_PADDING.x * 2;
  const availHeight = height - BOOK_PADDING.top - BOOK_PADDING.bottom;
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
  const { isDouble, pageWidth, pageHeight } = computeBookLayout(width, height, ratio, orientation);
  const bookWidth = pageWidth * (isDouble ? 2 : 1);
  const availWidth = width - BOOK_PADDING.x * 2;
  const availHeight = height - BOOK_PADDING.top - BOOK_PADDING.bottom;
  const bookLeft = BOOK_PADDING.x + (availWidth - bookWidth) / 2;
  return {
    left: bookLeft + (isDouble ? pageWidth : 0),
    top: BOOK_PADDING.top + (availHeight - pageHeight) / 2,
    width: pageWidth,
    height: pageHeight,
  };
}

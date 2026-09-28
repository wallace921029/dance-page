// page-flip（StPageFlip）没有自带类型声明，这里只声明项目用到的部分
declare module "page-flip" {
  export interface FlipSetting {
    startPage: number;
    size: "fixed" | "stretch";
    width: number;
    height: number;
    minWidth: number;
    maxWidth: number;
    minHeight: number;
    maxHeight: number;
    drawShadow: boolean;
    flippingTime: number;
    usePortrait: boolean;
    startZIndex: number;
    autoSize: boolean;
    maxShadowOpacity: number;
    showCover: boolean;
    mobileScrollSupport: boolean;
    clickEventForward: boolean;
    useMouseEvents: boolean;
    swipeDistance: number;
    showPageCorners: boolean;
    disableFlipByClick: boolean;
  }

  export interface WidgetEvent<T> {
    data: T;
    object: PageFlip;
  }

  export interface Page {
    /** soft：卷页效果；hard：像硬纸板一样整张翻转 */
    setDensity(density: "soft" | "hard"): void;
  }

  export class PageFlip {
    constructor(element: HTMLElement, setting: Partial<FlipSetting>);
    loadFromHTML(items: HTMLElement[]): void;
    on(event: "flip", callback: (e: WidgetEvent<number>) => void): PageFlip;
    on(event: "changeState", callback: (e: WidgetEvent<string>) => void): PageFlip;
    on(event: "init", callback: (e: WidgetEvent<{ page: number; mode: string }>) => void): PageFlip;
    flipNext(corner?: "top" | "bottom"): void;
    flipPrev(corner?: "top" | "bottom"): void;
    turnToPage(page: number): void;
    /** 带动画翻到指定页（无论隔多少页，都只播放一次翻页动画） */
    flip(page: number, corner?: "top" | "bottom"): void;
    getCurrentPageIndex(): number;
    getPageCount(): number;
    getPage(index: number): Page;
    /** 会连同传入的根元素一起从 DOM 中移除 */
    destroy(): void;
  }
}

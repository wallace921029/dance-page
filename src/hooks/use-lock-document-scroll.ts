import { useLayoutEffect } from "react";

/**
 * 锁住整个文档的滚动：书架和阅读页都是固定一屏，不需要页面滚动。
 * iPad 主屏幕应用里，文档偶尔会被系统整体滚上去一截，露出底部的白色 body（回到书架也还在，
 * 下拉才会复位）。让 body 固定在视口里，文档就没有可滚动的范围，也就不会被顶上去。
 * 样式在 index.css 的 html.scroll-locked。
 */
export function useLockDocumentScroll() {
  useLayoutEffect(() => {
    const html = document.documentElement;
    window.scrollTo(0, 0);
    html.classList.add("scroll-locked");
    return () => html.classList.remove("scroll-locked");
  }, []);
}

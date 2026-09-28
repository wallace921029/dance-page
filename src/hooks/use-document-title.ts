import { useEffect } from "react";
import { APP_NAME } from "@/lib/app-info";

/** 设置浏览器标签页标题，格式为"页面名 · 萤火"；不传则只显示产品名 */
export function useDocumentTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} · ${APP_NAME}` : APP_NAME;
  }, [title]);
}

import { useEffect, useState } from "react";

type FullscreenDocument = Document & {
  webkitFullscreenElement?: Element | null;
  webkitExitFullscreen?: () => Promise<void>;
};
type FullscreenElement = HTMLElement & {
  webkitRequestFullscreen?: () => Promise<void>;
};

/** 浏览器全屏（iPad Safari 需要 webkit 前缀）。从主屏幕打开时本身就是全屏，不显示按钮 */
export function useFullscreen() {
  const doc = document as FullscreenDocument;
  const root = document.documentElement as FullscreenElement;
  const standalone = window.matchMedia("(display-mode: standalone)").matches;
  const supported = !standalone && Boolean(root.requestFullscreen ?? root.webkitRequestFullscreen);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const onChange = () => setActive(Boolean(doc.fullscreenElement ?? doc.webkitFullscreenElement));
    document.addEventListener("fullscreenchange", onChange);
    document.addEventListener("webkitfullscreenchange", onChange);
    return () => {
      document.removeEventListener("fullscreenchange", onChange);
      document.removeEventListener("webkitfullscreenchange", onChange);
    };
  }, [doc]);

  const toggle = () => {
    if (active) {
      (doc.exitFullscreen ?? doc.webkitExitFullscreen)?.call(doc);
    } else {
      (root.requestFullscreen ?? root.webkitRequestFullscreen)?.call(root);
    }
  };
  return { supported, active, toggle };
}

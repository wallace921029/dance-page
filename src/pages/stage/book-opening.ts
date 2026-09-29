// "翻开进入阅读"过渡（D48）：封面从书架飞到阅读页上封面的位置，四周渐渐变成阅读页的舞台背景。
// 过渡层直接挂在 document.body 上，从书架切到阅读页时不会被卸载；阅读页的封面出现后再由阅读页撤掉。
import { READER_BACKGROUND } from "@/pages/stage/common";

const FLIGHT_MS = 520;
const FADE_OUT_MS = 220;
/** 阅读页迟迟没有撤掉过渡层时（加载失败等）自动撤掉 */
const SAFETY_TIMEOUT_MS = 5000;

type Rect = { left: number; top: number; width: number; height: number };

let overlay: HTMLDivElement | null = null;
let safetyTimer = 0;

export function isBookOpening() {
  return overlay !== null;
}

/** from 为封面在书架上的位置，to 为封面在阅读页上的位置（都是视口坐标） */
export function startBookOpening(image: HTMLImageElement, from: Rect, to: Rect): Promise<void> {
  finishBookOpening();
  const layer = document.createElement("div");
  // 过渡期间挡住点击，避免孩子连点打开别的书
  layer.style.cssText =
    "position:fixed;top:0;left:0;width:100%;height:var(--app-screen-height);z-index:100";
  const dim = document.createElement("div");
  dim.style.cssText = `position:absolute;inset:0;background:${READER_BACKGROUND};opacity:0`;
  const flyer = document.createElement("img");
  flyer.src = image.currentSrc || image.src;
  flyer.alt = "";
  flyer.style.cssText = `position:absolute;left:0;top:0;width:${from.width}px;height:${from.height}px;transform-origin:0 0;border-radius:6px;box-shadow:0 18px 40px rgba(0,0,0,.35);will-change:transform`;
  layer.append(dim, flyer);
  document.body.append(layer);
  overlay = layer;
  safetyTimer = window.setTimeout(finishBookOpening, SAFETY_TIMEOUT_MS);

  const easing = "cubic-bezier(.3,.7,.3,1)";
  dim.animate([{ opacity: 0 }, { opacity: 1 }], { duration: FLIGHT_MS, easing, fill: "forwards" });
  const flight = flyer.animate(
    [
      { transform: `translate(${from.left}px, ${from.top}px)` },
      {
        transform: `translate(${to.left}px, ${to.top}px) scale(${to.width / from.width}, ${to.height / from.height})`,
      },
    ],
    { duration: FLIGHT_MS, easing, fill: "forwards" },
  );
  return flight.finished.then(
    () => undefined,
    () => undefined,
  );
}

/** 阅读页封面已就位：淡出并移除过渡层 */
export function finishBookOpening() {
  window.clearTimeout(safetyTimer);
  const layer = overlay;
  overlay = null;
  if (!layer) return;
  layer.style.pointerEvents = "none";
  layer
    .animate([{ opacity: 1 }, { opacity: 0 }], { duration: FADE_OUT_MS, fill: "forwards" })
    .finished.finally(() => layer.remove());
}

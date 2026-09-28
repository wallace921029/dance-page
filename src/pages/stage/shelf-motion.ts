// 书架上的书本动效（D48）：进场依次跳上书架、点按回弹 + 光点、萤火虫落在书上。
// 只使用位移、缩放、透明度（GPU 友好）；系统开启"减少动态效果"或用户关闭开关时全部不播放。
import { useEffect, useState } from "react";
import { isBookOpening } from "@/pages/stage/book-opening";

const STORAGE_KEY = "firefly.shelf-motion";

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function readPreference() {
  try {
    return localStorage.getItem(STORAGE_KEY) !== "off";
  } catch {
    return true;
  }
}

/** 书本动效开关（保存在这台设备上）。enabled 同时考虑了系统的"减少动态效果" */
export function useShelfMotion() {
  const [preference, setPreferenceState] = useState(readPreference);
  const reduced = prefersReducedMotion();
  const setPreference = (on: boolean) => {
    setPreferenceState(on);
    try {
      localStorage.setItem(STORAGE_KEY, on ? "on" : "off");
    } catch {
      // 保存失败只影响下次打开时的默认值
    }
  };
  return { enabled: preference && !reduced, preference, reduced, setPreference };
}

// ---------- 进场：依次跳上书架 ----------

/** 进场动画每次打开应用只播一次，从阅读页返回书架时不再重播 */
let entrancePlayed = false;
/** 只让前面这些书依次出现，后面的直接显示，避免书多时等太久 */
export const ENTRANCE_MAX_ITEMS = 12;
export const ENTRANCE_STAGGER_MS = 90;

/**
 * 是否播放进场动画。只在本次打开应用后第一次进入书架时为 true，播完一轮后变回 false：
 * 从阅读页返回、或翻页后再回到第 1 页时（书会重新挂载），都不会再跳一次。
 */
export function useEntranceOnce(enabled: boolean, booksShown: boolean) {
  const [play, setPlay] = useState(() => enabled && !entrancePlayed);
  useEffect(() => {
    // 书真正显示出来后才开始计时，书单加载慢时也能看到进场动画
    if (!play || !booksShown) return;
    entrancePlayed = true;
    const timer = window.setTimeout(
      () => setPlay(false),
      ENTRANCE_MAX_ITEMS * ENTRANCE_STAGGER_MS + 800,
    );
    return () => window.clearTimeout(timer);
  }, [play, booksShown]);
  return play;
}

// ---------- 点按：回弹 + 光点 ----------

export const PRESS_BOUNCE_MS = 260;

const SPARK_CLASS =
  "pointer-events-none absolute left-0 top-0 size-2.5 rounded-full bg-[radial-gradient(circle,#FFF8D6_0_25%,#FFD66B_45%,rgba(255,214,107,0)_72%)] shadow-[0_0_14px_4px_rgba(255,214,107,.5)]";

export function playPressFeedback(image: HTMLElement, layer: HTMLElement | null) {
  image.animate(
    [
      { transform: "scale(1.05, .93)" },
      { transform: "scale(.97, 1.06) translateY(-5%)", offset: 0.45 },
      { transform: "scale(1.01, .99)", offset: 0.75 },
      { transform: "none" },
    ],
    { duration: PRESS_BOUNCE_MS, easing: "cubic-bezier(.3,.7,.4,1)" },
  );
  if (!layer) return;
  const base = layer.getBoundingClientRect();
  const rect = image.getBoundingClientRect();
  const cx = rect.left - base.left + rect.width / 2;
  const cy = rect.top - base.top + rect.height * 0.45;
  const count = 9;
  for (let i = 0; i < count; i++) {
    const spark = document.createElement("span");
    spark.className = SPARK_CLASS;
    layer.append(spark);
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4;
    const distance = rect.width * (0.55 + Math.random() * 0.35);
    spark
      .animate(
        [
          { transform: `translate(${cx}px, ${cy}px) scale(.6)`, opacity: 1 },
          {
            transform: `translate(${cx + Math.cos(angle) * distance}px, ${cy + Math.sin(angle) * distance}px) scale(1)`,
            opacity: 0,
          },
        ],
        { duration: 620, easing: "cubic-bezier(.2,.7,.3,1)" },
      )
      .finished.finally(() => spark.remove());
  }
}

// ---------- 萤火虫落在书上 ----------

const FIREFLY_CLASS =
  "pointer-events-none absolute left-0 top-0 size-3 rounded-full opacity-0 bg-[radial-gradient(circle,#FFF8D6_0_25%,#FFD66B_45%,rgba(255,214,107,0)_72%)] shadow-[0_0_18px_6px_rgba(255,214,107,.5)]";
const HALO_CLASS =
  "pointer-events-none absolute rounded-md opacity-0 shadow-[0_0_36px_10px_rgba(255,214,107,.5)]";
const FIRST_LANDING_MS = 4000;
const LANDING_INTERVAL_MS = [12_000, 20_000] as const;

function isFullyVisible(el: Element) {
  const r = el.getBoundingClientRect();
  return r.top >= 0 && r.left >= 0 && r.bottom <= window.innerHeight && r.right <= window.innerWidth;
}

/**
 * 每隔十几秒，一只萤火虫飞到屏幕上某本书的右上角停一会儿，这本书微微发亮，然后飞走。
 * layer 为铺满书架内容区的定位层；书封面元素带 data-shelf-cover 属性。
 */
export function useShelfFirefly(layerRef: React.RefObject<HTMLElement | null>, enabled: boolean) {
  useEffect(() => {
    const layer = layerRef.current;
    if (!enabled || !layer) return;
    const fly = document.createElement("span");
    fly.className = FIREFLY_CLASS;
    const halo = document.createElement("div");
    halo.className = HALO_CLASS;
    layer.append(halo, fly);
    let timer = 0;
    let stopped = false;
    const wait = (ms: number) => new Promise((resolve) => (timer = window.setTimeout(resolve, ms)));
    const nextDelay = () =>
      LANDING_INTERVAL_MS[0] + Math.random() * (LANDING_INTERVAL_MS[1] - LANDING_INTERVAL_MS[0]);

    const landOnce = async () => {
      const covers = [...document.querySelectorAll("[data-shelf-cover]")].filter(isFullyVisible);
      if (document.hidden || isBookOpening() || covers.length === 0) return;
      const cover = covers[Math.floor(Math.random() * covers.length)];
      const base = layer.getBoundingClientRect();
      const c = cover.getBoundingClientRect();
      const size = fly.offsetWidth;
      // 停在封面右上角
      const tx = c.right - base.left - size * 1.2;
      const ty = c.top - base.top - size * 0.4;
      // 从可见区域的左侧或右侧飞入
      const visibleTop = Math.max(0, -base.top);
      const fromLeft = Math.random() < 0.5;
      const sx = fromLeft ? -size * 2 : base.width + size;
      const sy = visibleTop + window.innerHeight * (0.2 + Math.random() * 0.4);
      const arc = window.innerHeight * 0.15;
      const easing = "ease-in-out";

      await fly.animate(
        [
          { transform: `translate(${sx}px, ${sy}px)`, opacity: 0 },
          {
            transform: `translate(${(sx + tx) / 2}px, ${Math.min(sy, ty) - arc}px)`,
            opacity: 1,
            offset: 0.5,
          },
          { transform: `translate(${tx}px, ${ty}px)`, opacity: 1 },
        ],
        { duration: 1600, easing, fill: "forwards" },
      ).finished;
      if (stopped) return;
      Object.assign(halo.style, {
        left: `${c.left - base.left}px`,
        top: `${c.top - base.top}px`,
        width: `${c.width}px`,
        height: `${c.height}px`,
      });
      halo.animate([{ opacity: 0 }, { opacity: 1 }, { opacity: 0 }], {
        duration: 2400,
        easing,
      });
      await wait(2400);
      if (stopped) return;
      const ex = fromLeft ? base.width + size : -size * 2;
      await fly.animate(
        [
          { transform: `translate(${tx}px, ${ty}px)`, opacity: 1 },
          { transform: `translate(${(tx + ex) / 2}px, ${ty - arc}px)`, opacity: 1, offset: 0.5 },
          { transform: `translate(${ex}px, ${visibleTop + window.innerHeight * 0.15}px)`, opacity: 0 },
        ],
        { duration: 1500, easing, fill: "forwards" },
      ).finished;
    };

    (async () => {
      await wait(FIRST_LANDING_MS);
      while (!stopped) {
        await landOnce().catch(() => undefined);
        if (stopped) return;
        await wait(nextDelay());
      }
    })();

    return () => {
      stopped = true;
      window.clearTimeout(timer);
      fly.getAnimations().forEach((a) => a.cancel());
      fly.remove();
      halo.remove();
    };
  }, [layerRef, enabled]);
}

// ---------- 收藏：手绘爱心的反馈动画（D56） ----------

const INK = "#2B2340";
const PARTICLE_SVGS = [
  // 小爱心
  `<svg viewBox="0 0 40 40" width="100%" height="100%"><path d="M20 34C13 29 5 23 5.5 14.5C6 8.5 12 5.5 16.5 8.5C18.5 10 19.5 12 20.3 14C21.2 11.3 23.5 7.5 28 7C33.5 6.5 36.5 11 35 17.5C33.5 24 26.5 29.5 20 34Z" fill="#FF6F91" stroke="${INK}" stroke-width="3" stroke-linejoin="round"/></svg>`,
  // 四角小星星
  `<svg viewBox="0 0 40 40" width="100%" height="100%"><path d="M20 4C21.5 14 26 18.5 36 20C26 21.5 21.5 26 20 36C18.5 26 14 21.5 4 20C14 18.5 18.5 14 20 4Z" fill="#FFD66B" stroke="${INK}" stroke-width="2.6" stroke-linejoin="round"/></svg>`,
  // 小圆点
  `<svg viewBox="0 0 40 40" width="100%" height="100%"><circle cx="20" cy="20" r="11" fill="#8FD3F4" stroke="${INK}" stroke-width="3.4"/></svg>`,
];

/**
 * 收藏：墨线像现场画出来一样描一遍，爱心弹起并左右晃，周围飘出几颗手绘小爱心和小星星。
 * heart 为爱心 SVG；小装饰放在 heart 最近的定位祖先元素里。
 */
export function playFavoriteFeedback(heart: SVGSVGElement) {
  const ink = heart.querySelector<SVGPathElement>('[data-part="ink"]');
  if (ink) {
    ink.style.strokeDasharray = "100";
    ink
      .animate([{ strokeDashoffset: 100 }, { strokeDashoffset: 0 }], {
        duration: 420,
        easing: "cubic-bezier(.4,.1,.3,1)",
      })
      .finished.finally(() => (ink.style.strokeDasharray = ""));
  }
  heart.animate(
    [
      { transform: "scale(.55) rotate(-14deg)" },
      { transform: "scale(1.28) rotate(9deg)", offset: 0.45 },
      { transform: "scale(.94) rotate(-4deg)", offset: 0.72 },
      { transform: "none" },
    ],
    { duration: 580, easing: "cubic-bezier(.3,.7,.4,1)" },
  );

  const container = heart.closest("button")?.parentElement;
  if (!container) return;
  const base = container.getBoundingClientRect();
  const rect = heart.getBoundingClientRect();
  const cx = rect.left - base.left + rect.width / 2;
  const cy = rect.top - base.top + rect.height / 2;
  const count = 7;
  for (let i = 0; i < count; i++) {
    const particle = document.createElement("span");
    const size = rect.width * (0.42 + Math.random() * 0.2);
    particle.innerHTML = PARTICLE_SVGS[i % PARTICLE_SVGS.length];
    particle.style.cssText = `position:absolute;left:0;top:0;width:${size}px;height:${size}px;pointer-events:none;z-index:20`;
    container.append(particle);
    // 主要往上方和两侧飘
    const angle = (-165 + (150 * i) / (count - 1) + (Math.random() * 16 - 8)) * (Math.PI / 180);
    const distance = rect.width * (0.9 + Math.random() * 0.6);
    const x = cx + Math.cos(angle) * distance - size / 2;
    const y = cy + Math.sin(angle) * distance - size / 2;
    const spin = Math.random() * 60 - 30;
    particle
      .animate(
        [
          {
            transform: `translate(${cx - size / 2}px, ${cy - size / 2}px) scale(.3) rotate(0deg)`,
            opacity: 0,
          },
          {
            transform: `translate(${x}px, ${y}px) scale(1) rotate(${spin}deg)`,
            opacity: 1,
            offset: 0.55,
          },
          {
            transform: `translate(${x}px, ${y - rect.height * 0.35}px) scale(.8) rotate(${spin * 1.5}deg)`,
            opacity: 0,
          },
        ],
        { duration: 760, delay: 90, easing: "cubic-bezier(.2,.7,.3,1)", fill: "backwards" },
      )
      .finished.finally(() => particle.remove());
  }
}

/** 取消收藏：轻轻缩一下、晃一下 */
export function playUnfavoriteFeedback(heart: SVGSVGElement) {
  heart.animate(
    [
      { transform: "none" },
      { transform: "scale(.78) rotate(-10deg)", offset: 0.4 },
      { transform: "scale(1.05) rotate(4deg)", offset: 0.75 },
      { transform: "none" },
    ],
    { duration: 340, easing: "ease-out" },
  );
}

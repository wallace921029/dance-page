// 书架页的四套主题（D47）。设计参考：docs/design/shelf-style-options.html
import { useState } from "react";

export type ShelfThemeId = "night" | "sunny" | "dusk" | "garden";

export interface ShelfTheme {
  id: ShelfThemeId;
  name: string;
  /** 深色主题：给页面加 .dark，让 shadcn 组件使用深色配色 */
  dark: boolean;
  /** CSS background-image（多层渐变），画在固定铺满屏幕的背景层上 */
  background: string;
  /** 品牌名、标题等主要文字 */
  text: string;
  /** 书名等次要文字 */
  caption: string;
  /** 右上角头像 */
  avatar: string;
  /** 封面描边和投影：让浅色、深色封面都能从背景里"跳"出来 */
  cover: string;
  /** 封面下方的暖色光斑 */
  lightPool?: boolean;
  /** 绘本立在木书架上 */
  plank?: boolean;
  /** 偶尔有萤火虫飞来停在书上（D48） */
  fireflies?: boolean;
}

const STARS = [
  [12, 22, 0.85],
  [27, 9, 0.6],
  [44, 16, 0.75],
  [63, 7, 0.6],
  [71, 25, 0.7],
  [90, 30, 0.55],
  [83, 12, 0.7],
  [5, 40, 0.5],
]
  .map(([x, y, a]) => `radial-gradient(circle at ${x}% ${y}%, rgba(255,255,255,${a}) 0 1.5px, transparent 2.5px)`)
  .join(", ");

export const SHELF_THEMES: Record<ShelfThemeId, ShelfTheme> = {
  night: {
    id: "night",
    name: "萤火夜空",
    dark: true,
    background: `${STARS}, radial-gradient(ellipse 70% 55% at 50% 0%, rgba(255,214,140,.16), transparent 70%), linear-gradient(#1A1F4D, #262C63 62%, #30377A)`,
    text: "text-stage-light",
    caption: "text-stage-light/85",
    avatar: "bg-white/12 text-stage-light",
    cover: "ring-2 ring-[rgba(255,238,196,.55)] shadow-[0_0_28px_rgba(255,214,140,.22)]",
    lightPool: true,
    fireflies: true,
  },
  sunny: {
    id: "sunny",
    name: "晴天书架",
    dark: false,
    background: "linear-gradient(#CBE6F2, #E4F2F3 55%, #EEF6EE)",
    text: "text-[#2E3A63]",
    caption: "text-[#3D4870]",
    avatar: "bg-white text-[#2E3A63] shadow-sm",
    cover: "ring-1 ring-[rgba(46,58,99,.12)] shadow-[6px_8px_18px_rgba(60,45,20,.28)]",
    plank: true,
  },
  dusk: {
    id: "dusk",
    name: "黄昏萤火",
    dark: true,
    background: "linear-gradient(#F4B997 0%, #D7A2B2 30%, #9185BF 58%, #4A4A8C 82%, #353873)",
    text: "text-[#FFF2D6]",
    caption: "text-[#FFF2D6] [text-shadow:0_1px_4px_rgba(40,30,70,.55)]",
    avatar: "bg-white/20 text-[#FFF2D6]",
    cover: "ring-2 ring-[rgba(255,248,230,.6)] shadow-[0_12px_28px_rgba(40,30,70,.35)]",
    fireflies: true,
  },
  garden: {
    id: "garden",
    name: "纸剪花园",
    dark: false,
    background: "linear-gradient(#E3EFEA, #EEF5EC 60%)",
    text: "text-[#35574A]",
    caption: "text-[#2E4E41]",
    avatar: "bg-white text-[#35574A] shadow-sm",
    cover: "ring-1 ring-[rgba(53,87,74,.14)] shadow-[5px_9px_20px_rgba(40,70,55,.3)]",
  },
};

export const SHELF_THEME_ORDER: ShelfThemeId[] = ["night", "sunny", "dusk", "garden"];

/** 点一下切换按钮后的下一套主题：四套轮流，最后一套之后回到第一套（D104） */
export function nextShelfTheme(id: ShelfThemeId): ShelfThemeId {
  return SHELF_THEME_ORDER[(SHELF_THEME_ORDER.indexOf(id) + 1) % SHELF_THEME_ORDER.length];
}
const DEFAULT_THEME: ShelfThemeId = "night";
const STORAGE_KEY = "firefly.shelf-theme";

function readStoredTheme(): ShelfThemeId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored in SHELF_THEMES) return stored as ShelfThemeId;
  } catch {
    // 隐私模式等情况下无法访问 localStorage，使用默认主题
  }
  return DEFAULT_THEME;
}

/** 当前书架主题，保存在这台设备上（每台平板可以各用各的主题） */
export function useShelfTheme() {
  const [themeId, setThemeId] = useState<ShelfThemeId>(readStoredTheme);
  const setTheme = (id: ShelfThemeId) => {
    setThemeId(id);
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // 保存失败只影响下次打开时的默认值
    }
  };
  return [SHELF_THEMES[themeId], setTheme] as const;
}

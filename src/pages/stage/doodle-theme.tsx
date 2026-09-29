// 手绘涂鸦风格的书架主题图标（D104），与收藏爱心、书本动效星星同一套画法：贴纸白边 + 蜡笔填充 + 两遍墨线。
// 每套主题一个图标：萤火夜空 = 月亮和星星、晴天书架 = 太阳、黄昏萤火 = 落在地平线上的半个太阳、纸剪花园 = 一朵花
import type { ShelfThemeId } from "@/pages/stage/shelf-themes";

const INK = "#2B2340";
const STICKER = "#FFFDF7";

// ---------- 萤火夜空 ----------
const MOON_PATH =
  "M26.5 5.5C17 6.5 10.5 14.5 11 23C11.5 31.5 19 37 28.5 35.2C21.8 33 18.6 27 19.4 20.8C20.2 14.6 23 9.6 26.5 5.5Z";
const MOON_STAR_PATH =
  "M30.4 9.4C30.7 11.8 31.6 12.8 34 13.4C31.6 14.1 30.8 15.2 30.4 17.8C30 15.4 29 14.3 26.8 13.6C29 13 30 12 30.4 9.4Z";

// ---------- 晴天书架 ----------
const SUN_PATH =
  "M20.2 12.4C25 12.2 28.2 15.6 28 20.2C27.8 24.8 24.4 28 19.8 27.8C15.2 27.6 12 24.2 12.3 19.7C12.6 15.4 15.9 12.6 20.2 12.4Z";
const SUN_RAYS =
  "M20 3.8C20.1 6 19.9 7.4 20.1 8.6M20.3 31.6C20.1 33 20.2 34.4 20 36.2M3.8 20.1C5.6 20 7 20.2 8.4 19.9M31.6 20.3C33 20.1 34.4 20.2 36.2 19.9M8.6 8.4C9.8 9.4 10.8 10.4 11.8 11.6M28.3 28.5C29.4 29.4 30.4 30.6 31.6 31.7M31.5 8.5C30.5 9.6 29.5 10.6 28.4 11.7M11.6 28.4C10.6 29.5 9.6 30.5 8.5 31.6";

// ---------- 黄昏萤火 ----------
const DUSK_SUN_PATH = "M9.2 27C9 20.4 14 15.2 20.2 15.1C26.6 15 31.2 20.4 30.9 27Z";
const DUSK_RAYS =
  "M20 6.6C20.1 8.4 19.9 9.6 20.1 10.8M7.6 13.4C8.9 14.5 9.8 15.4 10.8 16.6M32.5 13.5C31.2 14.6 30.3 15.4 29.2 16.6M4.4 22.4C5.8 22.3 6.8 22.5 7.8 22.3M35.6 22.4C34.2 22.3 33.2 22.5 32.2 22.3";
const DUSK_HORIZON = "M3.6 27.4C12 26.8 28 27.8 36.4 27.1";
const DUSK_WATER = "M9.4 32.2C14 31.4 17 32.6 21 31.8M23.6 32.4C27 31.8 29 32.4 31 32";

// ---------- 纸剪花园：五片花瓣绕着花心转一圈 ----------
const PETAL_PATH = "M20 19.4C15.8 13.4 16.2 6.6 20.2 4.6C24 6.4 24.6 13.4 20 19.4Z";
const PETAL_ANGLES = [0, 72, 144, 216, 288];
const STEM_PATH = "M20.2 24C20 29 20.6 33 20.4 37";
const LEAF_PATH = "M20.4 31.6C24.6 30.4 28.2 31.4 30.2 28.6C25.6 27.6 21.6 28.4 20.4 31.6Z";

export function DoodleTheme({ id, className }: { id: ShelfThemeId; className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} overflow="visible" aria-hidden>
      {id === "night" && <Night />}
      {id === "sunny" && <Sunny />}
      {id === "dusk" && <Dusk />}
      {id === "garden" && <Garden />}
    </svg>
  );
}

/** 墨线：主线 + 一道错位的淡线，像铅笔描了两遍 */
function Ink({ d, width = 2.2, fill = "none" }: { d: string; width?: number; fill?: string }) {
  return (
    <>
      <path
        d={d}
        fill={fill}
        stroke={INK}
        strokeWidth={width}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d={d}
        fill="none"
        stroke={INK}
        strokeWidth="1"
        strokeOpacity=".3"
        strokeLinecap="round"
        transform="translate(.8 -.7) rotate(2 20 20)"
      />
    </>
  );
}

/** 贴纸白边 */
function Sticker({ d, width = 7 }: { d: string; width?: number }) {
  return (
    <path
      d={d}
      fill={STICKER}
      stroke={STICKER}
      strokeWidth={width}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  );
}

function Night() {
  return (
    <>
      <Sticker d={MOON_PATH} />
      <Sticker d={MOON_STAR_PATH} />
      <path d={MOON_PATH} fill="#FFE9A8" />
      <path d={MOON_STAR_PATH} fill="#FFD66B" />
      {/* 月亮上的两个小坑 */}
      <g fill="#F5D27A">
        <circle cx="15.6" cy="19.4" r="1.6" />
        <circle cx="18.6" cy="28.6" r="1.2" />
      </g>
      <Ink d={MOON_PATH} />
      <Ink d={MOON_STAR_PATH} width={1.8} />
    </>
  );
}

function Sunny() {
  return (
    <>
      <Sticker d={SUN_RAYS} width={6.4} />
      <Sticker d={SUN_PATH} />
      <path d={SUN_PATH} fill="#FFC94A" />
      {/* 高光 */}
      <path
        d="M15.6 17.6C16.2 15.8 17.6 14.8 19.4 14.7"
        stroke="#FFF6D6"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <Ink d={SUN_RAYS} width={2.2} />
      <Ink d={SUN_PATH} />
    </>
  );
}

function Dusk() {
  return (
    <>
      <Sticker d={DUSK_RAYS} width={6.4} />
      <Sticker d={DUSK_SUN_PATH} />
      <Sticker d={DUSK_HORIZON} width={6} />
      <path d={DUSK_SUN_PATH} fill="#FF9E7A" />
      <path
        d="M13.4 22.6C14.4 19.8 16.6 18.2 19 18"
        stroke="#FFD2B8"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <Ink d={DUSK_RAYS} width={2.2} />
      <Ink d={DUSK_SUN_PATH} />
      <Ink d={DUSK_HORIZON} />
      <Ink d={DUSK_WATER} width={1.8} />
    </>
  );
}

function Garden() {
  return (
    <>
      <Sticker d={STEM_PATH} width={6.4} />
      <Sticker d={LEAF_PATH} width={6} />
      {PETAL_ANGLES.map((angle) => (
        <g key={angle} transform={`rotate(${angle} 20 19.4)`}>
          <Sticker d={PETAL_PATH} width={6.4} />
        </g>
      ))}
      <path d={LEAF_PATH} fill="#8FCB9B" />
      {PETAL_ANGLES.map((angle) => (
        <g key={angle} transform={`rotate(${angle} 20 19.4)`}>
          <path d={PETAL_PATH} fill="#F7A8B8" />
        </g>
      ))}
      <Ink d={STEM_PATH} width={2.4} />
      <Ink d={LEAF_PATH} width={2} />
      {PETAL_ANGLES.map((angle) => (
        <g key={angle} transform={`rotate(${angle} 20 19.4)`}>
          <Ink d={PETAL_PATH} width={2} />
        </g>
      ))}
      {/* 花心 */}
      <circle cx="20.2" cy="19.6" r="3.6" fill="#FFD66B" stroke={INK} strokeWidth="2" />
    </>
  );
}

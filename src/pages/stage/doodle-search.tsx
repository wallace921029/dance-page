// 手绘涂鸦风格的搜索图标（D118），与收藏爱心、书本动效星星同一套画法：贴纸白边 + 蜡笔填充 + 两遍墨线。
// 一把画得不太圆的放大镜：淡蓝色的镜片带一道高光，金黄色的手柄
import { useId } from "react";

/** 不太圆的手画圆圈（镜片） */
const LENS_PATH =
  "M17.2 6.4C23.4 6 28.4 10.8 28.2 17.2C28 23.4 23 28 16.9 27.8C10.8 27.6 6.2 22.8 6.5 16.8C6.8 11 11.4 6.7 17.2 6.4Z";
/** 手柄：一笔从镜片右下斜着画出去 */
const HANDLE_PATH = "M25 25.4C28.2 28.4 31 31.2 34.4 34.6";
const HIGHLIGHT_PATH = "M11.6 15.2C12.2 12.4 14.2 10.8 16.6 10.4";
const INK = "#2B2340";
const STICKER = "#FFFDF7";

export function DoodleSearch({ className }: { className?: string }) {
  const clipId = `doodle-search-${useId().replace(/[^\w-]/g, "")}`;
  return (
    <svg viewBox="0 0 40 40" className={className} overflow="visible" aria-hidden>
      <defs>
        <clipPath id={clipId}>
          <path d={LENS_PATH} />
        </clipPath>
      </defs>
      {/* 贴纸白边：在深色、浅色书架主题上都清楚 */}
      <g stroke={STICKER} strokeLinecap="round" strokeLinejoin="round" fill={STICKER}>
        <path d={LENS_PATH} strokeWidth="7" />
        <path d={HANDLE_PATH} strokeWidth="13" fill="none" />
      </g>
      {/* 手柄：墨线描边 + 金黄色蜡笔 */}
      <path d={HANDLE_PATH} fill="none" stroke={INK} strokeWidth="8.4" strokeLinecap="round" />
      <path d={HANDLE_PATH} fill="none" stroke="#FFD66B" strokeWidth="5.2" strokeLinecap="round" />
      <path
        d="M27.6 27.6C29.4 29.4 30.8 30.8 32.6 32.6"
        fill="none"
        stroke="#FFE9A8"
        strokeWidth="1.8"
        strokeLinecap="round"
        opacity=".85"
      />
      {/* 镜片：淡蓝色 + 蜡笔涂抹的斜线纹理 */}
      <path d={LENS_PATH} fill="#BDE7FF" />
      <g clipPath={`url(#${clipId})`}>
        <path
          d="M0 14 L14 0 M0 24 L24 0 M2 32 L32 2 M8 38 L38 8 M16 42 L42 16"
          stroke="#E4F5FF"
          strokeWidth="2.4"
          strokeLinecap="round"
          opacity=".9"
        />
      </g>
      {/* 墨线：主线 + 一道错位的淡线，像铅笔描了两遍 */}
      <path
        d={LENS_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d={LENS_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="1"
        strokeOpacity=".35"
        strokeLinecap="round"
        transform="translate(.9 -.7) rotate(2 17 17)"
      />
      <path
        d={HIGHLIGHT_PATH}
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="2.4"
        strokeLinecap="round"
        opacity=".95"
      />
    </svg>
  );
}

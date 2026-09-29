// 手绘涂鸦风格的刷新图标（D120），与收藏爱心、搜索放大镜同一套画法：贴纸白边 + 蜡笔填充 + 两遍墨线。
// 薄荷绿的不规则圆里，一道兜了一圈的墨线箭头
import { useId } from "react";

/** 不太圆的手画圆圈 */
const BLOB_PATH =
  "M20 3.8C29.6 3.5 36.6 10.4 36.2 20.2C35.8 29.6 29 36.6 19.8 36.3C10.6 36 3.6 29.4 3.9 19.8C4.2 11 10.8 4.1 20 3.8Z";
/** 兜了一圈的箭杆（缺口在右上方）和箭头 */
const ARC_PATH = "M26.7 14.6C23.2 10.6 17 10.8 13.6 14.6C10.2 18.4 10.6 24.4 14.4 27.4C18.2 30.4 24.4 29.8 27.4 25.8C28.2 24.6 28.7 23.2 28.7 21.8";
const HEAD_PATH = "M24.6 22.6L28.9 18.6L32.6 22.8";
const INK = "#2B2340";

export function DoodleRefresh({ className }: { className?: string }) {
  const clipId = `doodle-refresh-${useId().replace(/[^\w-]/g, "")}`;
  return (
    <svg viewBox="0 0 40 40" className={className} overflow="visible" aria-hidden>
      <defs>
        <clipPath id={clipId}>
          <path d={BLOB_PATH} />
        </clipPath>
      </defs>
      {/* 贴纸白边：在深色、浅色书架主题上都清楚 */}
      <path d={BLOB_PATH} fill="#FFFDF7" stroke="#FFFDF7" strokeWidth="7" strokeLinejoin="round" />
      <path d={BLOB_PATH} fill="#9BE3C4" />
      {/* 蜡笔涂抹的斜线纹理 */}
      <g clipPath={`url(#${clipId})`}>
        <path
          d="M0 15 L15 0 M0 25 L25 0 M2 33 L33 2 M8 39 L39 8 M16 42 L42 16 M26 44 L44 26"
          stroke="#D3F5E6"
          strokeWidth="2.4"
          strokeLinecap="round"
          opacity=".85"
        />
      </g>
      {/* 墨线：主线 + 一道错位的淡线，像铅笔描了两遍 */}
      <path
        d={BLOB_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d={BLOB_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="1"
        strokeOpacity=".35"
        transform="translate(.9 -.8) rotate(3 20 20)"
      />
      <g fill="none" stroke={INK} strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
        <path d={ARC_PATH} />
        <path d={HEAD_PATH} />
      </g>
    </svg>
  );
}

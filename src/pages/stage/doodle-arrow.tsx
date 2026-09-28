// 手绘涂鸦风格的翻页按钮图标（D57），与收藏爱心同一套画法：贴纸白边 + 蜡笔填充 + 两遍墨线
import { useId } from "react";

/** 不太圆的手画圆圈 */
const BLOB_PATH =
  "M24 4.6C35.2 4.1 44.1 12.6 43.5 24.6C42.9 35.6 34.3 43.9 23.4 43.5C12.6 43.1 4.3 34.6 4.7 23.3C5.1 12.9 13.1 5.1 24 4.6Z";
/** 手画的向右箭头：箭杆 + 箭头 */
const ARROW_PATH = "M14.2 24.6C20.1 24.1 26.2 24.4 32.4 24.1M25.8 17.2C28.4 19.6 30.9 21.9 33.1 24.3C30.8 26.5 28.5 28.7 26.1 31.2";
const INK = "#2B2340";

export function DoodleArrow({
  direction,
  className,
  ref,
}: {
  direction: "previous" | "next";
  className?: string;
  ref?: React.Ref<SVGSVGElement>;
}) {
  const clipId = `doodle-arrow-${useId().replace(/[^\w-]/g, "")}`;
  return (
    <svg ref={ref} viewBox="0 0 48 48" className={className} overflow="visible" aria-hidden>
      <defs>
        <clipPath id={clipId}>
          <path d={BLOB_PATH} />
        </clipPath>
      </defs>
      <path d={BLOB_PATH} fill="#FFFDF7" stroke="#FFFDF7" strokeWidth="7" strokeLinejoin="round" />
      <path d={BLOB_PATH} fill="#FFD66B" />
      <g clipPath={`url(#${clipId})`}>
        <path
          d="M0 18 L18 0 M0 28 L28 0 M2 36 L36 2 M8 42 L42 8 M16 46 L46 16 M26 48 L48 26"
          stroke="#FFE9A8"
          strokeWidth="2.6"
          strokeLinecap="round"
          opacity=".85"
        />
      </g>
      <path
        d={BLOB_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d={BLOB_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="1.1"
        strokeOpacity=".35"
        transform="translate(.9 -.8) rotate(3 24 24)"
      />
      {/* "上一页"把箭头左右翻转 */}
      <g data-part="arrow" transform={direction === "previous" ? "matrix(-1 0 0 1 48 0)" : undefined}>
        <path
          d={ARROW_PATH}
          fill="none"
          stroke={INK}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
    </svg>
  );
}

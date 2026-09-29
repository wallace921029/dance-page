// 手绘涂鸦风格的"书本动效"开关图标（D103），与收藏爱心、翻页箭头同一套画法：
// 贴纸白边 + 蜡笔填充 + 两遍墨线。开着时是亮起来的金黄色（小星星缓慢闪烁，没有外圈），关着时是没亮的灰紫色（没有蜡笔纹、不闪）
import { useId } from "react";

/** 故意画得不太对称的四角星，像手画的 */
const BIG_STAR_PATH =
  "M17 5C17.9 12.4 21.6 17.1 29 19.1C21.7 20.6 18.6 25 17.4 33C16.4 25.4 12.6 21.4 5 19.6C12.4 17.8 16.2 13.4 17 5Z";
const SMALL_STAR_PATH =
  "M31.2 3.2C31.6 6 32.7 7.3 35.5 8C32.7 8.9 31.7 10.2 31.1 13.2C30.7 10.4 29.3 9 26.6 8.2C29.2 7.4 30.7 6.1 31.2 3.2Z";
const INK = "#2B2340";

export function DoodleSparkle({ on, className }: { on: boolean; className?: string }) {
  const clipId = `doodle-sparkle-${useId().replace(/[^\w-]/g, "")}`;
  // 关着时是没亮的灰紫色：不会和白色贴纸边混在一起
  const fill = on ? "#FFD66B" : "#CFC8E3";
  return (
    <svg viewBox="0 0 40 40" className={className} overflow="visible" aria-hidden>
      <defs>
        <clipPath id={clipId}>
          <path d={BIG_STAR_PATH} />
        </clipPath>
      </defs>
      {/* 贴纸白边：在深色、浅色书架主题上都清楚 */}
      <g fill="#FFFDF7" stroke="#FFFDF7" strokeWidth="7" strokeLinejoin="round">
        <path d={BIG_STAR_PATH} />
        <path d={SMALL_STAR_PATH} />
      </g>
      <g fill={fill} style={{ transition: "fill .25s ease" }}>
        <path d={BIG_STAR_PATH} />
        <path d={SMALL_STAR_PATH} />
      </g>
      {on && (
        // 蜡笔涂抹的斜线纹理
        <g clipPath={`url(#${clipId})`}>
          <path
            d="M0 18 L18 0 M0 28 L28 0 M2 36 L36 2 M8 42 L42 8 M16 46 L46 16 M26 48 L48 26"
            stroke="#FFE9A8"
            strokeWidth="2.4"
            strokeLinecap="round"
            opacity=".85"
          />
        </g>
      )}
      {/* 墨线：主线 + 一道错位的淡线，像铅笔描了两遍 */}
      <g fill="none" stroke={INK} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d={BIG_STAR_PATH} />
        <g
          // 开着时小星星缓慢闪烁；系统减少动态效果时不闪
          className={
            on
              ? "animate-twinkle origin-center [transform-box:fill-box] motion-reduce:animate-none"
              : undefined
          }
        >
          <path d={SMALL_STAR_PATH} />
        </g>
      </g>
      <path
        d={BIG_STAR_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="1"
        strokeOpacity=".35"
        strokeLinecap="round"
        transform="translate(.9 -.7) rotate(2 17 19)"
      />
    </svg>
  );
}

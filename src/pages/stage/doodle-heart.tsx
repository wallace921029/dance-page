// 手绘涂鸦风格的收藏爱心（D56）：贴纸白边 + 奶油 / 粉色底 + 蜡笔涂抹 + 两遍墨线
import { useId } from "react";

/** 故意画得不太对称的心形，像手画的 */
const DOODLE_HEART_PATH =
  "M20 34.5C13 29.4 5.2 23.4 5.4 14.2C5.6 8.1 11.4 5.2 16.1 8.3C18.2 9.7 19.4 11.7 20.3 13.9C21.1 11.2 23.4 7.4 27.7 6.9C33.4 6.3 36.6 11 35.2 17.2C33.8 23.8 26.4 29.6 20 34.5Z";

const INK = "#2B2340";

export function DoodleHeart({
  filled,
  className,
  ref,
}: {
  filled: boolean;
  className?: string;
  ref?: React.Ref<SVGSVGElement>;
}) {
  // useId 的返回值带特殊字符，不能直接用在 url(#...) 里
  const clipId = `doodle-heart-${useId().replace(/[^\w-]/g, "")}`;
  return (
    <svg ref={ref} viewBox="0 0 40 40" className={className} overflow="visible" aria-hidden>
      <defs>
        <clipPath id={clipId}>
          <path d={DOODLE_HEART_PATH} />
        </clipPath>
      </defs>
      {/* 贴纸白边：让爱心在深色、浅色、彩色封面上都清楚 */}
      <path
        d={DOODLE_HEART_PATH}
        fill="#FFFDF7"
        stroke="#FFFDF7"
        strokeWidth="7"
        strokeLinejoin="round"
      />
      <path
        data-part="fill"
        d={DOODLE_HEART_PATH}
        fill={filled ? "#FF6F91" : "#FFF3E0"}
        style={{ transition: "fill .25s ease" }}
      />
      {filled && (
        <>
          {/* 蜡笔涂抹的斜线纹理 */}
          <g clipPath={`url(#${clipId})`} data-part="scribble">
            <path
              d="M1 16 L15 2 M2 24 L24 2 M5 31 L31 5 M11 35 L36 10 M18 37 L38 17 M26 38 L39 25"
              stroke="#FF9DB5"
              strokeWidth="2.2"
              strokeLinecap="round"
              opacity=".8"
            />
          </g>
          {/* 高光 */}
          <path
            d="M10.4 14.6C10.6 12.1 12.3 10.5 14.6 10.6"
            stroke="#FFFFFF"
            strokeWidth="2.2"
            strokeLinecap="round"
            fill="none"
            opacity=".95"
          />
        </>
      )}
      {/* 墨线：主线 + 一道错位的淡线，像铅笔描了两遍 */}
      <path
        data-part="ink"
        d={DOODLE_HEART_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={100}
      />
      <path
        d={DOODLE_HEART_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="1.1"
        strokeOpacity=".35"
        strokeLinecap="round"
        transform="translate(.9 -.7) rotate(2 20 20)"
      />
    </svg>
  );
}

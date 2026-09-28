// 手绘涂鸦风格的朗读小喇叭（docs/06 第 8.2 节），与翻页按钮同一套画法：贴纸白边 + 蜡笔填充 + 两遍墨线
import { useId } from "react";
import { cn } from "cn";

/** 不太圆的手画圆圈（与翻页按钮相同） */
const BLOB_PATH =
  "M24 4.6C35.2 4.1 44.1 12.6 43.5 24.6C42.9 35.6 34.3 43.9 23.4 43.5C12.6 43.1 4.3 34.6 4.7 23.3C5.1 12.9 13.1 5.1 24 4.6Z";
/** 喇叭：方形底座 + 张开的喇叭口，边线故意不太直 */
const SPEAKER_PATH =
  "M12.6 20.4C14.6 20.2 16.6 20.5 18.6 20.2L25.2 14.8C25.9 21 25.7 27.3 25.4 33.5L18.5 28.2C16.6 28 14.6 28.3 12.7 28.1C12.3 25.5 12.2 23 12.6 20.4Z";
const WAVE_NEAR = "M29.4 19.9C31.3 22.5 31.4 25.8 29.5 28.4";
const WAVE_FAR = "M33.3 16.1C36.8 20.7 36.9 27.4 33.4 32.1";
const INK = "#2B2340";

export function DoodleSpeaker({ playing, className }: { playing: boolean; className?: string }) {
  const clipId = `doodle-speaker-${useId().replace(/[^\w-]/g, "")}`;
  return (
    <svg viewBox="0 0 48 48" className={className} overflow="visible" aria-hidden>
      <defs>
        <clipPath id={clipId}>
          <path d={BLOB_PATH} />
        </clipPath>
      </defs>
      <path d={BLOB_PATH} fill="#FFFDF7" stroke="#FFFDF7" strokeWidth="7" strokeLinejoin="round" />
      <path d={BLOB_PATH} fill={playing ? "#FFB86B" : "#FFD66B"} style={{ transition: "fill .25s ease" }} />
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
      <path d={SPEAKER_PATH} fill={INK} stroke={INK} strokeWidth="1.6" strokeLinejoin="round" />
      {/* 声波：播放时一闪一闪 */}
      <g
        fill="none"
        stroke={INK}
        strokeWidth="2.6"
        strokeLinecap="round"
        className={cn(playing && "animate-pulse motion-reduce:animate-none")}
      >
        <path d={WAVE_NEAR} />
        <path d={WAVE_FAR} opacity={playing ? 1 : 0.55} />
      </g>
    </svg>
  );
}

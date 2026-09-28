// 书架上"有朗读"的标记（D70）：手绘小音符，与收藏爱心同一套画法（贴纸白边 + 暖黄填充 + 墨线）
const HEAD_PATH =
  "M4.6 18.1C4.8 16.2 7 14.8 9.1 15.1C10.9 15.4 11.8 16.8 11.3 18.3C10.7 20.1 8.5 21.3 6.6 20.9C5.3 20.6 4.5 19.5 4.6 18.1Z";
const STEM_PATH = "M11.1 17.8C11.2 13.2 11 8.6 11.4 3.7";
const FLAG_PATH = "M11.4 3.7C13.6 5.3 16.4 6.2 17.3 9C17.8 10.6 17.2 12 16.3 12.9";
const INK = "#2B2340";

export function DoodleNote({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 22 24" className={className} overflow="visible" aria-hidden>
      {/* 贴纸白边：在深色、浅色书架主题上都清楚 */}
      <g fill="none" stroke="#FFFDF7" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round">
        <path d={HEAD_PATH} />
        <path d={STEM_PATH} />
        <path d={FLAG_PATH} />
      </g>
      <path d={HEAD_PATH} fill="#FFD66B" />
      <g fill="none" stroke={INK} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d={HEAD_PATH} />
        <path d={STEM_PATH} />
        <path d={FLAG_PATH} />
      </g>
    </svg>
  );
}

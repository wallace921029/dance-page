// 手绘涂鸦风格的默认头像，以及账户小弹窗里用的两个图标（D105）。
// 与收藏爱心、书本动效星星同一套画法：贴纸白边 + 蜡笔填充 + 两遍墨线
const INK = "#2B2340";
const STICKER = "#FFFDF7";

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

// ---------- 默认头像：圆脸小人 ----------
const FACE_PATH =
  "M20.4 9.2C27.6 9 33.2 14.6 33 22C32.8 29.2 27.2 34.8 20 34.6C12.8 34.4 7.2 28.8 7.4 21.6C7.6 14.4 13.2 9.4 20.4 9.2Z";
const HAIR_PATH =
  "M12.2 14.2C12.6 8.8 17 5.2 22.2 5.6C27.2 6 30.4 9.6 28.6 13.6C25.6 11.4 20.6 11 17 12.6C15.4 13.4 13.8 14 12.2 14.2Z";
const COWLICK_PATH = "M21 5.8C21.4 3.6 23 2.4 25 2.8";
const SMILE_PATH = "M15.4 27C17.4 29.8 22.6 29.8 24.8 26.8";

export function DoodleAvatar({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} overflow="visible" aria-hidden>
      <Sticker d={FACE_PATH} />
      <Sticker d={HAIR_PATH} width={6} />
      <Sticker d={COWLICK_PATH} width={6} />
      <path d={FACE_PATH} fill="#FFDDBD" />
      <path d={HAIR_PATH} fill="#8A6247" />
      {/* 脸颊的红晕 */}
      <g fill="#FF9DB5" opacity=".75">
        <circle cx="11.8" cy="26.2" r="2.3" />
        <circle cx="28.4" cy="26.2" r="2.3" />
      </g>
      <Ink d={FACE_PATH} />
      <Ink d={HAIR_PATH} width={2} />
      <Ink d={COWLICK_PATH} width={2} />
      {/* 眼睛和高光 */}
      <g fill={INK}>
        <circle cx="15.2" cy="22" r="1.9" />
        <circle cx="24.8" cy="22" r="1.9" />
      </g>
      <g fill="#FFFFFF">
        <circle cx="15.8" cy="21.3" r=".65" />
        <circle cx="25.4" cy="21.3" r=".65" />
      </g>
      <path
        d={SMILE_PATH}
        fill="none"
        stroke={INK}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------- 管理后台：齿轮 ----------
const TOOTH_PATH = "M17.8 6.2C17.9 3.6 22.3 3.4 22.4 6.1L22.9 11H17.4Z";
const TOOTH_ANGLES = [0, 45, 90, 135, 180, 225, 270, 315];
const GEAR_BODY_PATH =
  "M20.2 10.6C25.6 10.4 29.6 14.4 29.4 20C29.2 25.4 25.4 29.4 19.9 29.2C14.4 29 10.6 25.2 10.8 19.8C11 14.4 14.8 10.8 20.2 10.6Z";
const GEAR_HOLE_PATH =
  "M20.1 16C22.4 15.9 24 17.6 23.9 19.9C23.8 22.2 22.2 23.9 19.9 23.8C17.6 23.7 16.1 22.1 16.2 19.8C16.3 17.6 17.9 16.1 20.1 16Z";

export function DoodleGear({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} overflow="visible" aria-hidden>
      {TOOTH_ANGLES.map((angle) => (
        <g key={angle} transform={`rotate(${angle} 20 20)`}>
          <Sticker d={TOOTH_PATH} width={5.6} />
        </g>
      ))}
      <Sticker d={GEAR_BODY_PATH} width={6} />
      {TOOTH_ANGLES.map((angle) => (
        <g key={angle} transform={`rotate(${angle} 20 20)`}>
          <path d={TOOTH_PATH} fill="#FFC94A" />
        </g>
      ))}
      <path d={GEAR_BODY_PATH} fill="#FFC94A" />
      {/* 高光 */}
      <path
        d="M14.2 16.6C15 14.8 16.6 13.6 18.4 13.4"
        stroke="#FFF1BF"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      {TOOTH_ANGLES.map((angle) => (
        <g key={angle} transform={`rotate(${angle} 20 20)`}>
          <Ink d={TOOTH_PATH} width={1.9} />
        </g>
      ))}
      <Ink d={GEAR_BODY_PATH} width={2} />
      <path d={GEAR_HOLE_PATH} fill="#FFF3E0" />
      <Ink d={GEAR_HOLE_PATH} width={2} />
    </svg>
  );
}

// ---------- 退出登录：门 + 走出去的箭头 ----------
const DOOR_PATH =
  "M8.2 7C8 5.6 9 4.6 10.4 4.6H22.2C23.6 4.6 24.6 5.6 24.5 7L24.7 33.2C24.7 34.6 23.7 35.6 22.3 35.5H10.4C9 35.6 8 34.6 8.2 33.2Z";
const DOOR_ARROW_PATH =
  "M17.6 20.2C23.6 19.8 29.4 20.4 35 20.1M29.6 13.8C32 16.2 33.8 18.2 35.4 20.2C33.6 22.4 31.6 24.4 29 26.6";

export function DoodleExit({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} overflow="visible" aria-hidden>
      <Sticker d={DOOR_PATH} />
      <Sticker d={DOOR_ARROW_PATH} width={6.4} />
      <path d={DOOR_PATH} fill="#E8B27C" />
      {/* 木纹 */}
      <path
        d="M13.4 9C13.2 15 13.6 21 13.3 27.6M19 9.4C18.8 14 19.2 19 18.9 23"
        stroke="#F3CDA0"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="21" cy="21.4" r="1.5" fill="#FFF3E0" />
      <Ink d={DOOR_PATH} />
      <Ink d={DOOR_ARROW_PATH} width={2.6} />
    </svg>
  );
}

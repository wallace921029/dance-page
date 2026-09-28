// 书架主题的背景与装饰：固定铺满屏幕、位于内容下方，不接收点击。
// 背景渐变画在这层固定元素上，而不是 background-attachment: fixed（iPad Safari 不支持，滚动时渐变会被拉长）
import type { ShelfTheme, ShelfThemeId } from "@/pages/stage/shelf-themes";

type Spot = { left: string; top: string; duration?: number; delay?: number };

function Fireflies({ spots }: { spots: Spot[] }) {
  return spots.map((spot, i) => (
    <span
      key={i}
      className="absolute size-2.5 animate-firefly rounded-full bg-[radial-gradient(circle,#FFF8D6_0_25%,#FFD66B_45%,rgba(255,214,107,0)_72%)] shadow-[0_0_14px_4px_rgba(255,214,107,.45)] motion-reduce:animate-none"
      style={{
        left: spot.left,
        top: spot.top,
        animationDuration: `${spot.duration ?? 7}s`,
        animationDelay: `${spot.delay ?? 0}s`,
      }}
    />
  ));
}

function Cloud({ className, opacity = 0.9 }: { className: string; opacity?: number }) {
  return (
    <svg viewBox="0 0 40 16" className={`absolute ${className}`} aria-hidden>
      <path
        d="M6 14 a5 5 0 0 1 2-9.6 a7 7 0 0 1 13-2 a6 6 0 0 1 11 3.6 a4.6 4.6 0 0 1 1 8Z"
        fill="#fff"
        opacity={opacity}
      />
    </svg>
  );
}

function NightBackdrop() {
  return (
    <>
      <svg viewBox="0 0 10 10" className="absolute top-24 right-[8%] size-12" aria-hidden>
        {/* 用遮罩挖出月牙，不依赖背景色 */}
        <mask id="shelf-crescent">
          <rect width="10" height="10" fill="#fff" />
          <circle cx="6.8" cy="3.8" r="3.6" fill="#000" />
        </mask>
        <circle cx="5" cy="5" r="4" fill="#F7E7A1" mask="url(#shelf-crescent)" />
      </svg>
      <svg
        viewBox="0 0 100 18"
        preserveAspectRatio="none"
        className="absolute inset-x-0 bottom-0 h-[clamp(70px,14vh,150px)] w-full"
        aria-hidden
      >
        <path d="M0 9 Q12 2 26 8 T52 7 T78 8 T100 5 V18 H0Z" fill="#2B3471" />
        <path d="M0 13 Q18 7 36 12 T70 11 T100 10 V18 H0Z" fill="#232A5E" />
      </svg>
      <Fireflies
        spots={[
          { left: "5%", top: "46%" },
          { left: "31%", top: "82%", duration: 9, delay: -3 },
          { left: "52%", top: "30%", duration: 11, delay: -5 },
          { left: "74%", top: "78%" },
          { left: "93%", top: "52%", duration: 9, delay: -2 },
          { left: "18%", top: "22%", duration: 11, delay: -6 },
        ]}
      />
    </>
  );
}

function SunnyBackdrop() {
  return (
    <>
      <svg viewBox="0 0 10 10" className="absolute top-3 left-1/2 size-14 -translate-x-1/2" aria-hidden>
        <circle cx="5" cy="5" r="3.4" fill="#FFE08A" />
        <circle cx="5" cy="5" r="4.8" fill="none" stroke="#FFE08A" strokeWidth=".5" strokeDasharray="1 1.2" />
      </svg>
      <Cloud className="top-28 left-[5%] w-44" />
      <Cloud className="top-[45%] right-[6%] w-32" opacity={0.8} />
      <Cloud className="bottom-[12%] left-[38%] w-28" opacity={0.7} />
    </>
  );
}

function DuskBackdrop() {
  return (
    <>
      <svg
        viewBox="0 0 100 20"
        preserveAspectRatio="none"
        className="absolute inset-x-0 bottom-0 h-[clamp(70px,14vh,150px)] w-full"
        aria-hidden
      >
        <path d="M0 12 Q10 9 20 11 T40 10 T60 12 T80 9 T100 11 V20 H0Z" fill="#2F2F63" />
      </svg>
      {/* 小屋和小树单独画，避免随屏幕宽度拉伸变形 */}
      <svg
        viewBox="0 0 12 10"
        className="absolute right-[12%] bottom-[clamp(28px,6vh,62px)] w-[clamp(40px,6vw,72px)]"
        aria-hidden
      >
        <path d="M1 10 V4.5 l5-4 5 4 V10Z" fill="#2F2F63" />
        <rect x="4.9" y="5.4" width="2.2" height="2.2" fill="#FFD66B" />
      </svg>
      <svg
        viewBox="0 0 10 14"
        className="absolute bottom-[clamp(30px,6.5vh,66px)] left-[8%] w-[clamp(26px,3.5vw,44px)]"
        aria-hidden
      >
        <path d="M5 14 V7" stroke="#2F2F63" strokeWidth="1.4" />
        <circle cx="5" cy="5" r="4.5" fill="#2F2F63" />
      </svg>
      <Fireflies
        spots={[
          { left: "9%", top: "80%" },
          { left: "34%", top: "86%", duration: 9, delay: -3 },
          { left: "61%", top: "82%", duration: 11, delay: -5 },
          { left: "86%", top: "76%" },
        ]}
      />
    </>
  );
}

function GardenBackdrop() {
  return (
    <>
      <svg viewBox="0 0 40 16" className="absolute top-24 left-[10%] w-40" aria-hidden>
        <path
          d="M6 14 a5 5 0 0 1 2-9.6 a7 7 0 0 1 13-2 a6 6 0 0 1 11 3.6 a4.6 4.6 0 0 1 1 8Z"
          fill="#FAFCF8"
        />
      </svg>
      <svg
        viewBox="0 0 100 26"
        preserveAspectRatio="none"
        className="absolute inset-x-0 bottom-0 h-[clamp(90px,18vh,200px)] w-full drop-shadow-[0_-4px_6px_rgba(40,70,55,.18)]"
        aria-hidden
      >
        <path d="M0 10 Q20 2 40 9 T80 6 T100 8 V26 H0Z" fill="#C4DCC3" />
        <path d="M0 16 Q25 9 50 15 T100 13 V26 H0Z" fill="#A5CBA9" />
        <path d="M0 21 Q30 16 60 20 T100 19 V26 H0Z" fill="#86B592" />
      </svg>
    </>
  );
}

const BACKDROPS: Record<ShelfThemeId, () => React.ReactNode> = {
  night: NightBackdrop,
  sunny: SunnyBackdrop,
  dusk: DuskBackdrop,
  garden: GardenBackdrop,
};

export function ShelfBackdrop({ theme }: { theme: ShelfTheme }) {
  const Backdrop = BACKDROPS[theme.id];
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 overflow-hidden"
      style={{ backgroundImage: theme.background }}
    >
      <Backdrop />
    </div>
  );
}

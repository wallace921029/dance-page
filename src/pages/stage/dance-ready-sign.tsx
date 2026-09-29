// "Dance Ready!" 剧场招牌（D70，docs/02-reader.md）：封面底部一块会发光的小招牌，
// 虚线像一圈灯泡，缓慢呼吸发光；系统开启"减少动态效果"时不闪
import "@fontsource/zcool-qingke-huangyou/latin.css";
import { cn } from "cn";

export function DanceReadySign({
  className,
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <span
      className={cn(
        "pointer-events-none inline-block rounded-[0.4em] border-[0.14em] border-dotted border-stage-spot bg-stage-night/90 px-[0.55em] pt-[0.2em] pb-[0.1em] font-stage-sign leading-none tracking-wide whitespace-nowrap text-stage-spot animate-marquee-glow motion-reduce:animate-none",
        className,
      )}
      style={style}
    >
      Dance Ready!
    </span>
  );
}

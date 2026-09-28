// 封面动画（D96）：像魔法报纸上会动的照片。叠在静态封面上，开始播放后才淡入，
// 看不见（滚出屏幕、翻页中）时暂停并立即隐藏，露出下面的静态封面。视频首尾帧就是封面原图，切换不跳。
import { useEffect, useRef, useState } from "react";
import { cn } from "cn";

export function CoverVideo({
  src,
  active = true,
  className,
  style,
}: {
  src: string;
  /** false 时暂停并隐藏（如翻页过程中） */
  active?: boolean;
  className?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    if (!active) {
      video.pause();
      return;
    }
    // 只播放屏幕里看得见的：书架上的书多时省电、省内存
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) void video.play().catch(() => undefined);
        else video.pause();
      },
      { threshold: 0.1 },
    );
    observer.observe(video);
    return () => {
      observer.disconnect();
      video.pause();
    };
  }, [active, src]);

  const visible = active && playing;
  return (
    <video
      ref={ref}
      src={src}
      aria-hidden
      muted
      loop
      playsInline
      preload="metadata"
      disablePictureInPicture
      onPlaying={() => setPlaying(true)}
      onPause={() => setPlaying(false)}
      style={style}
      className={cn(
        // 与书架封面的上浮动画同样 0.3 秒，一起动
        "pointer-events-none transition-[opacity,transform] duration-300 motion-reduce:hidden",
        visible ? "opacity-100" : "opacity-0",
        // 翻页一开始就立即隐藏，不在卷起的页面上残留
        !active && "invisible",
        className,
      )}
    />
  );
}

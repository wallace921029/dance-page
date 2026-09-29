// 叠在静态画面上的循环视频：封面动画（D96，像魔法报纸上会动的照片）和开页动画（A4，Dance Ready!）。
// 开始播放后才淡入，看不见（滚出屏幕、翻页中）时暂停并立即隐藏，露出下面的静态画面。
// 视频是正放再倒放的来回循环，首尾都是原画，切换不跳（D99）。系统开启"减少动态效果"时不显示。
import { useEffect, useRef, useState } from "react";
import { cn } from "cn";

// 视频整个下载到内存里缓存起来（D117）：书架翻页、阅读页翻页会卸载再重建 <video>，
// 交给浏览器自己取的话，iPad Safari 每次都要重新分段请求、等缓冲，封面会静止好一会儿才动。
// 动画都只有几秒，放内存里没问题；总量有上限，最久没用的先丢（正在播放的不丢）。
const MAX_CACHE_BYTES = 64 * 1024 * 1024;

type CachedVideo = { url: string; size: number; refs: number };

// Map 的插入顺序就是最近使用的顺序：最久没用的在最前面
const cache = new Map<string, CachedVideo>();
const pending = new Map<string, Promise<CachedVideo | null>>();

function trimCache() {
  let total = 0;
  for (const entry of cache.values()) total += entry.size;
  for (const [src, entry] of cache) {
    if (total <= MAX_CACHE_BYTES) return;
    if (entry.refs > 0) continue;
    URL.revokeObjectURL(entry.url);
    cache.delete(src);
    total -= entry.size;
  }
}

function loadVideo(src: string): Promise<CachedVideo | null> {
  const hit = cache.get(src);
  if (hit) {
    cache.delete(src);
    cache.set(src, hit);
    return Promise.resolve(hit);
  }
  let request = pending.get(src);
  if (!request) {
    request = fetch(src)
      .then((res) => (res.ok ? res.blob() : Promise.reject(new Error(String(res.status)))))
      .then((blob) => {
        const entry = { url: URL.createObjectURL(blob), size: blob.size, refs: 0 };
        cache.set(src, entry);
        trimCache();
        return entry;
      })
      .catch(() => null)
      .finally(() => pending.delete(src));
    pending.set(src, request);
  }
  return request;
}

/** 返回可以给 <video> 用的地址：缓存好的本地地址；下载失败时退回原地址；下载完成前为 undefined */
function useCachedVideoUrl(src: string) {
  const [state, setState] = useState<{ src: string; url: string } | null>(null);
  useEffect(() => {
    let cancelled = false;
    let held: CachedVideo | null = null;
    void loadVideo(src).then((entry) => {
      if (cancelled) return;
      if (entry) {
        entry.refs += 1;
        held = entry;
      }
      setState({ src, url: entry?.url ?? src });
    });
    return () => {
      cancelled = true;
      if (held) held.refs -= 1;
    };
  }, [src]);
  return state?.src === src ? state.url : undefined;
}

export function LoopVideo({
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
  const url = useCachedVideoUrl(src);

  useEffect(() => {
    const video = ref.current;
    if (!video || !url) return;
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
  }, [active, url]);

  const visible = active && playing;
  return (
    <video
      ref={ref}
      src={url}
      aria-hidden
      muted
      loop
      playsInline
      preload="auto"
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

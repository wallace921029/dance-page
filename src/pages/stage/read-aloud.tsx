// 阅读页的朗读按钮：每页的手绘小喇叭、顶部的"自动朗读"开关。逻辑在 use-read-aloud.ts
import { useSyncExternalStore } from "react";
import { cn } from "cn";
import type { ReaderUnit } from "@/api/types";
import { Button } from "@/components/ui/button";
import { DoodleSpeaker } from "@/pages/stage/doodle-speaker";
import type { BookOverlayLayout } from "@/pages/stage/flip-book";
import {
  getPlayingStoryAudio,
  playStoryAudio,
  stopStoryAudio,
  subscribeStoryAudio,
  unlockStoryAudio,
} from "@/pages/stage/story-audio";
import { type Slots, speakerSpots } from "@/pages/stage/use-read-aloud";

/** 叠在书上的朗读按钮（FlipBook 的 overlay）。翻页过程中隐藏 */
export function ReadAloudSpeakers({
  layout,
  units,
  slots,
  flipping,
}: {
  layout: BookOverlayLayout;
  units: ReaderUnit[];
  slots: Slots | null;
  flipping: boolean;
}) {
  const playingUrl = useSyncExternalStore(subscribeStoryAudio, getPlayingStoryAudio);
  if (!slots) return null;
  const spots = speakerSpots(units, slots);
  // 按钮大小随页面缩放，手指也好点
  const size = Math.round(Math.min(56, Math.max(40, layout.pageWidth * 0.09)));

  return spots.map(({ unit, position }) => {
    const playing = playingUrl === unit.audio_url;
    return (
      <Button
        key={`${position}-${unit.audio_url}`}
        variant="ghost"
        size="icon"
        aria-label={playing ? "停止朗读" : "朗读这一页"}
        title={playing ? "停止朗读" : "朗读这一页"}
        onClick={() => {
          unlockStoryAudio();
          if (playing) stopStoryAudio();
          else void playStoryAudio([unit.audio_url!]);
        }}
        style={{ width: size, height: size }}
        className={cn(
          "pointer-events-auto absolute bottom-3 rounded-full bg-transparent p-0 transition-[opacity,transform] duration-200 hover:scale-110 hover:bg-transparent focus-visible:ring-stage-spot/60 active:scale-95 motion-reduce:transition-none dark:hover:bg-transparent [&_svg:not([class*='size-'])]:size-full",
          position === "left" && "left-3 -rotate-6",
          position === "right" && "right-3 rotate-6",
          position === "center" && "left-1/2 -translate-x-1/2",
          playing && "scale-110",
          flipping && "pointer-events-none opacity-0",
        )}
      >
        <DoodleSpeaker
          playing={playing}
          className="size-full drop-shadow-[0_2px_2px_rgba(30,20,50,.35)]"
        />
      </Button>
    );
  });
}

/** 阅读页顶部的"自动朗读"开关 */
export function AutoReadToggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <Button
      variant="ghost"
      aria-pressed={on}
      title={on ? "关闭自动朗读" : "打开自动朗读：翻到新页自动读"}
      onClick={onToggle}
      className={cn(
        "h-11 gap-1.5 rounded-full px-3.5 font-stage-title text-base tracking-wider backdrop-blur-sm focus-visible:ring-stage-spot/50 [&_svg:not([class*='size-'])]:size-7",
        on
          ? "bg-stage-spot text-stage-night hover:bg-stage-spot/85 hover:text-stage-night"
          : "bg-white/10 text-stage-light hover:bg-white/20 hover:text-stage-light",
      )}
    >
      <DoodleSpeaker playing={false} />
      自动朗读
    </Button>
  );
}

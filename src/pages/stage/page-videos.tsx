// 开页动画（A4，Dance Ready!）：叠在当前可见页上的循环视频（docs/06 第 8.2 节）。
// 只给看得见的页加载视频；翻页开始时立即隐藏，停稳后淡入（LoopVideo）。
// 合并单元的视频是两页宽：对开时整段铺满两页，竖屏单页时左页显示左半边、右页显示右半边（D74）
import type { ReaderUnit } from "@/api/types";
import type { BookOverlayLayout } from "@/pages/stage/flip-book";
import { LoopVideo } from "@/pages/stage/loop-video";
import type { Slots } from "@/pages/stage/use-read-aloud";

type VideoSpot = {
  unit: ReaderUnit;
  /** 从第几个位置开始（对开时 0 为左页、1 为右页） */
  slot: number;
  /** 占几个位置 */
  span: number;
  /** 起始位置上显示的是单元的第几页（视频向左偏移几个页宽） */
  offset: number;
};

function videoSpots(units: ReaderUnit[], slots: Slots): VideoSpot[] {
  const spots: VideoSpot[] = [];
  slots.forEach((page, slot) => {
    const unit = page === null ? undefined : units.find((u) => u.pages.includes(page));
    if (!unit || page === null) return;
    const last = spots.at(-1);
    // 合并单元的两页在对开里左右相邻：一个视频铺满两页
    if (last && last.unit === unit && last.slot + last.span === slot) {
      last.span += 1;
      return;
    }
    spots.push({ unit, slot, span: 1, offset: unit.pages.indexOf(page) });
  });
  return spots;
}

export function PageVideos({
  layout,
  units,
  slots,
  flipping,
}: {
  layout: BookOverlayLayout;
  /** 有动画的单元 */
  units: ReaderUnit[];
  slots: Slots | null;
  flipping: boolean;
}) {
  if (!slots) return null;
  const { pageWidth, pageHeight } = layout;
  return videoSpots(units, slots).map(({ unit, slot, span, offset }) => (
    <div
      key={`${slot}-${unit.video_url}`}
      className="absolute top-0 overflow-hidden"
      style={{ left: slot * pageWidth, width: span * pageWidth, height: pageHeight }}
    >
      <LoopVideo
        src={unit.video_url!}
        active={!flipping}
        // 拉伸铺满：视频就是这几页原画生成的，服务商输出的宽高比可能差几个像素，
        // 用 object-fill 让画面边缘与下面的静态页对齐，淡入时不跳
        className="absolute top-0 h-full max-w-none object-fill"
        style={{ left: -offset * pageWidth, width: unit.pages.length * pageWidth }}
      />
    </div>
  ));
}

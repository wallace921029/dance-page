// 阅读页的朗读逻辑（docs/02-reader.md "后续（AI 阶段）"、docs/06 第 8.2 节）：
// "自动朗读"开关（记在本机，D68）、对开朗读顺序（D69）、竖屏单页的合并单元（D74）。按钮在 read-aloud.tsx
import { useEffect, useRef, useState } from "react";
import type { ReadOrder, ReaderUnit } from "@/api/types";
import {
  playStoryAudio,
  preloadStoryAudio,
  stopStoryAudio,
  unlockStoryAudio,
} from "@/pages/stage/story-audio";

const AUTO_READ_KEY = "firefly.autoRead";
/** 翻页停稳后等一会儿再自动朗读：连续快速翻页时不会每页都读一两个字 */
const AUTO_READ_DELAY_MS = 250;
/** 提前下载并解码前后这么多页的朗读 */
const PRELOAD_PAGES = 2;

function loadAutoRead() {
  try {
    return localStorage.getItem(AUTO_READ_KEY) === "1";
  } catch {
    return false;
  }
}

function saveAutoRead(on: boolean) {
  try {
    localStorage.setItem(AUTO_READ_KEY, on ? "1" : "0");
  } catch {
    // 隐私模式等情况下存不了，只在本次打开有效
  }
}

export type Slots = (number | null)[];

function unitAt(units: ReaderUnit[], page: number | null) {
  return page === null ? undefined : units.find((u) => u.pages.includes(page));
}

type SpeakerSpot = { unit: ReaderUnit; position: "left" | "right" | "center" };

/** 当前可见页上的朗读按钮：对开时每页一个，合并单元只有一个（放在书脊下方） */
export function speakerSpots(units: ReaderUnit[], slots: Slots): SpeakerSpot[] {
  if (slots.length === 1) {
    const unit = unitAt(units, slots[0]);
    return unit ? [{ unit, position: "left" }] : [];
  }
  const left = unitAt(units, slots[0]);
  const right = unitAt(units, slots[1]);
  if (left && left === right) return [{ unit: left, position: "center" }];
  const spots: SpeakerSpot[] = [];
  if (left) spots.push({ unit: left, position: "left" });
  if (right) spots.push({ unit: right, position: "right" });
  return spots;
}

/** 翻到这里时自动朗读哪些单元，按顺序 */
function autoReadUnits(units: ReaderUnit[], slots: Slots, readOrder: ReadOrder) {
  if (slots.length === 1) {
    const page = slots[0];
    const unit = unitAt(units, page);
    // 竖屏单页显示合并单元时，只在翻到它的前一页时读一次（D74）
    if (!unit || (unit.pages.length === 2 && page !== unit.pages[0])) return [];
    return [unit];
  }
  const left = unitAt(units, slots[0]);
  const right = unitAt(units, slots[1]);
  if (left && left === right) return [left];
  const list = [left, right].filter((u): u is ReaderUnit => u !== undefined);
  return readOrder === "right_first" ? list.reverse() : list;
}

/**
 * 朗读状态。slots 为 FlipBook 报告的当前可见页（null 表示还没排版）；
 * skipFirstAutoRead：从书架翻开进入时封面马上会被自动翻开，先不读封面
 */
export function useReadAloud({
  units,
  readOrder,
  slots,
  flipping,
  skipFirstAutoRead,
}: {
  units: ReaderUnit[];
  readOrder: ReadOrder;
  slots: Slots | null;
  flipping: boolean;
  skipFirstAutoRead: boolean;
}) {
  const [autoRead, setAutoRead] = useState(loadAutoRead);
  const lastAutoKeyRef = useRef<string | null>(null);
  const skipFirstRef = useRef(skipFirstAutoRead);
  const slotsKey = slots?.join(",") ?? null;

  // 离开阅读页时停止
  useEffect(() => stopStoryAudio, []);

  // 开始翻页、或翻到了别的页：立即停止
  useEffect(() => {
    if (flipping) stopStoryAudio();
  }, [flipping]);
  useEffect(() => {
    stopStoryAudio();
  }, [slotsKey]);

  // 预先下载附近几页的朗读
  useEffect(() => {
    if (!slots) return;
    const pages = slots.filter((p): p is number => p !== null);
    if (!pages.length) return;
    const from = Math.min(...pages) - PRELOAD_PAGES;
    const to = Math.max(...pages) + PRELOAD_PAGES;
    preloadStoryAudio(
      units
        .filter((u) => u.audio_url && u.pages.some((p) => p >= from && p <= to))
        .map((u) => u.audio_url!),
    );
  }, [slots, units]);

  // 自动朗读：翻页停稳后读当前可见的单元，每到一个新位置只读一次
  useEffect(() => {
    if (!slots || slotsKey === null || flipping) return;
    if (skipFirstRef.current) {
      skipFirstRef.current = false;
      lastAutoKeyRef.current = slotsKey;
      return;
    }
    if (!autoRead || lastAutoKeyRef.current === slotsKey) return;
    const timer = window.setTimeout(() => {
      lastAutoKeyRef.current = slotsKey;
      const urls = autoReadUnits(units, slots, readOrder).map((u) => u.audio_url!);
      if (urls.length) void playStoryAudio(urls);
    }, AUTO_READ_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [autoRead, flipping, slots, slotsKey, units, readOrder]);

  const toggleAutoRead = () => {
    const next = !autoRead;
    if (next) {
      unlockStoryAudio();
      lastAutoKeyRef.current = null; // 打开时马上读当前页
    } else {
      stopStoryAudio();
    }
    saveAutoRead(next);
    setAutoRead(next);
  };

  return { autoRead, toggleAutoRead };
}

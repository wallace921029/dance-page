// 管理后台的进场动画（motion）。系统开启"减少动态效果"时由 AdminLayout 的 MotionConfig 去掉位移，只保留淡入
import { motion, type Transition } from "motion/react";
import { TableRow } from "@/components/ui/table";

const EASE: Transition["ease"] = [0.22, 1, 0.36, 1];
/** 依次进场时相邻两项的间隔（秒） */
const STEP = 0.06;
/** 表格行、缩略图数量多，间隔更短，且只错开前面这么多项，避免长列表最后几项等太久 */
const ROW_STEP = 0.03;
const MAX_STAGGERED = 12;

const MotionTableRow = motion.create(TableRow);

/**
 * 模块进场：淡入 + 轻微上浮。index 为同一页面里的第几个模块，用来错开进场时间。
 * 数据加载完才挂载的模块也会在挂载时播放。
 */
export function Reveal({
  index = 0,
  as = "div",
  className,
  children,
}: {
  index?: number;
  as?: "div" | "section";
  className?: string;
  children: React.ReactNode;
}) {
  const Component = as === "section" ? motion.section : motion.div;
  return (
    <Component
      className={className}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: EASE, delay: index * STEP }}
    >
      {children}
    </Component>
  );
}

/** 表格行进场：按行号依次淡入。行以数据 id 为 key，翻页、新增的行会在出现时播放 */
export function AnimatedTableRow({
  index,
  ...props
}: React.ComponentProps<typeof MotionTableRow> & { index: number }) {
  return (
    <MotionTableRow
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: EASE, delay: Math.min(index, MAX_STAGGERED) * ROW_STEP }}
      {...props}
    />
  );
}

/** 网格里的小项（如页面缩略图）进场：淡入 + 轻微放大 */
export function RevealItem({
  index,
  className,
  children,
}: {
  index: number;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.26, ease: EASE, delay: Math.min(index, MAX_STAGGERED) * ROW_STEP }}
    >
      {children}
    </motion.div>
  );
}

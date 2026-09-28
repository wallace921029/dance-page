// 书架标题右侧的搜索：点放大镜，搜索框弹性展开，输入书名即时筛选（D54）
import { useEffect, useImperativeHandle, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { StageRoundButton } from "@/pages/stage/common";

const BUTTON_SIZE = 44;
const MAX_WIDTH = 288;
/** 停止输入这么久后再更新地址里的搜索词 */
const COMMIT_DELAY_MS = 200;

export type ShelfSearchHandle = {
  /** 清空搜索词并收起搜索框（与点关闭按钮相同） */
  clear: () => void;
};

export function ShelfSearch({
  value,
  onChange,
  enableMotion,
  buttonClassName,
  ref,
}: {
  /** 地址里的搜索词，只用作初始值 */
  value: string;
  onChange: (value: string) => void;
  enableMotion: boolean;
  /** 搜索按钮随书架主题配色 */
  buttonClassName?: string;
  ref?: React.Ref<ShelfSearchHandle>;
}) {
  const [open, setOpen] = useState(value !== "");
  // 每次展开都用新的 key：收起动画还没播完就再次打开时，
  // AnimatePresence 会把正在退场的旧搜索框拉回来复用，旧输入框的焦点和光标状态会错乱
  const [openCount, setOpenCount] = useState(0);
  // 输入框自己保存正在输入的文字（包括输入法组字中的文字），稍后再写入地址；
  // 直接用地址里的值会因为更新慢半拍而吞掉刚输入的字。外部需要清空时调用 ref 上的 clear()
  const [text, setText] = useState(value);
  const commitTimer = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const reducedMotion = useReducedMotion();
  const animate = enableMotion && !reducedMotion;
  const [width] = useState(() => Math.min(window.innerWidth * 0.55, MAX_WIDTH));

  useEffect(() => () => window.clearTimeout(commitTimer.current), []);

  const update = (next: string) => {
    setText(next);
    window.clearTimeout(commitTimer.current);
    commitTimer.current = window.setTimeout(() => onChange(next), COMMIT_DELAY_MS);
  };

  const close = () => {
    window.clearTimeout(commitTimer.current);
    setText("");
    onChange("");
    setOpen(false);
  };
  useImperativeHandle(ref, () => ({ clear: close }));

  const transition = animate
    ? { type: "spring" as const, stiffness: 420, damping: 32 }
    : { duration: 0 };

  return (
    <AnimatePresence initial={false} mode="popLayout">
      {open ? (
        <motion.div
          key={`search-${openCount}`}
          initial={{ width: BUTTON_SIZE, opacity: 0.4 }}
          animate={{ width, opacity: 1 }}
          exit={{ width: BUTTON_SIZE, opacity: 0 }}
          transition={transition}
          className="overflow-hidden rounded-full"
        >
          <InputGroup className="h-11 rounded-full border-current/20 bg-white/85 text-foreground backdrop-blur-sm dark:bg-white/10">
            <InputGroupAddon>
              <Search />
            </InputGroupAddon>
            <InputGroupInput
              ref={inputRef}
              // 挂载时立即获得焦点，展开动画期间就能输入
              autoFocus
              type="search"
              enterKeyHint="search"
              placeholder="找一本绘本"
              aria-label="搜索绘本"
              value={text}
              onChange={(e) => update(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && close()}
              onBlur={() => text.trim() === "" && setOpen(false)}
              className="text-base [&::-webkit-search-cancel-button]:hidden"
            />
            <InputGroupAddon align="inline-end">
              <InputGroupButton
                size="icon-xs"
                aria-label="清除并关闭搜索"
                className="rounded-full"
                // 按下时就处理，避免输入框先失焦导致搜索框收起、点击落空
                onPointerDown={(e) => e.preventDefault()}
                onClick={close}
              >
                <X />
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </motion.div>
      ) : (
        <motion.div
          key="button"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.6, opacity: 0 }}
          transition={transition}
        >
          <StageRoundButton
            label="搜索绘本"
            onClick={() => {
              setOpenCount((n) => n + 1);
              setOpen(true);
            }}
            className={buttonClassName}
          >
            <Search />
          </StageRoundButton>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

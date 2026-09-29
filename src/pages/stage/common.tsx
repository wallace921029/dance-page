// 阅读端"小剧场"风格（D37）的公共部分：在 shadcn/ui 组件上套小剧场配色
import "@fontsource/zcool-xiaowei";
import "@fontsource-variable/noto-sans-sc";
import { cn } from "cn";
import { Button } from "@/components/ui/button";
import { APP_NAME, APP_NAME_EN } from "@/lib/app-info";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/** 登录、注册页背景：顶部中央一束暖色聚光 + 夜幕渐变（书架页的背景见 shelf-themes.ts） */
export const SHELF_BACKGROUND =
  "radial-gradient(ellipse 70% 60% at 50% -5%, rgba(255,214,140,.24), transparent 70%), linear-gradient(#141833, #1C2048)";

/** 阅读页：中心亮、四周暗的舞台光 */
export const READER_BACKGROUND =
  "radial-gradient(ellipse 62% 72% at 50% 46%, #2B3062, #0E1024 76%)";

/** 主要操作按钮（聚光色） */
export const stageSubmitButtonClass =
  "w-full bg-stage-spot text-stage-night hover:bg-stage-spot/85";

/** 半透明圆形图标按钮、暖金色图标。链接用 render={<Link />} 并传 nativeButton={false} */
export function StageRoundButton({
  label,
  className,
  ...props
}: React.ComponentProps<typeof Button> & { label: string }) {
  return (
    <Button
      variant="ghost"
      size="icon-lg"
      aria-label={label}
      title={label}
      className={cn(
        "size-11 rounded-full bg-white/10 text-stage-light backdrop-blur-sm hover:bg-white/20 hover:text-stage-light focus-visible:ring-stage-spot/50 [&_svg:not([class*='size-'])]:size-5",
        className,
      )}
      {...props}
    />
  );
}

/** 产品名：中文名 + 小字英文名（颜色跟随外层文字颜色） */
export function StageBrand({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex flex-col items-center leading-none", className)}>
      <span className="font-stage-title text-[1em] tracking-[0.2em]">{APP_NAME}</span>
      <span className="mt-1.5 text-[0.32em] tracking-[0.3em] uppercase opacity-70">
        {APP_NAME_EN}
      </span>
    </span>
  );
}

/** 登录、注册页的外框：夜幕背景上一张微微发光的卡片 */
export function StageAuthLayout({
  subtitle,
  children,
}: {
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div
      // fixed + 整屏高度（见 index.css 的 --app-screen-height）：iPad 主屏幕应用里 svh 比屏幕矮一截，底部会露出白条；
      // 卡片用 m-auto 居中，内容比屏幕高时（横屏软键盘弹出）可以在容器里滚动
      className="dark fixed top-0 left-0 flex h-(--app-screen-height) w-full overflow-y-auto p-6 font-stage text-foreground"
      style={{ background: SHELF_BACKGROUND }}
    >
      <Card className="m-auto w-full max-w-sm gap-6 bg-black/25 py-8 shadow-[0_0_60px_rgba(255,214,107,0.12)] ring-stage-light/20 backdrop-blur">
        <CardHeader className="px-8 text-center">
          <CardTitle className="text-4xl text-stage-light">
            <StageBrand />
          </CardTitle>
          <CardDescription>{subtitle}</CardDescription>
        </CardHeader>
        <CardContent className="px-8">{children}</CardContent>
      </Card>
    </div>
  );
}

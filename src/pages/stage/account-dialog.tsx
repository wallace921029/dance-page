// 书架右上角的头像和账户小弹窗（D105）：手绘默认头像，点开后是一张小卡片，
// 里面选"管理后台"（管理员才有）或"退出登录"。深色舞台配色，和登录页的卡片一致
import { useState } from "react";
import { useNavigate } from "react-router";
import { useLogout } from "@/api/auth";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { DoodleAvatar, DoodleExit, DoodleGear } from "@/pages/stage/doodle-avatar";

export function AccountDialog({ username, isAdmin }: { username: string; isAdmin: boolean }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const logout = useLogout();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon-lg"
            aria-label={`账户：${username}`}
            title={username}
            className="size-11 rotate-3 rounded-full bg-transparent p-1 transition-transform hover:scale-110 hover:bg-transparent focus-visible:ring-stage-spot/60 active:scale-95 motion-reduce:transition-none dark:hover:bg-transparent [&_svg:not([class*='size-'])]:size-full"
          />
        }
      >
        <DoodleAvatar className="size-full drop-shadow-[0_2px_2px_rgba(30,20,50,.35)]" />
      </DialogTrigger>
      {/* 弹窗渲染在书架之外，不继承书架主题，所以自己带上深色配色 */}
      <DialogContent className="dark max-w-72 gap-5 rounded-3xl border-2 border-dashed border-stage-light/45 bg-stage-night p-6 font-stage text-stage-light shadow-[0_0_60px_rgba(255,214,107,0.16)] ring-0 sm:max-w-72 [&_[data-slot=dialog-close]]:text-stage-light/80 [&_[data-slot=dialog-close]]:hover:bg-white/10 [&_[data-slot=dialog-close]]:hover:text-stage-light">
        <div className="flex flex-col items-center gap-1.5 text-center">
          <DoodleAvatar className="size-20 -rotate-3 drop-shadow-[0_3px_3px_rgba(0,0,0,.4)]" />
          <DialogTitle className="mt-1 font-stage-title text-2xl tracking-wider text-stage-light">
            {username}
          </DialogTitle>
          <DialogDescription className="text-xs text-stage-light/70">
            {isAdmin ? "管理员" : "小读者"}
          </DialogDescription>
        </div>

        <div className="flex flex-col gap-3">
          {isAdmin && (
            <AccountAction
              label="管理后台"
              onClick={() => {
                setOpen(false);
                navigate("/admin/books");
              }}
              icon={<DoodleGear className="size-full" />}
            />
          )}
          <AccountAction
            label="退出登录"
            disabled={logout.isPending}
            pending={logout.isPending}
            onClick={() =>
              logout.mutate(undefined, {
                onSuccess: () => {
                  setOpen(false);
                  navigate("/login", { replace: true });
                },
              })
            }
            icon={<DoodleExit className="size-full" />}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 弹窗里的大按钮：左边一个手绘图标，右边是名字；虚线框 */
function AccountAction({
  label,
  icon,
  onClick,
  disabled,
  pending,
}: {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  pending?: boolean;
}) {
  return (
    <Button
      variant="ghost"
      onClick={onClick}
      disabled={disabled}
      className="h-14 justify-start gap-3 rounded-2xl border-2 border-dashed border-stage-light/40 bg-white/5 px-4 font-stage-title text-lg tracking-wider text-stage-light hover:bg-white/12 hover:text-stage-light focus-visible:ring-stage-spot/50"
    >
      <span className="size-9 shrink-0 -rotate-6 drop-shadow-[0_2px_2px_rgba(30,20,50,.3)]">
        {pending ? <Spinner className="size-full p-1.5" /> : icon}
      </span>
      {label}
    </Button>
  );
}

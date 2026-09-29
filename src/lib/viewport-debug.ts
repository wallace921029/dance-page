// 临时的视口诊断浮层（排查 iPad 主屏幕应用底部出现白条）：连续快速点 6 下屏幕显示 / 隐藏，
// 显示各种"屏幕高度"的读数，截图发给开发者。问题查清后删除（见 docs/progress.md）。
const TAPS = 6;
const WINDOW_MS = 2500;

export function installViewportDebug() {
  let overlay: HTMLPreElement | null = null;
  let timer = 0;
  let taps: number[] = [];

  const probe = (css: string) => {
    const el = document.createElement("div");
    el.style.cssText = `position:fixed;left:0;top:0;visibility:hidden;pointer-events:none;${css}`;
    document.body.appendChild(el);
    const height = el.getBoundingClientRect().height;
    el.remove();
    return Math.round(height * 10) / 10;
  };

  const render = () => {
    if (!overlay) return;
    const vv = window.visualViewport;
    const root = document.documentElement;
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true;
    const lines = [
      `standalone=${standalone}  path=${location.pathname}`,
      `screen=${screen.width}x${screen.height}  dpr=${devicePixelRatio}`,
      `inner=${innerWidth}x${innerHeight}  outer=${outerWidth}x${outerHeight}`,
      `html.client=${root.clientWidth}x${root.clientHeight}  scrollH=${root.scrollHeight}`,
      `vv=${vv ? `${Math.round(vv.width)}x${Math.round(vv.height)} top=${Math.round(vv.offsetTop)} pageTop=${Math.round(vv.pageTop)} scale=${vv.scale}` : "n/a"}`,
      `scrollY=${Math.round(scrollY)}  body.h=${Math.round(document.body.getBoundingClientRect().height)}`,
      `vh=${probe("height:100vh")} dvh=${probe("height:100dvh")} svh=${probe("height:100svh")} lvh=${probe("height:100lvh")}`,
      `fixed inset0=${probe("bottom:0")}  app-screen=${probe("height:var(--app-screen-height)")}`,
      `safe top=${probe("height:env(safe-area-inset-top)")} bottom=${probe("height:env(safe-area-inset-bottom)")}`,
    ];
    overlay.textContent = lines.join("\n");
  };

  const toggle = () => {
    if (overlay) {
      window.clearInterval(timer);
      overlay.remove();
      overlay = null;
      return;
    }
    overlay = document.createElement("pre");
    overlay.style.cssText =
      "position:fixed;left:0;top:40px;z-index:99999;margin:0;padding:8px;background:rgba(0,0,0,.78);color:#7CFC9B;font:12px/1.4 ui-monospace,Menlo,monospace;pointer-events:none;white-space:pre";
    document.body.appendChild(overlay);
    render();
    timer = window.setInterval(render, 500);
  };

  window.addEventListener(
    "pointerdown",
    () => {
      const now = Date.now();
      taps = [...taps.filter((t) => now - t < WINDOW_MS), now];
      if (taps.length >= TAPS) {
        taps = [];
        toggle();
      }
    },
    { passive: true },
  );
}

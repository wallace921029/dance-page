# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""生成"添加到主屏幕"用的 PNG 图标（D59），输出到 public/icons/。

图标图案与 public/favicon.svg 一致：夜幕上一只萤火虫的暖光照着一本打开的书。
用本机的 Google Chrome 把 SVG 渲染成 PNG：

    uv run scripts/make-icons.py
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT_DIR = Path(__file__).resolve().parent.parent / "public" / "icons"

# 画布 512×512，不画圆角（iOS、Android 会自己裁成圆角或圆形）。
# {scale} 缩放背景以外的图案：maskable 图标要求图案落在中间 80% 的圆里
ICON_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#232a5c"/>
      <stop offset="1" stop-color="#141833"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="#FFD66B" stop-opacity=".85"/>
      <stop offset=".45" stop-color="#FFD66B" stop-opacity=".3"/>
      <stop offset="1" stop-color="#FFD66B" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="pool" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="#FFD66B" stop-opacity=".28"/>
      <stop offset="1" stop-color="#FFD66B" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" fill="url(#sky)"/>
  <g transform="translate(256 256) scale({scale}) translate(-256 -256)">
    <g fill="#FFF3C4">
      <circle cx="112" cy="118" r="6" opacity=".7"/>
      <circle cx="176" cy="70" r="4" opacity=".5"/>
      <circle cx="84" cy="224" r="4" opacity=".45"/>
      <circle cx="440" cy="300" r="5" opacity=".5"/>
    </g>
    <ellipse cx="256" cy="400" rx="210" ry="70" fill="url(#pool)"/>
    <circle cx="336" cy="190" r="140" fill="url(#glow)"/>
    <g transform="rotate(-30 318 170)">
      <!-- 萤火虫：发光的尾部 + 身体、头、触角、翅膀 -->
      <ellipse cx="344" cy="170" rx="40" ry="32" fill="#FFF3C4"/>
      <ellipse cx="292" cy="170" rx="30" ry="21" fill="#3a3358"/>
      <circle cx="256" cy="170" r="15" fill="#3a3358"/>
      <path d="M246 160q-16-22-34-24M250 158q-6-26-22-36" fill="none" stroke="#3a3358" stroke-width="5" stroke-linecap="round"/>
      <ellipse cx="300" cy="138" rx="34" ry="17" fill="#ffffff" opacity=".55" transform="rotate(-20 300 138)"/>
      <ellipse cx="320" cy="142" rx="30" ry="14" fill="#ffffff" opacity=".4" transform="rotate(12 320 142)"/>
    </g>
    <path d="M72 356c60-36 124-36 184 0v92c-64-34-124-34-184 0z" fill="#F5D98B"/>
    <path d="M440 356c-60-36-124-36-184 0v92c64-34 124-34 184 0z" fill="#E9C46A"/>
    <path d="M256 356v92" stroke="#C9A24E" stroke-width="6" stroke-linecap="round"/>
  </g>
</svg>
"""

# 文件名 → (边长, 图案缩放)
ICONS = {
    "apple-touch-icon.png": (180, 0.92),
    "icon-192.png": (192, 0.92),
    "icon-512.png": (512, 0.92),
    "icon-maskable-512.png": (512, 0.74),
}


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        for name, (size, scale) in ICONS.items():
            page = await browser.new_page(viewport={"width": size, "height": size})
            svg = ICON_SVG.format(size=size, scale=scale)
            await page.set_content(f'<body style="margin:0">{svg}</body>')
            await page.screenshot(path=OUT_DIR / name)
            await page.close()
            print(f"{name}: {size}×{size}")
        await browser.close()


asyncio.run(main())

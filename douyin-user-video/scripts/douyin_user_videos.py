#!/usr/bin/env python3
"""
获取抖音主页中的视频列表（基于浏览器渲染）

为什么使用浏览器方案:
- 抖音 web API 常需要动态签名参数（如 X-Bogus），直接 requests 请求常返回空内容
- 本脚本通过 Playwright 渲染页面，再从 DOM 中提取视频信息，稳定性更高

依赖:
  pip install playwright
  playwright install chromium

示例:
  python douyin_user_videos.py \
    --url "https://www.douyin.com/user/MS4wLjABAAAA4LqLxq7PLK9xEB5PPazcKTG-3oInPFTDwbqiSrRL_mg?from_tab_name=main"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List


def check_dependencies() -> None:
    """检查依赖是否安装。"""
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("缺少依赖: playwright", file=sys.stderr)
        print("请先执行: pip install playwright", file=sys.stderr)
        print("然后执行: playwright install chromium", file=sys.stderr)
        sys.exit(1)


check_dependencies()

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def extract_first_url(text: str) -> str:
    """从输入文本中提取第一个 URL。"""
    match = re.search(r"https?://[^\s]+", text)
    if not match:
        raise ValueError("未找到有效 URL")
    return match.group(0)


def parse_sec_uid_from_url(url: str) -> str:
    """从 /user/{sec_uid} 链接提取 sec_uid。"""
    match = re.search(r"/user/([^/?#]+)", url)
    return match.group(1) if match else ""


def collect_user_videos(
    user_url: str,
    max_scrolls: int = 10,
    scroll_pause: float = 1.2,
    headless: bool = True,
) -> Dict:
    """
    通过浏览器渲染页面并提取视频列表。

    返回字段:
    - input_url
    - final_url
    - sec_uid
    - video_count
    - videos: [{aweme_id, url, title, cover}]
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        try:
            page.goto(user_url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeoutError:
                # 抖音页面持续轮询时，networkidle 可能不触发，忽略即可
                pass

            # 多次滚动以触发更多视频加载
            stable_rounds = 0
            last_count = 0
            for _ in range(max_scrolls):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(scroll_pause)

                current_count = page.evaluate(
                    """
                    () => {
                      const ids = new Set();
                      for (const a of document.querySelectorAll('a[href*="/video/"]')) {
                        const href = a.getAttribute('href') || '';
                        const m = href.match(/\\/video\\/(\\d+)/);
                        if (m) ids.add(m[1]);
                      }
                      return ids.size;
                    }
                    """
                )

                if current_count == last_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                last_count = current_count

                # 连续两轮无新增，提前结束
                if stable_rounds >= 2:
                    break

            videos: List[Dict] = page.evaluate(
                """
                () => {
                  const map = new Map();
                  const anchors = document.querySelectorAll('a[href*="/video/"]');
                  for (const a of anchors) {
                    const rawHref = a.getAttribute('href') || '';
                    const m = rawHref.match(/\\/video\\/(\\d+)/);
                    if (!m) continue;
                    const awemeId = m[1];
                    const fullUrl = new URL(rawHref, location.origin).href;

                    let title = '';
                    const img = a.querySelector('img');
                    if (img) {
                      title = (img.getAttribute('alt') || '').trim();
                    }
                    if (!title) {
                      title = (a.getAttribute('aria-label') || '').trim();
                    }
                    if (!title) {
                      const text = (a.textContent || '').replace(/\\s+/g, ' ').trim();
                      title = text.slice(0, 120);
                    }

                    const cover = img ? (img.getAttribute('src') || '').trim() : '';

                    if (!cover) {
                      continue;
                    }

                    if (!map.has(awemeId)) {
                      const item = {
                        aweme_id: awemeId,
                        url: fullUrl,
                        title: title || `douyin_${awemeId}`
                      };
                      item.cover = cover;
                      map.set(awemeId, item);
                    }
                  }
                  return Array.from(map.values());
                }
                """
            )

            result = {
                "input_url": user_url,
                "final_url": page.url,
                "sec_uid": parse_sec_uid_from_url(page.url) or parse_sec_uid_from_url(user_url),
                "video_count": len(videos),
                "videos": videos,
            }
            return result
        finally:
            context.close()
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="获取抖音主页中的视频列表（Playwright 版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python douyin_user_videos.py --url "https://www.douyin.com/user/xxxx"
  python douyin_user_videos.py --url "抖音主页链接文本" --output ./videos.json
  python douyin_user_videos.py --url "https://www.douyin.com/user/xxxx" --max-scrolls 15 --show-browser
        """,
    )
    parser.add_argument("--url", "-u", required=True, help="抖音用户主页链接，或包含链接的文本")
    parser.add_argument("--output", "-o", default="", help="输出目录（默认 output/<sec_uid>/videos.json）")
    parser.add_argument("--max-scrolls", type=int, default=10, help="最大滚动次数（默认 10）")
    parser.add_argument("--scroll-pause", type=float, default=1.2, help="每次滚动后等待秒数（默认 1.2）")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口（默认无头）")
    args = parser.parse_args()

    try:
        user_url = extract_first_url(args.url)
        result = collect_user_videos(
            user_url=user_url,
            max_scrolls=max(1, args.max_scrolls),
            scroll_pause=max(0.2, args.scroll_pause),
            headless=not args.show_browser,
        )

        json_text = json.dumps(result, ensure_ascii=False, indent=2)

        # 统一输出路径：output/<sec_uid>/videos.json
        sec_uid = result.get("sec_uid", "unknown")
        output_dir = Path(args.output) if args.output else Path("output") / sec_uid
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "videos.json"
        output_path.write_text(json_text, encoding="utf-8")
        print(f"已保存到: {output_path}")
        print(f"共获取视频: {result['video_count']} 条")
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

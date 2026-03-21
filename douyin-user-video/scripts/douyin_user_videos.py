#!/usr/bin/env python3
"""
获取抖音主页中的视频列表

支持三种方式:
1. Playwright 浏览器渲染（免费，稳定性高）
2. 哼哼猫 API（稳定，需要 API Key）
3. 抖音 API（兜底方案，可能被反爬）

自动降级：当 Playwright 不可用时，自动尝试其他方式。

依赖:
  # 方式1 Playwright（推荐）
  pip install playwright
  playwright install chromium

  # 方式2/3 API（需要 requests）
  pip install requests
  设置环境变量: MEOW_API_KEY（哼哼猫 API）

示例:
  python douyin_user_videos.py --url "https://www.douyin.com/user/MS4wLjABAAAA..."
  python douyin_user_videos.py --url "主页链接" --method meow --api-key "xxx"
  python douyin_user_videos.py --url "主页链接" --output ./output
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 检测依赖
PLAYWRIGHT_AVAILABLE = False
REQUESTS_AVAILABLE = False

try:
    import requests  # noqa: F401
    REQUESTS_AVAILABLE = True
except ImportError:
    pass

try:
    import playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


def extract_first_url(text: str) -> str:
    """从输入文本中提取第一个 URL。"""
    match = re.search(r"https?://[^\s]+", text)
    if not match:
        raise ValueError("未找到有效 URL")
    url = match.group(0)
    url = re.sub(r'[，。！？、；：""''（）【】《》\s]+$', '', url)
    return url


def parse_sec_uid_from_url(url: str) -> str:
    """从 /user/{sec_uid} 链接提取 sec_uid。"""
    match = re.search(r"/user/([^/?#]+)", url)
    return match.group(1) if match else ""


# ============ 哼哼猫 API 方式 ============

MEOW_API_URL = "https://api.meowload.net/openapi/extract/playlist"


def fetch_meow_page(url: str, api_key: str, cursor: Optional[str] = None) -> Dict:
    """哼哼猫 API 获取单页数据"""
    if not REQUESTS_AVAILABLE:
        raise ImportError("缺少 requests 模块，请执行: pip install requests")

    import requests

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "accept-language": "zh",
    }

    payload = {"url": url}
    if cursor:
        payload["cursor"] = cursor

    response = requests.post(MEOW_API_URL, json=payload, headers=headers, timeout=60)

    if response.status_code != 200:
        try:
            error = response.json()
            raise Exception(f"API 错误 ({response.status_code}): {error.get('message', '未知错误')}")
        except json.JSONDecodeError:
            raise Exception(f"API 错误 ({response.status_code}): {response.text}")

    return response.json()


def parse_meow_posts(posts: List[Dict]) -> List[Dict]:
    """解析哼哼猫 API 返回的 posts"""
    videos = []
    for post in posts:
        post_id = post.get("id", "")
        text = post.get("text", "").strip() or f"douyin_{post_id}"
        post_url = post.get("post_url", "")
        created_at = post.get("created_at", "")

        medias = post.get("medias", [])
        video_url = ""
        cover = ""

        for media in medias:
            if media.get("media_type") == "video":
                video_url = media.get("resource_url", "")
                cover = media.get("preview_url", "")
                break

        if not cover and medias:
            cover = medias[0].get("preview_url", "")

        publish_time = ""
        if created_at:
            try:
                ts = int(created_at) / 1000
                publish_time = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                pass

        videos.append({
            "aweme_id": post_id,
            "title": text[:100],
            "url": post_url or f"https://www.douyin.com/video/{post_id}",
            "cover": cover,
            "video_url": video_url,
            "publish_time": publish_time,
        })

    return videos


def collect_via_meow(
    url: str,
    api_key: str,
    max_videos: int = 100,
    delay: float = 1.0,
    show_progress: bool = True,
) -> Dict:
    """哼哼猫 API 方式获取视频列表"""
    all_videos = []
    cursor = None
    page = 1
    user_info = {}

    while len(all_videos) < max_videos:
        if show_progress:
            print(f"[Meow API] 正在获取第 {page} 页...")

        try:
            data = fetch_meow_page(url, api_key, cursor=cursor)
        except Exception as e:
            if page == 1:
                raise
            print(f"获取第 {page} 页失败: {e}", file=sys.stderr)
            break

        if not user_info and "user" in data:
            user_info = data["user"]

        posts = data.get("posts", [])
        videos = parse_meow_posts(posts)
        all_videos.extend(videos)

        if show_progress:
            print(f"  获取到 {len(videos)} 条，累计 {len(all_videos)} 条")

        if len(all_videos) >= max_videos:
            all_videos = all_videos[:max_videos]
            break

        if not data.get("has_more", False):
            break

        cursor = data.get("next_cursor")
        if not cursor:
            break

        page += 1
        time.sleep(delay)

    return {
        "sec_uid": parse_sec_uid_from_url(url),
        "video_count": len(all_videos),
        "videos": all_videos,
        "user": user_info,
        "source": "meow_api",
    }


# ============ 抖音 API 方式（兜底） ============

DY_API_URL = "https://www.douyin.com/aweme/v1/web/aweme/post/"

DY_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def get_dy_api_videos(sec_uid: str, max_cursor: int = 0, count: int = 20) -> Dict:
    """抖音 API 获取视频列表（可能被反爬）"""
    if not REQUESTS_AVAILABLE:
        raise ImportError("缺少 requests 模块，请执行: pip install requests")

    import requests

    params = {
        "sec_user_id": sec_uid,
        "count": count,
        "max_cursor": max_cursor,
        "aid": "6383",
        "cookie_enabled": "true",
        "platform": "PC",
        "downlink": "10",
    }

    response = requests.get(DY_API_URL, params=params, headers=DY_API_HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_dy_api_response(data: Dict) -> List[Dict]:
    """解析抖音 API 响应"""
    videos = []
    for item in data.get("aweme_list", []) or []:
        if not item:
            continue
        aweme_id = item.get("aweme_id", "")
        desc = item.get("desc", "").strip() or f"douyin_{aweme_id}"

        cover = ""
        cover_info = item.get("video", {}).get("cover", {})
        if cover_info.get("url_list"):
            cover = cover_info["url_list"][0]

        videos.append({
            "aweme_id": aweme_id,
            "title": desc[:100],
            "url": f"https://www.douyin.com/video/{aweme_id}",
            "cover": cover,
        })
    return videos


def collect_via_dy_api(sec_uid: str, max_videos: int = 100, show_progress: bool = True) -> Dict:
    """抖音 API 方式获取视频列表（兜底方案）"""
    all_videos = []
    max_cursor = 0
    has_more = True
    page = 1

    while has_more and len(all_videos) < max_videos:
        if show_progress:
            print(f"[抖音 API] 正在获取第 {page} 页...")

        try:
            data = get_dy_api_videos(sec_uid, max_cursor=max_cursor, count=20)
        except Exception as e:
            if page == 1:
                raise
            print(f"获取失败: {e}", file=sys.stderr)
            break

        videos = parse_dy_api_response(data)
        all_videos.extend(videos)

        if show_progress:
            print(f"  获取到 {len(videos)} 条，累计 {len(all_videos)} 条")

        has_more = data.get("has_more", False)
        max_cursor = data.get("max_cursor", 0)

        if len(all_videos) >= max_videos:
            all_videos = all_videos[:max_videos]
            break

        page += 1
        time.sleep(0.5)

    return {
        "sec_uid": sec_uid,
        "video_count": len(all_videos),
        "videos": all_videos,
        "source": "dy_api",
    }


# ============ Playwright 方式 ============

def collect_via_playwright(
    user_url: str,
    max_scrolls: int = 10,
    scroll_pause: float = 1.2,
    headless: bool = True,
    show_progress: bool = True,
) -> Dict:
    """Playwright 方式获取视频列表"""
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("缺少 playwright 模块，请执行: pip install playwright && playwright install chromium")

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    if show_progress:
        print("[Playwright] 正在启动浏览器...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        try:
            if show_progress:
                print("[Playwright] 正在加载页面...")
            page.goto(user_url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeoutError:
                pass

            stable_rounds = 0
            last_count = 0
            for i in range(max_scrolls):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(scroll_pause)

                current_count = page.evaluate(
                    """() => {
                      const ids = new Set();
                      for (const a of document.querySelectorAll('a[href*="/video/"]')) {
                        const m = (a.getAttribute('href') || '').match(/\\/video\\/(\\d+)/);
                        if (m) ids.add(m[1]);
                      }
                      return ids.size;
                    }"""
                )

                if current_count == last_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                last_count = current_count

                if show_progress and current_count > 0:
                    print(f"[Playwright] 滚动 {i+1}/{max_scrolls}，已发现 {current_count} 个视频")

                if stable_rounds >= 2:
                    break

            videos: List[Dict] = page.evaluate(
                """() => {
                  const map = new Map();
                  for (const a of document.querySelectorAll('a[href*="/video/"]')) {
                    const rawHref = a.getAttribute('href') || '';
                    const m = rawHref.match(/\\/video\\/(\\d+)/);
                    if (!m) continue;
                    const awemeId = m[1];
                    const fullUrl = new URL(rawHref, location.origin).href;

                    let title = '';
                    const img = a.querySelector('img');
                    if (img) title = (img.getAttribute('alt') || '').trim();
                    if (!title) title = (a.getAttribute('aria-label') || '').trim();
                    if (!title) title = (a.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120);

                    const cover = img ? (img.getAttribute('src') || '').trim() : '';
                    if (!cover) continue;

                    if (!map.has(awemeId)) {
                      map.set(awemeId, {
                        aweme_id: awemeId,
                        url: fullUrl,
                        title: title || `douyin_${awemeId}`,
                        cover: cover
                      });
                    }
                  }
                  return Array.from(map.values());
                }"""
            )

            return {
                "input_url": user_url,
                "final_url": page.url,
                "sec_uid": parse_sec_uid_from_url(page.url) or parse_sec_uid_from_url(user_url),
                "video_count": len(videos),
                "videos": videos,
                "source": "playwright",
            }
        finally:
            context.close()
            browser.close()


# ============ 主函数 ============

def main() -> None:
    parser = argparse.ArgumentParser(
        description="获取抖音主页视频列表（支持多种方式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python douyin_user_videos.py --url "https://www.douyin.com/user/xxxx"
  python douyin_user_videos.py --url "主页链接" --method meow --api-key "xxx"
  python douyin_user_videos.py --url "主页链接" --method playwright --show-browser
  python douyin_user_videos.py --url "主页链接" --output ./output

方式说明:
  playwright - 浏览器渲染（免费，稳定，需要安装 chromium）
  meow      - 哼哼猫 API（稳定，需要 API Key）
  dy_api    - 抖音 API（免费，可能被反爬）
  auto      - 自动选择（playwright > meow > dy_api）
        """,
    )
    parser.add_argument("--url", "-u", required=True, help="抖音用户主页链接")
    parser.add_argument("--output", "-o", default="", help="输出目录（默认 output/<sec_uid>/videos.json）")
    parser.add_argument("--method", "-m", choices=["auto", "playwright", "meow", "dy_api"], default="auto",
                        help="获取方式: auto(自动), playwright(浏览器), meow(哼哼猫API), dy_api(抖音API)")
    parser.add_argument("--api-key", "-k", help="哼哼猫 API 密钥（也可通过 MEOW_API_KEY 环境变量设置）")
    parser.add_argument("--max-scrolls", type=int, default=10, help="Playwright 最大滚动次数（默认 10）")
    parser.add_argument("--scroll-pause", type=float, default=1.2, help="Playwright 滚动等待秒数（默认 1.2）")
    parser.add_argument("--max-videos", type=int, default=100, help="API 方式最大获取数量（默认 100）")
    parser.add_argument("--delay", type=float, default=1.0, help="API 分页请求间隔秒数（默认 1.0）")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口")
    args = parser.parse_args()

    try:
        user_url = extract_first_url(args.url)
        sec_uid = parse_sec_uid_from_url(user_url)

        if not sec_uid:
            print(f"错误: 无法从 URL 提取 sec_uid", file=sys.stderr)
            sys.exit(1)

        method = args.method
        result = None

        # 获取 API Key（哼哼猫）
        meow_api_key = args.api_key or os.getenv("MEOW_API_KEY")

        if method == "auto":
            # 自动选择：playwright > meow > dy_api
            if PLAYWRIGHT_AVAILABLE:
                print("使用 Playwright 方式...")
                try:
                    result = collect_via_playwright(
                        user_url=user_url,
                        max_scrolls=args.max_scrolls,
                        scroll_pause=args.scroll_pause,
                        headless=not args.show_browser,
                    )
                except Exception as e:
                    print(f"Playwright 失败: {e}", file=sys.stderr)
                    if meow_api_key and REQUESTS_AVAILABLE:
                        print("降级到哼哼猫 API 方式...")
                        result = collect_via_meow(user_url, meow_api_key, max_videos=args.max_videos, delay=args.delay)
                    elif REQUESTS_AVAILABLE:
                        print("降级到抖音 API 方式...")
                        result = collect_via_dy_api(sec_uid, max_videos=args.max_videos)
                    else:
                        raise
            elif meow_api_key and REQUESTS_AVAILABLE:
                print("使用哼哼猫 API 方式...")
                result = collect_via_meow(user_url, meow_api_key, max_videos=args.max_videos, delay=args.delay)
            elif REQUESTS_AVAILABLE:
                print("使用抖音 API 方式...")
                result = collect_via_dy_api(sec_uid, max_videos=args.max_videos)
            else:
                print("错误: 需要安装依赖", file=sys.stderr)
                print("  pip install playwright && playwright install chromium", file=sys.stderr)
                print("  或 pip install requests", file=sys.stderr)
                sys.exit(1)

        elif method == "playwright":
            result = collect_via_playwright(
                user_url=user_url,
                max_scrolls=args.max_scrolls,
                scroll_pause=args.scroll_pause,
                headless=not args.show_browser,
            )

        elif method == "meow":
            if not meow_api_key:
                print("错误: 需要哼哼猫 API 密钥", file=sys.stderr)
                print("  通过 --api-key 参数或 MEOW_API_KEY 环境变量设置", file=sys.stderr)
                sys.exit(1)
            result = collect_via_meow(user_url, meow_api_key, max_videos=args.max_videos, delay=args.delay)

        elif method == "dy_api":
            result = collect_via_dy_api(sec_uid, max_videos=args.max_videos)

        # 保存结果
        json_text = json.dumps(result, ensure_ascii=False, indent=2)

        output_dir = Path(args.output) if args.output else Path("output") / result["sec_uid"]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "videos.json"
        output_path.write_text(json_text, encoding="utf-8")

        print(f"已保存到: {output_path}")
        print(f"共获取视频: {result['video_count']} 条 (来源: {result.get('source', 'unknown')})")

    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
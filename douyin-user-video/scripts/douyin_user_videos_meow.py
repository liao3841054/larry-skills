#!/usr/bin/env python3
"""
抖音用户主页视频列表获取 - 10倍猫 API 方式

使用哼哼猫「主页批量提取」API 获取主页视频列表，稳定性高。
支持抖音、TikTok 等多个平台。

依赖:
  pip install requests

环境变量:
  MEOW_API_KEY: 10倍猫 API 密钥（在开发者管理中心获取）

示例:
  python douyin_user_videos_meow.py --url "https://www.douyin.com/user/MS4wLjABAAAA..."
  python douyin_user_videos_meow.py --url "主页链接" --api-key "your-api-key"
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

import requests


# API 配置
API_URL = "https://api.meowload.net/openapi/extract/playlist"


def extract_first_url(text: str) -> str:
    """从输入文本中提取第一个 URL。"""
    match = re.search(r"https?://[^\s]+", text)
    if not match:
        raise ValueError("未找到有效 URL")
    # 清理 URL 末尾可能的非 URL 字符
    url = match.group(0)
    # 移除末尾的标点符号
    url = re.sub(r'[，。！？、；：""''（）【】《》\s]+$', '', url)
    return url


def parse_sec_uid_from_url(url: str) -> str:
    """从 URL 中提取 sec_uid。"""
    match = re.search(r"/user/([^/?#]+)", url)
    return match.group(1) if match else "unknown"


def fetch_playlist_page(
    url: str,
    api_key: str,
    cursor: Optional[str] = None,
    lang: str = "zh",
) -> Dict:
    """
    获取单页数据

    参数:
        url: 主页链接
        api_key: API 密钥
        cursor: 分页游标（第一页不传）
        lang: 错误消息语言

    返回:
        API 响应数据
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "accept-language": lang,
    }

    payload = {"url": url}
    if cursor:
        payload["cursor"] = cursor

    response = requests.post(API_URL, json=payload, headers=headers, timeout=60)

    if response.status_code != 200:
        try:
            error = response.json()
            raise Exception(f"API 错误 ({response.status_code}): {error.get('message', '未知错误')}")
        except json.JSONDecodeError:
            raise Exception(f"API 错误 ({response.status_code}): {response.text}")

    return response.json()


def parse_posts_to_videos(posts: List[Dict]) -> List[Dict]:
    """
    将 API 返回的 posts 转换为统一的视频列表格式

    参数:
        posts: API 返回的 posts 数组

    返回:
        统一格式的视频列表
    """
    videos = []

    for post in posts:
        post_id = post.get("id", "")
        text = post.get("text", "").strip() or f"douyin_{post_id}"
        post_url = post.get("post_url", "")
        created_at = post.get("created_at", "")

        # 解析媒体信息
        medias = post.get("medias", [])
        video_url = ""
        cover = ""

        for media in medias:
            if media.get("media_type") == "video":
                video_url = media.get("resource_url", "")
                cover = media.get("preview_url", "")
                break

        # 如果没有视频，取第一个媒体的预览图
        if not cover and medias:
            cover = medias[0].get("preview_url", "")

        # 格式化发布时间
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


def fetch_all_videos(
    url: str,
    api_key: str,
    max_videos: int = 100,
    delay: float = 1.0,
    show_progress: bool = True,
) -> Dict:
    """
    获取所有视频（自动分页）

    参数:
        url: 主页链接
        api_key: API 密钥
        max_videos: 最大获取数量
        delay: 请求间隔（秒）
        show_progress: 是否显示进度

    返回:
        包含视频列表的字典
    """
    all_videos = []
    cursor = None
    page = 1
    user_info = {}

    while len(all_videos) < max_videos:
        if show_progress:
            print(f"正在获取第 {page} 页...")

        try:
            data = fetch_playlist_page(url, api_key, cursor=cursor)
        except Exception as e:
            if page == 1:
                raise
            print(f"获取第 {page} 页失败: {e}", file=sys.stderr)
            break

        # 保存用户信息
        if not user_info and "user" in data:
            user_info = data["user"]

        # 解析视频
        posts = data.get("posts", [])
        videos = parse_posts_to_videos(posts)
        all_videos.extend(videos)

        if show_progress:
            print(f"  获取到 {len(videos)} 条，累计 {len(all_videos)} 条")

        # 检查是否达到上限
        if len(all_videos) >= max_videos:
            all_videos = all_videos[:max_videos]
            break

        # 检查是否有下一页
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="获取抖音主页视频列表（10倍猫 API 方式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python douyin_user_videos_meow.py --url "https://www.douyin.com/user/MS4wLjABAAAA..."
  python douyin_user_videos_meow.py --url "主页链接" --output ./output
  python douyin_user_videos_meow.py --url "主页链接" --max-videos 50 --delay 2

环境变量:
  MEOW_API_KEY: API 密钥（可替代 --api-key 参数）

获取 API 密钥: https://api.meowload.net/developer
        """,
    )
    parser.add_argument("--url", "-u", required=True, help="抖音用户主页链接")
    parser.add_argument("--api-key", "-k", help="10倍猫 API 密钥（也可通过 MEOW_API_KEY 环境变量设置）")
    parser.add_argument("--output", "-o", default="", help="输出目录（默认 output/<sec_uid>/videos.json）")
    parser.add_argument("--max-videos", type=int, default=100, help="最大获取数量（默认 100）")
    parser.add_argument("--delay", type=float, default=1.0, help="分页请求间隔秒数（默认 1.0）")
    parser.add_argument("--quiet", "-q", action="store_true", help="安静模式")
    args = parser.parse_args()

    # 获取 API Key
    api_key = args.api_key or os.getenv("MEOW_API_KEY")
    if not api_key:
        print("错误: 需要提供 API 密钥", file=sys.stderr)
        print("  通过 --api-key 参数或 MEOW_API_KEY 环境变量设置", file=sys.stderr)
        print("  获取 API 密钥: https://api.meowload.net/developer", file=sys.stderr)
        sys.exit(1)

    try:
        url = extract_first_url(args.url)
        result = fetch_all_videos(
            url=url,
            api_key=api_key,
            max_videos=args.max_videos,
            delay=args.delay,
            show_progress=not args.quiet,
        )

        # 保存结果
        json_text = json.dumps(result, ensure_ascii=False, indent=2)

        output_dir = Path(args.output) if args.output else Path("output") / result["sec_uid"]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "videos.json"
        output_path.write_text(json_text, encoding="utf-8")

        print(f"已保存到: {output_path}")
        print(f"共获取视频: {result['video_count']} 条")

        if result.get("user"):
            print(f"博主: {result['user'].get('username', '未知')}")

    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
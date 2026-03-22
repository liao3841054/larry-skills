#!/usr/bin/env python3
"""批量下载视频并提取字幕"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import requests
import ffmpeg


def download_video(url: str, output_path: Path, title: str = ""):
    """下载视频"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15'
    }
    print(f"  正在下载: {title[:50]}...")

    response = requests.get(url, headers=headers, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    progress = downloaded / total_size * 100
                    print(f"\r  下载进度: {progress:.1f}%", end="", flush=True)

    print(f"\n  下载完成: {output_path.name}")
    return output_path


def extract_audio(video_path: Path) -> Path:
    """提取音频"""
    audio_path = video_path.with_suffix('.mp3')
    print("  正在提取音频...")

    ffmpeg.input(str(video_path)).output(
        str(audio_path), acodec='libmp3lame', q=0
    ).run(capture_stdout=True, capture_stderr=True, overwrite_output=True)

    return audio_path


def transcribe_audio(audio_path: Path, api_key: str) -> str:
    """使用硅基流动 API 转录音频"""
    print("  正在识别语音...")

    url = "https://api.siliconflow.cn/v1/audio/transcriptions"

    with open(audio_path, 'rb') as f:
        files = {
            'file': (audio_path.name, f, 'audio/mpeg'),
            'model': (None, 'FunAudioLLM/SenseVoiceSmall')
        }
        headers = {"Authorization": f"Bearer {api_key}"}

        response = requests.post(url, files=files, headers=headers, timeout=300)
        response.raise_for_status()

        result = response.json()
        return result.get('text', '')


def main():
    # 配置
    sec_uid = "MS4wLjABAAAA-q9LCYwozQdPJPg0BLpmnMi1YhVLUpYPiHrr4GFnAm6tlHaHOrMUjmGS3W1aS7AM"
    output_dir = Path("output") / sec_uid
    videos_json = output_dir / "videos.json"
    api_key = os.getenv("API_KEY")

    if not api_key:
        print("错误: 未设置 API_KEY 环境变量")
        sys.exit(1)

    # 读取视频列表
    with open(videos_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    videos = data['videos']
    print(f"共 {len(videos)} 个视频待处理\n")

    # 处理每个视频
    for i, video in enumerate(videos, 1):
        title = video['title']
        video_url = video['video_url']

        if not video_url:
            print(f"[{i}/{len(videos)}] 跳过: 无视频链接 - {title[:30]}...")
            continue

        print(f"[{i}/{len(videos)}] 处理: {title[:50]}...")

        # 创建视频目录
        video_id = f"video_{i}"
        video_dir = output_dir / video_id
        video_dir.mkdir(parents=True, exist_ok=True)

        video_path = video_dir / f"{video_id}.mp4"
        transcript_path = video_dir / "transcript.md"

        try:
            # 下载视频
            download_video(video_url, video_path, title)

            # 提取音频
            audio_path = extract_audio(video_path)

            # 转录音频
            text = transcribe_audio(audio_path, api_key)

            # 保存字幕
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"# {title}\n\n")
                f.write(f"| 属性 | 值 |\n")
                f.write(f"|------|----|\n")
                f.write(f"| 提取时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
                f.write(f"| 视频链接 | [点击查看]({video.get('url', '')}) |\n\n")
                f.write(f"---\n\n")
                f.write(f"## 文案内容\n\n")
                f.write(text)

            print(f"  字幕已保存: {transcript_path}\n")

            # 清理音频文件
            audio_path.unlink()

        except Exception as e:
            print(f"  错误: {e}\n")
            continue

    print("全部处理完成!")


if __name__ == "__main__":
    main()
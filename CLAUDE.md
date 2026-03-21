# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a skills repository containing tools for Douyin (抖音, TikTok China) video processing. Each skill is a self-contained directory with a `SKILL.md` file describing its purpose and usage.

## Current Skills

### douyin-user-video

抖音无水印视频下载、文案提取和博主主页视频解析工具.

**Scripts:**
- `douyin_downloader.py` - Downloads videos without watermarks and extracts text from audio via SiliconFlow API
- `douyin_user_videos.py` - Parses user profile pages to get video lists using Playwright

**Dependencies:**
```bash
pip install requests ffmpeg-python playwright
playwright install chromium
```

**System requirements:**
- FFmpeg must be installed (macOS: `brew install ffmpeg`, Ubuntu: `apt install ffmpeg`)

**Environment variables:**
- `API_KEY` - SiliconFlow API key for text extraction (get from https://cloud.siliconflow.cn/)

**Key commands:**
```bash
# Get video info and download link (no API key needed)
python douyin-user-video/scripts/douyin_downloader.py --link "抖音分享链接" --action info

# Download video
python douyin-user-video/scripts/douyin_downloader.py --link "抖音分享链接" --action download --output ./videos

# Extract text from video (requires API_KEY)
python douyin-user-video/scripts/douyin_downloader.py --link "抖音分享链接" --action extract --output ./output

# Parse user profile video list
python douyin-user-video/scripts/douyin_user_videos.py --url "https://www.douyin.com/user/<sec_uid>?f" --output ./videos.json
```

## Architecture Notes

**DouyinProcessor class** (`douyin_downloader.py`): Core processor that handles URL parsing, video downloading, audio extraction via FFmpeg, and text transcription via SiliconFlow's SenseVoice API. Supports automatic audio segmentation for files exceeding 1 hour or 50MB.

**Browser-based parsing** (`douyin_user_videos.py`): Uses Playwright to render pages and extract video data from DOM, since Douyin's web API requires dynamic signature parameters (X-Bogus) that are difficult to generate programmatically.
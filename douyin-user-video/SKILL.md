---
name: douyin-user-video
description: "抖音/TikTok中国版视频处理工具：无水印下载、文案提取、主页解析。当用户提到抖音、douyin、TikTok中国、抖音视频下载、去水印、视频转文字、提取视频文案、获取博主视频列表、解析抖音主页时触发此技能。即使用户没有明确说出'技能'或'工具'，只要涉及以上需求就应使用。"
---

# 抖音无水印视频下载、文案提取和主页解析

从抖音分享链接获取无水印视频下载链接, 下载视频, 并使用语音识别提取视频中的文案, 自动保存到文件; 同时支持解析抖音博主主页中的视频列表.

## 功能概述

- **获取下载链接**: 从抖音分享链接解析出无水印视频的直接下载地址 (无需 API 密钥)
- **下载视频**: 将无水印视频下载到本地指定目录
- **提取文案**: 通过语音识别从视频中提取文字内容 (需要硅基流动 API 密钥)
- **自动保存**: 每个视频的文案自动保存到独立文件夹 (视频ID为文件夹名)
- **主页视频解析**: 从抖音博主主页链接提取视频列表（视频ID、标题、链接、封面）

## 环境要求

### 依赖安装

```bash
pip install requests ffmpeg-python

# 主页解析 - Playwright 方式（推荐）
pip install playwright
playwright install chromium
```

**说明：** 主页解析支持两种方式，自动降级：
- **Playwright**（推荐）：通过浏览器渲染，稳定性高
- **API**（兜底）：当 Playwright 不可用时自动降级，仅需 `requests`

### 系统要求

- FFmpeg 必须安装在系统中 (用于音视频处理)
- macOS: `brew install ffmpeg`
- Ubuntu: `apt install ffmpeg`

### API 密钥配置 (仅文案提取需要)

文案提取功能使用硅基流动 API, 需要设置环境变量:

```bash
export API_KEY="your-siliconflow-api-key"
```

获取 API 密钥: https://cloud.siliconflow.cn/

## 使用方法

### 命令行使用

脚本位于 `scripts/` 目录下。在技能目录下执行：

```bash
# 获取视频信息和下载链接 (无需 API 密钥)
python scripts/douyin_downloader.py --link "抖音分享链接" --action info

# 下载视频到 output/ 目录
python scripts/douyin_downloader.py --link "抖音分享链接" --action download

# 下载视频到指定博主目录 (output/<sec_uid>/<video_id>.mp4)
python scripts/douyin_downloader.py --link "抖音分享链接" --action download --sec-uid "MS4wLjABAAAA..."

# 提取视频文案 (需要 API_KEY 环境变量)
python scripts/douyin_downloader.py --link "抖音分享链接" --action extract

# 提取文案并保存视频到博主目录
python scripts/douyin_downloader.py --link "抖音分享链接" --action extract --sec-uid "MS4wLjABAAAA..." --save-video

# 安静模式 (减少输出)
python scripts/douyin_downloader.py --link "抖音分享链接" --action extract --quiet

# 解析博主主页视频列表 (自动选择方式，Playwright 优先)
python scripts/douyin_user_videos.py --url "https://www.douyin.com/user/MS4wLjABAAAA4LqLxq7PLK9xEB5PPazcKTG-3oInPFTDwbqiSrRL_mg?f"

# 强制使用 API 方式（无需浏览器，适合无头环境）
python scripts/douyin_user_videos.py --url "主页链接" --method api

# 强制使用 Playwright 方式
python scripts/douyin_user_videos.py --url "主页链接" --method playwright --show-browser
```

### 支持的主页链接格式

- `https://www.douyin.com/user/<sec_uid>?f`
- `https://www.douyin.com/user/<sec_uid>?from_tab_name=main`
- 也支持在整段文本中自动提取上述 URL

### 输出目录结构

所有输出统一在 `output/` 目录下，按博主分组：

```
output/
├── <sec_uid>/                    # 博主目录 (可选)
│   ├── videos.json               # 博主视频列表 (主页解析生成)
│   └── <video_id>/               # 视频目录
│       ├── transcript.md         # Markdown 格式文案
│       └── <video_id>.mp4        # 视频 (使用 --save-video)
└── <video_id>/                   # 单视频目录 (无 --sec-uid 时)
    ├── transcript.md
    └── <video_id>.mp4
```

**说明：**
- 使用 `--sec-uid` 参数时，视频/文案输出到 `output/<sec_uid>/<video_id>/`
- 不使用 `--sec-uid` 时，直接输出到 `output/<video_id>/`
- 主页解析 (`douyin_user_videos.py`) 自动保存到 `output/<sec_uid>/videos.json`

### Markdown 文案格式

```markdown
# 视频标题

| 属性 | 值 |
|------|-----|
| 视频ID | `7600361826030865707` |
| 提取时间 | 2026-01-30 14:19:00 |
| 下载链接 | [点击下载](url) |

---

## 文案内容

(语音识别的文字内容)
```

### Python 代码调用

```python
import sys
sys.path.insert(0, 'scripts')  # 添加脚本目录到路径

from douyin_downloader import get_video_info, download_video, extract_text

# 获取视频信息
info = get_video_info("抖音分享链接")
print(f"视频ID: {info['video_id']}")
print(f"标题: {info['title']}")
print(f"下载链接: {info['url']}")

# 下载视频 (无 sec_uid，输出到 output/<video_id>.mp4)
video_path = download_video("抖音分享链接", output_dir="./output")

# 下载视频到博主目录 (输出到 output/<sec_uid>/<video_id>.mp4)
video_path = download_video("抖音分享链接", output_dir="./output", sec_uid="MS4wLjABAAAA...")

# 提取文案 (无 sec_uid)
result = extract_text("抖音分享链接", output_dir="./output")

# 提取文案到博主目录 (输出到 output/<sec_uid>/<video_id>/transcript.md)
result = extract_text("抖音分享链接", output_dir="./output", sec_uid="MS4wLjABAAAA...", save_video=True)
print(f"文案已保存到: {result['output_path']}")
print(result['text'])
```

## 工作流程

### 获取视频信息

1. 解析抖音分享链接, 提取真实的视频 URL
2. 模拟移动端请求获取页面数据
3. 从页面 JSON 数据中提取无水印视频地址
4. 返回视频 ID, 标题和下载链接

### 提取视频文案

1. 解析分享链接获取视频信息
2. 下载视频到临时目录
3. 使用 FFmpeg 从视频中提取音频 (MP3 格式)
4. 调用硅基流动 SenseVoice API 进行语音识别
5. 清理临时文件, 返回识别的文本

### 解析博主主页视频列表

1. 打开抖音用户主页 URL（如 `https://www.douyin.com/user/<sec_uid>?f`）
2. 通过浏览器滚动触发页面继续加载
3. 从页面中提取每条视频的 `aweme_id`、标题、链接、封面
4. 输出为 JSON 结果，便于后续批量下载或分析

## 常见问题

### 无法解析链接

- 确保链接是有效的抖音分享链接
- 视频链接格式通常为 `https://v.douyin.com/xxxxx/` 或完整的抖音视频 URL
- 主页链接格式可使用 `https://www.douyin.com/user/<sec_uid>?f`

### 提取文案失败

- 检查 `API_KEY` 环境变量是否已设置
- 确保 API 密钥有效且有足够的配额
- 确保 FFmpeg 已正确安装

### 下载速度慢

- 这取决于网络条件和视频大小
- 脚本会显示下载进度

## 注意事项

- 本工具仅供学习和研究使用
- 使用时需遵守相关法律法规
- 请勿用于任何侵犯版权或违法的目的

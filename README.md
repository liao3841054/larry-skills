# Larry Skills

Claude Code 技能仓库，包含多个实用工具。

## 技能列表

### [douyin-user-video](./douyin-user-video)

抖音无水印视频下载、文案提取和博主主页视频解析工具。

**功能：**
- 获取无水印视频下载链接
- 下载视频到本地
- 语音识别提取视频文案
- 解析博主主页视频列表

**快速开始：**

```bash
# 安装依赖
pip install requests ffmpeg-python playwright
playwright install chromium

# 获取视频信息
python douyin-user-video/scripts/douyin_downloader.py --link "抖音分享链接" --action info

# 下载视频
python douyin-user-video/scripts/douyin_user_videos.py --link "抖音分享链接" --action download

# 提取文案 (需要 API_KEY)
export API_KEY="your-siliconflow-api-key"
python douyin-user-video/scripts/douyin_downloader.py --link "抖音分享链接" --action extract

# 解析博主主页
python douyin-user-video/scripts/douyin_user_videos.py --url "https://www.douyin.com/user/<sec_uid>?f"
```

详细文档请查看 [douyin-user-video/SKILL.md](./douyin-user-video/SKILL.md)。

## 许可证

MIT
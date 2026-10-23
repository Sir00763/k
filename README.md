# 帧记 · Frame Notes

一个开源的 YouTube 文稿工作台。粘贴视频链接后，优先读取已有字幕；没有可读取字幕时，自动下载音轨并使用本地 Whisper 模型转写。无需付费转写 API 密钥。

## 功能

- YouTube 普通链接、短链接、Shorts 链接识别。
- 无字幕视频自动语音转写，显示进度与时间戳。
- TXT / SRT / VTT 导入，或粘贴文稿。
- 本地音频上传转写，支持 MP3 / M4A / WAV / WEBM / MP4。
- 文稿搜索、跳转视频时间点、重点原句提取。
- 一键复制纯文本（无时间戳），或复制带时间轴的完整文稿。
- 导出 TXT / Markdown，浏览器保存最近 8 份文稿。

## 快速运行

需要 Node.js 20+、Python 3.10+。建议至少 2 GB 可用内存；较长音频或更大模型需要更多内存。

Mac：下载源码并双击「启动帧记.command」。初次启动会安装依赖，初次语音识别会下载模型。

macOS / Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
FRAME_PYTHON="$PWD/.venv/bin/python" PORT=8789 node scripts/dev.mjs
```

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FRAME_PYTHON = "$PWD\.venv\Scripts\python.exe"
$env:PORT = "8789"
node scripts/dev.mjs
```

浏览器打开 http://127.0.0.1:8789 ，粘贴链接，点击「识别视频」。

Docker（需要先安装 Docker）：

```sh
docker compose up --build -d
```

Docker 配置已提供，尚未在本次开发环境实际构建。更完整的部署说明见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 工作方式与限制

1. 尝试读取已有字幕；不可用则读取音轨。
2. 使用多语言 `base` 模型在本机 CPU 上识别，不需要云转写密钥。`FRAME_WHISPER_MODEL=small` 可换用更大的模型，下载量、处理时间和内存需求也会增加。
3. 自动语音识别可能出现错别字、漏字，必须结合音频校对。重点提取使用规则筛选原句，不是 AI 摘要或翻译。
4. 一次执行一个识别任务，上传不超过 200 MB，音频不超过 2 小时。重新启动服务会丢失正在运行的任务记录；成功识别的视频缓存可以复用。
5. YouTube 的登录、地区与服务器 IP 限制可能导致下载失败，不保证任何链接均可处理，不会自动读取浏览器 Cookie。
6. 需要能访问 PyPI、YouTube 和 Hugging Face 的网络。开源不等于在线托管：别人可以自行运行；要共用一个公网网址，仍需服务器。

## 数据

模型、视频文稿缓存与临时音频写入 `.runtime/`，不应加入 Git。成功识别后删除对应音频，失败任务可能留下临时文件。浏览器历史保存在当前浏览器，可在页面中清空。

源代码不包含开发者的文稿、音频、模型权重、账号凭据或托管项目标识。模型权重会在首次使用时从模型发布方下载，其许可独立于本项目。

## 检查

```sh
npm run check
```

本地开发中已使用无字幕视频验证完整的链接下载与语音识别流程。Docker 与公网服务器需要在目标环境另行验收。

## 开源许可

原创应用代码采用 [MIT License](LICENSE)。依赖和模型遵循各自许可证，见 [THIRD_PARTY.md](THIRD_PARTY.md)。

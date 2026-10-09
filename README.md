# 第二世界旅行海报

旅行实拍 → 纸上世界 → **3:4 PNG + 恰好3秒 MP4**。每张独立设计，通常约60%原照、40%纸面，真实结构先连接，再完成一个小互动。

**v1.1.0 已加入不用 GPT 的出图入口**：SenseNova U1.5 Lite 编辑图片，本地脚本制作水纹动画。可直接使用命令行，也能作为 Skill 安装到有文件执行能力的 AI 助手。无需 GPT 订阅或 OpenAI Key；新海报需要自己的 SenseNova Key 和可用额度。

这版是安装配置后可操作，还不是全自动一键成品：连接与文字要看图检查，水面需鼠标圈选。动画是二维纹理搬运，复杂人物动作和新视频模型尚未接入。

## 一次安装

下载并解压仓库，进入文件夹。需要 Python 3.10+ 与系统 FFmpeg（含 ffprobe，加入 PATH）：

| 系统 | 安装示例 |
| --- | --- |
| macOS | `brew install ffmpeg` |
| Windows | `winget install --id Gyan.FFmpeg -e`，然后重新打开终端 |
| Ubuntu / Debian | `sudo apt install ffmpeg python3-venv` |

执行 `python3 bootstrap.py`（Windows 用 `python bootstrap.py`）。它创建 `.venv`、安装 Python 依赖并检查系统工具，不自动安装系统软件，不保存凭据。

以下 `PYTHON` 换成 macOS/Linux 的 `.venv/bin/python`，Windows 的 `.venv\Scripts\python.exe`：

```bash
PYTHON quickstart.py doctor
PYTHON quickstart.py demo --out work/demo
```

`demo` 使用附带授权示例，无需接口 Key。打开 `work/demo/poster_3s.mp4` 确认水纹可见，岸线与文字固定。示例原片和海报见 [examples/sayram](examples/sayram)。

## 自己的照片，不用 GPT

在 [SenseNova Token 平台](https://token.sensenova.cn/) 获取自己的 Key，额度、价格和模型可用性以平台为准，不承诺永久免费。凭据仅放在当前进程环境变量：

```bash
# macOS / Linux
export SENSENOVA_API_KEY='你的Key'
```

```powershell
# Windows PowerShell
$env:SENSENOVA_API_KEY='你的Key'
```

`poster` 会把预排版照片上传到配置的 SenseNova 图片服务，消耗额度，不自动重试。不要提交 Key、终端截图或私人照片。

1. **先看裁切**，此步骤不上传照片。默认保留下缘，照片占 .58，裁掉面积超过20%会停止。

```bash
PYTHON quickstart.py prepare photo.jpg --location "赛里木湖" --out work/my-poster
```

打开 `preview.png`，检查主体与连接点。必要时用 `--crop-anchor 0.5 1` 调整归一化锚点或用 `--photo-share` 调整照片占比（.55–.65）。不能为了比例裁掉关键主体。

2. 从真实到达照片下缘的道路、水面、阶梯等结构出发，用 `--idea` 说明准确接续与一个互动，没有合适结构时先改裁切。中文句子未指定时写地名，诗句出处由使用者或助手查证。

```bash
PYTHON quickstart.py poster photo.jpg --location "赛里木湖" --caption "赛里木湖" --idea "从下缘真实结构准确延续，在纸上完成一个具体互动" --out work/my-poster
```

查看 `poster.png` 的连接、文字与人物支撑，失败则调整意图后显式加 `--overwrite` 重试。程序重新贴回上方缩放裁切后的原照片，报告差值为零；这不能称为原分辨率无损，也不保证生成区自动融合。

3. **鼠标圈选水面**，无需写 JSON。

```bash
PYTHON quickstart.py select work/my-poster/poster.png --out work/my-poster
```

打开 `water-mask-editor.html`，沿水面逐点点击并闭合；扣除挡在水前的树林、人物、岸线和文字；点两下画流向。分别保存 `water_mask.png`、`motion.json` 到同一个任务目录。页面离线运行、不上传图片。

4. **导出视频**。

```bash
PYTHON quickstart.py animate work/my-poster/poster.png --out work/my-poster
```

自动导出 `poster_3s.mp4` 并检查24 fps、72帧、3秒、无声、完整解码和运动指标。还要完整看一次：数值检查不能保证视觉自然。最终使用 `poster.png` 与 `poster_3s.mp4`，无需发布过程文件。MP4 是转换 Live Photo 的素材，工具不生成原生 Live Photo。

## 作为 Skill 安装

把 [skills/create-second-world-posters](skills/create-second-world-posters) 整个目录添加到宿主 Skill 安装入口。核心包不硬编码私人目录，依赖与凭据来自当前进程。

公开包 frontmatter 包含 name、description、version，符合 AgentDock 规范；只接受前两项的宿主可以删除 version 行，正文版本说明保留。`run.py` 通过 stdin JSON 提供 status、prepare、poster、select_motion、animate、check_pair、audit_motion。见 [SKILL.md](skills/create-second-world-posters/SKILL.md) 与 [接口说明](skills/create-second-world-posters/references/providers.md)。

## 验证和限制

```bash
PYTHON -B -m unittest discover -s tests -v
```

测试包含实际视频编码、固定区域与覆盖保护，以及图片服务的源照片恢复、错误处理和凭据保护。浏览器操作与示例验证记录见 [docs/VALIDATION.md](docs/VALIDATION.md)。公开示例不使用用户私有旅行照片。

当前水流沿一个恒定方向，弯河、多向流和窄水带可能不适合；没有自动语义分割。错误选区会导致错误区域运动。固定区域的原始帧像素不变，视频编码仍可能带来轻微像素差。新视频生成项目尚未集成。

代码与文档采用 [Apache-2.0](LICENSE)；示例照片另有授权，见 [来源说明](examples/sayram/ATTRIBUTION.md)。服务使用遵守对应平台条款。

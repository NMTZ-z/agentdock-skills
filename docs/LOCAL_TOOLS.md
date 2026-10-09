# 可选本地工具

本页只适用于能运行本地命令的使用者或 Agent。通用海报设计可以直接使用宿主绘图工具，不要求安装这些脚本。

## 安装与离线示例

需要 Python 3.10+ 和系统 FFmpeg（含 ffprobe，加入 PATH）。

| 系统 | 安装 FFmpeg 示例 |
| --- | --- |
| macOS | `brew install ffmpeg` |
| Windows | `winget install --id Gyan.FFmpeg -e`，随后重新打开终端 |
| Ubuntu / Debian | `sudo apt install ffmpeg python3-venv` |

在仓库目录执行 `python3 bootstrap.py`（Windows 用 `python bootstrap.py`）。它创建 .venv、安装依赖并检查系统工具，不自动安装系统软件或保存凭据。

将下方 `PYTHON` 换成 macOS/Linux 的 `.venv/bin/python`，或 Windows 的 `.venv\\Scripts\\python.exe`：

```bash
PYTHON quickstart.py doctor
PYTHON quickstart.py demo --out work/demo
```

示例不需要图片服务 Key。打开 `work/demo/poster_3s.mp4`，看完三秒并确认湖水可辨认地运动，岸线与文字保持稳定。

## 预览、出图与动画

1. 先做离线裁切预览：

```bash
PYTHON quickstart.py prepare photo.jpg --location "赛里木湖" --out work/my-poster
```

查看 `preview.png`。必要时调整 `--crop-anchor 0.5 1` 或 `--photo-share`（.55–.65）；默认裁掉面积超过20%会停止。具体输入见 [工具选择](../skills/create-second-world-posters/references/providers.md)。

2. 用 Agent 当前可用的图像编辑工具完成海报，保存为 `work/my-poster/poster.png`。附带 `quickstart.py poster` 只是一个已测试的服务适配器；若主动选择它，再读 [适配器说明](../skills/create-second-world-posters/references/optional-image-service.md)。它并不自动路由所有绘图模型。

3. 离线圈选水面：

```bash
PYTHON quickstart.py select work/my-poster/poster.png --out work/my-poster
```

打开 `water-mask-editor.html`，圈水面并扣除遮挡物、岸线、人物与文字，再画流向。将 `water_mask.png` 与 `motion.json` 保存到该任务目录。修改海报后重新选区。

4. 导出并检查三秒视频：

```bash
PYTHON quickstart.py animate work/my-poster/poster.png --out work/my-poster
```

输出 `poster_3s.mp4`；自动核对24 fps、72帧、三秒、无音轨、完整解码及运动指标。还须看完视频，数值不能替代视觉检查。局部范围选错会使错误区域运动，单方向水纹不适合所有水域。

## 核心包与宿主差异

公开核心包的 frontmatter 含 name、description、version。只接受前两项的宿主可在自己的安装副本中删除 version 行，保留正文版本；不要修改原始发布包。

`run.py` 通过 stdin JSON 提供 status、prepare、poster、select_motion、animate、check_pair、audit_motion。status 的 ready 诊断本地动画依赖，poster_ready 诊断附带图片适配器；它们不诊断 Agent 自带的绘图能力。核心目录沿用 `create-second-world-posters` 标识，兼容已有安装；项目显示名为 Travel in the Second World。

复现测试：

```bash
PYTHON -B -m unittest discover -s tests -v
```

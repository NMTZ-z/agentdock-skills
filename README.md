# 第二世界旅行海报 Skills

将每张旅行实拍独立延伸成一个温暖、留白的纸上世界：结构先接通，再发生一个轻巧互动。最终交付 **3:4 竖版 PNG** 和可用于后续转换 Live Photo 的 **3 秒 MP4**。

当前发布 **v1.0.0**，包含 `create-second-world-posters`。它固化经过实际旅行作品迭代验证的设计流程与最后的平滑局部水纹方案，适合在提供图像编辑工具和文件执行能力的 AI 助手中使用。

## 包含什么

- 构图与裁切：通常照片约 55–65%，纸上世界约 35–45%，以主体与真实连接结构为先；每张独立设计。
- 地点文案：按实际地点查证，优先用户指定的中文句子；不能虚构诗句出处。
- 局部修图：修正人物支撑与接触关系，保护正确区域，检查前后像素差。
- 三秒水纹：显式水面遮罩，连续同向搬运，保持岸线、树木、人物和文字不动；逐帧检查折叠与过度拉伸。
- 验收：尺寸、时长、帧率、完整解码与手机尺寸动态检查。

## 安装

Skill 包在 [`skills/create-second-world-posters`](skills/create-second-world-posters)。将整个目录添加到宿主支持的 Skill 位置，或使用宿主的 Skill 包安装功能；先阅读 `SKILL.md`。

这是普通文档 Skill，不依赖某个宿主的私有目录。公开包 frontmatter 包含 `name`、`description`、`version`，符合 AgentDock Skill 规范；只接受 `name`、`description` 的宿主，可删除 `version` 行，保留正文版本说明与其余内容。

海报设计需要宿主实际提供的图像生成/编辑工具。包内 Python 脚本只负责局部水纹、检查与诊断，不会仅凭照片自动画出纸上世界。

## 脚本依赖

Python 3.10+、NumPy、Pillow、SciPy、ffmpeg、ffprobe。先在自己的项目环境准备依赖，例如：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

ffmpeg 与 ffprobe 通过系统包管理器安装并加入 PATH；工具不会自动下载安装。无需 API Key 或业务环境变量。

## 快速使用

在 Skill 根目录执行 `python3 run.py`，通过 stdin 传入 JSON。使用已准备依赖的 Python 环境；不要在安装目录存放照片、遮罩、视频或报告。

```bash
printf '%s' '{"skill_action":"status"}' | python3 run.py
```

准备自己的 3:4 PNG 和与它同尺寸的显式水面遮罩，在任务目录写配置；[参数与执行说明](skills/create-second-world-posters/references/motion.md) 包含完整输入契约。

```json
{
  "bounds": [0.20, 0.80],
  "water_mask": "water_mask.png",
  "direction": [-0.35, 0.36],
  "travel_pixels": 64,
  "edge_fade_pixels": 180
}
```

每张图应重新判断范围、流向、可见幅度与渐弱宽度，上述参数仅示意。

```bash
python3 run.py <<'JSON'
{"skill_action":"animate","image":"/path/to/job/final.png","video":"/path/to/job/final_3s.mp4","config":"/path/to/job/motion.json","report":"/path/to/job/transport_report.json"}
JSON
```

可用动作：`status`、`animate`、`check_pair`、`audit_motion`。输出为 JSON，错误包含稳定的 `code` 与说明；默认拒绝覆盖视频。所有任务路径由调用者指定，遮罩相对路径以配置文件目录为基准。

## 验证

从仓库根目录执行：

```bash
python3 -B -m unittest discover -s tests -v
```

测试使用程序生成的抽象纹理夹具，检查实际编码、3 秒格式、受保护区域、拒绝覆盖和失败诊断。公开仓库不包含个人照片或旅行成品。数值检查不替代目视检查；最终仍需确认连接自然、人物落在干燥岸边、动态手机上可辨认、没有折叠或支撑漂移。

## 限制与后续

当前动画是 **二维纹理搬运**，不是视频模型、真实水体模拟或原生 Live Photo；它不能完成复杂人物动作，恒定流向也不适合所有弯曲河流。保留的早期 `animate_local.py` 用于兼容参考，标准入口不调用其直接位移算法。

原片保留依赖实际图像编辑与合成能力：生成式重绘不能称为无损，重采样也不能称为原像素完全未变。宿主无法精确保留时必须说明限制。

新视频生成项目尚未接入。本版作为可复现基线保存，待安装、调用和实际验收完成后另发版本。

## 许可证

Apache-2.0，见 [LICENSE](LICENSE)。照片、字体和外部图像编辑服务由使用者自行提供并遵守对应授权。

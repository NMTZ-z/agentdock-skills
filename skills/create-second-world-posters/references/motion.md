# 三秒动画与执行

## 能力边界

本版固化最后验证通过的平滑水纹搬运方案：显式水面遮罩、遮罩内部宽缓过渡、RK2 速度场积分、每帧从同一静态图采样、逐帧检查采样映射没有折叠。固定 24 fps、72 帧、恰好 3 秒、无声 H.264/yuv420p。

这是二维纹理运动，不是视频模型、三维水体模拟或原生 Live Photo。视频不强制首尾相同，静态图对应 1.5 秒附近；不能让水倒流以凑循环。当前标准入口只提供恒定方向的平滑水流；复杂弯河、多向流、人物动作和纸张翻折应另行规划，不能承诺脚本自动处理。保留的 `scripts/animate_local.py` 是早期工具与兼容参考，其直接位移方式曾出现折叠，不作为水流交付方案。

需要 Python 3.10+、Pillow、NumPy、SciPy、ffmpeg 和 ffprobe；无需业务环境变量或凭据。工具不会下载、安装、上传文件。先从 Skill 根目录执行 `python3 run.py`，stdin 输入：

```json
{"skill_action":"status"}
```

`ok: true` 仅说明状态查询成功；只有 `ready: true` 才说明依赖完整。

## 独立任务配置

先查看实际最终海报，手工建立与海报等大的灰度水面遮罩：白色允许流动、黑色固定；扣除树枝、岸线、人物、文字和支撑物。不能按蓝色识别水，也不能跨图复用固定位置。保护遮罩可选，任何非黑像素将完全固定。运动范围之外直接恢复源像素，这个保证发生在编码前；有损 MP4 仍可能存在轻微压缩差异。

将配置保存在自己的任务目录，例如 `motion.json`：

```json
{
  "bounds": [0.20, 0.80],
  "water_mask": "water_mask.png",
  "protect_mask": "protect_mask.png",
  "direction": [-0.35, 0.36],
  "travel_pixels": 64,
  "edge_fade_pixels": 180
}
```

- `bounds`：整张海报的归一化纵向范围；不代替水面遮罩。
- `water_mask`、`protect_mask`：相对于配置所在目录定位；也接受任务输入的绝对路径。必须与海报同尺寸。
- `direction`：沿实际水流的方向向量，分别以画幅宽和高为尺度，脚本再归一化。非零且连续；每张图重新判断。
- `travel_pixels`：三秒内原尺寸水纹行程。64 像素是验证案例的参数，不是通用最佳值；以 390 宽手机预览换算，至少 4 屏幕像素只是一条防止几乎静止的门槛。
- `edge_fade_pixels`：只在允许的遮罩内部渐弱。180 像素是验证案例中的宽缓过渡，随尺寸与河道宽度调整。过窄过渡可能被变形检查拒绝；过宽会减弱窄河运动。失败后调整范围、方向、行程或渐弱宽度，不关闭检查。

按实际情况配置，先连通水面，再让纹理流动。仅动水时不加入人物、树林、光影的辅助运动。小人臀部与双脚在岸上，不能随水流滑动。

## 执行与检查

从 Skill 根目录运行 `python3 run.py`，每次 stdin 传入一个 JSON 对象。相对的任务路径相对于当前工作目录解析；不要假设当前目录是照片目录。

```json
{
  "skill_action":"animate",
  "image":"/path/to/job/final.png",
  "video":"/path/to/job/final_3s.mp4",
  "config":"/path/to/job/motion.json",
  "report":"/path/to/job/transport_report.json"
}
```

默认拒绝覆盖已有视频；用户已授权修改同一作品时增加 `"overwrite": true`。暂存视频通过格式检查后才写入目标。`report` 是内部 QA 产物；它包含编码前保护像素差、采样 Jacobian、折叠数与帧变化，不能用这些数字替代视觉检查。

```json
{
  "skill_action":"check_pair",
  "image":"/path/to/job/final.png",
  "video":"/path/to/job/final_3s.mp4",
  "before":"/path/to/job/approved_before.png",
  "unchanged_boxes":[[0,0,1152,800]]
}
```

`before` 和 `unchanged_boxes` 仅用于局部修图，非修改任务可省略。坐标是当前原尺寸像素，每次重新填写。该检查核对 PNG、3:4、视频尺寸、24 fps、72 帧、3 秒、无音轨与完整解码。

```json
{
  "skill_action":"audit_motion",
  "video":"/path/to/job/final_3s.mp4",
  "roi":[0.50,0.42,0.97,0.62],
  "width":390,
  "report":"/path/to/job/phone_report.json",
  "qa":"/path/to/job/phone_qa.jpg"
}
```

ROI 仅展示结构，按当前主动态区域改写。RGB 差也包括压缩和光影，不等同于运动距离或动作质量。检查 0、0.75、1.5、2.25、接近 3 秒的全图和放大图，并以手机完整画幅播放：必须能直接看出什么在怎么动，同时树木、岸线、文字、人物及支撑点固定，没有折叠或漂移。

输出结构为 `ok`、`skill_action`、`result`；失败包含稳定 `code` 与可读 `message`。脚本失败时不得宣称导出成功。逐帧保护与折叠检查是辅助门槛，不能证明物理真实性。

## 后续方向

保留当前方法作为 1.0.0 基线。未来视频生成项目安装、实际调用和验证完成后，另起版本接入；本版不把任何未安装的模型或项目写成已有能力。

# v1.1.0 验证记录

2026-10-09，macOS ARM64，Python 3.14。Ubuntu Python 3.12 由仓库 CI 验证；Windows 安装说明已提供，但未在 Windows 机器实测。

- 实际调用 SenseNova `sensenova-u1.5-lite` 图片编辑接口，输入公开 CC0 实拍、输出1152×1536海报。照片高891像素，占58.01%，裁切面积13.84%，准备照片复用差值0。原分辨率经过重采样，因此不称为无损。
- 第一张试图从木栈道下方接水，衔接不合格；改为准确延续真实栈道后得到公开示例。说明了模型输出仍须检查，不承诺一次出图全部合格。
- 从新建的隔离目录和新建 Python 环境安装运行依赖，没有图片服务 Key，成功导出附带示例。全流程不依赖 GPT。
- 5 项自动测试覆盖本地预览、缺 Key 无上传无生成输出、裁切边界、输出符号链接保护、真实 HTTP 图片恢复、禁止重定向、服务错误不泄漏 Key、模型改变尺寸时拒绝、过期选区拒绝、视频实际编码与保护范围。
- 用真实 Chromium 浏览器逐点圈选、扣除区域、绘制流向并分别下载 PNG 与 JSON；外部网络请求0，未闭合轮廓禁止导出。Playwright 仅为开发检查依赖，普通使用者无需安装。
- 实际三秒示例：24 fps、72帧、H.264、无声、完整解码通过，保护原始像素差0、折叠0，最小映射面积尺度约0.781。按实际湖面 ROI 检查，手机尺寸变化超过12的像素约22.5%，无接近静止警报。
- 初版默认审计范围覆盖静止纸面，未覆盖湖水；现已由圈选遮罩计算真实检查范围。图像修改后 SHA-256 不一致时拒绝旧选区。
- PNG 与手机尺寸抽帧已目视检查，人物支撑、字和岸线固定。未将这些数值或抽帧检查宣称为用户设备上的完整实时播放验证；请发布前看完3秒。

复现核心测试：

```bash
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python quickstart.py demo --out work/check
```

浏览器专项检查（可选开发步骤，显式安装）：

```bash
.venv/bin/python -m pip install playwright
.venv/bin/python -m playwright install chromium
.venv/bin/python -B tests/verify_picker.py --image examples/sayram/poster.png --out work/browser-check
```

图片 API 在隔离目录外另行使用用户已配置的服务凭据实测；普通自动测试使用本地 HTTP 测试服务，不向收费平台发请求。自动检查不能保证所有真实照片的艺术效果或所有水域的流向正确。

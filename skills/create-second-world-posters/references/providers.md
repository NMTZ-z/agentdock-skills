# 工具选择与输入契约

## 按实际能力选择

优先使用 Agent 已有的图像编辑工具，将原片作为编辑输入，按 [设计细则](design-and-edits.md) 组织参考图、保护区域、连接交点及单一互动。模型选择不受本 Skill 限制；各工具的参考图、蒙版、尺寸及局部编辑语法由 Agent 依官方接口处理，不凭空套用某个厂商的参数。

输出后实际查看连接、文字、支撑及保护区。若模型重绘全图，使用可用合成工具复用源片并检查接缝；没有这种能力时说明原片保留的限制。更换模型不降低验收要求。

通用静态流程不要求 Python 或任何特定 Key。若选用打包的图片接口，单独读取 [可选适配器](optional-image-service.md)；缺少该接口凭据不阻止宿主原生绘图。其他提供商由宿主自己调用，本包不宣称已经适配。

## 本地裁切预览（可选）

仅在有文件执行能力时，从 Skill 根目录运行 `python3 -B run.py`，stdin 传入：

```json
{"skill_action":"prepare","image":"/path/source.jpg","location":"赛里木湖","caption":"赛里木湖","idea":"从准确连接交点延续真实结构，再设计一个互动","output_dir":"/path/job"}
```

此动作离线写出 `preview.png`、`layout_report.json`、`edit_prompt.txt`。可用宿主绘图工具编辑预览，也可自行按同样几何规划创建画布。查看主体与下缘结构后再出图；生成模型不一定精确保留尺寸及原照，需要另行验收。

参数：`width` 为 768–3072 中 96 的整数倍，默认 1152；`photo_share` 默认 .58，范围 .55–.65；`crop_anchor` 默认 [.5,1]；`max_crop` 默认 .20，显式审阅后才提高；`overwrite` 默认 false。锚点与比例按每张照片选择，不能裁掉关键主体。

## 本地水面选择（可选）

```json
{"skill_action":"select_motion","image":"/path/job/poster.png","output_dir":"/path/job"}
```

打开生成的 `water-mask-editor.html`，逐点圈水面并闭合，扣除遮挡枝叶、人物、岸线与文字；选起点与终点画流向。将 `water_mask.png` 与 `motion.json` 保存到同一任务目录。页面离线运行，无外部资源或网络请求。修改海报后重新选区，不能复用过期配置。

该工具没有自动语义分割；需要用户或能操作浏览器的 Agent 选范围。多块水面共用一个方向，窄水带、弯河或多向流未必适合。调用方式与验收见 [本地动画](motion.md)。

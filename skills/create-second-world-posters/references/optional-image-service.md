# 可选图片服务适配器

仅在宿主没有合适图像编辑工具、且使用者主动选择此已测试适配器时阅读。本接口不是 Skill 的依赖，也不限制 Agent 使用其他绘图模型。`poster` 仅实现下面的具体协议，不是通用模型路由。

## 能力分工

SenseNova `sensenova-u1.5-lite` 负责图片编辑；6.8 Flash Lite 是理解和规划模型，不能用它代替图片接口。这条路线不需要 GPT、OpenAI Key 或 GPT 订阅，但需要用户自己的 SenseNova Key 和平台可用额度，价格与额度以服务方为准。动画在本地运行，不调用视频模型。

仅从当前进程读取：

| 环境变量 | 默认或要求 |
| --- | --- |
| `SENSENOVA_API_KEY` | 图片生成必需；不回显、不写文件 |
| `SENSENOVA_BASE_URL` | `https://token.sensenova.cn/v1`；HTTPS，仅显式本地测试允许 HTTP |
| `SENSENOVA_IMAGE_MODEL` | `sensenova-u1.5-lite` |
| `SENSENOVA_TIMEOUT_SECONDS` | 180，允许 1–600 |

使用 `/images/edits` 的 JSON 接口、Base64 图片输入与输出。禁止自动重试收费请求；错误响应不回显原文，以免泄漏凭据。官方接口说明：[SenseNova U1.5 Lite Token Plan](https://www.sensetime.com/cn/news/sensenova-u1-5-lite-token-plan-20260911-1741)。

## 预览与生成

从 Skill 根目录运行 `python3 -B run.py`，stdin 传入：

```json
{"skill_action":"prepare","image":"/path/source.jpg","location":"赛里木湖","caption":"赛里木湖","idea":"从准确的连接交点延续真实结构，再设计一个互动","output_dir":"/path/job"}
```

`prepare` 仅写本地 `preview.png`、`layout_report.json` 和 `edit_prompt.txt`。必须查看预览，确认主体未被裁掉、连接结构真正到达照片下缘。再将动作改为 `poster` 生成。无需删除预览；最终输出为 `poster.png`，其余过程文件用于核验。

可选参数：`width` 为 768–3072 中 96 的整数倍，默认 1152；`photo_share` 默认 .58，范围 .55–.65；`crop_anchor` 为归一化裁切锚点，默认 [.5,1] 保留下缘；`max_crop` 默认 .20，明确审阅后才提高；`overwrite` 默认为 false。每张照片重新决定锚点，不能沿用默认值裁掉人物或连接点。

生成后程序将准备好的缩放裁切照片重新贴回上部，核对差值为零。这只保证相对准备图的像素保留，不能称为原分辨率无损，也不能保证生成区衔接。检查接点、文字、单一互动及人物支撑，失败则修正意图或切换可用编辑工具；不能用模糊掩盖不对齐。


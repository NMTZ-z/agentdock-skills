# 示例素材授权与处理

原照片：**The shore of Sayram Lake.jpg**，作者 **Fumikas Sagisavas**，2023-06-24，Wikimedia Commons 自有作品，**CC0 1.0**。

来源：https://commons.wikimedia.org/wiki/File:The_shore_of_Sayram_Lake.jpg
授权：https://creativecommons.org/publicdomain/zero/1.0/

source.jpg 是公开原片的1280像素缩略图，非用户私有照片。原片只经过等比缩放与裁切（约13.84%面积）；poster.png 上方直接复用准备好的照片。下方由 SenseNova U1.5 Lite 编辑生成，再复用上方源像素；栈道向下变成纸带，一个旅人坐在有支撑的凳上。衔接和文字经过目视检查，仍属于模型输出示例，不保证每次同样质量。poster_report.json 记录布局与像素保留，prompt.txt 是实际编辑提示词。

water_mask.png 与 motion.json 由本地浏览器圈选器实际下载，湖面选区不包括岸地、人物、栈道、文字和纸带。动画只让原照片的湖水运动，纸上人物保持固定。

代码和说明使用仓库 Apache-2.0；原片独立采用 CC0，不能把代码许可证代替原片授权。生成区由本项目制作，使用仍遵守图片服务条款。未更改 Wikimedia 上的原文件。

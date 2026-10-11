# 顶部加载动画

此动画放在原有图片轮播上方，使用 GitHub README 可显示的 APNG，无需 JavaScript。浅色、深色版本均播放一次，共 12 秒，最后停在欢迎画面；启用系统「减少动态效果」时直接显示静态欢迎画面。

仅参考《明日方舟》[莱茵生命：访问](https://www.bilibili.com/video/BV1rr4y1b7sz/)开场加载段：逐字访问提示 → 连续绘制 ∞ 标志并展开正负符号 → 身份验证文字 → 黑白圆弧及橙色轨道点 → 欢迎画面。原片约 20 秒的流程压缩到 12 秒，改为 4:1 横幅并加入 Profile 名称。验证文字属于动画内容。

生成命令（依赖 Pillow 12.3.0）：

```sh
python scripts/build_loading.py
```

`config.json` 可修改 `profile_name`、`subtitle`（最多 24 个可打印 ASCII 字符）、画布大小（保持 4:1）、`fps`（10–60）和 `duration_ms`（11000–20000）。动作在前 10.4 秒完成，其余时间停留在欢迎画面。默认名称为 `SIRUI MEI`，画布为 1280 × 320、60 fps；默认输出目录为 `assets/`，可用 `--output-dir` 覆盖。

## 来源与许可

- ∞ 连续曲线和圆环运动参考 [LBEILC/RhineLabUI](https://github.com/LBEILC/RhineLabUI/tree/12cc5e4013acb9408f753ff71de6b8492299b7c8)，固定修订 `12cc5e4013acb9408f753ff71de6b8492299b7c8` 的 `src/brand.ts`、`src/boot-logo-tracks.ts`、`src/boot-motion.ts` 和 `src/boot-orbit-tracks.ts`。仅改编加载段，不引入三维场景、模型、音频或其他应用功能。代码版权与 MIT 许可见 [RHINELAB-LICENSE.txt](RHINELAB-LICENSE.txt)；原作名称、标志与视觉设计的权利归原权利人所有。
- 使用 Barlow Regular / SemiBold 替代参考中的 Novecento 字体，字体随项目保存，避免依赖本机字体或外部字体服务。来源为 [Google Fonts / Barlow](https://github.com/google/fonts/tree/bd8f81ddb5c74d5c8897b36ad88b440266245103/ofl/barlow)，固定修订 `bd8f81ddb5c74d5c8897b36ad88b440266245103`，许可见 [fonts/OFL.txt](fonts/OFL.txt)。
- [provenance.json](provenance.json) 记录源修订和字体文件的 SHA-256。

原视频仅用于对照，不随仓库分发；原有插画素材不参与动画生成。

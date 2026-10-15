# 顶部开场动画

此动画放在原有图片轮播上方，使用 GitHub README 可显示的 APNG，无需 JavaScript。浅色、深色版本各播放一次，约 13 秒，最后停在欢迎画面；启用系统「减少动态效果」时直接显示静态欢迎画面。

动作按[个人网站](https://siruimei07.github.io/)的开场（网站仓库 `src/boot/`）校正，沿用网站逐帧测得的轨迹，只把等待的停顿压缩为 4 倍速：`ACCESS PERMISSION REQUIRED` 不规则地逐字打出 → ∞± 标志沿一条连续轮廓画出，加减号弹出，下方打出 `RHINE LAB LLC.` → 标志左移，左上角名字滑入，右下 `POWERED BY RHINE LAB` 逐段显现 → `ID CONFIRMED : VISITOR` / `REQUEST RECEIVED` / `START PROCESSING...` → `PERMISSION AUTHORIZED` 圆环收拢 → `WELCOME TO / SIRUI MEI / PERSONAL DATABASE`。画面保持简洁：纯色底与两道淡淡的 ∞ 轮廓，名字不加黑条，字体为 Barlow。验证文字只是动画内容，不检查身份。

生成命令（依赖 Pillow 12.3.0）：

```sh
python scripts/build_loading.py
```

`config.json` 可修改 `profile_name`、`subtitle`（最多 24 个可打印 ASCII 字符）、画布大小（保持 4:1）、`fps`（10–60）和 `duration_ms`（11000–20000，且不短于动作所需的约 12.9 秒）。默认输出目录为 `assets/`，可用 `--output-dir` 覆盖。每个主题的整段动画共用一张 256 色调色板，主题色及其抗锯齿过渡预先保留，体积约为同等 RGB APNG 的三分之一。

## 来源与许可

- 时间轴与轨迹来自网站仓库 [siruimei07/siruimei07.github.io](https://github.com/siruimei07/siruimei07.github.io/tree/22cb96903d5d554c342073a8f8d30527ff1ca057/src/boot)，固定修订 `22cb96903d5d554c342073a8f8d30527ff1ca057`；测量数据移植在 `scripts/boot_tracks.py`，`scripts/test_boot_tracks.py` 用网站上算出的数值核对插值。
- 网站的轨迹改编自 [LBEILC/RhineLabUI](https://github.com/LBEILC/RhineLabUI/tree/12cc5e4013acb9408f753ff71de6b8492299b7c8)（固定修订 `12cc5e4013acb9408f753ff71de6b8492299b7c8`）。代码版权与 MIT 许可见 [RHINELAB-LICENSE.txt](RHINELAB-LICENSE.txt)；原作名称、标志与视觉设计的权利归原权利人所有。
- 字体见 [../fonts/README.md](../fonts/README.md)；[provenance.json](provenance.json) 记录上述来源与修订。

原视频不随仓库分发；原有插画素材不参与动画生成。

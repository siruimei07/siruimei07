# 顶部开场动画

Profile 最上方的面板复刻[个人网站](https://siruimei07.github.io/)的开场，让 GitHub 主页与网站读起来是同一份档案。它是 GitHub README 可以显示的 APNG，无需 JavaScript：浅色、深色版本各播放一次，约 13 秒后停在最终画面；启用系统「减少动态效果」时直接显示这张静态画面。

## 流程

与网站 `src/boot/` 的开场一致，沿用网站逐帧测得的轨迹（莱茵生命特别映像的 25 fps 帧号），只把等待的停顿压缩为 4 倍速，让整段适合在 README 里看完：

1. 浅灰白纸面与两条模糊的 DNA 双螺旋上，`ACCESS PERMISSION REQUIRED` 不规则地逐字打出。
2. ∞± 标志沿一条连续轮廓画出，加减号弹出、加号转过四分之一圈，下方打出 `RHINE LAB LLC.`。
3. 标志左移，左上角 `SIRUI MEI / SYNTHESIZE INFORMATION / ANALYSIS OS` 三行错开滑入，右下 `POWERED BY RHINE LAB` 逐段显现。
4. `ID CONFIRMED : VISITOR` → `REQUEST RECEIVED` → `START PROCESSING...`（标志缺口随之移动，末尾短暂缺字）。
5. `PERMISSION AUTHORIZED`：黑白圆环从画面外收拢、字距收紧，中心图形接替文字。
6. 黑白闪切后出现 `WELCOME TO / SIRUI MEI / PERSONAL DATABASE`，名字上扫过黑条。
7. **README 专属的最终画面**：左侧是网站总览的身份区（∞ 标签、`UNDERGRADUATE / UNIVERSITY OF TORONTO`、`STATISTICS · ECONOMICS · QUANT`），右侧是橙色页签点与 `PRSN-001 / PERSONAL INFORMATION LOADED`，左下 `PERSONNEL SECTION`，底部是网站的中文字幕「欢迎访问 Sirui Mei 的个人资料档案」。

验证与访问提示只是动画内容，不检查身份。README 中的图片无法交互，所以没有网站的跳过按钮与退场。

## 生成

```sh
python -m pip install Pillow==12.3.0
python scripts/build_loading.py
```

输出 `assets/loading-light.png`、`assets/loading-dark.png`（动画）与 `assets/loading-static-light.png`、`assets/loading-static-dark.png`（最终画面）。`--config`、`--output-dir` 可指定其他设置与输出目录。为控制体积，每个主题的整段动画共用一张 256 色调色板，主题色及其抗锯齿过渡预先保留，因此橙色点与细线不会变色；体积约为同等 RGB APNG 的三分之一。

## 设置

`config.json`：

| 键 | 说明 |
| --- | --- |
| `width`、`height` | 输出尺寸，保持 4:1（640–1920 宽）；画面按 1280 × 320 设计后缩放 |
| `fps` | 10–60，默认 60 |
| `duration_ms` | 11000–20000，且不能短于动作所需时间（约 13.3 秒），其余时间停在最终画面 |
| `profile_name`、`subtitle` | 欢迎卡片上的名字与 `PERSONAL DATABASE` |
| `tagline` | 左上角第二行 `SYNTHESIZE INFORMATION` |
| `rank`、`affiliation`、`focus` | 最终画面的身份区；`focus` 为 1–4 个领域，以 ` · ` 连接 |
| `code` | 右侧档案编号 |
| `captions` | 四句中文字幕，依次对应访问、身份确认、核验通过与欢迎；只能使用字体子集里的字，缺字时生成脚本会报错 |

英文字段限可打印 ASCII。

## 来源与许可

- 时间轴、轨迹、几何、文案与配色来自网站仓库 [siruimei07/siruimei07.github.io](https://github.com/siruimei07/siruimei07.github.io/tree/22cb96903d5d554c342073a8f8d30527ff1ca057/src/boot)，固定修订 `22cb96903d5d554c342073a8f8d30527ff1ca057`；测量数据移植在 `scripts/boot_tracks.py`，`scripts/test_boot_tracks.py` 用网站上算出的数值核对插值。
- 网站的轨迹改编自 [LBEILC/RhineLabUI](https://github.com/LBEILC/RhineLabUI/tree/12cc5e4013acb9408f753ff71de6b8492299b7c8)（固定修订 `12cc5e4013acb9408f753ff71de6b8492299b7c8`）。代码版权与 MIT 许可见 [RHINELAB-LICENSE.txt](RHINELAB-LICENSE.txt)；原作名称、标志与视觉设计的权利归原权利人所有。
- 字体（Montserrat、JetBrains Mono、Noto Sans SC 子集）见 [../fonts/README.md](../fonts/README.md)。
- [provenance.json](provenance.json) 记录上述来源与修订。

原视频不随仓库分发；横幅插画不参与动画生成。

# 横幅素材

把喜欢的图片放进 `banners/originals/`，提交并推送到 GitHub 后，横幅工作流会自动重新生成。支持 PNG、JPG、JPEG、WebP；不同图片请使用不同的文件名（不含扩展名也不能重复）。

当前素材：

| 文件 | 画面 |
| --- | --- |
| `47_i13_1.png` | 金色麦田 |
| `60_i09.png` | 灰色荒原与石碑 |
| `61_i21.png` | 绿色花海 |

原图保留不变。生成脚本裁成约 3:1，并把下半部分逐渐变为透明，让横幅融入 GitHub 浅色或深色背景。当前三张图只裁切和改变透明度，RGB 像素完全保留。不会调用 Imagegen 或重绘画面。

## 切换方式

`banners/config.json` 中的 `selection` 控制默认选择：

- `"slideshow"`（默认）：在页面内每 12 秒自动切换一张，循环播放。先显示 `default` 指定的图片，再按文件名顺序显示其他图片。
- `"auto"`：按 UTC 日期每天选择一张静态图片，文件名排序决定顺序。同一天重复运行会选择同一张。
- `"default"`：固定使用 `default` 指定的图片，初始为 `60_i09.png`。
- `"47_i13_1.png"` 等原始文件名：固定使用指定图片。

页面轮播使用支持完整透明度的 APNG 图片，不依赖 JavaScript，也没有点击切换按钮。启用系统「减少动态效果」时，主页使用静态横幅。可修改 `interval_ms` 调整每张图的停留时间，`12000` 表示 12 秒。

手动运行 GitHub 工作流时可填写 `slideshow`、`auto`、`default` 或完整文件名；该选择会保存到配置中，后续运行也会继续使用。留空则保持当前设置。要恢复页面内轮播，填写 `slideshow`。

## 调整裁切

默认以原图中心裁成约 3:1。1600 × 900 的图片会生成 1600 × 534 横幅。每张静态裁切保留原始分辨率；轮播需要统一画布，新增不同尺寸的图片会按比例缩放至不超过 1600 × 534 的共同画布，不拉伸。

在 `images` 中按完整文件名设置 `crop_y`（竖直位置）或 `crop_x`（水平位置）：

```json
"new-picture.jpg": { "crop_y": 0.5 }
```

- 小数 `0.0` 到 `1.0` 表示在可移动范围内的位置：`0.0` 靠上/左，`0.5` 居中，`1.0` 靠下/右。
- 整数表示从原图上方/左侧开始裁切的像素数。例如 `250` 表示距离上边缘 250 像素；`1` 则是 1 像素。
- 不写配置的新图片会自动居中裁切。已附带的三张图已单独调整位置。

## 本地生成

先安装 Python 和 Pillow，然后在仓库根目录运行：

```bash
python -m pip install Pillow
python scripts/build_banner.py
python scripts/build_banner.py --select slideshow --save-selection
python scripts/build_banner.py --select 60_i09.png
python scripts/build_banner.py --select 60_i09.png --save-selection
python scripts/build_banner.py --select auto --date 2026-10-07
```

每张静态横幅保存在 `assets/banners/`；当前横幅（默认是 APNG 轮播）保存在 `assets/banner.png`，供主页引用。`assets/banner-static.png` 是减少动态效果时使用的静态版本。

本地命令只有加上 `--save-selection` 才会保存选择；不加时只生成本次横幅。

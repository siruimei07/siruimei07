# 分区标题与按钮

README 中的分区标题和链接按钮沿用[个人网站](https://siruimei07.github.io/)的组件，生成为透明背景的 PNG（按 4 倍绘制、2 倍保存），浅色、深色主题各一张，融入 GitHub 的页面背景：

| 图片 | 网站对应的组件 |
| --- | --- |
| `header-*.png` | 总览上的标注：Γ 角标、带长尾的黑色 `SECTION 0X.` 标签、粗体标题、引线与圆点；右侧是页签点与四角方块的 `FILE NUMBER` 框 |
| `button-*.png` | `.btn`：`■ 标签` 加 70% 透明度的链接文字，实心为墨色底，空心为 2 px 描边 |

## 修改

编辑 `config.json` 后运行：

```sh
python scripts/build_sections.py
```

输出在 `assets/sections/`。推送到 `main` 后工作流也会重新生成。

- `headers`：`id`（文件名，小写字母、数字与连字符）、两位数的 `number`、`title`、`description`、档案编号 `code`，以及可选的中文 `zh`。
- `buttons`：`id`、`label`、`handle`（按钮上的链接文字）与 `style`（`filled` 或 `outline`）。链接地址写在 README 的 `<a href>` 里。

英文字段限可打印 ASCII。中文只能使用 `banners/fonts/` 字体子集里的字，缺字时生成脚本会列出缺少的字并停止。按钮宽度随文字变化；改动文字后，把 README 中按钮 `<img>` 的 `width` 改为新图片宽度的一半。

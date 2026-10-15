# 分区标题

README 中的分区标题沿用[个人网站](https://siruimei07.github.io/)总览上的标注：Γ 角标、带长尾的黑色 `SECTION 0X.` 标签、粗体标题、引线与圆点，右侧是页签点与四角方块的 `FILE NUMBER` 框。图片为透明背景的 PNG（按 4 倍绘制、2 倍保存），浅色、深色主题各一张，融入 GitHub 的页面背景。

## 修改

编辑 `config.json` 后运行：

```sh
python scripts/build_sections.py
```

输出在 `assets/sections/`。推送到 `main` 后工作流也会重新生成。

每个标题包括 `id`（文件名，小写字母、数字与连字符）、两位数的 `number`、`title`、`description`、档案编号 `code`，以及可选的中文 `zh`。英文字段限可打印 ASCII；中文只能使用 `banners/fonts/` 字体子集里的字，缺字时生成脚本会列出缺少的字并停止。

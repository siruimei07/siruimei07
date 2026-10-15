# 字体

Profile 中生成的图片使用以下字体，随仓库保存，生成时不依赖本机字体或外部字体服务。

| 文件 | 用途 | 来源 |
| --- | --- | --- |
| `Barlow-Regular.ttf`、`Barlow-SemiBold.ttf` | 顶部开场动画 | [google/fonts](https://github.com/google/fonts/tree/bd8f81ddb5c74d5c8897b36ad88b440266245103/ofl/barlow) |
| `Montserrat[wght].ttf` | 分区标题与统计卡片（网站的 `--f-latin`） | [google/fonts](https://github.com/google/fonts/tree/bd8f81ddb5c74d5c8897b36ad88b440266245103/ofl/montserrat) |
| `JetBrainsMono[wght].ttf` | 统计卡片中的编号与时间（网站的 `--f-mono`） | [google/fonts](https://github.com/google/fonts/tree/bd8f81ddb5c74d5c8897b36ad88b440266245103/ofl/jetbrainsmono) |
| `noto-sans-sc-500.woff2` | 中文 | 网站仓库 [`src/fonts/`](https://github.com/siruimei07/siruimei07.github.io/tree/22cb96903d5d554c342073a8f8d30527ff1ca057/src/fonts) 的 Noto Sans SC 子集 |

Barlow 与两款可变字体固定在 google/fonts 修订 `bd8f81ddb5c74d5c8897b36ad88b440266245103`，中文子集固定在网站修订 `22cb96903d5d554c342073a8f8d30527ff1ca057`；[provenance.json](provenance.json) 记录每个文件的来源路径与 SHA-256，测试会逐一核对。

中文字体只包含网站用到的字。分区标题或统计卡片里写了子集之外的汉字时，生成脚本会列出缺少的字并停止，而不是画出空框；这时换一种说法，或在网站仓库重新生成子集后再复制过来。

四款字体均以 SIL Open Font License 1.1 授权：[OFL-Barlow.txt](OFL-Barlow.txt)、[OFL-Montserrat.txt](OFL-Montserrat.txt)、[OFL-JetBrainsMono.txt](OFL-JetBrainsMono.txt)、[OFL-NotoSansSC.txt](OFL-NotoSansSC.txt)。

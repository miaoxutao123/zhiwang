# 知网文章爬虫

使用 DrissionPage 开发的知网（CNKI）文章爬虫，支持自动搜索并抓取文章的摘要、关键词、DOI等公开信息。

## 功能特点

- ✅ 无头/有头模式切换
- ✅ 多种排序方式（相关度、被引量、下载量、发表时间）
- ✅ 反爬检测和自动停止
- ✅ **自动下载 Chromium（国内镜像源）**
- ✅ 支持保存为 JSON/CSV 格式

## 安装

```bash
pip install -r requirements.txt
```

## 浏览器配置

首次使用时，如果未检测到Chrome/Chromium浏览器，会自动从国内镜像源下载到项目目录：

```
zhiwang/
└── browsers/
    └── chromium/
        └── chrome.exe  (Windows)
```

**手动下载浏览器：**
```bash
python -m cnki.browser
```

**检查浏览器状态：**
```bash
python -m cnki.browser --check
```

**镜像源：**
- npmmirror（淘宝镜像）：`https://registry.npmmirror.com/-/binary/chromium-browser-snapshots`
- ghproxy（GitHub加速）：备用源

## 快速开始

```python
from cnki import search_cnki

# 基本搜索
results = search_cnki("深度学习")

# 按被引量排序
results = search_cnki("机器学习", max_results=20, sort_order="cited")

# 指定返回字段
results = search_cnki(
    "神经网络",
    fields=["title", "abstract", "cite_count"],
)
```

## 命令行使用

```bash
python -m cnki.api "深度学习" -n 10 -s cited -o result.json
```

## API 参数

```python
search_cnki(
    keyword: str,           # 搜索关键词
    max_results: int = 10,  # 最大结果数
    sort_order: str = "relevance",  # 排序: relevance/date/cited/download
    headless: bool = True,  # 无头模式
    fields: list = None,    # 返回字段
    get_details: bool = True,  # 获取详情页
)
```

## 项目结构

```
zhiwang/
├── cnki/                    # 核心包
│   ├── __init__.py          # 包入口
│   ├── api.py               # API封装
│   ├── browser.py           # 浏览器工具
│   ├── crawler.py           # 基础版爬虫
│   └── crawler_headless.py  # 高级版爬虫
├── example.py               # 使用示例
├── requirements.txt         # 依赖
└── README.md                # 文档
```

## 抓取字段

| 字段 | 说明 |
|------|------|
| title | 标题 |
| author | 作者 |
| abstract | 摘要 |
| keywords | 关键词 |
| doi | DOI |
| cite_count | 被引量 |
| download_count | 下载量 |
| source | 来源 |
| pub_date | 发表日期 |

## 免责声明

本工具仅供学习和研究使用，请遵守知网的使用条款和相关法律法规。
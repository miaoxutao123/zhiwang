# 知网文章爬虫

使用 DrissionPage 开发的知网（CNKI）文章爬虫，支持自动搜索并抓取文章的摘要、关键词、DOI等公开信息，并支持多源智能下载PDF。

## 功能特点

- ✅ 无头/有头模式切换
- ✅ 多种排序方式（相关度、被引量、下载量、发表时间）
- ✅ 反爬检测和自动停止
- ✅ **自动下载 Chromium（国内镜像源）**
- ✅ 支持保存为 JSON/CSV 格式
- ✅ **多源智能下载PDF（Sci-Hub、Anna's Archive、Google Scholar）**

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

### 搜索文章

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

### 下载论文

```python
from cnki import search_cnki, download_paper, download_by_doi, download_by_title

# 1. 搜索并下载（自动尝试所有可用源）
results = search_cnki("深度学习", max_results=5)
for article in results:
    result = download_paper(article)
    if result.success:
        print(f"✓ 下载成功: {result.filepath}")

# 2. 通过DOI下载（最可靠，适用于有DOI的期刊论文）
result = download_by_doi("10.1038/nature12373")

# 3. 通过标题下载
result = download_by_title("深度学习研究综述")

# 4. 指定下载源顺序
result = download_paper(article, sources=["scihub", "annas_archive", "google_scholar"])
```

## 下载源说明

| 来源 | 适用场景 | 成功率 |
|------|----------|--------|
| **CNKI** | 知网论文 | 需登录/机构IP |
| **Sci-Hub (DOI)** | 有DOI的期刊论文 | ⭐⭐⭐⭐⭐ |
| **Sci-Hub (标题)** | 英文论文 | ⭐⭐⭐ |
| **Anna's Archive** | 中英文论文/书籍 | ⭐⭐⭐ |
| **Google Scholar** | 作者主页、机构库PDF | ⭐⭐⭐⭐ |

**智能下载优先级：** CNKI → Sci-Hub(DOI) → Sci-Hub(标题) → Anna's Archive → Google Scholar

## 命令行使用

```bash
# 搜索
python -m cnki.api search "深度学习" -n 10 -s cited -o result.json

# 下载（通过DOI）
python -m cnki.api download --doi "10.1038/nature12373"

# 下载（通过标题）
python -m cnki.api download --title "深度学习研究综述"

# 搜索并下载
python -m cnki.api download --keyword "深度学习" -n 5
```

## API 参数

### search_cnki

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

### download_paper

```python
download_paper(
    article: dict,          # 文章信息（包含title, doi, url等）
    save_dir: str = "./downloads",  # 保存目录
    sources: list = None,   # 下载源顺序，默认尝试所有
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
│   ├── crawler_headless.py  # 高级版爬虫
│   └── downloader.py        # 论文下载器（多源）
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

## 下载结果

| 字段 | 说明 |
|------|------|
| success | 是否成功 |
| source | 下载来源 |
| filepath | 文件路径 |
| message | 详细信息 |

## 注意事项

1. **学位论文**：通常没有国际DOI，主要依赖Google Scholar和Anna's Archive
2. **最新论文**：可能尚未被开放获取源收录
3. **CNKI直接下载**：需要登录账号或通过机构IP访问
4. **Sci-Hub镜像**：如遇访问问题，会自动切换备用镜像

## 免责声明

本工具仅供学习和研究使用，请遵守知网的使用条款和相关法律法规。下载论文请尊重版权，仅用于个人学习研究。
# 知网文章爬虫

使用 DrissionPage 开发的知网（CNKI）文章爬虫，支持自动搜索并抓取文章的摘要、关键词、DOI等公开信息，并支持多源智能下载PDF和PDF转Markdown。

## 功能特点

- ✅ 无头/有头模式切换
- ✅ 多种排序方式（相关度、被引量、下载量、发表时间）
- ✅ 反爬检测和自动停止
- ✅ **自动下载 Chromium（国内镜像源）**
- ✅ 支持保存为 JSON/CSV 格式
- ✅ **多源智能下载PDF（Sci-Hub、Anna's Archive、Google Scholar）**
- ✅ **PDF转Markdown（支持图片、公式、表格提取）**
- ✅ **智能路由：自动检测PDF类型，选择最佳转换后端**

## 安装

```bash
pip install -r requirements.txt
```

### 安装PDF转换依赖（可选）

```bash
# ★ 推荐（低配置服务器）：DeepSeek-OCR云端API
pip install deepseek-ocr pdfplumber
# 需要设置环境变量: export DS_OCR_API_KEY="你的硅基流动API密钥"
# 新用户可在 https://cloud.siliconflow.cn 获得2000万tokens免费额度

# 高配置服务器：marker-pdf（本地运行，专为学术论文优化）
pip install marker-pdf

# 或完整安装（支持更多格式）
pip install marker-pdf[full]

# 其他备选方案
pip install pymupdf4llm    # 轻量级
pip install markitdown     # Microsoft出品
pip install docling        # IBM出品（需GPU）
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

### PDF转Markdown

```python
from cnki import convert_pdf_to_markdown, smart_convert_pdf, PdfConverter, ConversionBackend
import os

# ============ ⭐ 最推荐：智能转换（自动选择最佳后端） ============

# 智能转换会自动检测PDF类型并选择最佳后端：
# - 文本PDF → pdfplumber（低资源，速度快）
# - 扫描件/图片PDF → deepseek_ocr（云端OCR）
# - 乱码PDF → deepseek_ocr（修复编码问题）

result = smart_convert_pdf("paper.pdf")
if result.success:
    print(f"✓ 转换成功: {result.markdown_path}")
    print(f"  PDF类型: {result.pdf_type}")       # text_pdf / scanned_pdf / garbled_text
    print(f"  使用后端: {result.backend_used}")   # pdfplumber / deepseek_ocr
    print(f"  图片数量: {result.image_count}")

# 智能转换（指定API密钥用于扫描件识别）
result = smart_convert_pdf(
    "scanned_paper.pdf",
    api_key="你的硅基流动API密钥",  # 或设置环境变量 SILICONFLOW_API_KEY
    output_dir="./output",
)

# ============ 推荐：DeepSeek-OCR云端API（适合2c2g等低配置服务器） ============

# 设置API密钥（硅基流动）
os.environ["DS_OCR_API_KEY"] = "你的API密钥"

# 使用DeepSeek-OCR转换
result = convert_pdf_to_markdown("paper.pdf", backend="deepseek_ocr")
if result.success:
    print(f"✓ Markdown: {result.markdown_path}")
    print(f"  图片数量: {result.image_count}")

# 高级用法：自定义DeepSeek-OCR参数
converter = PdfConverter(
    backend=ConversionBackend.DEEPSEEK_OCR,
    api_key="你的API密钥",
    # api_base_url="https://api.siliconflow.cn/v1/chat/completions",  # 默认
    extract_images=True,  # 同时提取论文图片
)
result = converter.convert("paper.pdf", output_dir="./output")

# ============ 其他转换方式 ============

# 1. 简单转换（使用pdfplumber，纯本地，低资源）
result = convert_pdf_to_markdown("paper.pdf", backend="pdfplumber")

# 2. 高质量转换（使用marker-pdf，需要高配置）
result = convert_pdf_to_markdown("paper.pdf", backend="marker")

# 3. 指定输出目录
result = convert_pdf_to_markdown(
    "paper.pdf",
    output_dir="./output",
    extract_images=True,
)

# 4. 高级用法：使用LLM增强转换质量
converter = PdfConverter(
    backend=ConversionBackend.LLM_API,
    api_key="你的智谱API密钥",  # 支持GLM-4V-Flash（免费）
)
result = converter.convert("paper.pdf")

# 5. 批量转换
converter = PdfConverter(backend=ConversionBackend.DEEPSEEK_OCR)
results = converter.convert_batch(
    ["paper1.pdf", "paper2.pdf", "paper3.pdf"],
    output_dir="./output",
)

# 6. 后处理优化
from cnki import post_process_markdown
post_process_markdown(
    "output/paper.md",
    fix_equations=True,   # 修复数学公式格式
    fix_tables=True,      # 修复表格格式
    add_toc=True,         # 添加目录
)
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

## 转换后端说明

| 后端 | 特点 | 适用场景 | 资源需求 |
|------|------|----------|----------|
| **smart** | ⭐ **智能路由**，自动检测PDF类型并选择最佳后端 | **所有场景** | 自适应 |
| **deepseek_ocr** | DeepSeek-OCR云端API，高精度，支持中英文 | 扫描件、图片PDF | 云端（需API密钥） |
| **pdfplumber** | 纯Python，易安装，低资源 | 文本PDF、纯本地 | 低 |
| **llm_api** | 智谱GLM-4V-Flash（免费）或GPT-4V | 灵活，可免费使用 | 云端（需API密钥） |
| **marker-pdf** | 专为学术论文优化，支持图片/公式/表格 | 高质量学术论文 | 高（需GPU） |
| **docling** | IBM出品，学术论文解析能力强 | 高质量学术论文 | 高（需GPU） |
| **pymupdf4llm** | 轻量级，速度快 | 简单文档 | 低 |
| **markitdown** | Microsoft出品，易用 | 通用文档（暂不支持图片） | 低 |

### 智能路由说明

`smart_convert_pdf()` 函数会自动检测PDF类型并选择最佳后端：

```
PDF检测流程:
┌──────────────┐
│   输入PDF    │
└──────┬───────┘
       ▼
┌──────────────┐     无文本层      ┌──────────────┐
│ 检测文本层   │ ─────────────────▶│ 扫描件PDF    │
└──────┬───────┘                   └──────┬───────┘
       │ 有文本层                          │
       ▼                                   ▼
┌──────────────┐     乱码占比>30%   ┌──────────────┐
│ 检测乱码     │ ─────────────────▶│ 乱码PDF      │
└──────┬───────┘                   └──────┬───────┘
       │ 正常文本                          │
       ▼                                   ▼
┌──────────────┐                   ┌──────────────┐
│  文本PDF     │                   │ deepseek_ocr │
└──────┬───────┘                   └──────────────┘
       │
       ▼
┌──────────────┐
│  pdfplumber  │
└──────────────┘
```

### DeepSeek-OCR 环境配置

```bash
# 1. 安装依赖
pip install deepseek-ocr pdfplumber

# 2. 设置环境变量
export DS_OCR_API_KEY="你的硅基流动API密钥"

# 可选配置
export DS_OCR_BASE_URL="https://api.siliconflow.cn/v1/chat/completions"  # 默认
export DS_OCR_MODE="free_ocr"  # free_ocr(快速) / grounding(复杂表格) / ocr_image(详细)
```

**获取API密钥**：访问 https://cloud.siliconflow.cn 注册账号，新用户可获得2000万tokens免费额度。

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

# PDF转Markdown（推荐：DeepSeek-OCR云端API）
DS_OCR_API_KEY="你的密钥" python -m cnki.converter paper.pdf -b deepseek_ocr

# 使用pdfplumber（纯本地，低资源）
python -m cnki.converter paper.pdf -b pdfplumber

# 使用marker-pdf（高配置服务器）
python -m cnki.converter paper.pdf -b marker

# 指定输出目录
python -m cnki.converter paper.pdf -o ./output

# 启用后处理
python -m cnki.converter paper.pdf --post-process --add-toc
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

### convert_pdf_to_markdown

```python
convert_pdf_to_markdown(
    pdf_path: str,          # PDF文件路径
    output_dir: str = None, # 输出目录（默认PDF所在目录）
    backend: str = "marker", # 转换后端: marker/pdfplumber/deepseek_ocr/llm_api/...
    extract_images: bool = True,  # 是否提取图片
    use_llm: bool = False,  # 是否使用LLM增强
)
```

### smart_convert_pdf

```python
smart_convert_pdf(
    pdf_path: str,          # PDF文件路径
    output_dir: str = None, # 输出目录（默认PDF所在目录）
    api_key: str = None,    # DeepSeek-OCR API密钥（环境变量SILICONFLOW_API_KEY）
    extract_images: bool = True,  # 是否提取图片
)

# 返回 ConversionResult，包含额外字段：
# - pdf_type: 检测到的PDF类型 (text_pdf/scanned_pdf/garbled_text)
# - backend_used: 实际使用的后端
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
│   ├── downloader.py        # 论文下载器（多源）
│   └── converter.py         # PDF转Markdown转换器
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

## 转换结果

| 字段 | 说明 |
|------|------|
| success | 是否成功 |
| markdown_path | Markdown文件路径 |
| markdown_content | Markdown内容 |
| images_dir | 图片目录路径 |
| image_count | 提取的图片数量 |
| metadata | 文档元数据 |
| backend_used | 实际使用的转换后端 |
| pdf_type | PDF类型（仅smart_convert_pdf返回） |

## 注意事项

1. **学位论文**：通常没有国际DOI，主要依赖Google Scholar和Anna's Archive
2. **最新论文**：可能尚未被开放获取源收录
3. **CNKI直接下载**：需要登录账号或通过机构IP访问
4. **Sci-Hub镜像**：如遇访问问题，会自动切换备用镜像
5. **PDF转换后端选择**：
   - **2c2g等低配服务器**：推荐使用 `deepseek_ocr`（云端API）或 `pdfplumber`（本地）
   - **高配置服务器/GPU**：可使用 `marker-pdf` 或 `docling` 获得更好效果
6. **DeepSeek-OCR**：需要硅基流动API密钥，新用户可获得2000万tokens免费额度
7. **LLM增强**：支持智谱GLM-4V-Flash（免费）、GPT-4V等

## 免责声明

本工具仅供学习和研究使用，请遵守知网的使用条款和相关法律法规。下载论文请尊重版权，仅用于个人学习研究。
"""知网爬虫包.

提供知网文献搜索、抓取、下载和PDF转换功能。

使用示例:
    from cnki import search_cnki, SortOrder

    # 基本搜索
    results = search_cnki("深度学习")

    # 按被引量排序
    results = search_cnki("机器学习", sort_order="cited", max_results=20)

    # 下载论文
    from cnki import download_paper, search_and_download
    
    # 通过DOI下载
    result = download_paper({"doi": "10.1000/xyz"})
    
    # 搜索并下载
    articles, downloads = search_and_download("深度学习", max_results=3)
    
    # PDF转Markdown（指定后端）
    from cnki import convert_pdf_to_markdown
    result = convert_pdf_to_markdown("paper.pdf", backend="pdfplumber")
    
    # 智能PDF转换（自动选择最佳后端）
    from cnki import smart_convert_pdf
    result = smart_convert_pdf("paper.pdf")  # 自动检测PDF类型并选择最佳后端
"""

from cnki.api import (
    ALL_FIELDS,
    SortOrder,
    download_by_doi,
    download_by_title,
    get_article_info,
    search_and_download,
    search_cnki,
    search_cnki_simple,
)
from cnki.converter import (
    ConversionBackend,
    ConversionResult,
    PdfConverter,
    convert_pdf_to_markdown,
    post_process_markdown,
    smart_convert_pdf,
)
from cnki.crawler import CNKICrawler
from cnki.crawler_headless import CNKICrawlerHeadless
from cnki.crawler_headless import SortOrder as CrawlerSortOrder
from cnki.downloader import (
    DownloadResult,
    DownloadSource,
    PaperDownloader,
    download_paper,
    download_papers,
)

__all__ = [
    # 搜索API
    "search_cnki",
    "search_cnki_simple",
    "get_article_info",
    "search_and_download",
    "SortOrder",
    "ALL_FIELDS",
    # 下载API
    "download_paper",
    "download_papers",
    "download_by_doi",
    "download_by_title",
    "DownloadResult",
    "DownloadSource",
    "PaperDownloader",
    # 转换API
    "convert_pdf_to_markdown",
    "smart_convert_pdf",
    "post_process_markdown",
    "ConversionResult",
    "ConversionBackend",
    "PdfConverter",
    # 爬虫类
    "CNKICrawler",
    "CNKICrawlerHeadless",
    "CrawlerSortOrder",
]

__version__ = "1.3.0"
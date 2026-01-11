"""知网爬虫包.

提供知网文献搜索、抓取和下载功能。

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
    # 爬虫类
    "CNKICrawler",
    "CNKICrawlerHeadless",
    "CrawlerSortOrder",
]

__version__ = "1.1.0"
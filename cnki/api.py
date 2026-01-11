#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知网爬虫API封装.

提供简单易用的函数接口，可自定义参数搜索知网文献，并支持论文下载。
"""

from __future__ import annotations

import argparse
import json
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from cnki.downloader import (
    DownloadResult,
    DownloadSource,
    PaperDownloader,
    download_paper,
    download_papers,
)


class SortOrder(Enum):
    """排序方式枚举."""

    RELEVANCE = "relevance"
    DATE = "date"
    CITED = "cited"
    DOWNLOAD = "download"


ALL_FIELDS: list[str] = [
    "title", "authors", "source", "date", "cite_count", "download_count",
    "abstract", "keywords", "doi", "url", "dbcode", "dbname", "filename",
    "fund", "first_author", "institution",
]


def search_cnki(
    keyword: str,
    max_results: int = 10,
    sort_order: str | SortOrder = SortOrder.RELEVANCE,
    headless: bool = True,
    fields: Sequence[str] | None = None,
    get_details: bool = True,
    browser_path: str | None = None,
) -> list[dict[str, Any]]:
    """搜索知网文献."""
    from cnki.crawler_headless import CNKICrawlerHeadless
    from cnki.crawler_headless import SortOrder as CrawlerSortOrder

    if isinstance(sort_order, str):
        sort_map = {
            "relevance": CrawlerSortOrder.RELEVANCE,
            "date": CrawlerSortOrder.DATE,
            "cited": CrawlerSortOrder.CITED,
            "download": CrawlerSortOrder.DOWNLOAD,
        }
        crawler_sort = sort_map.get(sort_order.lower(), CrawlerSortOrder.RELEVANCE)
    elif isinstance(sort_order, SortOrder):
        sort_map = {
            SortOrder.RELEVANCE: CrawlerSortOrder.RELEVANCE,
            SortOrder.DATE: CrawlerSortOrder.DATE,
            SortOrder.CITED: CrawlerSortOrder.CITED,
            SortOrder.DOWNLOAD: CrawlerSortOrder.DOWNLOAD,
        }
        crawler_sort = sort_map.get(sort_order, CrawlerSortOrder.RELEVANCE)
    else:
        crawler_sort = CrawlerSortOrder.RELEVANCE

    crawler = CNKICrawlerHeadless(headless=headless, browser_path=browser_path)

    try:
        if get_details:
            results = crawler.search_and_crawl(
                keyword=keyword,
                max_results=max_results,
                sort_order=crawler_sort,
                get_details=True,
            )
        else:
            results = crawler.search(
                keyword=keyword,
                max_results=max_results,
                sort_order=crawler_sort,
            )

        if fields:
            return [{field: article.get(field) for field in fields} for article in results]
        return results
    finally:
        crawler.close()


def search_cnki_simple(
    keyword: str,
    max_results: int = 10,
    sort_by: str = "relevance",
) -> list[dict[str, Any]]:
    """简化版搜索函数."""
    return search_cnki(keyword=keyword, max_results=max_results, sort_order=sort_by)


def get_article_info(
    keyword: str,
    index: int = 0,
    headless: bool = True,
) -> dict[str, Any] | None:
    """获取单篇文章的详细信息."""
    results = search_cnki(keyword=keyword, max_results=index + 1, headless=headless)
    return results[index] if len(results) > index else None


# ==================== 下载功能 API ====================


def search_and_download(
    keyword: str,
    max_results: int = 5,
    download_dir: str | None = None,
    sources: list[str] | None = None,
    headless: bool = True,
) -> tuple[list[dict[str, Any]], list[DownloadResult]]:
    """搜索并下载论文.
    
    Args:
        keyword: 搜索关键词
        max_results: 最大结果数
        download_dir: 下载目录
        sources: 下载源列表，如 ["scihub", "annas_archive", "google_scholar"]
        headless: 是否使用无头模式
        
    Returns:
        (搜索结果列表, 下载结果列表)
        
    Example:
        >>> articles, downloads = search_and_download("深度学习", max_results=3)
        >>> for article, result in zip(articles, downloads):
        ...     if result.success:
        ...         print(f"✓ {article['title'][:30]}... -> {result.filepath}")
        ...     else:
        ...         print(f"✗ {article['title'][:30]}... : {result.message}")
    """
    # 搜索论文
    articles = search_cnki(
        keyword=keyword,
        max_results=max_results,
        headless=headless,
        get_details=True,  # 需要DOI
    )

    if not articles:
        return [], []

    # 下载论文
    download_results = download_papers(
        articles=articles,
        download_dir=download_dir,
        headless=headless,
        sources=sources,
    )

    return articles, download_results


def download_by_doi(
    doi: str,
    filename: str | None = None,
    download_dir: str | None = None,
    headless: bool = True,
) -> DownloadResult:
    """通过DOI下载论文（使用Sci-Hub）.
    
    Args:
        doi: 论文DOI，如 "10.1000/xyz"
        filename: 保存的文件名（不含扩展名）
        download_dir: 下载目录
        headless: 是否使用无头模式
        
    Returns:
        DownloadResult对象
        
    Example:
        >>> result = download_by_doi("10.1038/nature12373")
        >>> if result.success:
        ...     print(f"下载成功: {result.filepath}")
    """
    article = {"doi": doi}
    if filename:
        article["title"] = filename

    return download_paper(
        article=article,
        download_dir=download_dir,
        headless=headless,
        sources=["scihub"],
    )


def download_by_title(
    title: str,
    download_dir: str | None = None,
    sources: list[str] | None = None,
    headless: bool = True,
) -> DownloadResult:
    """通过标题搜索并下载论文.
    
    Args:
        title: 论文标题
        download_dir: 下载目录
        sources: 下载源列表，默认 ["annas_archive", "google_scholar"]
        headless: 是否使用无头模式
        
    Returns:
        DownloadResult对象
        
    Example:
        >>> result = download_by_title("Attention Is All You Need")
        >>> if result.success:
        ...     print(f"下载成功: {result.filepath}")
    """
    if sources is None:
        sources = ["annas_archive", "google_scholar"]

    return download_paper(
        article={"title": title},
        download_dir=download_dir,
        headless=headless,
        sources=sources,
    )


def main() -> None:
    """命令行入口函数."""
    parser = argparse.ArgumentParser(description="知网文献搜索与下载")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 搜索命令
    search_parser = subparsers.add_parser("search", help="搜索文献")
    search_parser.add_argument("keyword", help="搜索关键词")
    search_parser.add_argument("-n", "--max-results", type=int, default=10)
    search_parser.add_argument("-s", "--sort", choices=["relevance", "date", "cited", "download"], default="relevance")
    search_parser.add_argument("--headed", action="store_true")
    search_parser.add_argument("-f", "--fields", nargs="+")
    search_parser.add_argument("--no-details", action="store_true")
    search_parser.add_argument("-o", "--output")

    # 下载命令
    download_parser = subparsers.add_parser("download", help="下载论文")
    download_parser.add_argument("--doi", help="论文DOI")
    download_parser.add_argument("--title", help="论文标题")
    download_parser.add_argument("--keyword", help="搜索关键词并下载")
    download_parser.add_argument("-n", "--max-results", type=int, default=5)
    download_parser.add_argument("--source", choices=["scihub", "annas_archive", "google_scholar"], action="append")
    download_parser.add_argument("-o", "--output", default="downloads", help="下载目录")
    download_parser.add_argument("--headed", action="store_true")

    args = parser.parse_args()

    if args.command == "search" or args.command is None:
        # 兼容旧的用法
        if args.command is None:
            # 如果没有子命令，检查是否有位置参数
            if len(parser.parse_args().__dict__) <= 1:
                parser.print_help()
                return
            args = parser.parse_args()
            if not hasattr(args, "keyword"):
                parser.print_help()
                return

        print(f"搜索: {args.keyword} | 数量: {args.max_results} | 排序: {args.sort}")

        results = search_cnki(
            keyword=args.keyword,
            max_results=args.max_results,
            sort_order=args.sort,
            headless=not args.headed,
            fields=args.fields if hasattr(args, "fields") else None,
            get_details=not args.no_details if hasattr(args, "no_details") else True,
        )

        print(f"\n找到 {len(results)} 条结果:\n")
        for i, article in enumerate(results, 1):
            print(f"{i}. {article.get('title', 'N/A')}")
            if article.get("cite_count"):
                print(f"   被引: {article['cite_count']}")
            if article.get("doi"):
                print(f"   DOI: {article['doi']}")

        if hasattr(args, "output") and args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"已保存: {args.output}")

    elif args.command == "download":
        if args.keyword:
            # 搜索并下载
            print(f"搜索并下载: {args.keyword} | 数量: {args.max_results}")
            articles, downloads = search_and_download(
                keyword=args.keyword,
                max_results=args.max_results,
                download_dir=args.output,
                sources=args.source,
                headless=not args.headed,
            )

            print(f"\n下载结果:")
            for article, result in zip(articles, downloads):
                status = "✓" if result.success else "✗"
                title = article.get("title", "未知")[:40]
                if result.success:
                    print(f"  {status} {title}... -> {result.filepath}")
                else:
                    print(f"  {status} {title}... : {result.message}")

        elif args.doi:
            # 通过DOI下载
            result = download_by_doi(
                doi=args.doi,
                download_dir=args.output,
                headless=not args.headed,
            )
            if result.success:
                print(f"✓ 下载成功: {result.filepath}")
            else:
                print(f"✗ 下载失败: {result.message}")

        elif args.title:
            # 通过标题下载
            result = download_by_title(
                title=args.title,
                download_dir=args.output,
                sources=args.source,
                headless=not args.headed,
            )
            if result.success:
                print(f"✓ 下载成功: {result.filepath}")
            else:
                print(f"✗ 下载失败: {result.message}")

        else:
            download_parser.print_help()


if __name__ == "__main__":
    main()
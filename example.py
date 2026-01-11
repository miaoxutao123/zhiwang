#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知网爬虫使用示例.

包含搜索和下载功能的完整示例。
"""

from cnki import (
    search_cnki,
    SortOrder,
    download_paper,
    download_papers,
    download_by_doi,
    download_by_title,
    search_and_download,
    DownloadSource,
)


def search_examples():
    """搜索功能示例."""
    print("=" * 60)
    print("搜索功能示例")
    print("=" * 60)

    # 示例1: 基本搜索
    print("\n示例1: 基本搜索")
    results = search_cnki("深度学习", max_results=5)
    for r in results:
        print(f"  - {r['title'][:40]}... (被引:{r.get('cite_count', 0)})")

    # 示例2: 按被引量排序
    print("\n示例2: 按被引量排序")
    results = search_cnki("机器学习", max_results=5, sort_order="cited")
    for r in results:
        print(f"  - {r['title'][:40]}... (被引:{r.get('cite_count', 0)})")

    # 示例3: 指定返回字段
    print("\n示例3: 指定返回字段")
    results = search_cnki(
        "神经网络",
        max_results=3,
        fields=["title", "abstract", "cite_count", "doi"],
    )
    for r in results:
        print(f"  - {r['title'][:40]}...")
        if r.get("doi"):
            print(f"    DOI: {r['doi']}")
        if r.get("abstract"):
            print(f"    摘要: {r['abstract'][:50]}...")

    return results


def download_examples():
    """下载功能示例."""
    print("\n" + "=" * 60)
    print("下载功能示例")
    print("=" * 60)

    # 示例4: 通过DOI下载（使用Sci-Hub）
    print("\n示例4: 通过DOI下载")
    print("注意: 需要有效的DOI，以下为演示代码")
    print("""
    # 通过DOI下载
    result = download_by_doi("10.1038/nature12373")
    if result.success:
        print(f"下载成功: {result.filepath}")
    else:
        print(f"下载失败: {result.message}")
    """)

    # 示例5: 通过标题下载
    print("\n示例5: 通过标题下载")
    print("注意: 会搜索Anna's Archive和Google Scholar")
    print("""
    # 通过标题下载
    result = download_by_title("Attention Is All You Need")
    if result.success:
        print(f"下载成功: {result.filepath}")
    else:
        print(f"下载失败: {result.message}")
    """)

    # 示例6: 智能下载（自动选择下载源）
    print("\n示例6: 智能下载")
    print("""
    # 智能下载：自动尝试多个来源
    article = {
        "title": "深度学习在图像识别中的应用",
        "doi": "10.1000/example"  # 可选
    }
    result = download_paper(article)
    if result.success:
        print(f"来源: {result.source.value}")
        print(f"文件: {result.filepath}")
    """)

    # 示例7: 搜索并下载
    print("\n示例7: 搜索并下载")
    print("""
    # 搜索知网并下载找到的论文
    articles, downloads = search_and_download(
        keyword="深度学习",
        max_results=3,
        download_dir="./downloads"
    )
    
    for article, result in zip(articles, downloads):
        status = "✓" if result.success else "✗"
        print(f"{status} {article['title'][:30]}...")
        if result.success:
            print(f"   -> {result.filepath}")
    """)

    # 示例8: 批量下载
    print("\n示例8: 批量下载")
    print("""
    # 批量下载多篇论文
    articles = [
        {"title": "论文1", "doi": "10.1000/paper1"},
        {"title": "论文2", "doi": "10.1000/paper2"},
        {"title": "论文3"},  # 没有DOI，会使用其他来源
    ]
    
    results = download_papers(
        articles=articles,
        download_dir="./downloads",
        sources=["scihub", "annas_archive"]  # 指定下载源顺序
    )
    
    success_count = sum(1 for r in results if r.success)
    print(f"成功下载: {success_count}/{len(results)}")
    """)

    # 示例9: 使用PaperDownloader类
    print("\n示例9: 使用PaperDownloader类（更多控制）")
    print("""
    from cnki import PaperDownloader, DownloadSource
    
    # 创建下载器
    downloader = PaperDownloader(
        headless=True,
        download_dir="./papers",
        request_delay=3.0,  # 请求间隔
    )
    
    try:
        # 使用特定来源下载
        result = downloader.download_from_scihub("10.1038/nature12373")
        
        # 或者使用Anna's Archive
        result = downloader.download_from_annas_archive("论文标题")
        
        # 或者使用Google Scholar
        result = downloader.download_from_google_scholar("Paper Title")
        
        # 智能下载
        result = downloader.smart_download(
            article={"title": "...", "doi": "..."},
            sources=[DownloadSource.SCIHUB, DownloadSource.ANNAS_ARCHIVE]
        )
    finally:
        downloader.close()
    """)


def interactive_download_demo():
    """交互式下载演示（实际执行）."""
    print("\n" + "=" * 60)
    print("交互式下载演示")
    print("=" * 60)
    
    choice = input("\n是否执行实际下载测试? (y/N): ").strip().lower()
    if choice != "y":
        print("跳过下载测试")
        return

    # 先搜索获取一些论文
    print("\n正在搜索论文...")
    results = search_cnki("机器学习", max_results=2, get_details=True)

    if not results:
        print("未找到论文")
        return

    print(f"\n找到 {len(results)} 篇论文:")
    for i, r in enumerate(results):
        print(f"  {i+1}. {r['title'][:50]}...")
        if r.get("doi"):
            print(f"      DOI: {r['doi']}")

    # 选择下载
    choice = input("\n选择要下载的论文编号 (1-{}，0=跳过): ".format(len(results))).strip()
    if not choice or choice == "0":
        print("跳过下载")
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            article = results[idx]
            print(f"\n正在下载: {article['title'][:50]}...")
            
            result = download_paper(article, download_dir="./downloads")
            
            if result.success:
                print(f"\n✓ 下载成功!")
                print(f"  来源: {result.source.value if result.source else 'N/A'}")
                print(f"  文件: {result.filepath}")
            else:
                print(f"\n✗ 下载失败: {result.message}")
    except ValueError:
        print("无效的选择")


def main():
    """主函数."""
    print("=" * 60)
    print("知网爬虫完整示例")
    print("=" * 60)

    # 运行搜索示例
    search_examples()

    # 显示下载示例代码
    download_examples()

    # 可选：运行交互式下载
    interactive_download_demo()

    print("\n" + "=" * 60)
    print("示例完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
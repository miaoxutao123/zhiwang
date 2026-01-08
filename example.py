#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知网爬虫使用示例."""

from cnki import search_cnki, SortOrder


def main():
    """主函数."""
    print("=" * 60)
    print("知网爬虫示例")
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
        fields=["title", "abstract", "cite_count"],
    )
    for r in results:
        print(f"  - {r['title'][:40]}...")
        if r.get("abstract"):
            print(f"    摘要: {r['abstract'][:50]}...")


if __name__ == "__main__":
    main()
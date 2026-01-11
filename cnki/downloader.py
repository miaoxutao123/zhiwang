"""论文下载器模块.

支持多种下载源：
1. Sci-Hub - 通过DOI下载（最推荐，针对期刊论文）
2. Anna's Archive - 聚合搜索（支持中文标题）
3. Google Scholar - 寻找免费源（作者个人主页、机构库等）
"""

from __future__ import annotations

import os
import random
import re
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from DrissionPage import Chromium, ChromiumOptions

from cnki.browser import ensure_browser, find_chrome_path, setup_virtual_display


class DownloadSource(Enum):
    """下载源枚举."""

    CNKI = "cnki"  # 知网直接下载（需要登录或机构IP）
    SCIHUB = "scihub"
    SCIHUB_TITLE = "scihub_title"  # Sci-Hub标题搜索
    ANNAS_ARCHIVE = "annas_archive"
    GOOGLE_SCHOLAR = "google_scholar"


@dataclass
class DownloadResult:
    """下载结果."""

    success: bool
    source: DownloadSource | None = None
    filepath: str | None = None
    message: str = ""
    doi: str | None = None
    title: str | None = None


class PaperDownloader:
    """论文下载器类.
    
    支持通过多种来源下载论文PDF：
    - Sci-Hub: 需要DOI
    - Anna's Archive: 支持标题搜索
    - Google Scholar: 寻找免费PDF源
    """

    # Sci-Hub镜像站点（按可用性排序，可能需要更新）
    SCIHUB_MIRRORS = [
        "https://sci-hub.ren",  # 目前可用
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru",
        "https://sci-hub.shop",
        "https://sci-hub.wf",
    ]

    # Anna's Archive
    ANNAS_ARCHIVE_URL = "https://annas-archive.org"

    # Google Scholar
    GOOGLE_SCHOLAR_URL = "https://scholar.google.com"

    def __init__(
        self,
        headless: bool = True,
        browser_path: str | None = None,
        auto_download: bool = True,
        download_dir: str | None = None,
        request_delay: float = 2.0,
    ) -> None:
        """初始化下载器.
        
        Args:
            headless: 是否使用无头模式
            browser_path: 浏览器路径
            auto_download: 是否自动下载浏览器
            download_dir: PDF下载目录
            request_delay: 请求间隔（秒）
        """
        self.headless = headless
        self.request_delay = request_delay
        self.virtual_display = None

        # 设置下载目录
        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = Path("downloads")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        if headless:
            self.virtual_display = setup_virtual_display()

        self.options = ChromiumOptions()

        if browser_path:
            self.options.set_browser_path(browser_path)
        elif auto_download:
            auto_path = ensure_browser()
            if auto_path:
                print(f"使用浏览器: {auto_path}")
                self.options.set_browser_path(auto_path)
        else:
            auto_path = find_chrome_path()
            if auto_path:
                self.options.set_browser_path(auto_path)

        if headless:
            self.options.headless()
            self.options.set_argument("--disable-gpu")

        self.options.set_argument("--remote-allow-origins=*")
        self.options.set_argument("--no-sandbox")
        self.options.set_argument("--disable-dev-shm-usage")
        self.options.set_argument("--disable-blink-features=AutomationControlled")
        self.options.set_argument("--window-size=1920,1080")

        # 设置下载目录
        self.options.set_download_path(str(self.download_dir.absolute()))

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        ]
        self.options.set_argument(f"--user-agent={random.choice(user_agents)}")

        self.user_data_dir = tempfile.mkdtemp(prefix="paper_downloader_")
        self.options.set_user_data_path(self.user_data_dir)
        self.options.auto_port()

        self.browser = None
        self.page = None

    def start(self) -> bool:
        """启动浏览器."""
        try:
            print("正在启动浏览器...")
            self.browser = Chromium(self.options)
            time.sleep(2)
            self.page = self.browser.latest_tab
            if self.page:
                print("浏览器已启动")
                return True
            return False
        except Exception as e:
            print(f"启动失败: {e}")
            return False

    def close(self) -> None:
        """关闭浏览器."""
        if self.browser:
            try:
                self.browser.quit()
                print("浏览器已关闭")
            except Exception:
                pass
            finally:
                self.browser = None
                self.page = None

        if hasattr(self, "user_data_dir") and self.user_data_dir:
            import shutil
            shutil.rmtree(self.user_data_dir, ignore_errors=True)

        if self.virtual_display:
            try:
                self.virtual_display.stop()
            except Exception:
                pass

    def _sanitize_filename(self, title: str, max_length: int = 100) -> str:
        """清理文件名，移除非法字符."""
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', title)
        filename = re.sub(r'\s+', ' ', filename).strip()
        if len(filename) > max_length:
            filename = filename[:max_length]
        return filename

    def _wait_for_download(self, timeout: int = 60) -> str | None:
        """等待下载完成并返回文件路径."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查下载目录中的文件
            files = list(self.download_dir.glob("*.pdf"))
            crdownload_files = list(self.download_dir.glob("*.crdownload"))
            
            # 如果有正在下载的文件，继续等待
            if crdownload_files:
                time.sleep(1)
                continue
            
            # 如果有新的PDF文件
            if files:
                # 返回最新的文件
                newest_file = max(files, key=lambda f: f.stat().st_mtime)
                # 确保文件下载完成（大小不再变化）
                initial_size = newest_file.stat().st_size
                time.sleep(1)
                if newest_file.exists() and newest_file.stat().st_size == initial_size > 0:
                    return str(newest_file)
            
            time.sleep(1)
        
        return None

    # ==================== 知网直接下载 ====================

    def download_from_cnki(self, url: str, filename: str | None = None) -> DownloadResult:
        """从知网直接下载论文PDF.
        
        原理：将知网CAJ下载链接中的"nhdown"修改为"pdfdown"可下载PDF格式。
        注意：需要已登录知网账号或通过机构IP访问。
        
        Args:
            url: 论文详情页URL
            filename: 保存的文件名（不含扩展名）
            
        Returns:
            DownloadResult对象
        """
        if not self.page:
            if not self.start():
                return DownloadResult(
                    success=False,
                    source=DownloadSource.CNKI,
                    message="浏览器启动失败",
                )

        print(f"正在从知网下载: {url[:60]}...")

        try:
            # 访问详情页
            if url.startswith("//"):
                url = "https:" + url
            elif not url.startswith("http"):
                url = "https://kns.cnki.net" + url

            self.page.get(url)
            time.sleep(self.request_delay + random.uniform(0, 1))

            # 尝试找到下载链接
            pdf_download_url = None
            
            # 方法1: 直接查找PDF下载按钮
            pdf_btn = self.page.ele("css:a.btn-dlpdf", timeout=5)
            if pdf_btn:
                pdf_download_url = pdf_btn.attr("href")
            
            # 方法2: 查找CAJ下载链接并转换
            if not pdf_download_url:
                caj_btn = self.page.ele("css:a.btn-dlcaj", timeout=3)
                if not caj_btn:
                    caj_btn = self.page.ele("css:a[href*='nhdown']", timeout=3)
                
                if caj_btn:
                    caj_url = caj_btn.attr("href")
                    if caj_url:
                        # 关键技巧：将nhdown替换为pdfdown
                        pdf_download_url = caj_url.replace("nhdown", "pdfdown")
                        print(f"  将CAJ链接转换为PDF链接")

            # 方法3: 在页面中搜索下载链接
            if not pdf_download_url:
                page_html = self.page.html
                # 查找包含dflag=pdfdown的链接
                pdf_match = re.search(r'href=["\']([^"\']*dflag=pdfdown[^"\']*)["\']', page_html)
                if pdf_match:
                    pdf_download_url = pdf_match.group(1)
                else:
                    # 查找nhdown链接并转换
                    nh_match = re.search(r'href=["\']([^"\']*nhdown[^"\']*)["\']', page_html)
                    if nh_match:
                        pdf_download_url = nh_match.group(1).replace("nhdown", "pdfdown")

            if not pdf_download_url:
                return DownloadResult(
                    success=False,
                    source=DownloadSource.CNKI,
                    message="未找到下载链接（可能需要登录）",
                )

            # 处理相对URL
            if pdf_download_url.startswith("//"):
                pdf_download_url = "https:" + pdf_download_url
            elif pdf_download_url.startswith("/"):
                pdf_download_url = "https://kns.cnki.net" + pdf_download_url

            print(f"  下载链接: {pdf_download_url[:80]}...")

            # 下载文件
            if filename:
                save_path = self.download_dir / f"{self._sanitize_filename(filename)}.pdf"
            else:
                # 从页面获取标题
                title_elem = self.page.ele("css:.wx-tit h1", timeout=3)
                if title_elem:
                    save_path = self.download_dir / f"{self._sanitize_filename(title_elem.text[:80])}.pdf"
                else:
                    save_path = self.download_dir / f"cnki_{int(time.time())}.pdf"

            # 尝试下载
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                'Referer': url,
            }
            
            # 获取cookies从浏览器
            cookies = {}
            try:
                browser_cookies = self.page.cookies()
                for cookie in browser_cookies:
                    cookies[cookie.get('name', '')] = cookie.get('value', '')
            except Exception:
                pass

            response = requests.get(pdf_download_url, headers=headers, cookies=cookies, timeout=60, stream=True)

            if response.status_code == 200 and len(response.content) > 1000:
                content_type = response.headers.get('content-type', '')
                if 'pdf' in content_type.lower() or response.content[:4] == b'%PDF':
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"  ✓ 下载成功: {save_path}")
                    return DownloadResult(
                        success=True,
                        source=DownloadSource.CNKI,
                        filepath=str(save_path),
                        message="下载成功",
                    )
                else:
                    # 可能返回的是登录页面
                    return DownloadResult(
                        success=False,
                        source=DownloadSource.CNKI,
                        message="下载失败（可能需要登录或无权限）",
                    )
            else:
                return DownloadResult(
                    success=False,
                    source=DownloadSource.CNKI,
                    message=f"下载失败: HTTP {response.status_code}",
                )

        except Exception as e:
            return DownloadResult(
                success=False,
                source=DownloadSource.CNKI,
                message=f"下载失败: {e}",
            )

    # ==================== Sci-Hub 下载 ====================

    def download_from_scihub(self, doi: str, filename: str | None = None) -> DownloadResult:
        """通过Sci-Hub下载论文.
        
        Args:
            doi: 论文的DOI
            filename: 保存的文件名（不含扩展名）
            
        Returns:
            DownloadResult对象
        """
        if not self.page:
            if not self.start():
                return DownloadResult(
                    success=False,
                    source=DownloadSource.SCIHUB,
                    message="浏览器启动失败",
                    doi=doi,
                )

        print(f"正在通过Sci-Hub下载: {doi}")

        for mirror in self.SCIHUB_MIRRORS:
            try:
                result = self._try_scihub_mirror(mirror, doi, filename)
                if result.success:
                    return result
                time.sleep(self.request_delay)
            except Exception as e:
                print(f"  镜像 {mirror} 失败: {e}")
                continue

        return DownloadResult(
            success=False,
            source=DownloadSource.SCIHUB,
            message="所有Sci-Hub镜像均失败",
            doi=doi,
        )

    def _try_scihub_mirror(self, mirror: str, doi_or_title: str, filename: str | None, is_title: bool = False) -> DownloadResult:
        """尝试单个Sci-Hub镜像.
        
        Args:
            mirror: Sci-Hub镜像URL
            doi_or_title: DOI或论文标题
            filename: 保存的文件名
            is_title: 是否是标题搜索（而非DOI）
        """
        if is_title:
            # 标题搜索需要URL编码
            search_term = urllib.parse.quote(doi_or_title)
        else:
            search_term = doi_or_title
            
        url = f"{mirror}/{search_term}"
        print(f"  尝试镜像: {mirror}")
        
        self.page.get(url)
        time.sleep(self.request_delay + random.uniform(0, 1))

        # 检查是否找到论文（Sci-Hub会显示错误页面如果找不到）
        page_html = self.page.html
        if "article not found" in page_html.lower() or "статья не найдена" in page_html.lower():
            return DownloadResult(
                success=False,
                source=DownloadSource.SCIHUB,
                message="Sci-Hub未收录此论文",
                doi=doi_or_title if not is_title else None,
                title=doi_or_title if is_title else None,
            )

        # 检查是否有PDF iframe或直接链接
        pdf_url = None

        # 方法1: 查找embed或iframe中的PDF
        embed = self.page.ele("css:embed#pdf", timeout=5)
        if embed:
            pdf_url = embed.attr("src")
        
        if not pdf_url:
            iframe = self.page.ele("css:iframe#pdf", timeout=3)
            if iframe:
                pdf_url = iframe.attr("src")

        # 方法2: 查找直接的PDF链接
        if not pdf_url:
            pdf_link = self.page.ele("css:a[onclick*='.pdf']", timeout=3)
            if pdf_link:
                pdf_url = pdf_link.attr("href") or pdf_link.attr("onclick")
                if pdf_url and "location.href" in pdf_url:
                    match = re.search(r"location\.href='([^']+)'", pdf_url)
                    if match:
                        pdf_url = match.group(1)

        # 方法3: 在页面源码中搜索PDF URL
        if not pdf_url:
            pdf_match = re.search(r'(https?://[^"\'<>\s]+\.pdf[^"\'<>\s]*)', page_html)
            if pdf_match:
                pdf_url = pdf_match.group(1)

        if not pdf_url:
            return DownloadResult(
                success=False,
                source=DownloadSource.SCIHUB,
                message="未找到PDF链接",
                doi=doi_or_title if not is_title else None,
                title=doi_or_title if is_title else None,
            )

        # 处理相对URL
        if pdf_url.startswith("//"):
            pdf_url = "https:" + pdf_url
        elif pdf_url.startswith("/"):
            pdf_url = mirror + pdf_url

        # 清理URL（移除锚点等）
        pdf_url = pdf_url.split('#')[0]

        print(f"  找到PDF: {pdf_url[:80]}...")

        # 下载PDF
        if filename:
            save_path = self.download_dir / f"{self._sanitize_filename(filename)}.pdf"
        elif is_title:
            save_path = self.download_dir / f"{self._sanitize_filename(doi_or_title[:80])}.pdf"
        else:
            save_path = self.download_dir / f"{doi_or_title.replace('/', '_')}.pdf"

        try:
            # 优先使用requests直接下载（更快更可靠）
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                'Referer': mirror,
            }
            
            response = requests.get(pdf_url, headers=headers, timeout=60, stream=True)
            
            if response.status_code == 200 and len(response.content) > 1000:
                # 检查是否真的是PDF
                content_type = response.headers.get('content-type', '')
                if 'pdf' in content_type or response.content[:4] == b'%PDF':
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"  ✓ 下载成功: {save_path}")
                    return DownloadResult(
                        success=True,
                        source=DownloadSource.SCIHUB,
                        filepath=str(save_path),
                        message="下载成功",
                        doi=doi_or_title if not is_title else None,
                        title=doi_or_title if is_title else filename,
                    )
            
            # 如果requests失败，尝试浏览器下载
            print(f"  requests下载失败，尝试浏览器...")
            self.page.get(pdf_url)
            time.sleep(2)
            
            # 等待下载完成
            downloaded_file = self._wait_for_download(timeout=60)
            
            if downloaded_file:
                # 如果需要重命名
                if str(save_path) != downloaded_file:
                    import shutil
                    shutil.move(downloaded_file, str(save_path))
                
                print(f"  ✓ 下载成功: {save_path}")
                return DownloadResult(
                    success=True,
                    source=DownloadSource.SCIHUB,
                    filepath=str(save_path),
                    message="下载成功",
                    doi=doi_or_title if not is_title else None,
                    title=doi_or_title if is_title else filename,
                )
            else:
                return DownloadResult(
                    success=False,
                    source=DownloadSource.SCIHUB,
                    message="下载超时",
                    doi=doi_or_title if not is_title else None,
                    title=doi_or_title if is_title else None,
                )

        except Exception as e:
            return DownloadResult(
                success=False,
                source=DownloadSource.SCIHUB,
                message=f"下载失败: {e}",
                doi=doi_or_title if not is_title else None,
                title=doi_or_title if is_title else None,
            )

    def download_from_scihub_by_title(self, title: str, filename: str | None = None) -> DownloadResult:
        """通过标题在Sci-Hub搜索并下载论文.
        
        Sci-Hub也支持用论文标题搜索，虽然成功率比DOI低。
        
        Args:
            title: 论文标题
            filename: 保存的文件名（不含扩展名）
            
        Returns:
            DownloadResult对象
        """
        if not self.page:
            if not self.start():
                return DownloadResult(
                    success=False,
                    source=DownloadSource.SCIHUB,
                    message="浏览器启动失败",
                    title=title,
                )

        print(f"正在通过Sci-Hub搜索标题: {title[:50]}...")

        for mirror in self.SCIHUB_MIRRORS:
            try:
                result = self._try_scihub_mirror(mirror, title, filename, is_title=True)
                if result.success:
                    return result
                time.sleep(self.request_delay)
            except Exception as e:
                print(f"  镜像 {mirror} 失败: {e}")
                continue

        return DownloadResult(
            success=False,
            source=DownloadSource.SCIHUB,
            message="Sci-Hub标题搜索失败",
            title=title,
        )

    # ==================== Anna's Archive 下载 ====================

    def download_from_annas_archive(self, title: str, filename: str | None = None) -> DownloadResult:
        """通过Anna's Archive搜索并下载论文.
        
        Args:
            title: 论文标题
            filename: 保存的文件名（不含扩展名）
            
        Returns:
            DownloadResult对象
        """
        if not self.page:
            if not self.start():
                return DownloadResult(
                    success=False,
                    source=DownloadSource.ANNAS_ARCHIVE,
                    message="浏览器启动失败",
                    title=title,
                )

        print(f"正在通过Anna's Archive搜索: {title[:50]}...")

        # 构造搜索URL
        encoded_title = urllib.parse.quote(title)
        search_url = f"{self.ANNAS_ARCHIVE_URL}/search?q={encoded_title}"

        try:
            self.page.get(search_url)
            time.sleep(self.request_delay + random.uniform(0, 2))

            # 查找搜索结果
            results = self.page.eles("css:.h-[125px]", timeout=10)  # 结果卡片
            
            if not results:
                results = self.page.eles("css:a[href*='/md5/']", timeout=5)

            if not results:
                return DownloadResult(
                    success=False,
                    source=DownloadSource.ANNAS_ARCHIVE,
                    message="未找到匹配结果",
                    title=title,
                )

            print(f"  找到 {len(results)} 个结果")

            # 点击第一个结果
            first_result = results[0]
            detail_link = first_result.attr("href") if first_result.tag == "a" else None
            
            if not detail_link:
                link_elem = first_result.ele("css:a[href*='/md5/']", timeout=3)
                if link_elem:
                    detail_link = link_elem.attr("href")

            if not detail_link:
                return DownloadResult(
                    success=False,
                    source=DownloadSource.ANNAS_ARCHIVE,
                    message="无法获取详情页链接",
                    title=title,
                )

            # 访问详情页
            if not detail_link.startswith("http"):
                detail_link = self.ANNAS_ARCHIVE_URL + detail_link

            self.page.get(detail_link)
            time.sleep(self.request_delay)

            # 查找下载链接（通常有多个镜像）
            download_links = self.page.eles("css:a[href*='library.lol']", timeout=5)
            if not download_links:
                download_links = self.page.eles("css:a[href*='libgen']", timeout=3)
            if not download_links:
                download_links = self.page.eles("css:a.js-download-link", timeout=3)

            if not download_links:
                return DownloadResult(
                    success=False,
                    source=DownloadSource.ANNAS_ARCHIVE,
                    message="未找到下载链接",
                    title=title,
                )

            # 尝试下载
            for download_link in download_links[:3]:  # 最多尝试3个镜像
                try:
                    link_url = download_link.attr("href")
                    if not link_url:
                        continue

                    print(f"  尝试下载: {link_url[:60]}...")
                    
                    self.page.get(link_url)
                    time.sleep(2)

                    # 在镜像页面查找实际下载链接
                    actual_download = self.page.ele("css:a[href$='.pdf']", timeout=5)
                    if actual_download:
                        actual_url = actual_download.attr("href")
                        if actual_url:
                            self.page.get(actual_url)

                    # 等待下载
                    downloaded_file = self._wait_for_download(timeout=90)

                    if downloaded_file:
                        if filename:
                            save_path = self.download_dir / f"{self._sanitize_filename(filename)}.pdf"
                            import shutil
                            shutil.move(downloaded_file, str(save_path))
                            downloaded_file = str(save_path)

                        print(f"  ✓ 下载成功: {downloaded_file}")
                        return DownloadResult(
                            success=True,
                            source=DownloadSource.ANNAS_ARCHIVE,
                            filepath=downloaded_file,
                            message="下载成功",
                            title=title,
                        )

                except Exception as e:
                    print(f"  镜像失败: {e}")
                    continue

            return DownloadResult(
                success=False,
                source=DownloadSource.ANNAS_ARCHIVE,
                message="所有下载镜像均失败",
                title=title,
            )

        except Exception as e:
            return DownloadResult(
                success=False,
                source=DownloadSource.ANNAS_ARCHIVE,
                message=f"搜索失败: {e}",
                title=title,
            )

    # ==================== Google Scholar 下载 ====================

    def download_from_google_scholar(self, title: str, filename: str | None = None) -> DownloadResult:
        """通过Google Scholar寻找免费PDF源.
        
        Args:
            title: 论文标题
            filename: 保存的文件名（不含扩展名）
            
        Returns:
            DownloadResult对象
        """
        if not self.page:
            if not self.start():
                return DownloadResult(
                    success=False,
                    source=DownloadSource.GOOGLE_SCHOLAR,
                    message="浏览器启动失败",
                    title=title,
                )

        print(f"正在通过Google Scholar搜索: {title[:50]}...")

        # 构造搜索URL
        encoded_title = urllib.parse.quote(title)
        search_url = f"{self.GOOGLE_SCHOLAR_URL}/scholar?q={encoded_title}"

        try:
            self.page.get(search_url)
            time.sleep(self.request_delay + random.uniform(1, 3))

            # 检查是否被block
            if "sorry" in self.page.url.lower() or "captcha" in self.page.html.lower():
                return DownloadResult(
                    success=False,
                    source=DownloadSource.GOOGLE_SCHOLAR,
                    message="触发Google验证",
                    title=title,
                )

            # 查找带[PDF]标记的结果
            pdf_links = self.page.eles("css:.gs_or_ggsm a", timeout=10)
            
            # 过滤掉知网链接，优先选择其他来源
            free_pdf_links = []
            for link in pdf_links:
                href = link.attr("href")
                if href and ".pdf" in href.lower():
                    # 排除知网，优先其他来源
                    if "cnki" not in href.lower():
                        free_pdf_links.append(href)

            # 也搜索右侧的PDF链接
            side_links = self.page.eles("css:.gs_ggs a", timeout=3)
            for link in side_links:
                href = link.attr("href")
                if href and ".pdf" in href.lower() and "cnki" not in href.lower():
                    free_pdf_links.append(href)

            if not free_pdf_links:
                return DownloadResult(
                    success=False,
                    source=DownloadSource.GOOGLE_SCHOLAR,
                    message="未找到免费PDF源",
                    title=title,
                )

            print(f"  找到 {len(free_pdf_links)} 个PDF链接")

            # 尝试下载
            for pdf_url in free_pdf_links[:3]:
                try:
                    print(f"  尝试下载: {pdf_url[:60]}...")
                    
                    self.page.get(pdf_url)
                    time.sleep(2)

                    # 等待下载
                    downloaded_file = self._wait_for_download(timeout=60)

                    if downloaded_file:
                        if filename:
                            save_path = self.download_dir / f"{self._sanitize_filename(filename)}.pdf"
                            import shutil
                            shutil.move(downloaded_file, str(save_path))
                            downloaded_file = str(save_path)

                        print(f"  ✓ 下载成功: {downloaded_file}")
                        return DownloadResult(
                            success=True,
                            source=DownloadSource.GOOGLE_SCHOLAR,
                            filepath=downloaded_file,
                            message="下载成功",
                            title=title,
                        )

                except Exception as e:
                    print(f"  链接失败: {e}")
                    continue

            return DownloadResult(
                success=False,
                source=DownloadSource.GOOGLE_SCHOLAR,
                message="所有PDF链接均无法下载",
                title=title,
            )

        except Exception as e:
            return DownloadResult(
                success=False,
                source=DownloadSource.GOOGLE_SCHOLAR,
                message=f"搜索失败: {e}",
                title=title,
            )

    # ==================== 智能下载 ====================

    def smart_download(
        self,
        article: dict[str, Any],
        sources: list[DownloadSource] | None = None,
    ) -> DownloadResult:
        """智能下载论文，自动尝试多个来源.
        
        Args:
            article: 文章信息字典，应包含 title 和/或 doi
            sources: 要尝试的下载源列表，默认按优先级尝试所有源
            
        Returns:
            DownloadResult对象
        """
        title = article.get("title", "")
        doi = article.get("doi", "")

        if not title and not doi:
            return DownloadResult(
                success=False,
                message="缺少标题和DOI，无法下载",
            )

        # 默认下载源顺序
        link = article.get("link", "")
        
        if sources is None:
            sources = []
            # 如果有知网链接，优先尝试知网直接下载
            if link and "cnki" in link:
                sources.append(DownloadSource.CNKI)
            # 如果有DOI，优先使用Sci-Hub DOI搜索
            if doi:
                sources.append(DownloadSource.SCIHUB)
            # 如果有标题，也尝试Sci-Hub标题搜索（Sci-Hub支持标题搜索）
            if title:
                sources.append(DownloadSource.SCIHUB_TITLE)
            # 然后尝试Anna's Archive
            sources.append(DownloadSource.ANNAS_ARCHIVE)
            # 最后尝试Google Scholar
            sources.append(DownloadSource.GOOGLE_SCHOLAR)

        filename = self._sanitize_filename(title) if title else None

        print(f"\n{'='*50}")
        print(f"开始智能下载: {title[:50]}..." if title else f"DOI: {doi}")
        print(f"下载源顺序: {[s.value for s in sources]}")
        print(f"{'='*50}")

        for source in sources:
            print(f"\n>>> 尝试来源: {source.value}")
            
            try:
                if source == DownloadSource.CNKI:
                    if not link or "cnki" not in link:
                        print("  跳过: 缺少知网链接")
                        continue
                    result = self.download_from_cnki(link, filename)
                
                elif source == DownloadSource.SCIHUB:
                    if not doi:
                        print("  跳过: 缺少DOI")
                        continue
                    result = self.download_from_scihub(doi, filename)
                
                elif source == DownloadSource.SCIHUB_TITLE:
                    if not title:
                        print("  跳过: 缺少标题")
                        continue
                    result = self.download_from_scihub_by_title(title, filename)
                    
                elif source == DownloadSource.ANNAS_ARCHIVE:
                    if not title:
                        print("  跳过: 缺少标题")
                        continue
                    result = self.download_from_annas_archive(title, filename)
                    
                elif source == DownloadSource.GOOGLE_SCHOLAR:
                    if not title:
                        print("  跳过: 缺少标题")
                        continue
                    result = self.download_from_google_scholar(title, filename)
                    
                else:
                    continue

                if result.success:
                    return result

                print(f"  失败: {result.message}")
                time.sleep(self.request_delay)

            except Exception as e:
                print(f"  异常: {e}")
                continue

        return DownloadResult(
            success=False,
            message="所有下载源均失败",
            title=title,
            doi=doi,
        )

    def download_batch(
        self,
        articles: list[dict[str, Any]],
        sources: list[DownloadSource] | None = None,
        stop_on_failure: bool = False,
    ) -> list[DownloadResult]:
        """批量下载论文.
        
        Args:
            articles: 文章列表
            sources: 下载源列表
            stop_on_failure: 是否在失败时停止
            
        Returns:
            DownloadResult列表
        """
        results = []
        total = len(articles)

        print(f"\n开始批量下载 {total} 篇论文")
        print(f"下载目录: {self.download_dir}")

        for i, article in enumerate(articles):
            print(f"\n[{i+1}/{total}] 处理中...")
            
            result = self.smart_download(article, sources)
            results.append(result)

            if not result.success and stop_on_failure:
                print("检测到失败，停止批量下载")
                break

            # 添加延迟避免被封
            if i < total - 1:
                delay = self.request_delay + random.uniform(1, 3)
                print(f"等待 {delay:.1f} 秒...")
                time.sleep(delay)

        # 统计结果
        success_count = sum(1 for r in results if r.success)
        print(f"\n{'='*50}")
        print(f"批量下载完成: 成功 {success_count}/{len(results)}")
        print(f"{'='*50}")

        return results


def download_paper(
    article: dict[str, Any],
    download_dir: str | None = None,
    headless: bool = True,
    sources: list[str] | None = None,
) -> DownloadResult:
    """便捷函数：下载单篇论文.
    
    Args:
        article: 文章信息，应包含 title 和/或 doi
        download_dir: 下载目录
        headless: 是否使用无头模式
        sources: 下载源列表，如 ["scihub", "annas_archive", "google_scholar"]
        
    Returns:
        DownloadResult对象
        
    Example:
        >>> result = download_paper({"title": "论文标题", "doi": "10.1000/xyz"})
        >>> if result.success:
        ...     print(f"下载成功: {result.filepath}")
    """
    # 转换source字符串为枚举
    source_enums = None
    if sources:
        source_map = {
            "cnki": DownloadSource.CNKI,
            "scihub": DownloadSource.SCIHUB,
            "scihub_title": DownloadSource.SCIHUB_TITLE,
            "annas_archive": DownloadSource.ANNAS_ARCHIVE,
            "google_scholar": DownloadSource.GOOGLE_SCHOLAR,
        }
        source_enums = [source_map[s] for s in sources if s in source_map]

    downloader = PaperDownloader(
        headless=headless,
        download_dir=download_dir,
    )

    try:
        return downloader.smart_download(article, source_enums)
    finally:
        downloader.close()


def download_papers(
    articles: list[dict[str, Any]],
    download_dir: str | None = None,
    headless: bool = True,
    sources: list[str] | None = None,
) -> list[DownloadResult]:
    """便捷函数：批量下载论文.
    
    Args:
        articles: 文章列表
        download_dir: 下载目录
        headless: 是否使用无头模式
        sources: 下载源列表
        
    Returns:
        DownloadResult列表
    """
    source_enums = None
    if sources:
        source_map = {
            "cnki": DownloadSource.CNKI,
            "scihub": DownloadSource.SCIHUB,
            "scihub_title": DownloadSource.SCIHUB_TITLE,
            "annas_archive": DownloadSource.ANNAS_ARCHIVE,
            "google_scholar": DownloadSource.GOOGLE_SCHOLAR,
        }
        source_enums = [source_map[s] for s in sources if s in source_map]

    downloader = PaperDownloader(
        headless=headless,
        download_dir=download_dir,
    )

    try:
        return downloader.download_batch(articles, source_enums)
    finally:
        downloader.close()


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description="论文下载器")
    parser.add_argument("--doi", help="论文DOI")
    parser.add_argument("--title", help="论文标题")
    parser.add_argument("--source", choices=["scihub", "annas_archive", "google_scholar"])
    parser.add_argument("--output", "-o", default="downloads", help="下载目录")
    parser.add_argument("--headed", action="store_true", help="显示浏览器")

    args = parser.parse_args()

    if not args.doi and not args.title:
        parser.print_help()
        exit(1)

    article = {}
    if args.title:
        article["title"] = args.title
    if args.doi:
        article["doi"] = args.doi

    sources = [args.source] if args.source else None

    result = download_paper(
        article=article,
        download_dir=args.output,
        headless=not args.headed,
        sources=sources,
    )

    if result.success:
        print(f"\n✓ 下载成功: {result.filepath}")
    else:
        print(f"\n✗ 下载失败: {result.message}")
        exit(1)
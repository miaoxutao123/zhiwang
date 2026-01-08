"""浏览器下载和配置工具.

支持从国内镜像源下载Chromium到项目文件夹。
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import ssl
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# Chromium安装目录（项目文件夹内）
CHROMIUM_DIR = PROJECT_ROOT / "browsers" / "chromium"

# 国内镜像源
MIRRORS = {
    "npmmirror": "https://registry.npmmirror.com/-/binary/chromium-browser-snapshots",
    "ghproxy": "https://mirror.ghproxy.com/https://github.com/nicedisk/nicedisk.github.io/releases/download/chromium",
}


def get_chrome_path_in_project() -> str | None:
    """获取项目内的Chromium路径."""
    system = platform.system()
    
    if system == "Windows":
        chrome_exe = CHROMIUM_DIR / "chrome.exe"
    elif system == "Darwin":
        chrome_exe = CHROMIUM_DIR / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
    else:
        chrome_exe = CHROMIUM_DIR / "chrome"
    
    if chrome_exe.exists():
        return str(chrome_exe)
    
    # 搜索目录
    if CHROMIUM_DIR.exists():
        for root, _dirs, files in os.walk(CHROMIUM_DIR):
            if system == "Windows" and "chrome.exe" in files:
                return os.path.join(root, "chrome.exe")
            elif system != "Windows" and "chrome" in files:
                return os.path.join(root, "chrome")
    
    return None


def load_chrome_path_from_config() -> str | None:
    """从配置文件加载Chrome路径."""
    config_file = PROJECT_ROOT / ".chrome_path"
    try:
        if config_file.exists():
            path = config_file.read_text().strip()
            if os.path.exists(path):
                return path
    except Exception:
        pass
    return None


def save_chrome_path(chrome_path: str) -> None:
    """保存Chrome路径到配置文件."""
    config_file = PROJECT_ROOT / ".chrome_path"
    try:
        config_file.write_text(chrome_path)
    except Exception:
        pass


def find_chrome_path() -> str | None:
    """自动查找Chrome/Chromium浏览器路径.
    
    优先级：
    1. 项目内的Chromium
    2. 配置文件中保存的路径
    3. 系统安装的Chrome
    """
    # 1. 检查项目内的Chromium
    project_chrome = get_chrome_path_in_project()
    if project_chrome:
        return project_chrome
    
    # 2. 检查配置文件
    saved_path = load_chrome_path_from_config()
    if saved_path:
        return saved_path

    system = platform.system()

    # 3. 检查系统安装的Chrome
    if system == "Windows":
        # 检查本地下载的Chromium（旧位置）
        local_chromium = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "chromium"
        )
        for root, _dirs, files in os.walk(local_chromium):
            if "chrome.exe" in files:
                return os.path.join(root, "chrome.exe")

    # 尝试DrissionPage内置查找（排除Edge）
    try:
        from DrissionPage._functions.browser import get_chrome_path
        chrome_path = get_chrome_path(show_msg=False)
        if chrome_path and os.path.exists(chrome_path) and "edge" not in chrome_path.lower():
            return chrome_path
    except Exception:
        pass

    # 常见路径
    if system == "Windows":
        possible_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    elif system == "Darwin":
        possible_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        possible_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def _download_file(url: str, dest: str, desc: str = "下载") -> bool:
    """下载文件并显示进度."""
    print(f"{desc}: {url[:60]}...")
    
    def progress(count: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            percent = min(100, count * block_size * 100 // total_size)
            mb = count * block_size / 1024 / 1024
            total_mb = total_size / 1024 / 1024
            print(f"\r进度: {percent}% ({mb:.1f}/{total_mb:.1f} MB)", end="", flush=True)
    
    try:
        urllib.request.urlretrieve(url, dest, progress)
        print()
        return True
    except Exception as e:
        print(f"\n下载失败: {e}")
        return False


def _get_latest_version_npmmirror(platform_name: str) -> str | None:
    """从npmmirror获取最新版本号."""
    try:
        url = f"{MIRRORS['npmmirror']}/{platform_name}/LAST_CHANGE"
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8").strip()
    except Exception as e:
        print(f"获取版本号失败: {e}")
        return None


def download_chromium() -> str | None:
    """从国内镜像下载Chromium到项目文件夹.
    
    Returns:
        Chromium可执行文件路径，失败返回None
    """
    system = platform.system()
    machine = platform.machine().lower()
    
    print("=" * 50)
    print("Chromium浏览器下载工具（国内镜像）")
    print("=" * 50)
    print(f"系统: {system} {machine}")
    print(f"安装目录: {CHROMIUM_DIR}")
    
    # 确定平台名称
    if system == "Windows":
        if machine in ["amd64", "x86_64", "x64"]:
            platform_name = "Win_x64"
            zip_name = "chrome-win.zip"
        else:
            platform_name = "Win"
            zip_name = "chrome-win.zip"
    elif system == "Darwin":
        if machine == "arm64":
            platform_name = "Mac_Arm"
        else:
            platform_name = "Mac"
        zip_name = "chrome-mac.zip"
    else:  # Linux
        platform_name = "Linux_x64"
        zip_name = "chrome-linux.zip"
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="chromium_download_")
    zip_path = os.path.join(temp_dir, "chromium.zip")
    
    try:
        # 方法1: 从npmmirror下载
        print("\n尝试从npmmirror镜像下载...")
        version = _get_latest_version_npmmirror(platform_name)
        
        if version:
            print(f"最新版本: {version}")
            download_url = f"{MIRRORS['npmmirror']}/{platform_name}/{version}/{zip_name}"
            
            if _download_file(download_url, zip_path, "下载Chromium"):
                chrome_path = _extract_and_install(zip_path, temp_dir)
                if chrome_path:
                    return chrome_path
        
        # 方法2: 从ghproxy镜像下载（备用）
        print("\n尝试从ghproxy镜像下载...")
        if system == "Windows" and machine in ["amd64", "x86_64", "x64"]:
            download_url = f"{MIRRORS['ghproxy']}/chrome-win64.zip"
            if _download_file(download_url, zip_path, "下载Chromium"):
                chrome_path = _extract_and_install(zip_path, temp_dir)
                if chrome_path:
                    return chrome_path
        
        print("\n所有下载源都失败了")
        print("请手动下载Chrome浏览器: https://www.google.com/chrome/")
        return None
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _extract_and_install(zip_path: str, temp_dir: str) -> str | None:
    """解压并安装Chromium."""
    if not os.path.exists(zip_path) or os.path.getsize(zip_path) < 1000000:
        print("下载的文件不完整")
        return None
    
    print("正在解压...")
    extract_dir = os.path.join(temp_dir, "extract")
    os.makedirs(extract_dir, exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
    except Exception as e:
        print(f"解压失败: {e}")
        return None
    
    # 查找chrome可执行文件
    system = platform.system()
    chrome_exe = None
    chrome_dir = None
    
    for root, _dirs, files in os.walk(extract_dir):
        if system == "Windows" and "chrome.exe" in files:
            chrome_exe = os.path.join(root, "chrome.exe")
            chrome_dir = root
            break
        elif system != "Windows" and "chrome" in files:
            chrome_exe = os.path.join(root, "chrome")
            chrome_dir = root
            break
    
    if not chrome_exe:
        print("未找到chrome可执行文件")
        return None
    
    # 移动到项目目录
    print(f"安装到: {CHROMIUM_DIR}")
    
    if CHROMIUM_DIR.exists():
        shutil.rmtree(CHROMIUM_DIR, ignore_errors=True)
    
    CHROMIUM_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(chrome_dir, str(CHROMIUM_DIR))
    
    # 获取最终路径
    final_path = get_chrome_path_in_project()
    
    if final_path:
        save_chrome_path(final_path)
        print(f"✓ Chromium安装成功: {final_path}")
        return final_path
    
    return None


def setup_virtual_display() -> object | None:
    """在Linux上设置虚拟显示器."""
    if platform.system() != "Linux":
        return None

    display = os.environ.get("DISPLAY")
    if display:
        return None

    try:
        from pyvirtualdisplay import Display
        virtual_display = Display(visible=0, size=(1920, 1080))
        virtual_display.start()
        return virtual_display
    except ImportError:
        print("警告: 未安装pyvirtualdisplay")
        return None
    except Exception:
        return None


def ensure_browser() -> str | None:
    """确保有可用的浏览器，没有则自动下载.
    
    Returns:
        浏览器路径
    """
    # 先查找现有浏览器
    chrome_path = find_chrome_path()
    if chrome_path:
        return chrome_path
    
    # 没有找到，自动下载
    print("未检测到Chrome/Chromium浏览器，开始自动下载...")
    return download_chromium()


if __name__ == "__main__":
    # 直接运行此脚本可下载Chromium
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        path = find_chrome_path()
        if path:
            print(f"找到浏览器: {path}")
        else:
            print("未找到浏览器")
        sys.exit(0 if path else 1)
    
    # 检查是否已有浏览器
    existing = find_chrome_path()
    if existing:
        print(f"已找到浏览器: {existing}")
        choice = input("是否仍要下载新的Chromium到项目目录? (y/N): ").strip().lower()
        if choice != "y":
            sys.exit(0)
    
    chrome_path = download_chromium()
    if chrome_path:
        print("\n设置完成！")
    else:
        sys.exit(1)
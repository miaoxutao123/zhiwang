#!/usr/bin/env python3
"""
PDF转Markdown转换器模块

使用marker-pdf将学术论文PDF转换为Markdown格式，支持：
- 图片/图表提取
- 数学公式（LaTeX）
- 表格结构
- 文档元数据

依赖安装：
    pip install marker-pdf
    # 或完整安装（支持更多格式）
    pip install marker-pdf[full]
"""

import os
import re
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class ConversionBackend(Enum):
    """转换后端"""
    MARKER = "marker"           # marker-pdf（专为学术论文优化）
    PYMUPDF = "pymupdf"         # PyMuPDF4LLM（轻量级备选）
    MARKITDOWN = "markitdown"   # Microsoft MarkItDown
    PDFPLUMBER = "pdfplumber"   # pdfplumber（纯Python，易安装，低资源）
    DOCLING = "docling"         # IBM docling（推荐，学术论文解析能力强，需GPU或高配置）
    LLM_API = "llm_api"         # LLM API转换（适合低配置服务器，需要API密钥）
    DOTS_OCR = "dots_ocr"       # 小红书dots.ocr（1.7B参数，本地部署，结构化输出强）
    DEEPSEEK_OCR = "deepseek_ocr"  # DeepSeek-OCR云端API（推荐低配服务器，硅基流动）


@dataclass
class ConversionResult:
    """转换结果"""
    success: bool
    markdown_path: Optional[str] = None
    images_dir: Optional[str] = None
    image_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    backend: Optional[ConversionBackend] = None


class PdfConverter:
    """
    PDF转Markdown转换器
    
    使用示例：
        converter = PdfConverter()
        result = converter.convert("paper.pdf", output_dir="./output")
        
        if result.success:
            print(f"Markdown: {result.markdown_path}")
            print(f"图片数量: {result.image_count}")
    """
    
    def __init__(
        self,
        backend: ConversionBackend = ConversionBackend.MARKER,
        use_llm: bool = False,
        llm_provider: str = "gemini",  # gemini, openai, azure, ollama
        extract_images: bool = True,
        image_format: str = "png",
        max_pages: Optional[int] = None,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
    ):
        """
        初始化转换器
        
        Args:
            backend: 转换后端
            use_llm: 是否使用LLM增强转换质量（需要API密钥）
            llm_provider: LLM提供商
            extract_images: 是否提取图片
            image_format: 图片格式 (png, jpg, webp)
            max_pages: 最大处理页数（None为全部）
            api_key: LLM API密钥（用于LLM_API后端）
            api_base_url: API基础URL（可选，用于自定义端点）
        """
        self.backend = backend
        self.use_llm = use_llm
        self.llm_provider = llm_provider
        self.extract_images = extract_images
        self.image_format = image_format
        self.max_pages = max_pages
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("ZHIPU_API_KEY")
        self.api_base_url = api_base_url
        
        self._check_backend()
    
    def _check_backend(self):
        """检查后端是否可用"""
        if self.backend == ConversionBackend.MARKER:
            try:
                import marker
                self._marker_available = True
            except ImportError:
                self._marker_available = False
                print("警告: marker-pdf未安装，请运行: pip install marker-pdf")
        
        elif self.backend == ConversionBackend.PYMUPDF:
            try:
                import pymupdf4llm
                self._pymupdf_available = True
            except ImportError:
                self._pymupdf_available = False
                print("警告: pymupdf4llm未安装，请运行: pip install pymupdf4llm")
        
        elif self.backend == ConversionBackend.MARKITDOWN:
            try:
                from markitdown import MarkItDown
                self._markitdown_available = True
            except ImportError:
                self._markitdown_available = False
                print("警告: markitdown未安装，请运行: pip install markitdown")
        
        elif self.backend == ConversionBackend.PDFPLUMBER:
            try:
                import pdfplumber
                self._pdfplumber_available = True
            except ImportError:
                self._pdfplumber_available = False
                print("警告: pdfplumber未安装，请运行: pip install pdfplumber")
        
        elif self.backend == ConversionBackend.DOCLING:
            try:
                from docling.document_converter import DocumentConverter
                self._docling_available = True
            except ImportError:
                self._docling_available = False
                print("警告: docling未安装，请运行: pip install docling")
        
        elif self.backend == ConversionBackend.LLM_API:
            self._llm_api_available = bool(self.api_key)
            if not self._llm_api_available:
                print("警告: 未设置API密钥，请设置环境变量 OPENAI_API_KEY 或 ZHIPU_API_KEY")
        
        elif self.backend == ConversionBackend.DOTS_OCR:
            try:
                from dots_ocr import DotsOCRParser
                self._dots_ocr_available = True
            except ImportError:
                self._dots_ocr_available = False
                print("警告: dots_ocr未安装，请参考: https://github.com/rednote-hilab/dots.ocr")
        
        elif self.backend == ConversionBackend.DEEPSEEK_OCR:
            # DeepSeek-OCR 直接使用requests调用硅基流动API，无需额外SDK
            if not self.api_key:
                # 尝试从环境变量获取硅基流动API密钥
                self.api_key = os.environ.get("DS_OCR_API_KEY") or os.environ.get("SILICONFLOW_API_KEY")
            if not self.api_key:
                print("警告: 未设置API密钥，请设置环境变量 DS_OCR_API_KEY 或 SILICONFLOW_API_KEY")
                self._deepseek_ocr_available = False
            else:
                self._deepseek_ocr_available = True
    
    def convert(
        self,
        pdf_path: str,
        output_dir: Optional[str] = None,
        output_name: Optional[str] = None,
        auto_select_backend: bool = False,
    ) -> ConversionResult:
        """
        将PDF转换为Markdown
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录（默认为PDF所在目录）
            output_name: 输出文件名（不含扩展名，默认使用PDF文件名）
            auto_select_backend: 是否自动选择最佳后端（智能路由）
        
        Returns:
            ConversionResult 转换结果
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            return ConversionResult(
                success=False,
                message=f"文件不存在: {pdf_path}"
            )
        
        if not pdf_path.suffix.lower() == ".pdf":
            return ConversionResult(
                success=False,
                message=f"不是PDF文件: {pdf_path}"
            )
        
        # 确定输出路径
        if output_dir is None:
            output_dir = pdf_path.parent
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if output_name is None:
            output_name = pdf_path.stem
        
        # 智能路由：自动选择最佳后端
        if auto_select_backend:
            return self._smart_convert(pdf_path, output_dir, output_name)
        
        # 根据后端选择转换方法
        if self.backend == ConversionBackend.MARKER:
            return self._convert_with_marker(pdf_path, output_dir, output_name)
        elif self.backend == ConversionBackend.PYMUPDF:
            return self._convert_with_pymupdf(pdf_path, output_dir, output_name)
        elif self.backend == ConversionBackend.MARKITDOWN:
            return self._convert_with_markitdown(pdf_path, output_dir, output_name)
        elif self.backend == ConversionBackend.PDFPLUMBER:
            return self._convert_with_pdfplumber(pdf_path, output_dir, output_name)
        elif self.backend == ConversionBackend.DOCLING:
            return self._convert_with_docling(pdf_path, output_dir, output_name)
        elif self.backend == ConversionBackend.LLM_API:
            return self._convert_with_llm_api(pdf_path, output_dir, output_name)
        elif self.backend == ConversionBackend.DOTS_OCR:
            return self._convert_with_dots_ocr(pdf_path, output_dir, output_name)
        elif self.backend == ConversionBackend.DEEPSEEK_OCR:
            return self._convert_with_deepseek_ocr(pdf_path, output_dir, output_name)
        else:
            return ConversionResult(
                success=False,
                message=f"未知后端: {self.backend}"
            )
    
    def _smart_convert(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """智能路由：根据PDF特性自动选择最佳后端
        
        决策逻辑：
        1. 检测PDF是否包含可提取的文本层
        2. 分析文本质量（是否乱码、是否有意义）
        3. 根据结果选择后端：
           - 有高质量文本层 -> pdfplumber（快速，低资源）
           - 扫描PDF/无文本/乱码 -> DeepSeek-OCR 或 LLM_API
        """
        print(f"正在分析PDF特性: {pdf_path.name}")
        
        # 检测PDF类型
        pdf_type, sample_text = self._detect_pdf_type(pdf_path)
        
        print(f"  PDF类型: {pdf_type}")
        
        if pdf_type == "text_pdf":
            # 有文本层，使用pdfplumber（快速、低资源）
            print(f"  选择后端: pdfplumber（检测到文本层）")
            return self._convert_with_pdfplumber(pdf_path, output_dir, output_name)
        
        elif pdf_type == "scanned_pdf":
            # 扫描PDF，需要OCR
            # 优先使用DeepSeek-OCR（如果有API密钥）
            if self.api_key:
                print(f"  选择后端: DeepSeek-OCR（扫描PDF需要OCR）")
                return self._convert_with_deepseek_ocr(pdf_path, output_dir, output_name)
            else:
                # 回退到pdfplumber（可能质量较低）
                print(f"  选择后端: pdfplumber（无API密钥，回退使用）")
                return self._convert_with_pdfplumber(pdf_path, output_dir, output_name)
        
        elif pdf_type == "garbled_text":
            # 有文本层但是乱码（嵌入字体问题）
            # 这种情况下OCR可能也有问题，尝试pdfplumber
            print(f"  选择后端: pdfplumber（检测到乱码文本，尝试直接提取）")
            result = self._convert_with_pdfplumber(pdf_path, output_dir, output_name)
            
            # 检查结果质量
            if result.success and result.markdown_path:
                with open(result.markdown_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 如果结果质量差且有API密钥，尝试OCR
                if self._is_garbled_text(content) and self.api_key:
                    print(f"  pdfplumber结果质量差，切换到DeepSeek-OCR")
                    return self._convert_with_deepseek_ocr(pdf_path, output_dir, output_name)
            
            return result
        
        else:
            # 未知类型，默认使用pdfplumber
            print(f"  选择后端: pdfplumber（默认）")
            return self._convert_with_pdfplumber(pdf_path, output_dir, output_name)
    
    def _detect_pdf_type(self, pdf_path: Path) -> tuple:
        """检测PDF类型
        
        Returns:
            (pdf_type, sample_text)
            pdf_type: "text_pdf" | "scanned_pdf" | "garbled_text" | "unknown"
        """
        try:
            import pdfplumber
            
            with pdfplumber.open(str(pdf_path)) as pdf:
                if not pdf.pages:
                    return ("unknown", "")
                
                # 检查前几页
                sample_texts = []
                for page in pdf.pages[:3]:
                    text = page.extract_text() or ""
                    sample_texts.append(text)
                
                combined_text = "\n".join(sample_texts)
                
                if not combined_text.strip():
                    # 没有文本内容，可能是扫描PDF
                    return ("scanned_pdf", "")
                
                # 检测文本质量
                if self._is_garbled_text(combined_text):
                    return ("garbled_text", combined_text[:500])
                
                # 有正常文本
                return ("text_pdf", combined_text[:500])
                
        except ImportError:
            # pdfplumber未安装，无法检测
            return ("unknown", "")
        except Exception as e:
            print(f"  检测PDF类型失败: {e}")
            return ("unknown", "")
    
    def _is_garbled_text(self, text: str, threshold: float = 0.3) -> bool:
        """检测文本是否是乱码
        
        使用多个指标判断：
        1. 非ASCII可打印字符比例
        2. 连续重复字符
        3. 缺少常见英文单词
        """
        if not text or len(text) < 50:
            return False
        
        # 计算可读字符比例
        readable_chars = 0
        total_chars = 0
        
        for char in text:
            if char.isspace():
                continue
            total_chars += 1
            # 可读字符：字母、数字、常见标点
            if char.isalnum() or char in '.,;:!?\'\"()-[]{}@#$%&*+=/<>':
                readable_chars += 1
        
        if total_chars == 0:
            return True
        
        readable_ratio = readable_chars / total_chars
        
        # 检测连续重复字符（乱码特征）
        repeat_count = 0
        for i in range(len(text) - 2):
            if text[i] == text[i+1] == text[i+2] and not text[i].isspace():
                repeat_count += 1
        
        repeat_ratio = repeat_count / max(len(text), 1)
        
        # 判断标准
        if readable_ratio < 0.5:
            return True
        if repeat_ratio > 0.1:  # 超过10%的位置有连续重复
            return True
        
        return False
    
    def smart_convert(
        self,
        pdf_path: str,
        output_dir: Optional[str] = None,
        output_name: Optional[str] = None,
    ) -> ConversionResult:
        """智能转换：自动选择最佳后端
        
        这是一个便捷方法，等同于 convert(..., auto_select_backend=True)
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            output_name: 输出文件名
        
        Returns:
            ConversionResult 转换结果
        """
        return self.convert(pdf_path, output_dir, output_name, auto_select_backend=True)
    
    def _convert_with_marker(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """使用marker-pdf转换"""
        try:
            from marker.converters.pdf import PdfConverter as MarkerPdfConverter
            from marker.config.parser import ConfigParser
            from marker.output import save_output
        except ImportError:
            return ConversionResult(
                success=False,
                message="marker-pdf未安装，请运行: pip install marker-pdf"
            )
        
        try:
            print(f"正在使用marker转换: {pdf_path.name}")
            
            # 配置marker
            config = {
                "output_format": "markdown",
                "paginate_output": False,
            }
            
            if self.use_llm:
                config["use_llm"] = True
                config["llm_provider"] = self.llm_provider
            
            if self.max_pages:
                config["max_pages"] = self.max_pages
            
            # 创建转换器
            config_parser = ConfigParser(config)
            converter = MarkerPdfConverter(config=config_parser.generate_config_dict())
            
            # 执行转换
            rendered = converter(str(pdf_path))
            
            # 保存输出
            md_path = output_dir / f"{output_name}.md"
            images_dir = output_dir / f"{output_name}_images"
            
            # 提取markdown内容
            if hasattr(rendered, 'markdown'):
                markdown_content = rendered.markdown
            elif hasattr(rendered, 'text'):
                markdown_content = rendered.text
            else:
                markdown_content = str(rendered)
            
            # 处理图片
            image_count = 0
            if self.extract_images and hasattr(rendered, 'images'):
                images_dir.mkdir(parents=True, exist_ok=True)
                
                for idx, (img_name, img_data) in enumerate(rendered.images.items()):
                    img_path = images_dir / f"image_{idx + 1}.{self.image_format}"
                    
                    if hasattr(img_data, 'save'):
                        img_data.save(str(img_path))
                    elif isinstance(img_data, bytes):
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                    
                    # 更新markdown中的图片引用
                    markdown_content = markdown_content.replace(
                        img_name,
                        f"{output_name}_images/image_{idx + 1}.{self.image_format}"
                    )
                    image_count += 1
            
            # 保存markdown
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 提取元数据
            metadata = {}
            if hasattr(rendered, 'metadata'):
                metadata = rendered.metadata
            
            print(f"✓ 转换成功: {md_path}")
            if image_count > 0:
                print(f"  图片数量: {image_count}")
            
            return ConversionResult(
                success=True,
                markdown_path=str(md_path),
                images_dir=str(images_dir) if image_count > 0 else None,
                image_count=image_count,
                metadata=metadata,
                message="转换成功",
                backend=ConversionBackend.MARKER
            )
            
        except Exception as e:
            return ConversionResult(
                success=False,
                message=f"marker转换失败: {str(e)}",
                backend=ConversionBackend.MARKER
            )
    
    def _convert_with_pymupdf(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """使用PyMuPDF4LLM转换"""
        try:
            import pymupdf4llm
            import pymupdf
        except ImportError:
            return ConversionResult(
                success=False,
                message="pymupdf4llm未安装，请运行: pip install pymupdf4llm"
            )
        
        try:
            print(f"正在使用PyMuPDF转换: {pdf_path.name}")
            
            # 转换为markdown
            md_text = pymupdf4llm.to_markdown(
                str(pdf_path),
                write_images=self.extract_images,
                image_path=str(output_dir / f"{output_name}_images"),
                image_format=self.image_format,
                pages=list(range(self.max_pages)) if self.max_pages else None,
            )
            
            # 保存markdown
            md_path = output_dir / f"{output_name}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_text)
            
            # 统计图片数量
            images_dir = output_dir / f"{output_name}_images"
            image_count = 0
            if images_dir.exists():
                image_count = len(list(images_dir.glob(f"*.{self.image_format}")))
            
            # 提取元数据
            metadata = {}
            doc = pymupdf.open(str(pdf_path))
            if doc.metadata:
                metadata = dict(doc.metadata)
            doc.close()
            
            print(f"✓ 转换成功: {md_path}")
            if image_count > 0:
                print(f"  图片数量: {image_count}")
            
            return ConversionResult(
                success=True,
                markdown_path=str(md_path),
                images_dir=str(images_dir) if image_count > 0 else None,
                image_count=image_count,
                metadata=metadata,
                message="转换成功",
                backend=ConversionBackend.PYMUPDF
            )
            
        except Exception as e:
            return ConversionResult(
                success=False,
                message=f"PyMuPDF转换失败: {str(e)}",
                backend=ConversionBackend.PYMUPDF
            )
    
    def _convert_with_markitdown(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """使用Microsoft MarkItDown转换"""
        try:
            from markitdown import MarkItDown
        except ImportError:
            return ConversionResult(
                success=False,
                message="markitdown未安装，请运行: pip install markitdown"
            )
        
        try:
            print(f"正在使用MarkItDown转换: {pdf_path.name}")
            
            # 创建转换器
            md = MarkItDown()
            
            # 执行转换
            result = md.convert(str(pdf_path))
            
            # 保存markdown
            md_path = output_dir / f"{output_name}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(result.text_content)
            
            print(f"✓ 转换成功: {md_path}")
            
            return ConversionResult(
                success=True,
                markdown_path=str(md_path),
                image_count=0,  # MarkItDown当前不支持图片提取
                message="转换成功（注：MarkItDown暂不支持图片提取）",
                backend=ConversionBackend.MARKITDOWN
            )
            
        except Exception as e:
            return ConversionResult(
                success=False,
                message=f"MarkItDown转换失败: {str(e)}",
                backend=ConversionBackend.MARKITDOWN
            )
    
    def _convert_with_pdfplumber(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """使用pdfplumber转换"""
        try:
            import pdfplumber
            from PIL import Image
        except ImportError:
            return ConversionResult(
                success=False,
                message="pdfplumber未安装，请运行: pip install pdfplumber"
            )
        
        try:
            print(f"正在使用pdfplumber转换: {pdf_path.name}")
            
            markdown_lines = []
            images_dir = output_dir / f"{output_name}_images"
            image_count = 0
            metadata = {}
            
            with pdfplumber.open(str(pdf_path)) as pdf:
                # 提取元数据
                if pdf.metadata:
                    metadata = dict(pdf.metadata)
                
                total_pages = len(pdf.pages)
                pages_to_process = pdf.pages[:self.max_pages] if self.max_pages else pdf.pages
                
                for page_num, page in enumerate(pages_to_process, 1):
                    print(f"  处理页面 {page_num}/{len(pages_to_process)}...")
                    
                    # 添加页面分隔符
                    if page_num > 1:
                        markdown_lines.append("\n---\n")
                    
                    # 提取文本
                    text = page.extract_text()
                    if text:
                        # 尝试识别标题（简单启发式）
                        lines = text.split('\n')
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            
                            # 简单的标题识别：短行且全大写或以数字开头
                            if len(line) < 80 and (line.isupper() or re.match(r'^\d+\.?\s+', line)):
                                markdown_lines.append(f"\n## {line}\n")
                            else:
                                markdown_lines.append(line)
                        markdown_lines.append("\n")
                    
                    # 提取表格
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        if table and len(table) > 0:
                            markdown_lines.append("\n")
                            # 表头
                            if table[0]:
                                header = " | ".join(str(cell) if cell else "" for cell in table[0])
                                markdown_lines.append(f"| {header} |")
                                separator = " | ".join("---" for _ in table[0])
                                markdown_lines.append(f"| {separator} |")
                            # 表格内容
                            for row in table[1:]:
                                if row:
                                    row_text = " | ".join(str(cell) if cell else "" for cell in row)
                                    markdown_lines.append(f"| {row_text} |")
                            markdown_lines.append("\n")
                    
                    # 提取图片
                    if self.extract_images:
                        images = page.images
                        for img_idx, img in enumerate(images):
                            try:
                                # 使用页面裁剪获取图片
                                x0, y0, x1, y1 = img['x0'], img['top'], img['x1'], img['bottom']
                                cropped = page.crop((x0, y0, x1, y1))
                                pil_image = cropped.to_image(resolution=150).original
                                
                                # 保存图片
                                images_dir.mkdir(parents=True, exist_ok=True)
                                img_filename = f"page{page_num}_img{img_idx + 1}.{self.image_format}"
                                img_path = images_dir / img_filename
                                pil_image.save(str(img_path))
                                
                                # 添加图片引用
                                markdown_lines.append(f"\n![图片]({output_name}_images/{img_filename})\n")
                                image_count += 1
                            except Exception as e:
                                print(f"    警告: 提取图片失败 - {e}")
            
            # 保存markdown
            md_path = output_dir / f"{output_name}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(markdown_lines))
            
            print(f"✓ 转换成功: {md_path}")
            if image_count > 0:
                print(f"  图片数量: {image_count}")
            
            return ConversionResult(
                success=True,
                markdown_path=str(md_path),
                images_dir=str(images_dir) if image_count > 0 else None,
                image_count=image_count,
                metadata=metadata,
                message="转换成功",
                backend=ConversionBackend.PDFPLUMBER
            )
            
        except Exception as e:
            return ConversionResult(
                success=False,
                message=f"pdfplumber转换失败: {str(e)}",
                backend=ConversionBackend.PDFPLUMBER
            )
    
    def _convert_with_docling(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """使用IBM docling转换（推荐用于学术论文）"""
        try:
            from docling.document_converter import DocumentConverter
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import PdfFormatOption
        except ImportError:
            return ConversionResult(
                success=False,
                message="docling未安装，请运行: pip install docling"
            )
        
        try:
            print(f"正在使用docling转换: {pdf_path.name}")
            
            # 配置docling pipeline
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True  # 启用OCR
            pipeline_options.do_table_structure = True  # 启用表格结构识别
            
            # 创建转换器
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            
            # 执行转换
            result = converter.convert(str(pdf_path))
            
            # 导出为Markdown
            markdown_content = result.document.export_to_markdown()
            
            # 保存markdown
            md_path = output_dir / f"{output_name}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 提取并保存图片
            images_dir = output_dir / f"{output_name}_images"
            image_count = 0
            
            if self.extract_images:
                try:
                    # docling的图片通常在document.pictures中
                    if hasattr(result.document, 'pictures') and result.document.pictures:
                        images_dir.mkdir(parents=True, exist_ok=True)
                        
                        for idx, picture in enumerate(result.document.pictures):
                            try:
                                img_filename = f"figure_{idx + 1}.{self.image_format}"
                                img_path = images_dir / img_filename
                                
                                # 获取图片数据
                                if hasattr(picture, 'image') and picture.image:
                                    if hasattr(picture.image, 'save'):
                                        picture.image.save(str(img_path))
                                    elif isinstance(picture.image, bytes):
                                        with open(img_path, 'wb') as f:
                                            f.write(picture.image)
                                    image_count += 1
                                    
                                    # 更新markdown中的图片引用
                                    # docling通常会生成类似 ![](image_ref) 的格式
                                    if hasattr(picture, 'ref') and picture.ref:
                                        markdown_content = markdown_content.replace(
                                            picture.ref,
                                            f"{output_name}_images/{img_filename}"
                                        )
                            except Exception as e:
                                print(f"    警告: 提取图片 {idx + 1} 失败 - {e}")
                        
                        # 重新保存更新后的markdown
                        if image_count > 0:
                            with open(md_path, 'w', encoding='utf-8') as f:
                                f.write(markdown_content)
                except Exception as e:
                    print(f"    警告: 图片提取过程出错 - {e}")
            
            # 提取元数据
            metadata = {}
            if hasattr(result.document, 'metadata') and result.document.metadata:
                metadata = dict(result.document.metadata)
            
            print(f"✓ 转换成功: {md_path}")
            if image_count > 0:
                print(f"  图片数量: {image_count}")
            
            return ConversionResult(
                success=True,
                markdown_path=str(md_path),
                images_dir=str(images_dir) if image_count > 0 else None,
                image_count=image_count,
                metadata=metadata,
                message="转换成功",
                backend=ConversionBackend.DOCLING
            )
            
        except Exception as e:
            import traceback
            return ConversionResult(
                success=False,
                message=f"docling转换失败: {str(e)}\n{traceback.format_exc()}",
                backend=ConversionBackend.DOCLING
            )
    
    def _convert_with_llm_api(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """使用LLM API转换（适合低配置服务器）
        
        流程：
        1. 用pypdfium2将PDF转为页面图片
        2. 用pdfplumber提取嵌入的图片（figures）
        3. 用多模态LLM进行OCR和格式化
        
        支持：智谱GLM-4V-Flash（免费）, OpenAI GPT-4V, Claude等
        """
        import base64
        import requests
        
        # 检查pypdfium2（必需，用于页面渲染）
        try:
            import pypdfium2 as pdfium
        except ImportError:
            return ConversionResult(
                success=False,
                message="需要安装pypdfium2: pip install pypdfium2"
            )
        
        if not self.api_key:
            return ConversionResult(
                success=False,
                message="未设置API密钥，请设置环境变量 OPENAI_API_KEY 或 ZHIPU_API_KEY"
            )
        
        try:
            print(f"正在使用LLM API转换: {pdf_path.name}")
            
            images_dir = output_dir / f"{output_name}_images"
            images_dir.mkdir(parents=True, exist_ok=True)
            
            # ============ 步骤1: 提取嵌入图片（figures） ============
            figure_count = 0
            figure_map = {}  # page_num -> [figure_paths]
            
            if self.extract_images:
                print("  步骤1: 提取论文中的图片（figures）...")
                try:
                    import pdfplumber
                    with pdfplumber.open(str(pdf_path)) as pdf:
                        pages_to_process = pdf.pages[:self.max_pages] if self.max_pages else pdf.pages
                        for page_num, page in enumerate(pages_to_process, 1):
                            page_figures = []
                            for img_idx, img in enumerate(page.images):
                                try:
                                    x0, y0, x1, y1 = img['x0'], img['top'], img['x1'], img['bottom']
                                    # 过滤太小的图片（可能是装饰元素）
                                    if (x1 - x0) < 50 or (y1 - y0) < 50:
                                        continue
                                    cropped = page.crop((x0, y0, x1, y1))
                                    pil_image = cropped.to_image(resolution=150).original
                                    
                                    figure_count += 1
                                    fig_filename = f"figure_{figure_count}.{self.image_format}"
                                    fig_path = images_dir / fig_filename
                                    pil_image.save(str(fig_path))
                                    page_figures.append(fig_filename)
                                except Exception:
                                    pass
                            if page_figures:
                                figure_map[page_num] = page_figures
                    print(f"  提取了 {figure_count} 张图片")
                except ImportError:
                    print("  提示: 安装pdfplumber可以提取论文图片: pip install pdfplumber")
                except Exception as e:
                    print(f"  图片提取失败（将继续）: {e}")
            
            # ============ 步骤2: PDF转页面图片 ============
            print("  步骤2: 将PDF页面转换为图片...")
            page_images = []
            
            pdf_doc = pdfium.PdfDocument(str(pdf_path))
            for i, page in enumerate(pdf_doc):
                if self.max_pages and i >= self.max_pages:
                    break
                bitmap = page.render(scale=2)  # 2x缩放，提高OCR质量
                pil_image = bitmap.to_pil()
                img_path = images_dir / f"page_{i+1}.png"
                pil_image.save(str(img_path), "PNG")
                page_images.append((i+1, img_path))
            pdf_doc.close()
            
            print(f"  生成了 {len(page_images)} 页图片")
            
            # ============ 步骤3: 调用LLM API进行OCR ============
            print("  步骤3: 调用LLM API进行OCR...")
            markdown_parts = []
            
            for page_num, img_path in page_images:
                print(f"  处理页面 {page_num}/{len(page_images)}...")
                
                # 读取图片并转base64
                with open(img_path, "rb") as f:
                    img_base64 = base64.b64encode(f.read()).decode()
                
                # 调用API进行OCR
                page_md = self._call_llm_api(img_base64, page_num=page_num)
                
                if page_md:
                    # 如果这一页有提取到的图片，添加引用
                    if page_num in figure_map:
                        figures_md = "\n\n".join([
                            f"![Figure]({output_name}_images/{fig})"
                            for fig in figure_map[page_num]
                        ])
                        page_md = page_md + f"\n\n{figures_md}"
                    
                    markdown_parts.append(f"<!-- Page {page_num} -->\n\n{page_md}")
                else:
                    markdown_parts.append(f"<!-- Page {page_num}: OCR失败 -->\n\n")
                
                # 删除页面截图（只保留figures）
                if self.extract_images and figure_count > 0:
                    img_path.unlink(missing_ok=True)
            
            # ============ 步骤4: 合并并保存 ============
            markdown_content = "\n\n---\n\n".join(markdown_parts)
            
            md_path = output_dir / f"{output_name}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 清理
            if not self.extract_images:
                import shutil
                shutil.rmtree(images_dir, ignore_errors=True)
                images_dir = None
            elif figure_count == 0:
                # 如果没有提取到figures，保留页面截图
                pass
            
            print(f"✓ 转换成功: {md_path}")
            if figure_count > 0:
                print(f"  提取图片: {figure_count} 张")
            
            return ConversionResult(
                success=True,
                markdown_path=str(md_path),
                images_dir=str(images_dir) if images_dir and images_dir.exists() else None,
                image_count=figure_count if figure_count > 0 else len(page_images),
                message="转换成功（LLM API）",
                backend=ConversionBackend.LLM_API
            )
            
        except Exception as e:
            import traceback
            return ConversionResult(
                success=False,
                message=f"LLM API转换失败: {str(e)}\n{traceback.format_exc()}",
                backend=ConversionBackend.LLM_API
            )
    
    def _call_llm_api(self, img_base64: str, page_num: int = 1) -> str:
        """调用LLM API进行单页OCR"""
        import requests
        
        prompt = """请将这张学术论文页面转换为Markdown格式。要求：
1. 保持原文的段落结构
2. 标题使用适当的 # 级别
3. 数学公式使用 LaTeX 格式（行内用$，行间用$$）
4. 表格使用Markdown表格格式
5. 图片位置标记为 <!-- Figure X -->
6. 保持参考文献格式
7. 不要添加任何解释，只输出Markdown内容"""

        # 检测API类型并调用
        if "sk-" in self.api_key and len(self.api_key) > 50:
            # OpenAI格式
            return self._call_openai_api(img_base64, prompt)
        else:
            # 智谱GLM格式
            return self._call_zhipu_api(img_base64, prompt)
    
    def _call_openai_api(self, img_base64: str, prompt: str) -> str:
        """调用OpenAI兼容API"""
        import requests
        
        base_url = self.api_base_url or "https://api.openai.com/v1"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4096
        }
        
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"    OpenAI API调用失败: {e}")
            return ""
    
    def _call_zhipu_api(self, img_base64: str, prompt: str) -> str:
        """调用智谱GLM API"""
        import requests
        
        base_url = self.api_base_url or "https://open.bigmodel.cn/api/paas/v4"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "glm-4v-flash",  # 免费的视觉模型
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4096
        }
        
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"    智谱API调用失败: {e}")
            return ""
    
    def _convert_with_deepseek_ocr(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """使用DeepSeek-OCR云端API转换（推荐用于低配置服务器）
        
        通过硅基流动(SiliconFlow)云端API调用DeepSeek-OCR模型进行PDF转Markdown。
        无需本地GPU，非常适合2c2g等低配置服务器。
        
        流程：
        1. 用pdf2image将PDF转为页面图片
        2. 逐页调用DeepSeek-OCR API进行识别
        3. 用pdfplumber提取嵌入的图片（figures）
        
        需要设置环境变量:
        - DS_OCR_API_KEY: 硅基流动API密钥
        """
        import base64
        import requests
        
        # 检查pdf2image（必需，用于页面渲染）
        try:
            from pdf2image import convert_from_path
        except ImportError:
            return ConversionResult(
                success=False,
                message="需要安装pdf2image: pip install pdf2image（还需要poppler）"
            )
        
        if not self.api_key:
            return ConversionResult(
                success=False,
                message="未设置API密钥，请设置环境变量 DS_OCR_API_KEY 或 SILICONFLOW_API_KEY"
            )
        
        try:
            print(f"正在使用DeepSeek-OCR云端API转换: {pdf_path.name}")
            
            # 确定API端点
            base_url = self.api_base_url or os.environ.get(
                "DS_OCR_BASE_URL",
                "https://api.siliconflow.cn/v1"
            )
            
            images_dir = output_dir / f"{output_name}_images"
            images_dir.mkdir(parents=True, exist_ok=True)
            
            # ============ 步骤1: 提取嵌入图片（figures） ============
            figure_count = 0
            figure_map = {}  # page_num -> [figure_paths]
            
            if self.extract_images:
                print("  步骤1: 提取论文中的图片（figures）...")
                try:
                    import pdfplumber
                    with pdfplumber.open(str(pdf_path)) as pdf:
                        pages_to_process = pdf.pages[:self.max_pages] if self.max_pages else pdf.pages
                        for page_num, page in enumerate(pages_to_process, 1):
                            page_figures = []
                            for img_idx, img in enumerate(page.images):
                                try:
                                    x0, y0, x1, y1 = img['x0'], img['top'], img['x1'], img['bottom']
                                    # 过滤太小的图片（可能是装饰元素）
                                    if (x1 - x0) < 50 or (y1 - y0) < 50:
                                        continue
                                    cropped = page.crop((x0, y0, x1, y1))
                                    pil_image = cropped.to_image(resolution=150).original
                                    
                                    figure_count += 1
                                    fig_filename = f"figure_{figure_count}.{self.image_format}"
                                    fig_path = images_dir / fig_filename
                                    pil_image.save(str(fig_path))
                                    page_figures.append(fig_filename)
                                except Exception:
                                    pass
                            if page_figures:
                                figure_map[page_num] = page_figures
                    print(f"  提取了 {figure_count} 张图片")
                except ImportError:
                    print("  提示: 安装pdfplumber可以提取论文图片: pip install pdfplumber")
                except Exception as e:
                    print(f"  图片提取失败（将继续）: {e}")
            
            # ============ 步骤2: PDF转页面图片 ============
            print("  步骤2: 将PDF页面转换为图片...")
            page_images = []
            
            # 使用pdf2image转换PDF页面
            pil_images = convert_from_path(
                str(pdf_path),
                dpi=200,  # 适中的DPI，平衡质量和速度
                first_page=1,
                last_page=self.max_pages if self.max_pages else None,
            )
            
            for i, pil_image in enumerate(pil_images):
                img_path = images_dir / f"page_{i+1}.png"
                pil_image.save(str(img_path), "PNG")
                page_images.append((i+1, img_path))
            
            print(f"  生成了 {len(page_images)} 页图片")
            
            # ============ 步骤3: 调用DeepSeek-OCR API进行OCR ============
            print("  步骤3: 调用DeepSeek-OCR API进行OCR...")
            markdown_parts = []
            
            for page_num, img_path in page_images:
                print(f"  处理页面 {page_num}/{len(page_images)}...")
                
                # 读取图片并转base64
                with open(img_path, "rb") as f:
                    img_base64 = base64.b64encode(f.read()).decode()
                
                # 调用DeepSeek-OCR API
                page_md = self._call_deepseek_ocr_api(img_base64, base_url)
                
                if page_md:
                    # 如果这一页有提取到的图片，添加引用
                    if page_num in figure_map:
                        figures_md = "\n\n".join([
                            f"![Figure]({output_name}_images/{fig})"
                            for fig in figure_map[page_num]
                        ])
                        page_md = page_md + f"\n\n{figures_md}"
                    
                    markdown_parts.append(f"<!-- Page {page_num} -->\n\n{page_md}")
                else:
                    markdown_parts.append(f"<!-- Page {page_num}: OCR失败 -->\n\n")
                
                # 删除页面截图（只保留figures）
                if self.extract_images and figure_count > 0:
                    img_path.unlink(missing_ok=True)
            
            # ============ 步骤4: 合并并保存 ============
            markdown_content = "\n\n---\n\n".join(markdown_parts)
            
            md_path = output_dir / f"{output_name}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 清理页面截图（如果没有提取figures）
            if not self.extract_images:
                import shutil
                shutil.rmtree(images_dir, ignore_errors=True)
                images_dir = None
            elif figure_count == 0:
                # 删除空的图片目录
                for img_path in images_dir.glob("page_*.png"):
                    img_path.unlink(missing_ok=True)
                if not any(images_dir.iterdir()):
                    images_dir.rmdir()
                    images_dir = None
            
            print(f"✓ 转换成功: {md_path}")
            if figure_count > 0:
                print(f"  提取图片: {figure_count} 张")
            
            return ConversionResult(
                success=True,
                markdown_path=str(md_path),
                images_dir=str(images_dir) if images_dir and images_dir.exists() else None,
                image_count=figure_count,
                message="转换成功（DeepSeek-OCR云端API）",
                backend=ConversionBackend.DEEPSEEK_OCR
            )
            
        except Exception as e:
            import traceback
            return ConversionResult(
                success=False,
                message=f"DeepSeek-OCR转换失败: {str(e)}\n{traceback.format_exc()}",
                backend=ConversionBackend.DEEPSEEK_OCR
            )
    
    def _call_deepseek_ocr_api(self, img_base64: str, base_url: str) -> str:
        """调用硅基流动的DeepSeek-OCR API"""
        import requests
        
        # OCR提示词（针对学术论文优化）
        prompt = """请将这张学术论文页面的内容转换为Markdown格式。要求：
1. 保持原文的段落结构和格式
2. 标题使用适当的 # 级别
3. 数学公式使用 LaTeX 格式（行内用$，行间用$$）
4. 表格使用Markdown表格格式
5. 保持参考文献格式
6. 只输出识别到的内容，不要添加任何解释"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-ai/DeepSeek-OCR",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1  # 低温度，提高一致性
        }
        
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"    DeepSeek-OCR API调用失败: {e}")
            return ""
    
    def _convert_with_dots_ocr(
        self,
        pdf_path: Path,
        output_dir: Path,
        output_name: str,
    ) -> ConversionResult:
        """使用dots.ocr转换（待实现）"""
        return ConversionResult(
            success=False,
            message="dots_ocr后端尚未完全实现，请使用其他后端",
            backend=ConversionBackend.DOTS_OCR
        )
    
    def convert_batch(
        self,
        pdf_paths: List[str],
        output_dir: str,
        progress_callback=None,
    ) -> List[ConversionResult]:
        """
        批量转换PDF
        
        Args:
            pdf_paths: PDF文件路径列表
            output_dir: 输出目录
            progress_callback: 进度回调函数 (current, total, filename)
        
        Returns:
            转换结果列表
        """
        results = []
        total = len(pdf_paths)
        
        for idx, pdf_path in enumerate(pdf_paths, 1):
            if progress_callback:
                progress_callback(idx, total, Path(pdf_path).name)
            
            result = self.convert(pdf_path, output_dir)
            results.append(result)
        
        return results


def convert_pdf_to_markdown(
    pdf_path: str,
    output_dir: Optional[str] = None,
    backend: str = "marker",
    extract_images: bool = True,
    use_llm: bool = False,
) -> ConversionResult:
    """
    便捷函数：将PDF转换为Markdown
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        backend: 转换后端 (marker/pymupdf/markitdown/pdfplumber/deepseek_ocr/llm_api)
        extract_images: 是否提取图片
        use_llm: 是否使用LLM增强
    
    Returns:
        ConversionResult 转换结果
    
    使用示例：
        result = convert_pdf_to_markdown("paper.pdf")
        if result.success:
            print(f"转换完成: {result.markdown_path}")
    """
    backend_enum = ConversionBackend(backend)
    converter = PdfConverter(
        backend=backend_enum,
        extract_images=extract_images,
        use_llm=use_llm,
    )
    return converter.convert(pdf_path, output_dir)


def smart_convert_pdf(
    pdf_path: str,
    output_dir: Optional[str] = None,
    api_key: Optional[str] = None,
    extract_images: bool = True,
) -> ConversionResult:
    """
    智能PDF转换：自动检测PDF类型并选择最佳后端
    
    智能路由逻辑：
    1. 检测PDF是否有文本层
    2. 如果有文本层，检测文本是否乱码
    3. 根据检测结果自动选择：
       - 文本PDF → pdfplumber（资源占用低，速度快）
       - 扫描件PDF → deepseek_ocr（云端OCR，适合低配服务器）
       - 乱码PDF → deepseek_ocr（修复编码问题）
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录（默认与PDF同目录）
        api_key: DeepSeek-OCR API密钥（用于扫描件识别）
                 默认从环境变量 SILICONFLOW_API_KEY 获取
        extract_images: 是否提取图片
    
    Returns:
        ConversionResult 转换结果，包含：
        - success: 是否成功
        - markdown_path: Markdown文件路径
        - markdown_content: Markdown内容
        - backend_used: 实际使用的后端
        - pdf_type: 检测到的PDF类型 (text_pdf/scanned_pdf/garbled_text)
        - error: 错误信息（如果失败）
    
    使用示例：
        # 基本用法（自动检测和转换）
        result = smart_convert_pdf("paper.pdf")
        if result.success:
            print(f"使用后端: {result.backend_used}")
            print(f"PDF类型: {result.pdf_type}")
            print(f"输出文件: {result.markdown_path}")
        
        # 指定API密钥（用于扫描件）
        result = smart_convert_pdf(
            "scanned_paper.pdf",
            api_key="your-siliconflow-api-key"
        )
    
    环境变量：
        SILICONFLOW_API_KEY: DeepSeek-OCR API密钥
    """
    converter = PdfConverter(
        backend=ConversionBackend.PDFPLUMBER,  # 默认后端，smart_convert会覆盖
        extract_images=extract_images,
        api_key=api_key,
    )
    return converter.smart_convert(pdf_path, output_dir)


def post_process_markdown(
    markdown_path: str,
    fix_equations: bool = True,
    fix_tables: bool = True,
    fix_headings: bool = True,
    add_toc: bool = False,
) -> str:
    """
    对转换后的Markdown进行后处理优化
    
    Args:
        markdown_path: Markdown文件路径
        fix_equations: 修复数学公式格式
        fix_tables: 修复表格格式
        fix_headings: 修复标题层级
        add_toc: 添加目录
    
    Returns:
        处理后的Markdown内容
    """
    with open(markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if fix_equations:
        # 修复行内公式
        content = re.sub(r'\$\s+', r'$', content)
        content = re.sub(r'\s+\$', r'$', content)
        
        # 修复行间公式
        content = re.sub(r'\$\$\s+', r'$$\n', content)
        content = re.sub(r'\s+\$\$', r'\n$$', content)
    
    if fix_tables:
        # 确保表格前后有空行
        content = re.sub(r'([^\n])\n(\|)', r'\1\n\n\2', content)
        content = re.sub(r'(\|)\n([^\n|])', r'\1\n\n\2', content)
    
    if fix_headings:
        # 规范化标题格式
        content = re.sub(r'^(#{1,6})\s*([^\n]+)', r'\1 \2', content, flags=re.MULTILINE)
    
    if add_toc:
        # 生成目录
        toc_lines = ["# 目录\n"]
        headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        
        for level, title in headings:
            if title != "目录":
                indent = "  " * (len(level) - 1)
                anchor = re.sub(r'[^\w\s-]', '', title.lower())
                anchor = re.sub(r'\s+', '-', anchor)
                toc_lines.append(f"{indent}- [{title}](#{anchor})")
        
        toc_lines.append("\n---\n")
        toc = "\n".join(toc_lines)
        content = toc + content
    
    # 保存处理后的文件
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return content


# 命令行接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PDF转Markdown转换器")
    parser.add_argument("pdf_path", help="PDF文件路径")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument(
        "-b", "--backend",
        choices=["marker", "pymupdf", "markitdown", "pdfplumber", "docling", "llm_api", "dots_ocr", "deepseek_ocr"],
        default="pdfplumber",
        help="转换后端 (默认: pdfplumber；推荐低配服务器使用: deepseek_ocr)"
    )
    parser.add_argument(
        "--api-key",
        help="LLM API密钥（用于llm_api后端）"
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="不提取图片"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="使用LLM增强转换质量"
    )
    parser.add_argument(
        "--post-process",
        action="store_true",
        help="后处理优化"
    )
    parser.add_argument(
        "--add-toc",
        action="store_true",
        help="添加目录"
    )
    
    args = parser.parse_args()
    
    # 创建转换器
    backend_enum = ConversionBackend(args.backend)
    converter = PdfConverter(
        backend=backend_enum,
        extract_images=not args.no_images,
        use_llm=args.use_llm,
        api_key=args.api_key,
    )
    
    result = converter.convert(args.pdf_path, output_dir=args.output)
    
    if result.success:
        print(f"\n转换成功!")
        print(f"  Markdown: {result.markdown_path}")
        if result.images_dir:
            print(f"  图片目录: {result.images_dir}")
            print(f"  图片数量: {result.image_count}")
        
        if args.post_process:
            print("\n正在后处理...")
            post_process_markdown(
                result.markdown_path,
                add_toc=args.add_toc,
            )
            print("后处理完成")
    else:
        print(f"\n转换失败: {result.message}")
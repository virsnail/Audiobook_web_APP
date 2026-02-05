"""
EPUB 处理工具（方案2专用）

此模块专门用于处理 EPUB 格式电子书，完全独立于方案1的 TXT 处理逻辑。
主要功能：
1. 解压 EPUB 文件（EPUB 本质上是 ZIP 格式）
2. 解析 EPUB 结构（container.xml → OPF → NCX/NAV）
3. 提取章节信息和 HTML 文件
4. 生成 EPUB manifest，关联音频和对齐文件
"""

import os
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


def extract_epub(epub_path: str, output_dir: str) -> Path:
    """
    解压 EPUB 文件到指定目录
    
    Args:
        epub_path: EPUB 文件路径
        output_dir: 输出目录
        
    Returns:
        解压后的目录路径
    """
    epub_extract_dir = Path(output_dir) / "epub"
    epub_extract_dir.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(epub_extract_dir)
    
    return epub_extract_dir


def find_container_xml(epub_root: Path) -> Optional[Path]:
    """
    查找 container.xml 文件
    
    根据 EPUB 标准，container.xml 总是在 META-INF/container.xml
    """
    # 标准路径
    standard_path = epub_root / "META-INF" / "container.xml"
    if standard_path.exists():
        return standard_path
    
    # 如果标准路径不存在，搜索整个目录树
    for root, dirs, files in os.walk(epub_root):
        for file in files:
            if file.lower() == "container.xml":
                return Path(root) / file
    
    return None


def parse_container_xml(container_path: Path) -> Optional[Path]:
    """
    解析 container.xml，获取 OPF 文件路径
    
    Args:
        container_path: container.xml 文件路径
        
    Returns:
        OPF 文件的绝对路径
    """
    try:
        tree = ET.parse(container_path)
        root = tree.getroot()
        
        # EPUB 的 container 命名空间
        ns = {'container': 'urn:oasis:names:tc:opendocument:xmlns:container'}
        
        # 查找 rootfile 元素
        rootfile = root.find('.//container:rootfile', ns)
        
        if rootfile is not None:
            opf_relative_path = rootfile.get('full-path')
            opf_absolute_path = container_path.parent.parent / opf_relative_path
            
            if opf_absolute_path.exists():
                return opf_absolute_path
    
    except Exception as e:
        print(f"Error parsing container.xml: {e}")
    
    return None


def parse_opf_file(opf_path: Path) -> Dict:
    """
    解析 OPF 文件，提取书籍结构信息
    
    Returns:
        {
            'metadata': {'title': ..., 'creator': ...},
            'manifest': {item_id: {'href': ..., 'media_type': ...}},
            'spine': [{'id': ..., 'href': ..., 'order': ...}],
            'opf_dir': Path
        }
    """
    try:
        tree = ET.parse(opf_path)
        root = tree.getroot()
        
        # OPF 命名空间
        ns = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }
        
        result = {
            'metadata': {},
            'manifest': {},
            'spine': [],
            'opf_dir': opf_path.parent
        }
        
        # 提取元数据
        title_elem = root.find('.//dc:title', ns)
        if title_elem is not None and title_elem.text:
            result['metadata']['title'] = title_elem.text
        
        creator_elem = root.find('.//dc:creator', ns)
        if creator_elem is not None and creator_elem.text:
            result['metadata']['creator'] = creator_elem.text
        
        # 解析 manifest（所有资源文件）
        manifest_elem = root.find('.//opf:manifest', ns)
        if manifest_elem is not None:
            for item in manifest_elem.findall('opf:item', ns):
                item_id = item.get('id')
                href = item.get('href')
                media_type = item.get('media-type')
                properties = item.get('properties', '')
                
                if item_id and href:
                    result['manifest'][item_id] = {
                        'href': href,
                        'media_type': media_type,
                        'properties': properties
                    }
        
        # 解析 spine（阅读顺序）
        spine_elem = root.find('.//opf:spine', ns)
        if spine_elem is not None:
            for idx, itemref in enumerate(spine_elem.findall('opf:itemref', ns), 1):
                idref = itemref.get('idref')
                if idref and idref in result['manifest']:
                    manifest_item = result['manifest'][idref]
                    result['spine'].append({
                        'order': idx,
                        'id': idref,
                        'href': manifest_item['href'],
                        'media_type': manifest_item['media_type'],
                        'properties': manifest_item.get('properties', '')
                    })
        
        return result
        
    except Exception as e:
        print(f"Error parsing OPF file: {e}")
        return {
            'metadata': {},
            'manifest': {},
            'spine': [],
            'opf_dir': opf_path.parent
        }


def parse_ncx_file(opf_dir: Path) -> Dict[str, str]:
    """
    解析 NCX 文件，获取章节标题
    
    Returns:
        {href: title} 映射
    """
    ncx_titles = {}
    
    try:
        # 在同一目录下查找 NCX 文件
        ncx_files = list(opf_dir.glob("*.ncx"))
        
        if not ncx_files:
            return ncx_titles
        
        ncx_path = ncx_files[0]
        tree = ET.parse(ncx_path)
        root = tree.getroot()
        
        # NCX 命名空间
        ns = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
        
        # 递归提取所有 navPoint
        def extract_nav_points(element, level=0):
            for nav_point in element.findall('ncx:navPoint', ns):
                # 获取标题
                nav_label = nav_point.find('ncx:navLabel/ncx:text', ns)
                title = nav_label.text if nav_label is not None and nav_label.text else ""
                
                # 获取文件路径
                content = nav_point.find('ncx:content', ns)
                if content is not None:
                    src = content.get('src')
                    # 去掉锚点
                    file_path = src.split('#')[0] if src else ""
                    if file_path and title:
                        ncx_titles[file_path] = title
                
                # 递归处理子章节
                extract_nav_points(nav_point, level + 1)
        
        nav_map = root.find('ncx:navMap', ns)
        if nav_map is not None:
            extract_nav_points(nav_map)
    
    except Exception as e:
        print(f"Error parsing NCX file: {e}")
    
    return ncx_titles


def classify_chapter_type(filename: str, file_id: str) -> str:
    """
    根据文件名和 ID 判断章节类型
    """
    filename_lower = filename.lower()
    file_id_lower = file_id.lower()
    
    # 简化的分类规则
    patterns = {
        'Cover': [r'cover', r'_cvi_'],
        'Title': [r'title', r'_tp_'],
        'Copyright': [r'copyright', r'_cop_'],
        'Contents': [r'toc', r'contents?', r'inlinetoc'],
        'Introduction': [r'intro', r'_itr_'],
        'Chapter': [r'chapter', r'_c\d{3,4}_', r'^c\d{3,4}'],
    }
    
    for type_name, pattern_list in patterns.items():
        for pattern in pattern_list:
            if re.search(pattern, filename_lower) or re.search(pattern, file_id_lower):
                return type_name
    
    return 'Content'


def analyze_epub_structure(epub_dir: Path) -> Dict:
    """
    分析 EPUB 结构，生成章节信息
    
    Returns:
        {
            'chapters': [
                {
                    'id': 章节ID,
                    'order': 顺序,
                    'title': 标题,
                    'href': HTML文件相对路径,
                    'full_path': HTML文件绝对路径,
                    'type': 章节类型
                }
            ],
            'metadata': {...}
        }
    """
    # 1. 查找 container.xml
    container_path = find_container_xml(epub_dir)
    if not container_path:
        raise ValueError("Cannot find container.xml in EPUB")
    
    # 2. 解析 container.xml 获取 OPF 路径
    opf_path = parse_container_xml(container_path)
    if not opf_path:
        raise ValueError("Cannot find OPF file")
    
    # 3. 解析 OPF
    opf_data = parse_opf_file(opf_path)
    
    # 4. 解析 NCX 获取标题
    ncx_titles = parse_ncx_file(opf_data['opf_dir'])
    
    # 5. 生成章节列表
    chapters = []
    for spine_item in opf_data['spine']:
        href = spine_item['href']
        full_path = opf_data['opf_dir'] / href
        
        # 获取标题
        title = ncx_titles.get(href, '')
        
        # 分类
        chapter_type = classify_chapter_type(href, spine_item['id'])
        
        # 计算相对于解压根目录的路径
        try:
            file_path = full_path.relative_to(epub_dir)
            file_path_str = str(file_path)
        except ValueError:
            # Fallback if path is weird
            file_path_str = href
        
        chapters.append({
            'id': spine_item['id'],
            'order': spine_item['order'],
            'title': title,
            'href': href,
            'file_path': file_path_str,
            'full_path': str(full_path),
            'type': chapter_type
        })
    
    return {
        'chapters': chapters,
        'metadata': opf_data['metadata']
    }


def create_epub_manifest(epub_dir: Path, align_files: List[str]) -> Dict:
    """
    创建 EPUB manifest，关联章节和音频对齐文件
    
    Args:
        epub_dir: EPUB 解压目录
        align_files: 对齐文件列表 (例如 ['ch001_align.json', 'ch002_align.json'])
        
    Returns:
        EPUB manifest 数据
    """
    # 分析 EPUB 结构
    structure = analyze_epub_structure(epub_dir)
    
    # 提取章节编号从对齐文件
    # 例如: ch001_align.json -> 001
    align_chapter_ids = []
    pattern = re.compile(r'ch(\d+)_align\.json')
    for align_file in align_files:
        match = pattern.match(align_file)
        if match:
            align_chapter_ids.append(match.group(1))
    
    # 过滤出主要内容章节（排除封面、版权页等）
    content_chapters = [ch for ch in structure['chapters'] if ch['type'] == 'Chapter' or ch['type'] == 'Content']
    
    # 关联章节和对齐文件
    manifest_chapters = []
    for i, chapter in enumerate(content_chapters):
        if i < len(align_chapter_ids):
            chapter_id = align_chapter_ids[i]
            manifest_chapters.append({
                'id': chapter_id,
                'epub_id': chapter['id'],
                'order': chapter['order'],
                'title': chapter['title'],
                'title': chapter['title'],
                'href': chapter['href'],
                'file_path': chapter.get('file_path', chapter['href']),
                'has_audio': True,
                'audio_file': f'ch{chapter_id}_audio.mp3',
                'alignment_file': f'ch{chapter_id}_align.json'
            })
    
    return {
        'type': 'epub',
        'metadata': structure['metadata'],
        'chapters': manifest_chapters,
        'total_chapters': len(manifest_chapters)
    }


def extract_cover_image(epub_dir: Path, output_dir: Path) -> Optional[str]:
    """
    从 EPUB 中提取封面图片并保存到输出目录
    
    Args:
        epub_dir: EPUB 解压目录 (包含 META-INF)
        output_dir: 目标输出目录 (保存 cover.jpg 的位置)
        
    Returns:
        封面相对路径 (例如 "cover.jpg") 或 None
    """
    try:
        # 1. 查找 container.xml
        container_path = find_container_xml(epub_dir)
        if not container_path:
            return None
        
        # 2. 获取 OPF 路径
        opf_path = parse_container_xml(container_path)
        if not opf_path:
            return None
            
        # 3. 解析 OPF
        tree = ET.parse(opf_path)
        root = tree.getroot()
        ns = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }
        
        cover_href = None
        
        # 策略 A: 查找 manifest 中 properties="cover-image" 的 item
        # <item id="cover" href="cover.jpg" media-type="image/jpeg" properties="cover-image" />
        manifest_elem = root.find('.//opf:manifest', ns)
        if manifest_elem is not None:
            for item in manifest_elem.findall('opf:item', ns):
                props = item.get('properties', '')
                if 'cover-image' in props:
                    cover_href = item.get('href')
                    break
        
        # 策略 B: 查找 metadata 中的 meta name="cover"
        # <meta name="cover" content="cover-image-item-id" />
        if not cover_href:
            metadata_elem = root.find('.//opf:metadata', ns)
            if metadata_elem is not None:
                for meta in metadata_elem.findall('opf:meta', ns):
                    if meta.get('name') == 'cover':
                        cover_id = meta.get('content')
                        # 根据 ID 找 href
                        if manifest_elem is not None:
                            for item in manifest_elem.findall('opf:item', ns):
                                if item.get('id') == cover_id:
                                    cover_href = item.get('href')
                                    break
                        break
        
        # 4. 如果找到封面，复制文件
        if cover_href:
            # cover_href 是相对于 OPF 文件的路径
            src_path = opf_path.parent / cover_href
            if src_path.exists():
                # 确定扩展名
                ext = src_path.suffix.lower()
                if not ext: ext = ".jpg"
                
                target_name = f"cover{ext}"
                target_path = Path(output_dir) / target_name
                
                import shutil
                shutil.copy2(src_path, target_path)
                return target_name
                
    except Exception as e:
        print(f"Error extracting cover: {e}")
        
    return None

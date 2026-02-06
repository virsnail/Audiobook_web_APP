"""
TTS 文本转语音工具模块

使用 Edge-TTS 将文本转换为有声书格式：
- 生成 MP3 音频文件
- 生成词级别时间对齐 JSON
- 按预估时长分割长文本

参考: 用户提供的 Epub07 脚本
"""

import os
import re
import json
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TTSConfig:
    """TTS 配置"""
    
    # Edge-TTS 语音
    VOICE = 'zh-CN-YunyangNeural'
    
    # 章节片段时长限制（分钟）
    MAX_MINUTES_PER_SEGMENT = 8.0
    
    # 片段间静音间隔（秒）
    SEGMENT_SILENCE_DURATION = 1.0
    
    # FFmpeg 配置
    FFMPEG_COMMAND = 'ffmpeg'
    FFMPEG_BITRATE = '128k'


class TokenAnalyzer:
    """文本分析器"""
    
    @staticmethod
    def analyze_text(text: str) -> Dict[str, any]:
        """分析文本，返回统计数据"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = re.findall(r'\b[a-zA-Z]+\b', text)
        english_word_count = len(english_words)
        total_words = chinese_chars + english_word_count
        
        # 中文：约220字/分钟，英文：约200词/分钟
        chinese_minutes = chinese_chars / 220.0
        english_minutes = english_word_count / 200.0
        estimated_minutes = chinese_minutes + english_minutes
        
        return {
            'chinese_chars': chinese_chars,
            'english_words': english_word_count,
            'total_words': total_words,
            'estimated_minutes': estimated_minutes
        }


class MarkdownCleaner:
    """Markdown 内容清洗器"""
    
    @staticmethod
    def md_to_txt(md_content: str) -> str:
        """
        将 Markdown 内容转换为纯文本
        
        功能：
        - 移除代码块、链接、图片、HTML标签
        - 移除 Markdown 格式标记（标题#、粗体**、斜体*）
        - 移除列表标记、引用、表格
        - 清理多余空行
        - 如果输入已经是纯文本，不会出错
        """
        text = md_content
        
        # 移除代码块
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)
        
        # 移除链接但保留文本 [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # 移除图片 ![alt](url)
        text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除Markdown标题标记 (# ## ###) - 允许行首空格
        text = re.sub(r'^\s*#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # 移除水平线 (---, ***, ___, ===) - 允许行首/行尾空格
        text = re.sub(r'^\s*[-=_*—]{3,}\s*$', '', text, flags=re.MULTILINE)
        
        # 移除列表标记 (*, -, +, 1.) - 允许行首空格
        text = re.sub(r'^\s*[\*\-\+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        
        # 移除引用标记 (>)
        text = re.sub(r'^\s*>\s+', '', text, flags=re.MULTILINE)
        
        # 移除粗体和斜体 (*** ** * ___ __ _) - 使用非贪婪匹配
        # 这里使用简单循环来确保移除干净（例如嵌套情况）
        for _ in range(2):
            text = re.sub(r'\*\*\*([^\n]+?)\*\*\*', r'\1', text)
            text = re.sub(r'\*\*([^\n]+?)\*\*', r'\1', text)
            text = re.sub(r'\*([^\n]+?)\*', r'\1', text)
            text = re.sub(r'___([^\n]+?)___', r'\1', text)
            text = re.sub(r'__([^\n]+?)__', r'\1', text)
            text = re.sub(r'_([^\n]+?)_', r'\1', text)
        
        # 移除表格 (|xxx|xxx|)
        text = re.sub(r'\|[^\n]+\|', '', text)
        
        # 清理多余空行 (3个或更多连续换行 -> 2个换行)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 删除所有完全空白的行
        text = re.sub(r'^\s*$\n', '', text, flags=re.MULTILINE)
        
        return text.strip()

    @staticmethod
    def clean_copyright_text(text: str) -> str:
        """
        从文本中提取引号中的内容（如以 protected by copyright. 结尾时）
        并处理 Kindle Edition 后缀
        """
        # 处理版权保护信息
        if re.search(r'protected by copyright\.\s*$', text) or re.search(r'受版权保护。\s*$', text):
            match = re.search(r'[""\u201c](.*?)[""\u201d]', text, re.DOTALL)
            if match:
                text = match.group(1).strip()
        
        # 新增功能：如果最后一行以 "Kindle Edition." 结尾，删除最后一行
        if re.search(r'Kindle Edition\.\s*$', text):
            lines = text.split('\n')
            if len(lines) > 1:
                text = '\n'.join(lines[:-1])
                
        return text


def split_text_by_minutes(text: str, max_minutes: float = TTSConfig.MAX_MINUTES_PER_SEGMENT) -> List[str]:
    """按预估时长拆分文本"""
    analysis = TokenAnalyzer.analyze_text(text)
    
    if analysis['estimated_minutes'] <= max_minutes:
        return [text]
    
    paragraphs = text.split('\n')
    paragraphs = [p for p in paragraphs if p.strip()]
    
    segments = []
    current_segment = []
    current_minutes = 0.0
    
    for para in paragraphs:
        para_analysis = TokenAnalyzer.analyze_text(para)
        para_minutes = para_analysis['estimated_minutes']
        
        # 单段超长，直接作为独立片段
        if para_minutes > max_minutes:
            if current_segment:
                segments.append('\n\n'.join(current_segment))
                current_segment = []
                current_minutes = 0.0
            segments.append(para)
            continue
        
        if current_minutes + para_minutes <= max_minutes:
            current_segment.append(para)
            current_minutes += para_minutes
        else:
            if current_segment:
                segments.append('\n\n'.join(current_segment))
            current_segment = [para]
            current_minutes = para_minutes
    
    if current_segment:
        segments.append('\n\n'.join(current_segment))
    
    return segments


async def run_edge_tts_with_alignment(
    text: str, 
    voice: str, 
    output_file: str, 
    align_file: str
) -> Tuple[bool, float, List[Dict]]:
    """
    使用 Edge TTS 生成音频，同时获取词级别对齐数据
    
    Returns:
        (success: bool, duration: float, alignment_data: List[Dict])
    """
    try:
        import edge_tts
    except ImportError:
        logger.error("edge_tts not installed. Run: pip install edge-tts")
        return False, 0.0, []
    
    alignment_data = []
    last_end_time = 0.0
    
    try:
        communicate = edge_tts.Communicate(text, voice, boundary='WordBoundary')
        
        with open(output_file, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start_time = chunk["offset"] / 10000000
                    duration = chunk["duration"] / 10000000
                    end_time = start_time + duration
                    
                    alignment_data.append({
                        "text": chunk["text"],
                        "start": round(start_time, 3),
                        "end": round(end_time, 3)
                    })
                    
                    last_end_time = max(last_end_time, end_time)
        
        with open(align_file, 'w', encoding='utf-8') as f:
            json.dump(alignment_data, f, ensure_ascii=False, indent=2)
        
        return True, last_end_time, alignment_data
        
    except Exception as e:
        logger.error(f"Edge TTS error: {str(e)}")
        return False, 0.0, []


def merge_audio_files_with_silence(
    audio_files: List[str], 
    output_path: str, 
    silence_duration: float = TTSConfig.SEGMENT_SILENCE_DURATION
) -> bool:
    """合并多个音频文件，片段之间添加静音间隔"""
    if len(audio_files) == 1:
        shutil.copy(audio_files[0], output_path)
        return True
    
    try:
        input_args = []
        for f in audio_files:
            input_args.extend(['-i', os.path.abspath(f)])
        
        if silence_duration > 0:
            filter_parts = []
            for i in range(len(audio_files)):
                if i < len(audio_files) - 1:
                    filter_parts.append(f"[{i}:a]apad=pad_dur={silence_duration}[a{i}]")
                else:
                    filter_parts.append(f"[{i}:a]anull[a{i}]")
            inputs_list = ''.join([f"[a{i}]" for i in range(len(audio_files))])
            concat_filter = f"{inputs_list}concat=n={len(audio_files)}:v=0:a=1[out]"
            filter_complex = ';'.join(filter_parts) + ';' + concat_filter
        else:
            filter_parts = [f"[{i}:a]" for i in range(len(audio_files))]
            filter_complex = f"{''.join(filter_parts)}concat=n={len(audio_files)}:v=0:a=1[out]"
        
        cmd = [
            TTSConfig.FFMPEG_COMMAND,
            *input_args,
            '-filter_complex', filter_complex,
            '-map', '[out]',
            '-codec:a', 'libmp3lame',
            '-b:a', TTSConfig.FFMPEG_BITRATE,
            '-y',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"合并音频失败: {str(e)}")
        return False


def merge_alignment_data(
    all_alignments: List[List[Dict]], 
    segment_durations: List[float], 
    silence_duration: float = TTSConfig.SEGMENT_SILENCE_DURATION
) -> List[Dict]:
    """合并多个片段的对齐数据，调整时间偏移"""
    merged = []
    time_offset = 0.0
    
    for i, alignment in enumerate(all_alignments):
        for item in alignment:
            merged.append({
                "text": item["text"],
                "start": round(item["start"] + time_offset, 3),
                "end": round(item["end"] + time_offset, 3)
            })
        
        if i < len(segment_durations):
            time_offset += segment_durations[i]
            if i < len(segment_durations) - 1:
                time_offset += silence_duration
    
    return merged


async def process_chapter_with_segments(
    chapter_text: str, 
    voice: str, 
    mp3_path: str, 
    align_path: str, 
    temp_dir: str
) -> Tuple[bool, float]:
    """处理可能需要拆分的章节：拆分 -> 分别TTS -> 合并"""
    segments = split_text_by_minutes(chapter_text, TTSConfig.MAX_MINUTES_PER_SEGMENT)
    
    if len(segments) == 1:
        success, duration, _ = await run_edge_tts_with_alignment(
            chapter_text, voice, mp3_path, align_path
        )
        return success, duration
    
    logger.info(f"章节过长，拆分为 {len(segments)} 个片段")
    
    segment_files = []
    all_alignments = []
    segment_durations = []
    
    for i, segment in enumerate(segments):
        seg_mp3 = os.path.join(temp_dir, f"seg_{i:03d}.mp3")
        seg_align = os.path.join(temp_dir, f"seg_{i:03d}.json")
        
        success, duration, alignment = await run_edge_tts_with_alignment(
            segment, voice, seg_mp3, seg_align
        )
        
        if success:
            segment_files.append(seg_mp3)
            all_alignments.append(alignment)
            segment_durations.append(duration)
        else:
            return False, 0.0
        
        await asyncio.sleep(0.5)  # Rate limiting
    
    # 合并音频
    silence_duration = TTSConfig.SEGMENT_SILENCE_DURATION
    if not merge_audio_files_with_silence(segment_files, mp3_path, silence_duration):
        return False, 0.0
    
    # 合并对齐数据
    merged_alignment = merge_alignment_data(all_alignments, segment_durations, silence_duration)
    with open(align_path, 'w', encoding='utf-8') as f:
        json.dump(merged_alignment, f, ensure_ascii=False, indent=2)
    
    total_duration = sum(segment_durations) + (len(segment_durations) - 1) * silence_duration
    
    # 清理临时文件
    for f in segment_files:
        try:
            os.remove(f)
        except:
            pass
    
    return True, total_duration


def get_mp3_duration(file_path: str) -> Optional[float]:
    """获取 MP3 文件时长（秒）"""
    try:
        from mutagen.mp3 import MP3
        audio = MP3(file_path)
        return audio.info.length
    except Exception:
        return None


async def process_text_to_audiobook(
    raw_text: str, 
    output_dir: str,
    book_title: str = "Untitled"
) -> Optional[Dict]:
    """
    将纯文本转换为有声书格式
    
    生成文件:
    - ch001_audio.mp3, ch001_text.txt, ch001_align.json
    - manifest.json
    
    Returns:
        manifest 数据，失败返回 None
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 按时长分割成章节
    chapters = split_text_by_minutes(raw_text, TTSConfig.MAX_MINUTES_PER_SEGMENT)
    
    chapters_info = []
    voice = TTSConfig.VOICE
    
    for idx, chapter_text in enumerate(chapters, 1):
        file_prefix = f"ch{idx:03d}"
        txt_path = os.path.join(output_dir, f"{file_prefix}_text.txt")
        mp3_path = os.path.join(output_dir, f"{file_prefix}_audio.mp3")
        align_path = os.path.join(output_dir, f"{file_prefix}_align.json")
        
        # 保存文本
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(chapter_text)
        
        analysis = TokenAnalyzer.analyze_text(chapter_text)
        logger.info(f"处理章节 {idx}/{len(chapters)}: {analysis['total_words']} 字")
        
        # 创建临时目录
        temp_dir = os.path.join(output_dir, f".temp_{file_prefix}")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            success, duration = await process_chapter_with_segments(
                chapter_text, voice, mp3_path, align_path, temp_dir
            )
            
            if success:
                chapters_info.append({
                    "id": idx,
                    "title": f"Chapter {idx}",
                    "audio_file": f"{file_prefix}_audio.mp3",
                    "align_file": f"{file_prefix}_align.json",
                    "text_file": f"{file_prefix}_text.txt",
                    "duration": round(duration, 2),
                    "words": analysis['total_words']
                })
            else:
                logger.error(f"章节 {idx} 处理失败")
                return None
        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # 章节间休息
        if idx < len(chapters):
            await asyncio.sleep(1.0)
    
    # 生成 manifest
    manifest = {
        "book_title": book_title,
        "created_at": datetime.now().isoformat(),
        "total_chapters": len(chapters_info),
        "total_duration": round(sum(ch.get('duration', 0) for ch in chapters_info), 2),
        "total_words": sum(ch.get('words', 0) for ch in chapters_info),
        "chapters": chapters_info
    }
    
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    logger.info(f"有声书生成完成: {len(chapters_info)} 章节, 总时长 {manifest['total_duration']/60:.1f} 分钟")
    
    return manifest

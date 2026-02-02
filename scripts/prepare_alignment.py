#!/usr/bin/env python3
"""
音频-文本对齐数据准备脚本 in Macbook M2

使用 stable-ts (MLX) 生成音频和文本的对齐数据
支持批量处理 00001.mp3 ~ 99999.mp3 格式的文件

用法:
    1. 直接在下方【用户配置区域】设置参数
    2. 运行: python prepare_alignment.py
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

try:
    import stable_whisper
    from tqdm import tqdm
except ImportError:
    print("错误: 请先安装依赖")
    print("运行: pip install -r requirements.txt")
    sys.exit(1)


# ============================================================
# 用户配置区域 - 在这里设置你的参数
# ============================================================

# 输入文件夹路径（包含 00001.mp3, 00001.txt 等文件）
INPUT_FOLDER = "/Users/max/dev/Audiobook_web_APP/audiobook_files"

# 输出文件路径
OUTPUT_ALIGNMENT_JSON = "alignment.json"
OUTPUT_MERGED_AUDIO = "merged_book.mp3"
OUTPUT_MERGED_TXT = "merged_book.txt"  # 合并后的文本文件

# Whisper 模型大小: "tiny", "base", "small", "medium", "large"
MODEL_SIZE = "medium"

# 语言代码: "zh" (中文), "en" (英文), "ja" (日文) 等
LANGUAGE = "zh"

# 是否合并音频文件
MERGE_AUDIO = True

# 音频文件之间的间隔时长（秒）
GAP_SECONDS = 1.0

# 是否合并文本文件
MERGE_TXT = True

# ============================================================
# 以下是脚本代码，无需修改
# ============================================================




def load_audio_files(input_dir: Path) -> List[tuple]:
    """
    加载音频文件和对应的文本文件
    
    返回: [(audio_path, text_path, index), ...]
    """
    files = []
    
    for audio_file in sorted(input_dir.glob("*.mp3")):
        # 获取文件编号 (例如 00001.mp3 -> 00001)
        stem = audio_file.stem
        
        # 查找对应的文本文件
        txt_file = input_dir / f"{stem}.txt"
        
        if txt_file.exists():
            files.append((audio_file, txt_file, stem))
        else:
            print(f"警告: 找不到 {stem}.txt，跳过 {audio_file.name}")
    
    return files


def transcribe_with_alignment(
    audio_path: Path,
    text_path: Path,
    model_name: str = "medium",
    language: str = "zh"
) -> Dict[str, Any]:
    """
    使用 stable-ts 对单个音频文件进行对齐
    
    参数:
        audio_path: 音频文件路径
        text_path: 文本文件路径
        model_name: Whisper 模型名称
        language: 语言代码
    
    返回:
        对齐结果字典（包含词级别时间戳）
    """
    # 读取参考文本
    with open(text_path, 'r', encoding='utf-8') as f:
        reference_text = f.read().strip()
    
    # 尝试使用 MLX 加速
    use_mlx = False
    try:
        import mlx_whisper
        print(f"  加载模型: {model_name} (MLX GPU 加速)")
        # 使用 mlx-whisper 进行转录（GPU 加速）
        result_mlx = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=f"mlx-community/whisper-{model_name}-mlx",
            verbose=False,
            language=language,
            word_timestamps=True  # 启用词级别时间戳
        )
        use_mlx = True
        print("  ✓ MLX GPU 加速已启用")
        
        # 提取词级别对齐数据
        segments = []
        segment_id = 0
        
        for segment in result_mlx["segments"]:
            # 检查是否有词级别数据
            if "words" in segment and segment["words"]:
                # 使用词级别时间戳
                for word_data in segment["words"]:
                    word_text = word_data.get("word", "").strip()
                    if not word_text:
                        continue
                    seg_data = {
                        "id": segment_id,
                        "start": round(word_data["start"], 2),
                        "end": round(word_data["end"], 2),
                        "text": word_text
                    }
                    segments.append(seg_data)
                    segment_id += 1
            else:
                # 回退到句子级别
                seg_data = {
                    "id": segment_id,
                    "start": round(segment["start"], 2),
                    "end": round(segment["end"], 2),
                    "text": segment["text"].strip()
                }
                segments.append(seg_data)
                segment_id += 1
        
        return {
            "segments": segments,
            "language": language,
            "duration": round(max([s["end"] for s in segments]) if segments else 0, 2)
        }
        
    except Exception as e:
        print(f"  ⚠ MLX GPU 加速不可用: {e}")
        print("\n" + "="*60)
        print("警告: 无法使用 GPU 加速，将使用 CPU 模式（速度会很慢）")
        print("="*60)
        
        # 要求用户确认
        user_input = input("\n是否继续使用 CPU 模式？输入 YES 继续，其他任何输入将退出: ").strip()
        
        if user_input != "YES":
            print("\n用户取消，程序退出。")
            sys.exit(0)
        
        print("\n用户确认，继续使用 CPU 模式...\n")
        use_mlx = False
    
    # 如果 MLX 失败，使用标准 stable-ts（CPU）
    if not use_mlx:
        print(f"  加载模型: {model_name} (CPU 模式)")
        model = stable_whisper.load_model(model_name)
        
        # 转录并对齐（只需要句子级别时间戳）
        print(f"  处理音频: {audio_path.name}")
        result = model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,  # 启用词级别时间戳
            initial_prompt=reference_text[:100],  # 使用前100字符作为提示
            vad=False  # 禁用 VAD 以加快速度
        )
        
        # 提取词级别对齐数据
        segments = []
        segment_id = 0
        
        for segment in result.segments:
            # 检查是否有词级别数据
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    word_text = word.word.strip() if hasattr(word, 'word') else str(word).strip()
                    if not word_text:
                        continue
                    seg_data = {
                        "id": segment_id,
                        "start": round(word.start, 2),
                        "end": round(word.end, 2),
                        "text": word_text
                    }
                    segments.append(seg_data)
                    segment_id += 1
            else:
                # 回退到句子级别
                seg_data = {
                    "id": segment_id,
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": segment.text.strip()
                }
                segments.append(seg_data)
                segment_id += 1
        
        return {
            "segments": segments,
            "language": language,
            "duration": round(result.duration, 2) if hasattr(result, 'duration') else 0
        }




def merge_audio_files(audio_files: List[Path], output_path: Path, gap_seconds: float = 1.0):
    """
    合并多个音频文件，并在每个文件之间插入静音间隔
    
    参数:
        audio_files: 音频文件列表
        output_path: 输出文件路径
        gap_seconds: 间隔时长（秒）
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        print("警告: pydub 未安装，跳过音频合并")
        return
    
    print("\n合并音频文件...")
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=int(gap_seconds * 1000))
    
    for i, audio_file in enumerate(tqdm(audio_files, desc="合并进度")):
        audio = AudioSegment.from_mp3(audio_file)
        combined += audio
        
        # 最后一个文件后不添加静音
        if i < len(audio_files) - 1:
            combined += silence
    
    combined.export(output_path, format="mp3")
    print(f"合并完成: {output_path}")


def adjust_timestamps_for_merged(
    alignments: List[Dict[str, Any]],
    gap_seconds: float = 1.0
) -> Dict[str, Any]:
    """
    调整时间戳以适应合并后的音频文件（词级别）
    
    参数:
        alignments: 各个音频文件的对齐数据列表
        gap_seconds: 间隔时长（秒）- 音频合并时在每个文件之间插入的静音时长
    
    返回:
        合并后的对齐数据
    """
    merged_segments = []
    current_offset = 0.0
    segment_id = 0
    
    for i, alignment in enumerate(alignments):
        for segment in alignment["segments"]:
            adjusted_segment = {
                "id": segment_id,
                "start": round(segment["start"] + current_offset, 2),
                "end": round(segment["end"] + current_offset, 2),
                "text": segment["text"]
            }
            
            merged_segments.append(adjusted_segment)
            segment_id += 1
        
        # 更新偏移量（当前音频时长 + 间隔）
        current_offset += alignment["duration"] + gap_seconds
    
    return {
        "segments": merged_segments,
        "language": alignments[0]["language"] if alignments else "zh",
        "duration": round(current_offset - gap_seconds, 2)  # 减去最后一个间隔
    }


def merge_txt_files(txt_files: List[Path], output_path: Path):
    """
    合并多个文本文件为一个文件
    
    参数:
        txt_files: 文本文件列表（已按顺序排列）
        output_path: 输出文件路径
    """
    print("\n合并文本文件...")
    merged_content = []
    
    for txt_file in tqdm(txt_files, desc="合并进度"):
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                merged_content.append(content)
    
    # 用换行符分隔各个文件内容
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(merged_content))
    
    print(f"合并完成: {output_path}")
    print(f"  - 文件数: {len(txt_files)}")
    print(f"  - 总字符数: {sum(len(c) for c in merged_content)}")


def main():
    parser = argparse.ArgumentParser(
        description="音频-文本对齐数据准备工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
提示: 你可以直接在脚本顶部的【用户配置区域】设置参数，
     也可以通过命令行参数覆盖这些设置。
        """
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(INPUT_FOLDER),
        help=f"包含音频和文本文件的目录 (默认: {INPUT_FOLDER})"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(INPUT_FOLDER).joinpath(OUTPUT_ALIGNMENT_JSON),
        help=f"输出的对齐数据文件 (默认: {Path(INPUT_FOLDER).joinpath(OUTPUT_ALIGNMENT_JSON)})"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_SIZE,
        choices=["tiny", "base", "small", "medium", "large"],
        help=f"Whisper 模型大小 (默认: {MODEL_SIZE})"
    )
    parser.add_argument(
        "--language",
        type=str,
        default=LANGUAGE,
        help=f"语言代码 (默认: {LANGUAGE})"
    )
    parser.add_argument(
        "--merge-audio",
        action="store_true",
        default=MERGE_AUDIO,
        help=f"是否合并音频文件 (默认: {MERGE_AUDIO})"
    )
    parser.add_argument(
        "--merged-audio-output",
        type=Path,
        default=Path(INPUT_FOLDER).joinpath(OUTPUT_MERGED_AUDIO),
        help=f"合并后的音频文件路径 (默认: {Path(INPUT_FOLDER).joinpath(OUTPUT_MERGED_AUDIO)})"
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=GAP_SECONDS,
        help=f"音频文件之间的间隔时长（秒，默认: {GAP_SECONDS}）"
    )
    parser.add_argument(
        "--merge-txt",
        action="store_true",
        default=MERGE_TXT,
        help=f"是否合并文本文件 (默认: {MERGE_TXT})"
    )
    parser.add_argument(
        "--merged-txt-output",
        type=Path,
        default=Path(INPUT_FOLDER).joinpath(OUTPUT_MERGED_TXT),
        help=f"合并后的文本文件路径 (默认: {Path(INPUT_FOLDER).joinpath(OUTPUT_MERGED_TXT)})"
    )

    
    args = parser.parse_args()
    
    # 检查输入目录
    if not args.input_dir.exists():
        print(f"错误: 输入目录不存在: {args.input_dir}")
        sys.exit(1)
    
    # ============================================================
    # 检查输出文件是否已存在
    # ============================================================
    alignment_exists = args.output.exists()
    merged_audio_exists = args.merged_audio_output.exists() if args.merge_audio else False
    merged_txt_exists = args.merged_txt_output.exists() if args.merge_txt else False
    
    if alignment_exists:
        print(f"✓ 对齐文件已存在: {args.output}")
    
    if merged_audio_exists:
        print(f"✓ 合并音频已存在: {args.merged_audio_output}")
    
    if merged_txt_exists:
        print(f"✓ 合并文本已存在: {args.merged_txt_output}")
    
    # 如果所有功能都已完成，询问是否跳过
    all_exist = (
        alignment_exists and 
        (not args.merge_audio or merged_audio_exists) and
        (not args.merge_txt or merged_txt_exists)
    )
    if all_exist:
        print("\n" + "="*60)
        print("所有输出文件都已存在！")
        print("="*60)
        user_input = input("\n是否重新生成？输入 YES 重新生成，其他任何输入将退出: ").strip()
        
        if user_input != "YES":
            print("\n用户选择跳过，程序退出。")
            sys.exit(0)
        
        print("\n用户确认，将重新生成所有文件...\n")
        alignment_exists = False
        merged_audio_exists = False
        merged_txt_exists = False
    
    # 加载音频文件
    print(f"\n扫描目录: {args.input_dir}")
    audio_files = load_audio_files(args.input_dir)
    
    if not audio_files:
        print("错误: 未找到任何音频-文本配对文件")
        sys.exit(1)
    
    print(f"找到 {len(audio_files)} 个音频-文本配对")
    
    # ============================================================
    # 功能 1: 生成对齐数据
    # ============================================================
    if alignment_exists:
        print("\n⏭️  跳过对齐数据生成（文件已存在）")
        # 加载现有对齐数据以供后续使用
        with open(args.output, 'r', encoding='utf-8') as f:
            merged_alignment = json.load(f)
        audio_paths = [audio_path for audio_path, _, _ in audio_files]
    else:
        print("\n📝 开始生成对齐数据...")
        # 处理每个音频文件
        alignments = []
        audio_paths = []
        
        for audio_path, text_path, stem in tqdm(audio_files, desc="处理进度"):
            print(f"\n处理 {stem}:")
            
            try:
                alignment = transcribe_with_alignment(
                    audio_path,
                    text_path,
                    model_name=args.model,
                    language=args.language
                )
                alignments.append(alignment)
                audio_paths.append(audio_path)
                
            except Exception as e:
                print(f"  错误: {e}")
                continue
        
        if not alignments:
            print("错误: 没有成功处理任何文件")
            sys.exit(1)
        
        # 合并对齐数据
        print("\n合并对齐数据...")
        merged_alignment = adjust_timestamps_for_merged(alignments, args.gap)
        
        # 保存对齐数据
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(merged_alignment, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 对齐数据已保存: {args.output}")
        print(f"  - 总段落数: {len(merged_alignment['segments'])}")
        print(f"  - 总时长: {merged_alignment['duration']:.2f} 秒")
    
    # ============================================================
    # 功能 2: 合并音频文件
    # ============================================================
    if args.merge_audio:
        if merged_audio_exists:
            print("\n⏭️  跳过音频合并（文件已存在）")
        else:
            print("\n🎵 开始合并音频...")
            merge_audio_files(audio_paths, args.merged_audio_output, args.gap)
    
    # ============================================================
    # 功能 3: 合并文本文件
    # ============================================================
    if args.merge_txt:
        if merged_txt_exists:
            print("\n⏭️  跳过文本合并（文件已存在）")
        else:
            print("\n📄 开始合并文本...")
            txt_paths = [txt_path for _, txt_path, _ in audio_files]
            merge_txt_files(txt_paths, args.merged_txt_output)
    
    print("\n" + "="*60)
    print("✅ 完成！")
    print("="*60)



if __name__ == "__main__":
    main()

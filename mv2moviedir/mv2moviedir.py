#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2024 mv2moviedir Contributors
# 本项目采用MIT许可证 (MIT License)
# 基于mv2tvdir项目改进，专门用于电影文件整理

# 版本信息
__version__ = "1.0.0"

"""
mv2moviedir - 将电影文件移动到按电影名组织的目录结构中

用法：
    mv2moviedir.py <源目录> <目标目录> [选项]

选项：
    --resolution=<分辨率>  只处理指定分辨率的文件 (例如: 1080p, 720p, 4K)
    --codec=<编码>        只处理指定编码的文件 (例如: x265, x264)
    --year-group          按年份分组电影 (创建年份子目录)
    --remove-source       移动文件后删除源目录（如果源目录为空或只剩下nfo、txt、jpg等文件）
    --force               强制处理所有视频文件，忽略AI字幕检查（默认只处理有AI字幕的文件）
    --no-override         不覆盖已存在的目标文件（默认会覆盖已存在的文件）

示例：
    mv2moviedir.py /downloads /media/movies
    mv2moviedir.py /downloads /media/movies --resolution=1080p
    mv2moviedir.py /downloads /media/movies --codec=x265
    mv2moviedir.py /downloads /media/movies --year-group
    mv2moviedir.py /downloads /media/movies --remove-source
"""

import os
import sys
import re
import shutil
import logging
import argparse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 支持的视频和字幕文件扩展名
VIDEO_EXTENSIONS = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm')
SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.sub', '.vtt', '.ssa')
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS + SUBTITLE_EXTENSIONS

# 不需要删除的文件类型（在源目录中保留的文件类型）
IGNORED_EXTENSIONS = ('.nfo', '.txt', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')

# 正则表达式模式
# 电视剧模式（包含SxxExx格式）- 用于排除电视剧文件
TV_SHOW_PATTERN = re.compile(r'[.\s\(\)\[\]][Ss][0-9]{1,2}[Ee][0-9]{1,2}[.\s\(\)\[\]]')

# 年份模式：匹配1900-2099年，更智能的匹配
# 优先匹配位于特定位置的年份，避免误识别电影名称中的年份
YEAR_PATTERN = re.compile(r'[.\s\(\)\[\]](19[0-9]{2}|20[0-9]{2})(?=[.\s\(\)\[\]]|$)')

# 更严格的年份模式：用于识别真正的发行年份
# 1. 年份后紧跟质量标识符、分辨率或编码信息的年份
# 2. 被括号包围的年份
# 3. 位于文件名末尾的年份
RELEASE_YEAR_PATTERNS = [
    re.compile(r'[.\s\(\)\[\]](19[0-9]{2}|20[0-9]{2})(?=[.\s\(\)\[\]](BluRay|BDRip|BRRip|DVDRip|WEBRip|WEB-DL|HDRip|Directors|Cut|Extended|Unrated|REMUX|REPACK|PROPER|REAL))', re.IGNORECASE),
    re.compile(r'[.\s\(\)\[\]](19[0-9]{2}|20[0-9]{2})(?=[.\s\(\)\[\]](\d+p|4K|8K|UHD|HD|x26[45]|H\.?26[45]|AVC|HEVC|VP9|AV1))', re.IGNORECASE),
    re.compile(r'\((19[0-9]{2}|20[0-9]{2})\)'),
    re.compile(r'\[(19[0-9]{2}|20[0-9]{2})\]'),
    re.compile(r'[.\s](19[0-9]{2}|20[0-9]{2})$'),
    re.compile(r'^(19[0-9]{2}|20[0-9]{2})$'),  # 整个文件名就是年份
    re.compile(r'[.\s](19[0-9]{2}|20[0-9]{2})[.\s]*$')
]

# 分辨率模式（支持更多分辨率）
RESOLUTION_PATTERN = re.compile(r'[.\s\(\)\[\]](\d+p|4K|8K|UHD|HD)(?=[.\s\(\)\[\]]|$)', re.IGNORECASE)

# 编码模式
CODEC_PATTERN = re.compile(r'[.\s\(\)\[\]](x26[45]|H\.?26[45]|AVC|HEVC|VP9|AV1)[.\s\(\)\[\]-]', re.IGNORECASE)

# 用于替换文件名中的分隔符的模式
SEPARATOR_PATTERN = re.compile(r'[\s\(\)\[\]]')

# 常见的电影质量标识符
QUALITY_PATTERNS = [
    r'[.\s\(\)\[\]](BluRay|BDRip|BRRip|DVDRip|WEBRip|WEB-DL|HDRip|CAMRip|TS|TC)[.\s\(\)\[\]]',
    r'[.\s\(\)\[\]](REMUX|REPACK|PROPER|REAL)[.\s\(\)\[\]]',
    r'[.\s\(\)\[\]](HDR|HDR10|DV|Dolby\.?Vision)[.\s\(\)\[\]]'
]

# 常见的发布组标识符
RELEASE_GROUP_PATTERN = re.compile(r'-([A-Z0-9]+)$|[\[\(]([A-Z0-9]+)[\]\)]$')


def is_movie(filename):
    """
    判断文件是否为电影（不包含SxxExx格式的视频文件）
    
    Args:
        filename: 文件名
        
    Returns:
        bool: 是否为电影
    """
    # 检查文件扩展名
    _, ext = os.path.splitext(filename)
    if ext.lower() not in VIDEO_EXTENSIONS:
        return False
    
    # 如果包含电视剧格式，则不是电影
    if TV_SHOW_PATTERN.search(filename):
        return False
    
    return True


def match_resolution_and_codec(filename, target_resolution=None, target_codec=None):
    """
    检查文件是否匹配目标分辨率和编码
    
    Args:
        filename: 文件名
        target_resolution: 目标分辨率 (例如: "1080p", "4K")
        target_codec: 目标编码 (例如: "x265", "H.264")
        
    Returns:
        bool: 是否匹配目标分辨率和编码
    """
    # 如果没有指定分辨率和编码，则匹配所有文件
    if not target_resolution and not target_codec:
        return True
    
    # 检查分辨率
    if target_resolution:
        resolution_match = RESOLUTION_PATTERN.search(filename)
        if not resolution_match:
            return False
        found_resolution = resolution_match.group(1).lower()
        target_resolution_lower = target_resolution.lower()
        if found_resolution != target_resolution_lower:
            return False
    
    # 检查编码
    if target_codec:
        codec_match = CODEC_PATTERN.search(filename)
        if not codec_match:
            return False
        found_codec = codec_match.group(1).lower().replace('.', '')
        target_codec_lower = target_codec.lower().replace('.', '')
        if found_codec != target_codec_lower:
            return False
    
    return True


def normalize_name(name):
    """
    统一的名称规整函数：用于文件名和目录名的标准化处理
    将空格、()、[]等分隔符替换为点号，并处理文件系统不兼容字符
    特别处理发行组织的特殊格式：-[GROUP] 和空格分隔的发行组织
    
    Args:
        name: 原始名称（文件名或目录名）
        
    Returns:
        str: 标准化后的名称，确保文件系统兼容性
    """
    # 先保存原始名称用于发行组织检测
    original_name = name
    
    # 检测并处理发行组织的特殊格式
    # 1. 处理 -[GROUP] 格式：保留减号，移除方括号
    release_group_bracket_pattern = re.compile(r'-\[([^\]]+)\]')
    if release_group_bracket_pattern.search(name):
        name = release_group_bracket_pattern.sub(r'-\1', name)
    
    # 2. 检测末尾的发行组织（通常是大写字母和数字的组合）
    # 如果末尾是空格+发行组织，将空格替换为减号
    # 支持发行组织后面跟字幕标识（如.ai.srt）的情况
    release_group_end_pattern = re.compile(r'\s+([A-Z0-9]{2,}(?:\.[A-Z0-9]+)*)(?=\.ai\.srt$|$)')
    match = release_group_end_pattern.search(name)
    if match:
        # 将末尾的空格+发行组织替换为减号+发行组织
        name = release_group_end_pattern.sub(r'-\1', name)
    
    # 替换空格、()、剩余的[]为点号
    # 注意：这里使用修改后的模式，因为我们已经处理了发行组织的方括号
    separator_pattern = re.compile(r'[\s\(\)\[\]]')
    normalized = separator_pattern.sub('.', name)
    
    # 处理可能出现的连续点号
    while '..' in normalized:
        normalized = normalized.replace('..', '.')
    
    # 替换文件系统不兼容的特殊字符
    file_system_unsafe = [':', '/', '\\', '|', '?', '*', '<', '>', '"']
    for char in file_system_unsafe:
        normalized = normalized.replace(char, '.')
    
    # 再次处理可能因替换产生的连续点号
    while '..' in normalized:
        normalized = normalized.replace('..', '.')
    
    # 去除开头和结尾的点号
    normalized = normalized.strip('.')
    
    # 如果结果为空，返回原始名称的简化版本
    if not normalized:
        # 只保留字母数字和基本符号
        normalized = re.sub(r'[^\w\-.]', '', original_name)
        if not normalized:
            normalized = "Unknown"
    
    return normalized


def remove_chinese_ads(filename):
    """
    去除文件名前面的中文广告内容，保留英文电影名称
    
    Args:
        filename: 原始文件名
        
    Returns:
        str: 去除中文广告内容后的文件名
    """
    # 常见的网址和广告模式，这些不是电影名称
    ad_patterns = [
        r'www\.[a-zA-Z0-9.-]+',  # 网址
        r'[a-zA-Z0-9.-]+\.com',  # .com域名
        r'[a-zA-Z0-9.-]+\.net',  # .net域名
        r'[a-zA-Z0-9.-]+\.org',  # .org域名
    ]
    
    # 检查是否包含中文字符
    if not re.search(r'[\u4e00-\u9fff]', filename):
        # 如果没有中文字符，检查是否有明显的广告内容
        for ad_pattern in ad_patterns:
            if re.search(ad_pattern, filename, re.IGNORECASE):
                # 找到广告内容，尝试从广告后开始
                match = re.search(ad_pattern, filename, re.IGNORECASE)
                if match:
                    after_ad = filename[match.end():].lstrip('. ')
                    if len(after_ad) >= 3:
                        return after_ad
        
        # 没有广告内容，直接返回原文件名
        return filename
    
    # 如果包含中文字符，查找第一个英文电影名称
    # 匹配英文电影名称模式：以英文字母开头的连续英文内容
    english_match = re.search(r'[A-Za-z][A-Za-z0-9\s\-\.]+(?:\d{4})?[A-Za-z0-9\s\-\.]*', filename)
    
    if english_match:
        english_part = english_match.group().strip()
        
        # 检查是否是广告
        is_ad = False
        for ad_pattern in ad_patterns:
            if re.search(ad_pattern, english_part, re.IGNORECASE):
                is_ad = True
                break
        
        if not is_ad and len(english_part) >= 3:
            return english_part
    
    # 如果所有方法都失败，返回原始文件名
    return filename


def extract_movie_info(filename):
    """
    从文件名中提取电影名称和年份
    
    Args:
        filename: 文件名
        
    Returns:
        tuple: (电影名称, 年份) 或者 (电影名称, None) 如果无法提取年份
    """
    # 移除文件扩展名（只移除已知的视频和字幕扩展名）
    basename = filename
    for ext in SUPPORTED_EXTENSIONS:
        if filename.lower().endswith(ext.lower()):
            basename = filename[:-len(ext)]
            break
    
    # 去除中文广告内容
    basename = remove_chinese_ads(basename)
    
    # 标准化文件名（替换空格、()、[]为点号）
    normalized_basename = normalize_name(basename)
    
    # 使用改进的年份识别逻辑
    year = None
    year_match = None
    movie_name_end = len(normalized_basename)
    
    # 按优先级尝试匹配年份模式
    for pattern in RELEASE_YEAR_PATTERNS:
        match = pattern.search(normalized_basename)
        if match:
            year_match = match
            # 提取年份数字
            if match.groups():
                year = int(match.group(1))
            else:
                # 对于没有分组的模式，提取整个匹配中的年份
                year_text = match.group(0)
                year_digits = re.search(r'(19[0-9]{2}|20[0-9]{2})', year_text)
                if year_digits:
                    year = int(year_digits.group(1))
            break
    
    # 如果使用严格模式找到了年份，确定电影名称的结束位置
    if year_match:
        # 找到年份在原始文件名中的位置，电影名称应该在年份之前结束
        year_start = year_match.start()
        # 寻找年份前最近的分隔符位置
        for i in range(year_start, -1, -1):
            if normalized_basename[i] in '.[]()':
                movie_name_end = i
                break
        else:
            movie_name_end = year_start
    else:
        # 如果没有找到明确的发行年份，按优先级尝试截断
        # 1. 首先尝试在分辨率之前截断
        resolution_match = RESOLUTION_PATTERN.search(normalized_basename)
        if resolution_match:
            movie_name_end = resolution_match.start()
        else:
            # 2. 如果没有分辨率，尝试在质量标识符之前截断
            for pattern in QUALITY_PATTERNS:
                quality_match = re.search(pattern, normalized_basename, re.IGNORECASE)
                if quality_match:
                    movie_name_end = quality_match.start()
                    break
            
            # 3. 如果没有质量标识符，尝试在编码之前截断
            if movie_name_end == len(normalized_basename):
                codec_match = CODEC_PATTERN.search(normalized_basename)
                if codec_match:
                    movie_name_end = codec_match.start()
        
        # 如果仍然没有找到合适的截断点，使用旧的年份模式作为后备
        if movie_name_end == len(normalized_basename):
            fallback_year_match = YEAR_PATTERN.search(normalized_basename)
            if fallback_year_match:
                # 检查这个年份是否可能是电影名称的一部分
                year_pos = fallback_year_match.start()
                # 如果年份前后都有字母，可能是电影名称的一部分，不使用
                before_year = normalized_basename[max(0, year_pos-2):year_pos]
                after_year = normalized_basename[fallback_year_match.end():fallback_year_match.end()+2]
                
                # 如果年份前后不是纯分隔符，可能是电影名称的一部分
                if not (re.match(r'^[.\s\(\)\[\]]*$', before_year) or 
                       re.match(r'^[.\s\(\)\[\]]*$', after_year)):
                    # 年份可能是电影名称的一部分，不截断
                    pass
                else:
                    year = int(fallback_year_match.group(1))
                    movie_name_end = fallback_year_match.start()
        
        # 最后尝试检查文件名末尾是否有年份（没有扩展名的情况）
        if year is None and movie_name_end == len(normalized_basename):
            # 检查文件名是否以年份结尾（包括没有分隔符的情况）
            end_year_match = re.search(r'(19[0-9]{2}|20[0-9]{2})$', normalized_basename)
            if not end_year_match:
                # 检查整个文件名是否就是年份
                end_year_match = re.match(r'^(19[0-9]{2}|20[0-9]{2})$', normalized_basename)
            
            if end_year_match:
                year = int(end_year_match.group(1))
                movie_name_end = end_year_match.start()
    
    # 提取电影名称部分
    movie_name_part = normalized_basename[:movie_name_end].strip('.')
    movie_name_parts = movie_name_part.split('.')
    
    # 清理电影名称，过滤掉空字符串，保留有意义的单字符和数字
    cleaned_parts = []
    meaningful_single_chars = {'A', 'I', 'X', 'V'}  # 常见的有意义单字符
    
    for part in movie_name_parts:
        part = part.strip()
        if part:
            # 保留长度大于1的部分，或者是有意义的单字符，或者是数字
            if len(part) > 1 or part.upper() in meaningful_single_chars or part.isdigit():
                cleaned_parts.append(part)
    
    # 重新组合电影名称
    movie_name = ' '.join(cleaned_parts).strip()
    
    if not movie_name:
        logging.warning(f"无法从 {filename} 中提取电影名称")
        return None, None
    
    return movie_name, year


def has_ai_subtitle(video_file_path):
    """
    检查视频文件是否存在对应的.ai.srt字幕文件
    
    Args:
        video_file_path: 视频文件的完整路径
        
    Returns:
        bool: 如果存在对应的.ai.srt字幕文件返回True，否则返回False
    """
    # 获取视频文件的目录和文件名（不含扩展名）
    video_dir = os.path.dirname(video_file_path)
    video_name = os.path.splitext(os.path.basename(video_file_path))[0]
    
    # 构造对应的.ai.srt字幕文件路径
    ai_subtitle_path = os.path.join(video_dir, f"{video_name}.ai.srt")
    
    return os.path.exists(ai_subtitle_path)


def check_directory_permissions(directory):
    """
    检查目录的读写权限
    
    Args:
        directory: 目录路径
        
    Returns:
        bool: 如果有读写权限返回True，否则返回False
    """
    if not os.path.exists(directory):
        # 检查父目录的写权限
        parent_dir = os.path.dirname(directory)
        while parent_dir and not os.path.exists(parent_dir):
            parent_dir = os.path.dirname(parent_dir)
        return os.access(parent_dir, os.W_OK) if parent_dir else False
    
    return os.access(directory, os.R_OK | os.W_OK)


def get_year_category(year):
    """
    根据年份获取归类目录名
    
    Args:
        year: 年份
        
    Returns:
        str: 年份归类目录名
    """
    if year is None:
        return "Unknown"
    
    if year >= 2024:
        # 2024年及之后按年归类
        return str(year)
    else:
        # 2023年及之前按10年归类
        decade = (year // 10) * 10
        return f"{decade}s"


def create_target_directory(base_dir, filename_without_ext, year=None, year_group=False):
    """
    创建目标目录结构
    
    Args:
        base_dir: 基础目录
        filename_without_ext: 完整的文件名（不含扩展名）
        year: 年份（可选）
        year_group: 是否按年份分组
        
    Returns:
        str: 创建的目标目录路径，如果创建失败返回None
    """
    # 先去除中文广告内容，然后规整完整文件名作为目录名（保留所有视频信息）
    cleaned_filename = remove_chinese_ads(filename_without_ext)
    movie_dir_name = normalize_name(cleaned_filename)
    
    # 确定目标路径
    if year_group:
        # 按年份分组：base_dir/年份归类/完整文件名/
        year_category = get_year_category(year)
        year_dir = os.path.join(base_dir, year_category)
        target_dir = os.path.join(year_dir, movie_dir_name)
        
        # 创建年份归类目录
        if not os.path.exists(year_dir):
            try:
                os.makedirs(year_dir)
                logging.info(f"创建年份归类目录: {year_dir}")
            except (PermissionError, OSError) as e:
                logging.error(f"无法创建年份归类目录 {year_dir}: {e}")
                return None
    else:
        # 直接在基础目录下：base_dir/完整文件名/
        target_dir = os.path.join(base_dir, movie_dir_name)
    
    # 创建电影目录
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir)
            logging.info(f"创建电影目录: {target_dir}")
        except (PermissionError, OSError) as e:
            logging.error(f"无法创建电影目录 {target_dir}: {e}")
            return None
    
    return target_dir


def can_remove_directory(directory):
    """
    检查目录是否可以删除（为空或只包含被忽略的文件类型）
    
    Args:
        directory: 目录路径
        
    Returns:
        bool: 是否可以删除目录
    """
    # 检查目录是否存在
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return False
    
    # 获取目录中的所有文件
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    
    # 如果目录为空，可以删除
    if not files:
        return True
    
    # 检查是否只包含被忽略的文件类型
    for file in files:
        _, ext = os.path.splitext(file)
        if ext.lower() not in IGNORED_EXTENSIONS:
            return False
    
    return True


def move_file(source_path, target_dir, override_files=True):
    """
    将文件移动到目标目录
    
    Args:
        source_path: 源文件路径
        target_dir: 目标目录
        override_files: 是否覆盖已存在的文件，默认为True
        
    Returns:
        bool: 是否成功移动文件
    """
    filename = os.path.basename(source_path)
    
    # 特殊处理复合扩展名（如.ai.srt）
    if filename.endswith('.ai.srt'):
        filename_without_ext = filename[:-7]  # 去掉 .ai.srt
        ext = '.ai.srt'
    else:
        # 获取文件扩展名
        filename_without_ext, ext = os.path.splitext(filename)
    
    # 先去除中文广告内容，再标准化文件名（不含扩展名），与目录名处理保持一致
    cleaned_filename_without_ext = remove_chinese_ads(filename_without_ext)
    normalized_filename_without_ext = normalize_name(cleaned_filename_without_ext)
    
    # 重新组合文件名
    normalized_filename = normalized_filename_without_ext + ext
    
    target_path = os.path.join(target_dir, normalized_filename)
    
    # 检查目标文件是否已存在
    if os.path.exists(target_path):
        if not override_files:
            logging.warning(f"目标文件已存在，跳过: {target_path}")
            return False
        else:
            logging.info(f"目标文件已存在，将覆盖: {target_path}")
    
    try:
        shutil.move(source_path, target_path)
        logging.info(f"移动文件: {source_path} -> {target_path}")
        return True
    except Exception as e:
        logging.error(f"移动文件失败: {source_path} -> {target_path}, 错误: {e}")
        return False


def process_directory(source_dir, target_base_dir, resolution=None, codec=None, 
                     year_group=False, remove_source=False, require_ai_subtitle=True, 
                     override_files=True):
    """
    处理源目录中的所有电影文件
    
    Args:
        source_dir: 源目录
        target_base_dir: 目标基础目录
        resolution: 目标分辨率 (例如: "1080p", "4K")
        codec: 目标编码 (例如: "x265", "H.264")
        year_group: 是否按年份分组
        remove_source: 是否在处理后删除源目录
        require_ai_subtitle: 是否只处理存在.ai.srt字幕文件的视频
        override_files: 是否覆盖已存在的文件，默认为True
        
    Returns:
        tuple: (成功数, 失败数, 跳过数, 删除目录数)
    """
    success_count = 0
    failure_count = 0
    skipped_count = 0
    removed_dirs_count = 0
    
    # 收集处理过的目录，用于后续检查是否可以删除
    processed_dirs = set()
    # 记录成功移动的视频文件，用于后续移动对应的字幕文件
    moved_videos = {}  # {video_basename_without_ext: (target_dir, source_dir)}
    
    # 第一阶段：处理视频文件
    for root, _, files in os.walk(source_dir, topdown=False):
        for filename in files:
            # 检查是否为电影文件
            if not is_movie(filename):
                continue
            
            # 检查是否匹配目标分辨率和编码
            if not match_resolution_and_codec(filename, resolution, codec):
                logging.info(f"跳过不匹配的文件: {filename}")
                skipped_count += 1
                continue
            
            source_path = os.path.join(root, filename)
            
            # 如果启用了AI字幕检查，检查是否存在对应的.ai.srt字幕文件
            if require_ai_subtitle:
                if not has_ai_subtitle(source_path):
                    logging.info(f"跳过文件: {filename} (未找到对应的.ai.srt字幕文件)")
                    skipped_count += 1
                    continue
            
            # 提取电影名称和年份
            movie_name, year = extract_movie_info(filename)
            if not movie_name:
                logging.warning(f"跳过文件: {filename} (无法提取电影名称)")
                skipped_count += 1
                continue
            
            # 检查年份是否提取成功
            if not year:
                logging.warning(f"跳过文件: {filename} (无法提取电影年份)")
                skipped_count += 1
                continue
            
            # 获取不含扩展名的完整文件名
            filename_without_ext = os.path.splitext(filename)[0]
            
            # 创建目标目录
            target_dir = create_target_directory(target_base_dir, filename_without_ext, year, year_group)
            if target_dir is None:
                logging.error(f"跳过文件: {filename} (无法创建目标目录)")
                failure_count += 1
                continue
                
            logging.info(f"目标目录: {target_dir} (电影: {movie_name}, 年份: {year or '未知'})")
            
            # 移动视频文件
            if move_file(source_path, target_dir, override_files):
                success_count += 1
                # 记录处理过的目录
                processed_dirs.add(os.path.dirname(source_path))
                # 记录成功移动的视频文件，用于后续移动字幕文件
                video_basename = os.path.splitext(filename)[0]
                moved_videos[video_basename] = (target_dir, root)
                logging.info(f"成功移动视频文件: {filename}")
            else:
                failure_count += 1
    
    # 第二阶段：处理字幕文件，只移动对应视频文件已成功移动的字幕文件
    for root, _, files in os.walk(source_dir, topdown=False):
        for filename in files:
            # 检查文件扩展名是否为字幕文件
            _, ext = os.path.splitext(filename)
            if ext.lower() not in SUBTITLE_EXTENSIONS:
                continue
            
            # 检查是否匹配目标分辨率和编码
            if not match_resolution_and_codec(filename, resolution, codec):
                logging.info(f"跳过不匹配的字幕文件: {filename}")
                skipped_count += 1
                continue
            
            source_path = os.path.join(root, filename)
            subtitle_basename = os.path.splitext(filename)[0]
            
            # 查找对应的视频文件是否已被移动
            corresponding_video = None
            for video_basename, (target_dir, video_root) in moved_videos.items():
                if video_root == root and subtitle_basename.startswith(video_basename):
                    corresponding_video = (target_dir, video_basename)
                    break
            
            if corresponding_video is None:
                logging.info(f"跳过字幕文件: {filename} (对应的视频文件未被移动)")
                skipped_count += 1
                continue
            
            target_dir, video_basename = corresponding_video
            
            # 移动字幕文件
            if move_file(source_path, target_dir, override_files):
                success_count += 1
                # 记录处理过的目录
                processed_dirs.add(os.path.dirname(source_path))
                logging.info(f"成功移动字幕文件: {filename} (对应视频: {video_basename})")
            else:
                failure_count += 1
    
    # 如果需要删除源目录
    if remove_source:
        # 收集所有需要检查的目录，包括处理过的目录及其父目录
        dirs_to_check = set(processed_dirs)
        
        # 对于每个处理过的目录，也检查其父目录（电影通常在单独的子目录中）
        for dir_path in list(processed_dirs):
            parent_dir = os.path.dirname(dir_path)
            # 确保不删除源目录本身，只删除其子目录
            if parent_dir != source_dir and parent_dir.startswith(source_dir):
                dirs_to_check.add(parent_dir)
        
        # 按照目录深度从深到浅排序，确保先删除子目录
        sorted_dirs = sorted(dirs_to_check, key=lambda x: x.count(os.sep), reverse=True)
        
        for dir_path in sorted_dirs:
            # 跳过源目录本身
            if dir_path == source_dir:
                continue
                
            if can_remove_directory(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    logging.info(f"删除源目录: {dir_path}")
                    removed_dirs_count += 1
                except Exception as e:
                    logging.error(f"删除源目录失败: {dir_path}, 错误: {e}")
            else:
                logging.debug(f"源目录不为空，跳过删除: {dir_path}")
    
    return success_count, failure_count, skipped_count, removed_dirs_count


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='将电影文件移动到按电影名组织的目录结构中')
    parser.add_argument('source_dir', help='源目录')
    parser.add_argument('target_dir', help='目标目录')
    parser.add_argument('--resolution', help='只处理指定分辨率的文件 (例如: 1080p, 720p, 4K)')
    parser.add_argument('--codec', help='只处理指定编码的文件 (例如: x265, x264, H.264)')
    parser.add_argument('--year-group', action='store_true', help='按年份分组电影 (创建年份子目录)')
    parser.add_argument('--remove-source', action='store_true', help='移动文件后删除源目录（如果源目录为空或只剩下nfo、txt、jpg等文件）')
    parser.add_argument('--force', action='store_true', help='强制处理所有视频文件，忽略AI字幕检查（默认只处理有AI字幕的文件）')
    parser.add_argument('--no-override', action='store_true', help='不覆盖已存在的目标文件（默认覆盖已存在的文件）')
    parser.add_argument('--version', action='version', version=f'mv2moviedir {__version__}')
    
    args = parser.parse_args()
    
    source_dir = args.source_dir
    target_dir = args.target_dir
    resolution = args.resolution
    codec = args.codec
    year_group = args.year_group
    remove_source = args.remove_source
    require_ai_subtitle = not args.force  # 默认启用AI字幕检查，--force时禁用
    override_files = not args.no_override  # 默认覆盖文件，--no-override时不覆盖
    
    # 检查源目录和目标目录是否存在
    if not os.path.isdir(source_dir):
        print(f"错误: 源目录不存在: {source_dir}")
        sys.exit(1)
    
    if not os.path.isdir(target_dir):
        print(f"错误: 目标目录不存在: {target_dir}")
        sys.exit(1)
    
    # 检查目标目录权限
    if not check_directory_permissions(target_dir):
        print(f"错误: 目标目录没有写权限: {target_dir}")
        print("请检查目录权限或使用sudo运行脚本")
        sys.exit(1)
    
    # 记录过滤条件
    filter_info = ""
    if resolution:
        filter_info += f", 分辨率 = {resolution}"
    if codec:
        filter_info += f", 编码 = {codec}"
    if year_group:
        filter_info += f", 按年份分组 = 是"
    if remove_source:
        filter_info += f", 删除源目录 = 是"
    if require_ai_subtitle:
        filter_info += f", 需要AI字幕 = 是"
    if not override_files:
        filter_info += f", 覆盖文件 = 否"
    
    logging.info(f"mv2moviedir v{__version__} - 开始处理: 源目录 = {source_dir}, 目标目录 = {target_dir}{filter_info}")
    
    # 处理目录
    success_count, failure_count, skipped_count, removed_dirs_count = process_directory(
        source_dir, target_dir, resolution, codec, year_group, remove_source, 
        require_ai_subtitle, override_files
    )
    
    # 输出处理结果
    result_info = f"处理完成: 成功 = {success_count}, 失败 = {failure_count}, 跳过 = {skipped_count}"
    if remove_source:
        result_info += f", 删除源目录 = {removed_dirs_count}"
    
    logging.info(result_info)


if __name__ == "__main__":
    main()
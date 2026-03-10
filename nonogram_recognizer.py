#!/usr/bin/env python3
"""
数织 (Nonogram) 约束识别器
利用黑色描边+黄色填充的特征进行精准识别

使用方法:
    python nonogram_recognizer.py                    # 识别 screen.png
    python nonogram_recognizer.py <图片路径>          # 识别指定图片
    python nonogram_recognizer.py --debug            # 保存调试图像
"""

import cv2
import numpy as np
from pathlib import Path
import argparse
import json
import pytesseract
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import os


# ============================================================
# 配置常量
# ============================================================

# 目标颜色: RGB(252, 254, 83) -> BGR: (83, 254, 252)
TARGET_COLOR = np.array([83, 254, 252])
# 颜色匹配阈值（欧氏距离）
COLOR_DISTANCE_THRESHOLD = 20
# 颜色距离阈值的平方（避免开方运算）
COLOR_DISTANCE_SQUARED = COLOR_DISTANCE_THRESHOLD ** 2

# 图像裁剪参数
CROP_MARGIN = 20  # 边框填充边距

# 黑色描边检测阈值
BLACK_THRESHOLD = 80
MORPH_KERNEL_SIZE = (2, 2)

# 数字分组阈值
SAME_ROW_THRESHOLD = 20  # 同一行数字的 y 坐标容差
SAME_COL_THRESHOLD = 20  # 同一列数字的 x 坐标容差
MERGE_DISTANCE = 28      # 合并相邻数字的间距阈值
GAME_AREA_Y_START = 500  # 游戏区域 y 坐标起始点
GAME_AREA_SIZE = (1200, 1900)  # (width, height)

# OCR 配置
OCR_CONFIG = '--psm 6 -c tessedit_char_whitelist=0123456789'


# ============================================================
# OCR 预处理函数
# ============================================================

def ocr_preprocess(crop):
    """
    OCR 预处理：
    1. 提取目标颜色（黄绿色数字）区域作为掩码
    2. 该颜色变黑色，其他颜色变白色

    目标颜色: (252, 254, 83) -> BGR: (83, 254, 252)
    """
    if crop.size == 0:
        return None

    # 1. 计算每个像素与目标颜色的距离平方（避免开方运算）
    diff = crop.astype(np.float32) - TARGET_COLOR.astype(np.float32)
    distance_squared = np.sum(diff ** 2, axis=2)

    # 2. 距离平方小于阈值的视为目标颜色
    mask = distance_squared < COLOR_DISTANCE_SQUARED

    # 3. 创建白底黑字：目标颜色为黑，其他为白
    result = np.where(mask[:, :, np.newaxis], (0, 0, 0), (255, 255, 255))
    result = result.astype(np.uint8)

    return result


# ============================================================
# 数字区域检测函数
# ============================================================

def get_digit_contours_by_black(img, debug_dir=None):
    """
    通过黑色描边检测数字区域
    """
    # 1. 转灰度并提取极黑区域 (描边阈值)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, black_mask = cv2.threshold(
        gray, BLACK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)

    # 2. 较小的形态学闭合
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, MORPH_KERNEL_SIZE)
    closed = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel)

    # 3. 寻找轮廓
    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"检测到 {len(contours)} 个轮廓")

    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "01_black_mask.png"), black_mask)
        cv2.imwrite(str(debug_dir / "02_closed_mask.png"), closed)

    all_digits = []

    p1 = [-1, -1]
    p2 = [-1, -1]

    # 4. 过滤并分类
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if y < GAME_AREA_Y_START:
            continue
        all_digits.append((x, y, w, h))
        if y > p1[1] + SAME_ROW_THRESHOLD:
            p1[1] = y
            p1[0] = x
        elif abs(y - p1[1]) <= SAME_ROW_THRESHOLD:
            p1[0] = max(p1[0], x)

        if x > p2[0] + SAME_COL_THRESHOLD:
            p2[0] = x
            p2[1] = y
        elif abs(x - p2[0]) <= SAME_COL_THRESHOLD:
            p2[1] = max(p2[1], y)

    row_digits = [x for x in all_digits if x[0] <= p1[0] + MERGE_DISTANCE]
    col_digits = [x for x in all_digits if x[1] <= p2[1] + MERGE_DISTANCE]

    print(p1, p2)

    return row_digits, col_digits, (p1[0] + MERGE_DISTANCE, p2[1] + MERGE_DISTANCE), (p2[0] + MERGE_DISTANCE, p1[1] + MERGE_DISTANCE)


# ============================================================
# OCR 识别函数
# ============================================================

# 并行OCR线程数配置
cpu_cores = os.cpu_count() or 4
ROW_COL_PARALLEL_WORKERS = min(cpu_cores - 1, 4)


def _ocr_single_digit(args):
    """单次OCR任务（用于并行执行）"""
    x, y, w, h, img = args
    crop = img[y:y + h, x:x + w]
    crop = cv2.copyMakeBorder(crop, CROP_MARGIN, CROP_MARGIN, CROP_MARGIN, CROP_MARGIN,
                              cv2.BORDER_CONSTANT, value=(255, 255, 255))
    if len(crop.shape) == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop
    text = pytesseract.image_to_string(gray, config=OCR_CONFIG)
    return (x, y, text.strip())


def _parallel_ocr(digit_regions, img):
    """
    并行OCR识别多个数字区域

    参数:
        digit_regions: [(x, y, w, h), ...] 数字区域列表
        img: 预处理后的图像

    返回:
        [(x, y, text), ...] 识别结果
    """
    if not digit_regions:
        return []

    # 准备任务数据
    tasks = [(x, y, w, h, img) for (x, y, w, h) in digit_regions]

    # 使用线程池并行执行
    with ThreadPoolExecutor(max_workers=ROW_COL_PARALLEL_WORKERS) as executor:
        results = list(executor.map(_ocr_single_digit, tasks))

    return results


def f_row(img, row_digits):
    """处理行约束数字识别"""
    print(f"检测到 {len(row_digits)} 个行数字区域")
    # 使用并行OCR
    result = _parallel_ocr(row_digits, img)
    result.sort(key=lambda x: (x[1], x[0]))
    position_groups = defaultdict(list)
    last_position = -1000
    for x, y, text in result:
        if y - last_position > SAME_ROW_THRESHOLD:
            position_groups[y].append([text, x])
            last_position = y
        else:
            position_groups[last_position].append([text, x])
    ans = []
    for y, values in position_groups.items():
        values.sort(key=lambda x: x[1])
        merged = []
        last_x = -1000
        for t, x in values:
            if x - last_x < MERGE_DISTANCE:
                merged[-1] += t
            else:
                merged.append(t)
                last_x = x
        ans.append(" ".join(merged))
    return '\n'.join(ans)


def f_col(img, col_digits):
    """处理列约束数字识别"""
    print(f"检测到 {len(col_digits)} 个列数字区域")
    # 使用并行OCR
    result = _parallel_ocr(col_digits, img)

    # result 先按 x 排序分组，再按 y 排序 分组
    result.sort(key=lambda x: (x[0], x[1]))
    primary_groups = defaultdict(list)
    last_position = -1000
    for x, y, text in result:
        if x - last_position > MERGE_DISTANCE:
            primary_groups[x].append([x, y, text])
            last_position = x
        else:
            primary_groups[last_position].append([x, y, text])
    ans = []
    for x, values in primary_groups.items():
        values.sort(key=lambda x: x[1])
        secondary_groups = defaultdict(list)
        last_position = -1000
        for x_item, y, text in values:
            if y - last_position > MERGE_DISTANCE:
                secondary_groups[y].append([x_item, y, text])
                last_position = y
            else:
                secondary_groups[last_position].append([x_item, y, text])
        merged = []
        for y, secondary_values in secondary_groups.items():
            secondary_values.sort(key=lambda x: x[0])
            merged.append("".join(item[2] for item in secondary_values))
        ans.append(" ".join(merged))

    return '\n'.join(ans)


# ============================================================
# 主识别函数
# ============================================================

def recognize_from_image(img_path, debug=False):
    """
    从图片识别数织约束

    参数:
        img_path: 图片路径或 pathlib.Path 对象
        debug: 是否保存调试图像

    返回:
        dict: {
            "row": "行约束字符串（每行一个，用空格分隔多个数字）",
            "col": "列约束字符串（每行一个，用空格分隔多个数字）",
            "pos": ((x1, y1), (x2, y2)) - 游戏区域边界坐标
        }
    """
    img_path = Path(img_path)
    img = cv2.imread(str(img_path))
    if img is None:
        raise FileNotFoundError(f"无法读取图像: {img_path}")

    debug_dir = img_path.parent / "debug"

    # img 截取游戏区域 (width=1200, height=1900)
    img = img[0:GAME_AREA_SIZE[1], 0:GAME_AREA_SIZE[0]]

    # 把整张图的目标颜色变成黑色，其余变成白色
    img = ocr_preprocess(img)

    if debug and debug_dir:
        cv2.imwrite(str(debug_dir / "03_ocr_preprocess.png"), img)

    # 从img中找黑色的数字区域
    row_digits, col_digits, p1, p2 = get_digit_contours_by_black(
        img, debug_dir)

    # 并行执行行和列的OCR识别，提升约50%性能
    with ThreadPoolExecutor(max_workers=2) as executor:
        row_future = executor.submit(f_row, img, row_digits)
        col_future = executor.submit(f_col, img, col_digits)
        row, col = row_future.result(), col_future.result()

    return {
        "row": row,
        "col": col,
        "pos": (p1, p2)
    }


def main():
    parser = argparse.ArgumentParser(description='数织约束识别器')
    parser.add_argument('image', nargs='?',
                        default='screen.png', help='图像文件路径')
    parser.add_argument('--debug', action='store_true', help='保存调试图像')
    args = parser.parse_args()

    # 图像路径（让 cv2.imread 处理文件不存在的情况）
    img_path = Path(__file__).parent / args.image
    if not img_path.is_file():
        img_path = Path(args.image)

    print(f"识别图片: {img_path}")
    print("-" * 50)

    try:
        result = recognize_from_image(img_path, debug=args.debug)

        print()
        print("行约束 (左侧，从上到下):")
        print(result['row'])

        print()
        print("列约束 (顶部，从左到右):")
        print(result['col'])

        print()
        print("=" * 50)
        print("JSON 格式输出:")
        print("=" * 50)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

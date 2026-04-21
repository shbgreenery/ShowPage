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
TARGET_COLOR1 = np.array([83, 254, 252])
# 目标颜色: RGB(172,131 ,31) -> BGR: (31, 131, 172)
TARGET_COLOR2 = np.array([31, 131, 172])
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
GAME_AREA_SIZE = (1200, 2200)  # (width, height)

# 约束边界验证阈值
ROW_CONSTRAINT_MIN_Y = 1700  # 行约束最小 y 边界
COL_CONSTRAINT_MIN_X = 1000  # 列约束最小 x 边界

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

    """
    if crop.size == 0:
        return None

    # 1. 计算每个像素与目标颜色的距离平方（避免开方运算）
    diff = crop.astype(np.float32) - TARGET_COLOR1.astype(np.float32)
    distance_squared = np.sum(diff ** 2, axis=2)
    diff2 = crop.astype(np.float32) - TARGET_COLOR2.astype(np.float32)
    distance_squared2 = np.sum(diff2 ** 2, axis=2)

    # 2. 距离平方小于阈值的视为目标颜色
    mask1 = distance_squared < COLOR_DISTANCE_SQUARED
    mask2 = distance_squared2 < COLOR_DISTANCE_SQUARED
    mask = mask1 | mask2

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
        if w < 10 or h < 30:
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

    return row_digits, col_digits, (p1[0] + 30, p2[1] + 50), (p2[0] + 50, p1[1] + 50)


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
    for psv in [6, 7, 8, 10]:
        config = f'--psm {psv} -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(gray, config=config)
        if text.strip():
            return (x, y, text.strip())
    # cv2.imwrite(f"debug/{x}_{y}.png", crop)
    return (x, y, "")


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


def _calculate_min_spacing(positions):
    """计算位置列表中间距的中位数"""
    if len(positions) < 2:
        return 50  # 默认间距
    sorted_pos = sorted(positions)
    spacings = []
    for i in range(1, len(sorted_pos)):
        spacing = sorted_pos[i] - sorted_pos[i-1]
        if spacing > 0:
            spacings.append(spacing)

    if not spacings:
        return 50

    # 计算中位数
    spacings.sort()
    n = len(spacings)
    if n % 2 == 1:
        return spacings[n // 2]
    else:
        return (spacings[n // 2 - 1] + spacings[n // 2]) / 2


def _pad_constraints(constraints, min_spacing, threshold_factor=1.5):
    """
    补全缺失的约束

    参数:
        constraints: [(position, value), ...] 位置值对列表
        min_spacing: 最小间距
        threshold_factor: 判断缺失的阈值倍数

    返回:
        补全后的约束值列表
    """
    if not constraints:
        return []

    # 按位置排序
    sorted_constraints = sorted(constraints, key=lambda x: x[0])

    threshold = min_spacing * threshold_factor
    result = []

    for i, (pos, value) in enumerate(sorted_constraints):
        if i > 0:
            prev_pos = sorted_constraints[i-1][0]
            gap = pos - prev_pos
            # 如果间距超过阈值，插入缺失的约束
            if gap > threshold:
                missing_count = int(round(gap / min_spacing)) - 1
                for _ in range(max(0, missing_count)):
                    result.append("-1")
        result.append(value)

    return result


def _finalize_constraints(constraints, target_counts=[10, 15]):
    """
    最终补齐约束到目标数量

    参数:
        constraints: 约束值列表
        target_counts: 目标数量列表（通常是10或15）

    返回:
        补齐后的约束值列表
    """
    current_count = len(constraints)
    target_count = None
    for tc in target_counts:
        if current_count <= tc:
            target_count = tc
            break

    if target_count is None:
        target_count = target_counts[-1]

    # 补齐到目标数量
    while len(constraints) < target_count:
        constraints.append("-1")

    return constraints[:target_count]


def _pad_to_boundary(constraints, positions, min_spacing, boundary_threshold):
    """
    根据边界阈值补全约束

    参数:
        constraints: 约束列表（会被修改）
        positions: 位置列表
        min_spacing: 最小间距
        boundary_threshold: 边界阈值
    """
    if positions:
        max_pos = max(positions)
        if max_pos < boundary_threshold:
            needed = int((boundary_threshold - max_pos) / min_spacing)
            for _ in range(max(0, needed)):
                constraints.append("-1")
    return constraints


def f_row(img, row_digits, col_max_y=None):
    """
    处理行约束数字识别

    参数:
        img: 预处理后的图像
        row_digits: 行数字区域列表
        col_max_y: 列约束的最大y坐标，用于确定行约束的起始位置
    """
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

    # 提取约束和位置信息用于补全
    constraints_with_pos = []
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
        constraint_value = " ".join(merged) if merged else "-1"
        constraints_with_pos.append((y, constraint_value))

    # 计算最小行间距
    y_positions = [pos for pos, _ in constraints_with_pos]
    min_dy = _calculate_min_spacing(y_positions)

    # 如果有列约束的最大y坐标，检查是否需要从该位置开始补全
    if col_max_y is not None and constraints_with_pos:
        expected_start_y = col_max_y + 50
        first_row_y = constraints_with_pos[0][0]
        if first_row_y > expected_start_y + min_dy * 1.5:
            # 需要在开头补全缺失的行
            missing_count = int(
                round((first_row_y - expected_start_y) / min_dy))
            # 使用列表拼接替代 insert(0, ...) 避免 O(n²)
            missing = [(expected_start_y, "-1")] * max(0, missing_count)
            constraints_with_pos = missing + constraints_with_pos

    # 补全中间缺失的行
    padded_constraints = _pad_constraints(constraints_with_pos, min_dy)

    # 行约束边界验证：最大的 y 必须大于 ROW_CONSTRAINT_MIN_Y
    _pad_to_boundary(padded_constraints, y_positions,
                     min_dy, ROW_CONSTRAINT_MIN_Y)

    # 最终补齐到目标数量（10或15）
    final_constraints = _finalize_constraints(padded_constraints)

    return '\n'.join(final_constraints)


def f_col(img, col_digits, row_max_x=None):
    """
    处理列约束数字识别

    参数:
        img: 预处理后的图像
        col_digits: 列数字区域列表
        row_max_x: 行约束的最大x坐标，用于确定列约束的起始位置
    """
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

    # 提取约束和位置信息用于补全
    constraints_with_pos = []
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
        constraint_value = " ".join(merged) if merged else "-1"
        constraints_with_pos.append((x, constraint_value))

    # 计算最小列间距
    x_positions = [pos for pos, _ in constraints_with_pos]
    min_dx = _calculate_min_spacing(x_positions)

    # 如果有行约束的最大x坐标，检查是否需要从该位置开始补全
    if row_max_x is not None and constraints_with_pos:
        expected_start_x = row_max_x + 30
        first_col_x = constraints_with_pos[0][0]
        if first_col_x > expected_start_x + min_dx * 1.5:
            # 需要在开头补全缺失的列
            missing_count = int(
                round((first_col_x - expected_start_x) / min_dx))
            # 使用列表拼接替代 insert(0, ...) 避免 O(n²)
            missing = [(expected_start_x, "-1")] * max(0, missing_count)
            constraints_with_pos = missing + constraints_with_pos

    # 补全中间缺失的列
    padded_constraints = _pad_constraints(constraints_with_pos, min_dx)

    # 列约束边界验证：最大的 x 必须大于 COL_CONSTRAINT_MIN_X
    _pad_to_boundary(padded_constraints, x_positions,
                     min_dx, COL_CONSTRAINT_MIN_X)

    # 最终补齐到目标数量（10或15）
    final_constraints = _finalize_constraints(padded_constraints)

    return '\n'.join(final_constraints)


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
    # p1: (row_max_x + 30, col_max_y + 50) - 行约束的x边界, 列约束的y边界
    # p2: (col_max_x + 50, row_max_y + 50) - 列约束的x边界, 行约束的y边界
    row_digits, col_digits, p1, p2 = get_digit_contours_by_black(
        img, debug_dir)

    # 提取边界坐标用于补全逻辑
    # p1[0] = row_max_x + 30, p1[1] = col_max_y + 50
    # p2[0] = col_max_x + 50, p2[1] = row_max_y + 50
    row_max_x = p1[0] - 30
    col_max_y = p1[1] - 50

    # 并行执行行和列的OCR识别，提升约50%性能
    # 传递坐标信息用于行列补全
    with ThreadPoolExecutor(max_workers=2) as executor:
        row_future = executor.submit(f_row, img, row_digits, col_max_y)
        col_future = executor.submit(f_col, img, col_digits, row_max_x)
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

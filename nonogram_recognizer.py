#!/usr/bin/env python3
"""
数织 (Nonogram) 约束识别器
利用黑色描边+黄色填充的特征进行精准识别
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
import logging

from logger_config import setup_logger

logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================
TARGET_COLOR1 = np.array([83, 254, 252])
TARGET_COLOR2 = np.array([31, 131, 172])
COLOR_DISTANCE_THRESHOLD = 20
COLOR_DISTANCE_SQUARED = COLOR_DISTANCE_THRESHOLD ** 2
CROP_MARGIN = 20
BLACK_THRESHOLD = 80
MORPH_KERNEL_SIZE = (2, 2)
SAME_ROW_THRESHOLD = 20
SAME_COL_THRESHOLD = 20
MERGE_DISTANCE = 28
GAME_AREA_Y_START = 500
GAME_AREA_SIZE = (1200, 2200)
ROW_CONSTRAINT_MIN_Y = 1700
COL_CONSTRAINT_MIN_X = 1000
OCR_CONFIG = '--psm 6 -c tessedit_char_whitelist=0123456789'

# ============================================================
# OCR 预处理函数
# ============================================================

def ocr_preprocess(crop):
    if crop.size == 0:
        return None

    diff = crop.astype(np.float32) - TARGET_COLOR1.astype(np.float32)
    distance_squared = np.sum(diff ** 2, axis=2)
    diff2 = crop.astype(np.float32) - TARGET_COLOR2.astype(np.float32)
    distance_squared2 = np.sum(diff2 ** 2, axis=2)

    mask = (distance_squared < COLOR_DISTANCE_SQUARED) | (distance_squared2 < COLOR_DISTANCE_SQUARED)
    result = np.where(mask[:, :, np.newaxis], (0, 0, 0), (255, 255, 255)).astype(np.uint8)
    return result

# ============================================================
# 数字区域检测函数
# ============================================================

def get_digit_contours_by_black(img, debug_dir=None):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, black_mask = cv2.threshold(gray, BLACK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, MORPH_KERNEL_SIZE)
    closed = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    logger.debug(f"检测到 {len(contours)} 个初始轮廓")

    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "01_black_mask.png"), black_mask)
        cv2.imwrite(str(debug_dir / "02_closed_mask.png"), closed)

    all_digits = []
    p1 = [-1, -1]
    p2 = [-1, -1]

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if y < GAME_AREA_Y_START or w < 10 or h < 30:
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

    row_digits = [d for d in all_digits if d[0] <= p1[0] + MERGE_DISTANCE]
    col_digits = [d for d in all_digits if d[1] <= p2[1] + MERGE_DISTANCE]

    logger.debug(f"行/列边界点: p1={p1}, p2={p2}")
    return row_digits, col_digits, (p1[0] + 30, p2[1] + 50), (p2[0] + 50, p1[1] + 50)

# ============================================================
# OCR 识别函数
# ============================================================

cpu_cores = os.cpu_count() or 4
ROW_COL_PARALLEL_WORKERS = min(cpu_cores - 1, 4)

def _ocr_single_digit(args):
    x, y, w, h, img = args
    crop = img[y:y + h, x:x + w]
    crop = cv2.copyMakeBorder(crop, CROP_MARGIN, CROP_MARGIN, CROP_MARGIN, CROP_MARGIN, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    for psv in [6, 7, 8, 10]:
        config = f'--psm {psv} -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(gray, config=config).strip()
        if text:
            return (x, y, text)
    return (x, y, "")

def _parallel_ocr(digit_regions, img):
    if not digit_regions:
        return []
    tasks = [(x, y, w, h, img) for (x, y, w, h) in digit_regions]
    with ThreadPoolExecutor(max_workers=ROW_COL_PARALLEL_WORKERS) as executor:
        return list(executor.map(_ocr_single_digit, tasks))

def _calculate_min_spacing(positions):
    if len(positions) < 2:
        return 50
    spacings = sorted([positions[i] - positions[i-1] for i in range(1, len(positions)) if positions[i] - positions[i-1] > 0])
    if not spacings: return 50
    mid = len(spacings) // 2
    return spacings[mid] if len(spacings) % 2 == 1 else (spacings[mid - 1] + spacings[mid]) / 2

def _pad_constraints(constraints, min_spacing, threshold_factor=1.5):
    if not constraints: return []
    sorted_constraints = sorted(constraints, key=lambda x: x[0])
    threshold = min_spacing * threshold_factor
    result = []
    for i, (pos, value) in enumerate(sorted_constraints):
        if i > 0:
            gap = pos - sorted_constraints[i-1][0]
            if gap > threshold:
                missing_count = int(round(gap / min_spacing)) - 1
                result.extend(["-1"] * max(0, missing_count))
        result.append(value)
    return result

def _finalize_constraints(constraints, target_counts=[10, 15]):
    current_count = len(constraints)
    target_count = next((tc for tc in target_counts if current_count <= tc), target_counts[-1])
    constraints.extend(["-1"] * (target_count - current_count))
    return constraints[:target_count]

def _pad_to_boundary(constraints, positions, min_spacing, boundary_threshold):
    if positions:
        max_pos = max(positions)
        if max_pos < boundary_threshold:
            needed = int((boundary_threshold - max_pos) / min_spacing)
            constraints.extend(["-1"] * max(0, needed))
    return constraints

def f_row(img, row_digits, col_max_y=None):
    logger.debug(f"检测到 {len(row_digits)} 个行数字区域")
    result = sorted(_parallel_ocr(row_digits, img), key=lambda x: (x[1], x[0]))
    position_groups = defaultdict(list)
    last_y = -1000
    for x, y, text in result:
        if y - last_y > SAME_ROW_THRESHOLD:
            last_y = y
        position_groups[last_y].append([text, x])

    constraints_with_pos = []
    for y, values in sorted(position_groups.items()):
        values.sort(key=lambda item: item[1])
        merged = []
        last_x = -1000
        for t, x in values:
            if x - last_x < MERGE_DISTANCE and merged:
                merged[-1] += t
            else:
                merged.append(t)
            last_x = x
        constraints_with_pos.append((y, " ".join(merged) if merged else "-1"))

    y_positions = [pos for pos, _ in constraints_with_pos]
    min_dy = _calculate_min_spacing(y_positions)

    if col_max_y is not None and constraints_with_pos:
        expected_start_y = col_max_y + 50
        if constraints_with_pos[0][0] > expected_start_y + min_dy * 1.5:
            missing_count = int(round((constraints_with_pos[0][0] - expected_start_y) / min_dy))
            constraints_with_pos = [(expected_start_y, "-1")] * max(0, missing_count) + constraints_with_pos

    padded = _pad_constraints(constraints_with_pos, min_dy)
    _pad_to_boundary(padded, y_positions, min_dy, ROW_CONSTRAINT_MIN_Y)
    return '\n'.join(_finalize_constraints(padded))

def f_col(img, col_digits, row_max_x=None):
    logger.debug(f"检测到 {len(col_digits)} 个列数字区域")
    result = sorted(_parallel_ocr(col_digits, img), key=lambda x: (x[0], x[1]))
    primary_groups = defaultdict(list)
    last_x = -1000
    for x, y, text in result:
        if x - last_x > MERGE_DISTANCE:
            last_x = x
        primary_groups[last_x].append([x, y, text])

    constraints_with_pos = []
    for x, values in sorted(primary_groups.items()):
        values.sort(key=lambda item: item[1])
        merged = [" ".join(item[2] for item in values)]
        constraints_with_pos.append((x, merged[0] if merged else "-1"))

    x_positions = [pos for pos, _ in constraints_with_pos]
    min_dx = _calculate_min_spacing(x_positions)

    if row_max_x is not None and constraints_with_pos:
        expected_start_x = row_max_x + 30
        if constraints_with_pos[0][0] > expected_start_x + min_dx * 1.5:
            missing_count = int(round((constraints_with_pos[0][0] - expected_start_x) / min_dx))
            constraints_with_pos = [(expected_start_x, "-1")] * max(0, missing_count) + constraints_with_pos

    padded = _pad_constraints(constraints_with_pos, min_dx)
    _pad_to_boundary(padded, x_positions, min_dx, COL_CONSTRAINT_MIN_X)
    return '\n'.join(_finalize_constraints(padded))


# ============================================================
# 主识别函数
# ============================================================

def recognize_from_image(img_path, debug=False):
    img_path = Path(img_path)
    img = cv2.imread(str(img_path))
    if img is None: raise FileNotFoundError(f"无法读取图像: {img_path}")

    debug_dir = img_path.parent / "debug_nonogram" if debug else None
    img = img[0:GAME_AREA_SIZE[1], 0:GAME_AREA_SIZE[0]]
    processed_img = ocr_preprocess(img)
    if debug and debug_dir: cv2.imwrite(str(debug_dir / "03_ocr_preprocess.png"), processed_img)

    row_digits, col_digits, p1, p2 = get_digit_contours_by_black(processed_img, debug_dir)
    row_max_x, col_max_y = p1[0] - 30, p1[1] - 50

    with ThreadPoolExecutor(max_workers=2) as executor:
        row_future = executor.submit(f_row, processed_img, row_digits, col_max_y)
        col_future = executor.submit(f_col, processed_img, col_digits, row_max_x)
        row, col = row_future.result(), col_future.result()

    return {"row": row, "col": col, "pos": (p1, p2)}

def main():
    parser = argparse.ArgumentParser(description='数织约束识别器')
    parser.add_argument('image', nargs='?', default='screen.png', help='图像文件路径')
    parser.add_argument('--debug', action='store_true', help='开启调试模式，显示详细日志')
    args = parser.parse_args()

    setup_logger(args.debug)

    img_path = Path(__file__).parent / args.image
    if not img_path.is_file(): img_path = Path(args.image)

    logger.info(f"开始识别图像: {img_path}")

    try:
        result = recognize_from_image(img_path, debug=args.debug)
        logger.info("识别成功！")
        logger.debug("行约束 (左侧，从上到下):\n" + result['row'])
        logger.debug("列约束 (顶部，从左到右):\n" + result['col'])
        logger.debug("JSON 格式输出:\n" + json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"识别失败: {e}", exc_info=True)

if __name__ == '__main__':
    main()

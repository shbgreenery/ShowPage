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
OCR_DIGIT_WHITELIST = '0123456789'


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
    _, black_mask = cv2.threshold(gray, BLACK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)

    # 2. 较小的形态学闭合
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, MORPH_KERNEL_SIZE)
    closed = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel)

    # 3. 寻找轮廓
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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

def f_row(img, row_digits, debug_dir=None):  # noqa: ARG001
    """处理行约束数字识别"""
    print(f"检测到 {len(row_digits)} 个行数字区域")
    result = []
    for _, (x, y, w, h) in enumerate(row_digits):
        crop = img[y:y + h, x:x + w]
        crop = cv2.copyMakeBorder(crop, CROP_MARGIN, CROP_MARGIN, CROP_MARGIN, CROP_MARGIN,
                                   cv2.BORDER_CONSTANT, value=(255, 255, 255))
        # 转为灰度图给 pytesseract
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop
        # 只识别数字
        text = pytesseract.image_to_string(gray, config=OCR_CONFIG)
        text = text.strip()
        result.append((x, y, text))
        if text == " " * len(text):
            print("识别到空行")
    result.sort(key=lambda x: (x[1], x[0]))
    group = defaultdict(list)
    ls = -1000
    for x, y, text in result:
        if y - ls > SAME_ROW_THRESHOLD:
            group[y].append([text, x])
            ls = y
        else:
            group[ls].append([text, x])
    ans = []
    for y, vs in group.items():
        vs.sort(key=lambda x: x[1])
        tmp = []
        lx = -1000
        for t, x in vs:
            if x - lx < MERGE_DISTANCE:
                tmp[-1] += t
            else:
                tmp.append(t)
                lx = x
        ans.append(" ".join(tmp))
    return '\n'.join(ans)


def f_col(img, col_digits, debug_dir=None):  # noqa: ARG001
    """处理列约束数字识别"""
    print(f"检测到 {len(col_digits)} 个列数字区域")
    result = []
    for _, (x, y, w, h) in enumerate(col_digits):
        crop = img[y:y + h, x:x + w]
        crop = cv2.copyMakeBorder(crop, CROP_MARGIN, CROP_MARGIN, CROP_MARGIN, CROP_MARGIN,
                                   cv2.BORDER_CONSTANT, value=(255, 255, 255))
        # 转为灰度图给 pytesseract
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop
        # 只识别数字
        text = pytesseract.image_to_string(gray, config=OCR_CONFIG)
        text = text.strip()
        result.append((x, y, text))

    #  result 先按 x 排序分组，再按y 排序 分组
    result.sort( key=lambda x: (x[0], x[1]))
    group = defaultdict(list)
    ls = -1000
    for x, y, text in result:
        if x - ls > MERGE_DISTANCE:
            group[x].append([x,y,text])
            ls = x
        else:
            group[ls].append([x,y,text])
    ans = []
    for x, vs in group.items():
        vs.sort(key=lambda x: x[1])
        ng = defaultdict(list)
        ls = -1000
        for x,y,text in vs:
            if y-ls>MERGE_DISTANCE:
                ng[y].append([x,y,text])
                ls = y
            else:
                ng[ls].append([x,y,text])
        tmp = []
        for y,vs2 in ng.items():
            vs2.sort(key=lambda x: x[0])
            tmp.append("".join(item[2] for item in vs2))
        ans.append(" ".join(tmp))

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
    row_digits, col_digits, p1, p2 = get_digit_contours_by_black(img, debug_dir)

    row = f_row(img, row_digits,debug_dir)
    col = f_col(img, col_digits,debug_dir)

    return {
        "row": row,
        "col": col,
        "pos": (p1, p2)
    }


def main():
    parser = argparse.ArgumentParser(description='数织约束识别器')
    parser.add_argument('image', nargs='?', default='screen.png', help='图像文件路径')
    parser.add_argument('--debug', action='store_true', help='保存调试图像')
    args = parser.parse_args()

    # 图像路径
    img_path = Path(__file__).parent / args.image
    if not img_path.exists():
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

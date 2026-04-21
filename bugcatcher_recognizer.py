import cv2
import numpy as np
import json
import argparse
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from sklearn.cluster import KMeans
import bisect
import logging

from bugcatcher_constants import JSONKeys
from logger_config import setup_logger

# 初始化日志记录器
logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================

# 网格线颜色 (BGR格式)
GRID_LINE_COLOR = np.array([72, 104, 158])
COLOR_DISTANCE_THRESHOLD = 30
COLOR_DISTANCE_SQUARED = COLOR_DISTANCE_THRESHOLD ** 2

# 形态学操作核大小
MORPH_KERNEL_SIZE_CLOSE = (5, 5)
MORPH_KERNEL_SIZE_OPEN = (3, 3)

# 游戏区域约束
GAME_AREA_MIN_Y = 800  # 游戏网格大致从 y=800 以下开始

# 格子大小与形状约束
MIN_CELL_AREA = 500
MAX_CELL_AREA = 50000
MIN_ASPECT_RATIO = 0.85  # 几乎是正方形
MAX_ASPECT_RATIO = 1.15

# 颜色采样参数
SAMPLE_MARGIN = 10  # 距离格子边缘的采样偏移量
CPU_CORES = os.cpu_count() or 4
COLOR_SAMPLING_WORKERS = min(CPU_CORES - 1, 8)

# K-means 聚类参数
N_CLUSTERS_MIN = 3
N_CLUSTERS_MAX = 10


# ============================================================
# 核心函数 - 格子检测
# ============================================================

def extract_grid_lines(img):
    """从图像中提取网格线掩码"""
    diff = img.astype(np.float32) - GRID_LINE_COLOR.astype(np.float32)
    distance_squared = np.sum(diff ** 2, axis=2)
    mask = distance_squared < COLOR_DISTANCE_SQUARED
    grid_mask = np.where(mask, 255, 0).astype(np.uint8)
    return grid_mask

def morphology_operations(mask):
    """对掩码进行形态学操作，连接断线、去除噪点"""
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, MORPH_KERNEL_SIZE_CLOSE)
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, MORPH_KERNEL_SIZE_OPEN)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_open)
    return opened

def find_cell_contours(mask):
    """寻找所有可能是格子的轮廓"""
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    return contours

def filter_and_sort_cells(contours):
    """过滤并排序轮廓，得到有序的格子列表"""
    valid_cells = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (MIN_CELL_AREA < area < MAX_CELL_AREA):
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        if w == 0 or h == 0: continue

        if y < GAME_AREA_MIN_Y:
            continue

        aspect_ratio = w / h
        if not (MIN_ASPECT_RATIO < aspect_ratio < MAX_ASPECT_RATIO):
            continue

        valid_cells.append((x, y, w, h))

    valid_cells.sort(key=lambda c: (c[1], c[0]))
    return valid_cells

def extract_grid_cells(img_path, debug_dir=None):
    """主函数：从图像中提取所有格子的边界框"""
    img = cv2.imread(str(img_path))
    if img is None:
        raise FileNotFoundError(f"无法读取图像: {img_path}")

    grid_mask = extract_grid_lines(img)
    morph_mask = morphology_operations(grid_mask)
    contours = find_cell_contours(morph_mask)
    cells = filter_and_sort_cells(contours)

    if debug_dir:
        debug_dir.mkdir(exist_ok=True)
        cv2.imwrite(str(debug_dir / "01_grid_mask.png"), grid_mask)
        cv2.imwrite(str(debug_dir / "02_morph_mask.png"), morph_mask)
        img_all_contours = img.copy()
        cv2.drawContours(img_all_contours, contours, -1, (0, 255, 0), 2)
        cv2.imwrite(str(debug_dir / "03_all_contours.png"), img_all_contours)
        img_filtered = img.copy()
        for x, y, w, h in cells:
            cv2.rectangle(img_filtered, (x, y), (x + w, y + h), (0, 0, 255), 3)
        cv2.imwrite(str(debug_dir / "04_filtered_cells.png"), img_filtered)

    return cells, img


# ============================================================
# 核心函数 - 颜色识别
# ============================================================

def sample_cell_color_corners(img, cell):
    """四角采样法：采样格子的四个角落颜色并取平均值"""
    x, y, w, h = cell
    margin = min(SAMPLE_MARGIN, w // 4, h // 4)

    points = [
        (x + margin, y + margin),
        (x + w - margin, y + margin),
        (x + margin, y + h - margin),
        (x + w - margin, y + h - margin),
    ]

    colors = []
    for px, py in points:
        bgr = img[py, px]
        rgb = (int(bgr[2]), int(bgr[1]), int(bgr[0]))
        colors.append(rgb)

    r_mean = int(np.mean([c[0] for c in colors]))
    g_mean = int(np.mean([c[1] for c in colors]))
    b_mean = int(np.mean([c[2] for c in colors]))

    return (r_mean, g_mean, b_mean)

def sample_all_colors_parallel(img, cells):
    """并行采样所有格子的颜色"""
    with ThreadPoolExecutor(max_workers=COLOR_SAMPLING_WORKERS) as executor:
        colors = list(executor.map(
            lambda c: sample_cell_color_corners(img, c),
            cells
        ))
    return colors

def find_optimal_k(data, min_k, max_k):
    """使用轮廓系数法自动寻找最佳K值"""
    from sklearn.metrics import silhouette_score
    best_k = -1
    best_score = -1

    unique_data_points = np.unique(data, axis=0)
    if len(unique_data_points) <= 1:
        return 1

    for k in range(min_k, max_k + 1):
        if k >= len(unique_data_points): continue
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(data)
        score = silhouette_score(data, labels)
        logger.debug(f"K-means with k={k}, silhouette score: {score:.4f}")
        if score > best_score:
            best_score = score
            best_k = k

    return best_k if best_k != -1 else min_k

def cluster_colors(colors, n_clusters=None):
    """K-means聚类，自动或手动确定聚类数"""
    color_array = np.array(colors)
    if n_clusters is None:
        n_clusters = find_optimal_k(color_array, N_CLUSTERS_MIN, N_CLUSTERS_MAX)
        logger.info(f"自动选择最佳 K值为: {n_clusters}")

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(color_array)
    centers = kmeans.cluster_centers_.astype(int)

    return labels, centers

def group_coordinates(coords, tolerance=20):
    """将一维坐标进行聚类，容差范围内视为同一行/列"""
    if not coords: return []
    sorted_coords = sorted(coords)
    groups = []
    current_group = [sorted_coords[0]]

    for c in sorted_coords[1:]:
        if c - current_group[-1] <= tolerance:
            current_group.append(c)
        else:
            groups.append(int(np.mean(current_group)))
            current_group = [c]
    groups.append(int(np.mean(current_group)))
    return groups

def find_nearest_index(sorted_coords, target):
    """使用二分查找找到最近值的索引"""
    i = bisect.bisect_left(sorted_coords, target)
    if i == 0:
        return 0
    if i == len(sorted_coords):
        return len(sorted_coords) - 1

    if abs(sorted_coords[i-1] - target) < abs(sorted_coords[i] - target):
        return i - 1
    return i

def build_color_matrix(cells, labels, unique_x, unique_y):
    """构建颜色矩阵并计算行列数"""
    num_rows = len(unique_y)
    num_cols = len(unique_x)
    matrix = [[-1] * num_cols for _ in range(num_rows)]

    annotated_cells = []
    for i, cell in enumerate(cells):
        cx = cell[0] + cell[2]//2
        cy = cell[1] + cell[3]//2

        r = find_nearest_index(unique_y, cy)
        c = find_nearest_index(unique_x, cx)

        matrix[r][c] = int(labels[i])
        annotated_cells.append({
            JSONKeys.ROW: r, JSONKeys.COL: c,
            JSONKeys.X: cell[0], JSONKeys.Y: cell[1],
            JSONKeys.W: cell[2], JSONKeys.H: cell[3],
            "color_id": int(labels[i])
        })

    return matrix, num_rows, num_cols, annotated_cells


# ============================================================
# 主函数与CLI接口
# ============================================================

def recognize_bugs(image_path, output_path='result.json', clusters=None, debug=False):
    """主逻辑封装，用于从其他脚本调用"""
    img_path = Path(image_path)
    debug_dir = img_path.parent / "debug_bugcatcher" if debug else None

    logger.info(f"开始识别图像: {img_path}")

    cells, img = extract_grid_cells(img_path, debug_dir)
    logger.debug(f"检测到 {len(cells)} 个有效格子")

    colors = sample_all_colors_parallel(img, cells)

    x_coords = [c[0] + c[2] // 2 for c in cells]
    y_coords = [c[1] + c[3] // 2 for c in cells]
    unique_x = group_coordinates(x_coords, tolerance=30)
    unique_y = group_coordinates(y_coords, tolerance=30)

    num_clusters = clusters
    if num_clusters is None:
        num_clusters = len(unique_y)
        logger.debug(f"根据格子几何位置分析，推测出有 {num_clusters} 种颜色区域。")

    labels, centers = cluster_colors(colors, num_clusters)
    logger.debug(f"识别出 {len(centers)} 种主要颜色")

    matrix, rows, cols, annotated_cells = build_color_matrix(cells, labels, unique_x, unique_y)
    color_map = {str(i): {"rgb": [int(v) for v in c], "count": int(np.sum(labels == i))} for i, c in enumerate(centers)}

    result = {
        JSONKeys.GRID_INFO: {JSONKeys.ROWS: rows, JSONKeys.COLS: cols, "total_cells": len(cells)},
        JSONKeys.COLOR_MAP: color_map,
        JSONKeys.COLOR_MATRIX: matrix,
        JSONKeys.CELLS: annotated_cells,
    }

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"识别完成！结果已保存到 {output_path}")
    else:
        logger.info("识别完成！")

    if debug:
        img_final = img.copy()
        for i, cell in enumerate(cells):
            color = centers[labels[i]]
            cv2.rectangle(img_final, (cell[0], cell[1]), (cell[0]+cell[2], cell[1]+cell[3]), tuple(color.tolist()), -1)
        cv2.imwrite(str(debug_dir / "05_color_result.png"), cv2.cvtColor(img_final.astype(np.uint8), cv2.COLOR_RGB2BGR))
        logger.info(f"调试图像已保存到 {debug_dir}")

    return result, output_path

def main():
    parser = argparse.ArgumentParser(description='田地捉虫 (Star Battle) 网格与颜色识别器')
    parser.add_argument('image', help='图像文件路径')
    parser.add_argument('--debug', action='store_true', help='开启调试模式，显示详细日志')
    parser.add_argument('--clusters', type=int, help='手动指定颜色聚类数')
    parser.add_argument('--output', default='result.json', help='输出JSON文件名')
    args = parser.parse_args()

    # 配置日志
    setup_logger(args.debug)

    try:
        recognize_bugs(args.image, args.output, args.clusters, args.debug)
    except Exception as e:
        logger.error(f"识别失败: {e}", exc_info=True)


if __name__ == '__main__':
    main()

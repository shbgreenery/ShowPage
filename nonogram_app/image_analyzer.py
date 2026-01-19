import cv2
import numpy as np
import pytesseract
import os


class ImageAnalyzer:
    def __init__(self):
        # 统一使用单行模式 (PSM 7)，因为我们把列也拼成了行
        self.tesseract_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
        self.debug = True

    def analyze_screenshot(self, image_path: str, manual_grid=None):
        try:
            image = cv2.imread(image_path)
            if image is None:
                return None, None, "无法读取图片"

            if not manual_grid:
                return None, None, "需要手动坐标"

            gx, gy, gw, gh = manual_grid

            ROWS = 15
            COLS = 15
            cell_h = gh / ROWS
            cell_w = gw / COLS

            # === 提取行 (左侧) ===
            row_hints = []
            for i in range(ROWS):
                y_start = int(gy + i * cell_h)
                y_end = int(gy + (i + 1) * cell_h)
                x_end = gx - 5
                x_start = max(5, x_end - 250)

                # 上下缩进，只取中间
                hint_img = image[y_start+10:y_end-10, x_start:x_end]

                # 行本身就是横的，直接处理
                nums = self._process_and_ocr(
                    hint_img, is_vertical=False, debug_id=f"row_{i}")
                if not nums:
                    row_hints.append([-1])
                else:
                    tmp = []
                    for c in list(nums):
                        tmp.append(int(c))
                    row_hints.append(tmp)

            # === 提取列 (上方) ===
            col_hints = []
            for j in range(COLS):
                x_start = int(gx + j * cell_w)
                x_end = int(gx + (j + 1) * cell_w)
                y_end = gy - 5
                y_start = max(0, y_end - 200)

                # 左右缩进
                hint_img = image[y_start:y_end, x_start+10:x_end-10]

                # 列是竖的，需要特殊处理
                nums = self._process_and_ocr(
                    hint_img, is_vertical=True, debug_id=f"col_{j}")
                if not nums:
                    col_hints.append([-1])
                else:
                    tmp = []
                    for c in list(nums):
                        tmp.append(int(c))
                    col_hints.append(tmp)

            return row_hints, col_hints, ""

        except Exception as e:
            import traceback
            traceback.print_exc()
            return None, None, str(e)

    def _process_and_ocr(self, img, is_vertical, debug_id=""):
        if img.size == 0:
            return []

        # 1. 预处理：HSV提取 + 二值化
        # 先把字抠出来，不管是横还是竖
        binary = self._preprocess_image(img)

        # 2. 关键修改：如果是列，进行【重排版】
        # 把竖排的 binary 图片变成横排的 binary 图片，数字保持直立
        if is_vertical:
            binary = self._vertical_to_horizontal_stitch(binary)

        # 3. 统一高度调整 (OCR 最佳高度 60)
        target_h = 60
        h, w = binary.shape[:2]
        if h > 0:
            scale = target_h / float(h)
            binary = cv2.resize(binary, None, fx=scale,
                                fy=scale, interpolation=cv2.INTER_NEAREST)

        # 4. 加宽白边
        binary = cv2.copyMakeBorder(
            binary, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

        # 5. OCR
        text = pytesseract.image_to_string(
            binary, config=self.tesseract_config)

        ans = ""
        text = text.replace('|', '1').replace('l', '1').replace('I', '1')
        text = text.replace('O', '0').replace('o', '0')
        text = text.replace('S', '5').replace('s', '5')
        text = text.replace('Z', '2')
        text = text.replace('?', '7')

        for part in text.split():
            clean = ''.join(filter(str.isdigit, part))
            if clean:
                ans += clean

        return ans

    def _preprocess_image(self, img):
        """提取文字并转为白底黑字"""
        # HSV 提取 (你验证过的 V>215)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower = np.array([0, 0, 215])
        upper = np.array([180, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)

        # 去噪
        kernel = np.ones((2, 2), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 连通域去噪
        mask = self._remove_small_noise(mask, min_size=15)

        # 膨胀加粗
        mask = cv2.dilate(mask, np.ones((2, 2), np.uint8), iterations=1)

        # 反转 (白底黑字)
        return cv2.bitwise_not(mask)

    def _vertical_to_horizontal_stitch(self, binary_img):
        """
        【核心魔法】
        将竖排的二值化图片（黑字白底）裁剪并拼接成横排
        """
        # 输入是白底黑字，为了找轮廓，先反转成黑底白字
        inverted = cv2.bitwise_not(binary_img)

        # 找轮廓
        contours, _ = cv2.findContours(
            inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return binary_img  # 没字，直接返回

        # 收集所有数字的包围盒
        boxes = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # 过滤掉极小的噪点
            if w * h > 10:
                boxes.append((x, y, w, h))

        # 按 Y 坐标排序 (从上到下)
        boxes.sort(key=lambda b: b[1])

        if not boxes:
            return binary_img

        # 创建一张新的空白横图
        # 高度取最高的数字高度 + padding
        # 宽度取所有数字宽度之和 + padding
        max_h = max([b[3] for b in boxes]) + 20
        total_w = sum([b[2] for b in boxes]) + (len(boxes) * 20) + 20

        # 白底
        new_img = np.full((max_h, total_w), 255, dtype=np.uint8)

        current_x = 10
        for (x, y, w, h) in boxes:
            # 抠出数字 (从原图 binary_img 抠，它是白底黑字的)
            digit_roi = binary_img[y:y+h, x:x+w]

            # 贴到新图上 (垂直居中)
            y_offset = (max_h - h) // 2
            new_img[y_offset:y_offset+h, current_x:current_x+w] = digit_roi

            # 移动 X 坐标
            current_x += w + 20  # 数字间距 20

        return new_img

    def _remove_small_noise(self, mask, min_size):
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8)
        output = np.zeros_like(mask)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= min_size:
                output[labels == i] = 255
        return output


if __name__ == "__main__":
    analyzer = ImageAnalyzer()

    # 图片路径
    img_path = "screenshot.png"  # 确保文件名对

    # 手动指定网格位置
    my_grid = (180, 890, 940, 940)

    if not os.path.exists(img_path):
        print("错误：找不到图片文件")
    else:
        print("开始分析...")
        r_hints, c_hints, err = analyzer.analyze_screenshot(
            img_path, manual_grid=my_grid)
        print(r_hints, c_hints)

        # if err:
        #     print(f"出错: {err}")
        # else:
        #     print("\n=== 提取结果 ===")
        #     print("行约束 (Rows):")
        #     for i, row in enumerate(r_hints):
        #         print(f"Row {i+1}: {row}")

        #     print("\n列约束 (Cols):")
        #     for i, col in enumerate(c_hints):
        #         print(f"Col {i+1}: {col}")

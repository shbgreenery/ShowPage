# color_picker.py
import cv2
import numpy as np

# 回调函数


def mouse_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        # 获取点击处的颜色
        pixel = hsv_img[y, x]
        h_val, s_val, v_val = pixel
        print(f"点击位置: ({x}, {y})")
        print(f"HSV值: H={h_val}, S={s_val}, V={v_val}")
        print(
            f"建议范围: Lower=[{max(0, h_val-10)}, {max(0, s_val-40)}, {max(0, v_val-40)}]")
        print(f"建议范围: Upper=[{min(180, h_val+10)}, 255, 255]")
        print("-" * 30)


# 读取图片 (改成你的截图路径)
image_path = "screenshot.png"
img = cv2.imread(image_path)

if img is None:
    print("找不到图片")
    exit()

# 缩放一下方便看
img = cv2.resize(img, None, fx=0.5, fy=0.5)

# 转换 HSV
hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

cv2.imshow("Click on the Yellow Numbers!", img)
cv2.setMouseCallback("Click on the Yellow Numbers!", mouse_click)

print("请点击图片中金黄色的数字部分...")
print("按 'q' 退出")

while True:
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()

import os
import random
from PIL import Image, ImageDraw
import numpy as np


def load_strokes(folder_path):
    """加载指定文件夹中的所有PNG笔画图片"""
    strokes = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.png'):
            try:
                filepath = os.path.join(folder_path, filename)
                stroke = Image.open(filepath).convert('RGBA')
                # 增强白色区域
                stroke = enhance_white(stroke)
                strokes.append(stroke)
            except Exception as e:
                print(f"无法加载图片 {filename}: {e}")
    return strokes


def enhance_white(image):
    """增强图像中的白色区域，使其更加明显"""
    width, height = image.size
    pixels = image.load()

    for y in range(height):
        for x in range(width):
            # 获取RGBA值
            r, g, b, a = pixels[x, y]

            # 如果不是透明像素，增强白色
            if a > 0:
                # 计算亮度
                brightness = (r + g + b) / 3

                # 如果接近白色，增强为纯白色
                if brightness > 180:  # 阈值可调整
                    pixels[x, y] = (255, 255, 255, a)
                # 如果接近黑色，增强为纯黑色
                elif brightness < 75:  # 阈值可调整
                    pixels[x, y] = (0, 0, 0, a)

    return image


def resize_stroke(stroke, target_area, max_dim=500):
    """调整笔画大小以适应目标面积和最大尺寸限制"""
    width, height = stroke.size
    current_area = width * height

    # 计算调整比例
    scale_factor = (target_area / current_area) ** 0.5

    # 确保调整后的尺寸不超过最大限制
    new_width = min(int(width * scale_factor), max_dim)
    new_height = min(int(height * scale_factor), max_dim)

    return stroke.resize((new_width, new_height), Image.LANCZOS)


def place_stroke_with_attraction(canvas, stroke, center_attraction=0.65, max_attempts=150):
    """尝试在画布上放置笔画，带有向中心吸引的趋势"""
    width, height = canvas.size
    stroke_width, stroke_height = stroke.size

    # 画布中心点
    center_x, center_y = width // 2, height // 2

    # 定义中心区域大小
    center_range = 25

    # 尝试多次寻找合适的位置
    for attempt in range(max_attempts):
        # 基础随机位置 - 使用更广泛的分布
        base_x_min = max(0, center_x - width // 3)
        base_x_max = min(width - stroke_width, center_x + width // 3)
        base_y_min = max(0, center_y - height // 3)
        base_y_max = min(height - stroke_height, center_y + height // 3)

        base_x = random.randint(base_x_min, base_x_max)
        base_y = random.randint(base_y_min, base_y_max)

        # 计算到中心的距离
        dist_x = center_x - (base_x + stroke_width // 2)
        dist_y = center_y - (base_y + stroke_height // 2)

        # 应用吸引力（降低吸引力强度）
        attraction_factor = min(1.0, attempt / max_attempts * center_attraction)
        attracted_x = int(base_x + dist_x * attraction_factor)
        attracted_y = int(base_y + dist_y * attraction_factor)

        # 确保位置在画布内
        x = max(0, min(attracted_x, width - stroke_width))
        y = max(0, min(attracted_y, height - stroke_height))

        position = (x, y)

        # 允许更大的重叠（阈值提高到0.5）
        if not is_overlapping(canvas, stroke, position, threshold=0.5):
            # 创建一个透明的图层用于放置笔画
            stroke_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            stroke_layer.paste(stroke, position, stroke)

            # 将笔画合并到画布上
            canvas = Image.alpha_composite(canvas, stroke_layer)
            return canvas, position

    # 如果尝试多次仍无法放置，返回原始画布
    return canvas, None


def is_overlapping(canvas, stroke, position, threshold=0.5):
    """检查笔画放置在指定位置是否与现有内容重叠超过阈值"""
    x, y = position
    width, height = stroke.size

    # 裁剪画布区域以匹配笔画大小
    try:
        canvas_region = canvas.crop((x, y, x + width, y + height))
    except ValueError:
        # 如果裁剪区域超出画布，认为重叠
        return True

    # 转换为numpy数组以便处理
    stroke_array = np.array(stroke)
    canvas_array = np.array(canvas_region)

    # 检查笔画的非透明部分
    stroke_alpha = stroke_array[:, :, 3] > 0

    # 画布的非黑色部分（有内容）
    if canvas_array.size == 0:
        return False

    canvas_non_black = np.sum(canvas_array[:, :, :3], axis=2) > 0

    # 计算重叠比例
    overlap = np.logical_and(stroke_alpha, canvas_non_black)
    overlap_ratio = np.sum(overlap) / np.sum(stroke_alpha) if np.sum(stroke_alpha) > 0 else 0

    return overlap_ratio > threshold


def group_strokes_by_type(strokes):
    """根据笔画类型进行分组"""
    horizontal = []
    vertical = []
    others = []

    for stroke in strokes:
        width, height = stroke.size
        if width > height * 1.5:
            horizontal.append(stroke)
        elif height > width * 1.5:
            vertical.append(stroke)
        else:
            others.append(stroke)

    return horizontal, vertical, others


def assemble_character(strokes, output_path):
    """将多个笔画组合成一个类似汉字的符号"""
    # 创建一个黑色的画布
    canvas = Image.new('RGBA', (200, 200), (0, 0, 0, 255))

    # 计算每个笔画的目标面积，基于画布大小和笔画数量
    total_area = 200 * 200
    target_area_per_stroke = total_area / (len(strokes) * 0.5)  # 进一步增大每个笔画的面积

    # 记录已放置的笔画位置
    placed_positions = []

    # 随机打乱笔画顺序
    random.shuffle(strokes)

    # 尝试按结构分组
    horizontal, vertical, others = group_strokes_by_type(strokes)

    # 随机混合各类笔画
    structured_strokes = []
    stroke_types = [horizontal, vertical, others]

    # 随机顺序添加不同类型的笔画
    while any(stroke_types):
        non_empty_types = [t for t in stroke_types if t]
        if not non_empty_types:
            break
        selected_type = random.choice(non_empty_types)
        structured_strokes.append(selected_type.pop(0))

    # 放置笔画，使用中心点吸引
    for i, stroke in enumerate(structured_strokes):
        # 调整笔画大小 - 所有笔画都应用统一的放大系数
        size_factor = 1.5  # 统一增大所有笔画的大小
        resized_stroke = resize_stroke(stroke, target_area_per_stroke * size_factor)

        # 尝试放置笔画，增加向中心的吸引力
        canvas, position = place_stroke_with_attraction(
            canvas, resized_stroke,
            center_attraction=0.65  # 降低吸引力，增加随机性
        )

        if position:
            placed_positions.append((resized_stroke, position))

    # 如果没有放置任何笔画，随机放置一个
    if not placed_positions and strokes:
        resized_stroke = resize_stroke(strokes[0], target_area_per_stroke)
        x = (500 - resized_stroke.size[0]) // 2
        y = (500 - resized_stroke.size[1]) // 2
        stroke_layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        stroke_layer.paste(resized_stroke, (x, y), resized_stroke)
        canvas = Image.alpha_composite(canvas, stroke_layer)

    # 转换为RGB模式并保存
    canvas_rgb = canvas.convert('RGB')
    canvas_rgb.save(output_path)
    print(f"已生成合成图片: {output_path}")

    return output_path


if __name__ == "__main__":
    # 设置输入文件夹路径，请修改为实际路径
    INPUT_FOLDER = r"F:\科研\06Machine Learning, EEG, and Word Reading in Children\Decomposed strokes of Chinese characters"
    # 设置输出文件夹路径，请修改为实际路径
    OUTPUT_FOLDER = r"F:\科研\06Machine Learning, EEG, and Word Reading in Children\output"

    # 设置随机种子（可选）
    RANDOM_SEED = None  # 设置为None使用随机种子

    # 设置随机种子（如果提供）
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    # 遍历输入文件夹中的所有子文件夹
    for subfolder in os.listdir(INPUT_FOLDER):
        subfolder_path = os.path.join(INPUT_FOLDER, subfolder)
        if os.path.isdir(subfolder_path):
            # 加载笔画
            strokes = load_strokes(subfolder_path)

            if not strokes:
                print(f"错误: 在 {subfolder_path} 中未找到PNG格式的笔画图片")
            else:
                print(f"已加载 {len(strokes)} 个笔画图片，来自 {subfolder_path}")
                # 生成输出图片路径
                output_path = os.path.join(OUTPUT_FOLDER, f"{subfolder}.png")
                # 组合字符
                assemble_character(strokes, output_path)
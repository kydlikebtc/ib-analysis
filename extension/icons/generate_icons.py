#!/usr/bin/env python3
"""
生成 Chrome 扩展所需的图标
使用 PIL 创建简单的 IB 风格图标
"""

import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("需要安装 Pillow: pip install Pillow")
    exit(1)


def create_icon(size: int, output_path: str):
    """创建指定尺寸的图标"""
    # 创建带有透明背景的图像
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 绘制圆形背景
    margin = size // 8
    bg_color = (46, 134, 171)  # #2E86AB - 主题蓝色
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=bg_color
    )

    # 绘制简化的图表图标代替文字
    center_x = size // 2
    center_y = size // 2

    # 绘制三个柱状条形图
    bar_width = size // 10
    bar_gap = size // 8
    bar_heights = [size // 4, size // 3, size // 2.5]

    for i, height in enumerate(bar_heights):
        x = center_x + (i - 1) * (bar_width + bar_gap) - bar_width // 2
        y_top = center_y - height // 2 + size // 10
        y_bottom = center_y + size // 4

        # 绘制柱状图
        draw.rectangle(
            [x, y_top, x + bar_width, y_bottom],
            fill='white'
        )

    # 绘制趋势线
    line_color = (144, 238, 144, 200)  # 淡绿色
    line_points = [
        (margin + size // 6, center_y + size // 8),
        (center_x - size // 10, center_y - size // 8),
        (center_x + size // 10, center_y),
        (size - margin - size // 6, center_y - size // 4)
    ]

    for i in range(len(line_points) - 1):
        draw.line(
            [line_points[i], line_points[i + 1]],
            fill=line_color,
            width=max(2, size // 20)
        )

    # 保存图像
    img.save(output_path, 'PNG')
    print(f"✅ 已创建: {output_path} ({size}x{size})")


def main():
    """生成所有需要的图标尺寸"""
    script_dir = Path(__file__).parent
    sizes = [16, 32, 48, 128]

    print("🎨 生成 Chrome 扩展图标...")
    print()

    for size in sizes:
        output_path = script_dir / f"icon{size}.png"
        create_icon(size, str(output_path))

    print()
    print("✅ 所有图标生成完成！")


if __name__ == '__main__':
    main()

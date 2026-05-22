#!/usr/bin/env python3
import os
import math
from PIL import Image, ImageDraw, ImagePath

def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))

def create_gradient_mask(width, height, draw_func):
    # Create high-res mask (4x for anti-aliasing)
    scale = 4
    w, h = width * scale, height * scale
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw_func(draw, scale)
    return mask.resize((width, height), Image.Resampling.LANCZOS)

def generate_linear_gradient(width, height, x1, y1, x2, y2, colors):
    # colors is a list of (stop, (r, g, b))
    grad = Image.new("RGBA", (width, height))
    pixels = grad.load()
    
    dx = x2 - x1
    dy = y2 - y1
    lensq = dx*dx + dy*dy
    
    for y in range(height):
        for x in range(width):
            if lensq == 0:
                t = 0
            else:
                t = ((x - x1) * dx + (y - y1) * dy) / lensq
            t = clamp(t, 0.0, 1.0)
            
            # Find the two colors to interpolate between
            c1, c2 = colors[0], colors[-1]
            for i in range(len(colors) - 1):
                if colors[i][0] <= t <= colors[i+1][0]:
                    c1, c2 = colors[i], colors[i+1]
                    break
            
            if c1[0] == c2[0]:
                factor = 0
            else:
                factor = (t - c1[0]) / (c2[0] - c1[0])
                
            r = int(c1[1][0] * (1 - factor) + c2[1][0] * factor)
            g = int(c1[1][1] * (1 - factor) + c2[1][1] * factor)
            b = int(c1[1][2] * (1 - factor) + c2[1][2] * factor)
            
            pixels[x, y] = (r, g, b, 255)
            
    return grad

def main():
    os.makedirs("../description", exist_ok=True)
    
    # --- WRITE SVG ---
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <!-- Top-left gradient -->
    <linearGradient id="topLeftGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF9E00" />
      <stop offset="50%" stop-color="#FF3E6C" />
      <stop offset="100%" stop-color="#7B2CBF" />
    </linearGradient>
    
    <!-- Top-right gradient -->
    <linearGradient id="topRightGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7B2CBF" />
      <stop offset="100%" stop-color="#5A189A" />
    </linearGradient>

    <!-- Bottom-right gradient -->
    <linearGradient id="bottomRightGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF3E6C" />
      <stop offset="50%" stop-color="#FF7A00" />
      <stop offset="100%" stop-color="#FFD000" />
    </linearGradient>
  </defs>

  <g transform="translate(0, 0)">
    <!-- Top-Left Shape -->
    <path d="M 256,256 L 256,64 L 112,64 Q 64,64 100,100 L 256,256 Z" fill="url(#topLeftGrad)" />

    <!-- Top-Right Shape -->
    <path d="M 256,256 L 256,64 L 400,64 Q 448,64 448,112 L 448,256 Z" fill="url(#topRightGrad)" />

    <!-- Bottom-Right Shape -->
    <path d="M 256,256 L 448,256 L 448,400 Q 448,448 412,412 L 256,256 Z" fill="url(#bottomRightGrad)" />
  </g>
</svg>
"""
    
    with open("../description/icon.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)
    print("✅ SVG icon written to ../description/icon.svg")

    # --- GENERATE PNG ---
    width, height = 512, 512
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    
    # 1. Top-Left Shape
    # Vertices high-res: (256,256) -> (1024, 1024), (256,64) -> (1024, 256), (112,64) -> (448, 256), Q(64,64)->(256,256) to (100,100)->(400,400)
    def draw_top_left(draw, s):
        # We approximate the quadratic bezier curve with a polygon
        points = []
        points.append((256*s, 256*s))
        points.append((256*s, 64*s))
        points.append((112*s, 64*s))
        # Bezier from (112, 64) to (100, 100) with control (64, 64)
        for i in range(21):
            t = i / 20.0
            x = (1-t)**2 * 112 + 2*t*(1-t)*64 + t**2 * 100
            y = (1-t)**2 * 64 + 2*t*(1-t)*64 + t**2 * 100
            points.append((x*s, y*s))
        draw.polygon(points, fill=255)
        
    mask_left = create_gradient_mask(width, height, draw_top_left)
    grad_left = generate_linear_gradient(
        width, height, 64, 64, 256, 256,
        [(0.0, (255, 158, 0)), (0.5, (255, 62, 108)), (1.0, (123, 44, 191))]
    )
    canvas.paste(grad_left, (0, 0), mask_left)

    # 2. Top-Right Shape
    def draw_top_right(draw, s):
        points = []
        points.append((256*s, 256*s))
        points.append((256*s, 64*s))
        points.append((400*s, 64*s))
        # Bezier from (400, 64) to (448, 112) with control (448, 64)
        for i in range(21):
            t = i / 20.0
            x = (1-t)**2 * 400 + 2*t*(1-t)*448 + t**2 * 448
            y = (1-t)**2 * 64 + 2*t*(1-t)*64 + t**2 * 112
            points.append((x*s, y*s))
        points.append((448*s, 256*s))
        draw.polygon(points, fill=255)
        
    mask_right = create_gradient_mask(width, height, draw_top_right)
    grad_right = generate_linear_gradient(
        width, height, 256, 64, 448, 256,
        [(0.0, (123, 44, 191)), (1.0, (90, 24, 154))]
    )
    canvas.paste(grad_right, (0, 0), mask_right)

    # 3. Bottom-Right Shape
    def draw_bottom_right(draw, s):
        points = []
        points.append((256*s, 256*s))
        points.append((448*s, 256*s))
        points.append((448*s, 400*s))
        # Bezier from (448, 400) to (412, 412) with control (448, 448)
        for i in range(21):
            t = i / 20.0
            x = (1-t)**2 * 448 + 2*t*(1-t)*448 + t**2 * 412
            y = (1-t)**2 * 400 + 2*t*(1-t)*448 + t**2 * 412
            points.append((x*s, y*s))
        draw.polygon(points, fill=255)
        
    mask_bottom = create_gradient_mask(width, height, draw_bottom_right)
    grad_bottom = generate_linear_gradient(
        width, height, 256, 256, 448, 448,
        [(0.0, (255, 62, 108)), (0.5, (255, 122, 0)), (1.0, (255, 208, 0))]
    )
    canvas.paste(grad_bottom, (0, 0), mask_bottom)

    canvas.save("../description/icon.png", "PNG")
    print("✅ PNG icon written to ../description/icon.png")

if __name__ == "__main__":
    main()

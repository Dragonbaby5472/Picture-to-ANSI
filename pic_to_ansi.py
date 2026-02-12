import argparse, os, sys, math
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageEnhance

CSI = "\x1b["
VERILOG_EXTENSIONS = {".sv", ".v", ".svh", ".vh"}

def srgb_to_linear(arr_u8):
    """sRGB to linear light space"""
    c = arr_u8.astype(np.float32) / 255.0
    a = c <= 0.04045
    out = np.empty_like(c, dtype=np.float32)
    out[a]  = c[a] / 12.92
    out[~a] = ((c[~a] + 0.055) / 1.055) ** 2.4
    return out

def linear_to_srgb(arr_f):
    """Linear light space to sRGB"""
    a = arr_f <= 0.0031308
    out = np.empty_like(arr_f, dtype=np.float32)
    out[a]  = 12.92 * arr_f[a]
    out[~a] = 1.055 * (arr_f[~a] ** (1/2.4)) - 0.055
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)

def resize_with_optimal_filter(pil_img, w, h, method='linear_lanczos'):
    """
    Optimized resize strategy.

    method options:
    - 'linear_lanczos': linear-light Lanczos (most accurate, can be over-sharp)
    - 'lanczos': standard Lanczos (balanced)
    - 'bicubic': bicubic interpolation (softer)
    - 'linear_bicubic': linear-light bicubic (soft and accurate)
    """
    if method == 'linear_lanczos':
        src = np.array(pil_img.convert("RGB"), dtype=np.uint8)
        lin = srgb_to_linear(src)
        chs = []
        for i in range(3):
            ch = Image.fromarray(lin[:, :, i], mode="F").resize((w, h), Image.Resampling.LANCZOS)
            chs.append(np.array(ch, dtype=np.float32))
        lin_small = np.stack(chs, axis=2)
        return Image.fromarray(linear_to_srgb(lin_small), "RGB")
    
    elif method == 'linear_bicubic':
        src = np.array(pil_img.convert("RGB"), dtype=np.uint8)
        lin = srgb_to_linear(src)
        chs = []
        for i in range(3):
            ch = Image.fromarray(lin[:, :, i], mode="F").resize((w, h), Image.Resampling.BICUBIC)
            chs.append(np.array(ch, dtype=np.float32))
        lin_small = np.stack(chs, axis=2)
        return Image.fromarray(linear_to_srgb(lin_small), "RGB")
    
    elif method == 'lanczos':
        return pil_img.resize((w, h), Image.Resampling.LANCZOS)
    
    elif method == 'bicubic':
        return pil_img.resize((w, h), Image.Resampling.BICUBIC)
    
    else:
        return pil_img.resize((w, h), Image.Resampling.LANCZOS)

def apply_edge_aware_sharpen(pil_img, strength='light'):
    """
    Edge-aware sharpening that only sharpens where needed.

    strength: 'none', 'light', 'medium', 'strong'
    """
    if strength == 'none':
        return pil_img
    
    params = {
        'light': {'radius': 0.7, 'percent': 80, 'threshold': 3},
        'medium': {'radius': 1.0, 'percent': 110, 'threshold': 2},
        'strong': {'radius': 1.2, 'percent': 140, 'threshold': 1}
    }
    
    p = params.get(strength, params['light'])
    return pil_img.filter(ImageFilter.UnsharpMask(
        radius=p['radius'], 
        percent=p['percent'], 
        threshold=p['threshold']
    ))

def enhance_color_separation(pil_img, saturation=1.0, contrast=1.0):
    """
    Enhance color separation.
    saturation: 1.0=no change, >1.0=increase, <1.0=decrease
    contrast: 1.0=no change, >1.0=increase, <1.0=decrease
    """
    img = pil_img
    
    if saturation != 1.0:
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(saturation)
    
    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast)
    
    return img

def apply_gentle_denoise(pil_img, radius=1):
    """
    Gentle denoise to remove small color noise.
    radius: 1-3
    """
    if radius <= 0:
        return pil_img
    return pil_img.filter(ImageFilter.MedianFilter(size=min(5, radius*2+1)))

def ansi_fg_bg(top_rgb, bot_rgb, use_upper=True, use_csi=True):
    """Standard half-block ANSI sequence without smart blending."""
    rt, gt, bt = top_rgb
    rb, gb, bb = bot_rgb
    ch = "▀" if use_upper else "▄"
    pre = CSI if use_csi else "["
    return f"{pre}38;2;{rt};{gt};{bt}m{pre}48;2;{rb};{gb};{bb}m{ch}{pre}0m"

def ansi_single(rgb, char="█", use_csi=True):
    """Full-block ANSI sequence."""
    r, g, b = rgb
    pre = CSI if use_csi else "["
    return f"{pre}38;2;{r};{g};{b}m{char}{pre}0m"

def resolve_output_format(output_format, output_file):
    """Resolve the final output format."""
    if output_format != "auto":
        return output_format

    if output_file:
        ext = os.path.splitext(output_file)[1].lower()
        if ext in VERILOG_EXTENSIONS:
            return "verilog"
    return "ansi"

def default_output_path(image_path, output_format):
    """Choose default output path when --output is not provided."""
    stem = os.path.splitext(os.path.basename(image_path))[0] or "output"
    ext = ".sv" if output_format == "verilog" else ".ans"
    return f"{stem}{ext}"

def escape_verilog_string(text):
    """Escape text for a Verilog string literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"')

def image_to_verilog_display(
    image_path, width=60, output_file=None, module_name="display_image",
    half_block=True, upper_half=True, char_full="█", use_csi=True,
    output_format="auto",
    resize_method='linear_bicubic',
    sharpen='light',
    denoise=0,
    saturation=1.0,
    contrast=1.0,
    cell_aspect=2.0
):
    """
    Refined image conversion with better line continuity and cleaner colors.

    Parameters:
    - output_format: 'verilog', 'ansi', 'auto'
      'auto' is inferred from output extension
      (.sv/.v/.svh/.vh => verilog, otherwise ansi)
    - resize_method: 'linear_lanczos', 'linear_bicubic', 'lanczos', 'bicubic'
      recommended: 'linear_bicubic' (soft and color-accurate)
    - sharpen: 'none', 'light', 'medium', 'strong'
      recommended: 'light' (recovers detail lost during resize)
    - denoise: 0-3, denoise strength (0=disabled)
    - saturation: color saturation (0.8-1.2)
    - contrast: contrast (0.9-1.1)
    """
    if not os.path.exists(image_path):
        print(f"Error: image file not found: '{image_path}'")
        return False
    
    try:
        src = Image.open(image_path).convert("RGB")
        src_w, src_h = src.size

        # Compute target dimensions
        aspect_ratio = src_h / src_w
        height_chars = max(1, int(round(width * aspect_ratio / cell_aspect)))

        if half_block:
            h_px = height_chars * 2
            if h_px % 2 == 1: 
                h_px += 1
        else:
            h_px = height_chars

        # 1. High-quality resize (core step)
        img = resize_with_optimal_filter(src, width, h_px, method=resize_method)
        
        # 2. Optional denoise to remove small color noise
        if denoise > 0:
            img = apply_gentle_denoise(img, radius=denoise)
        
        # 3. Color adjustment
        if saturation != 1.0 or contrast != 1.0:
            img = enhance_color_separation(img, saturation=saturation, contrast=contrast)
        
        # 4. Light sharpening compensation
        if sharpen != 'none':
            img = apply_edge_aware_sharpen(img, strength=sharpen)

        # 5. Generate ANSI lines (standard mode, no smart blending)
        ansi_lines = []
        w, h = img.size
        
        if half_block:
            if h % 2 == 1:
                h -= 1
                img = img.crop((0, 0, w, h))
            
            for y in range(0, h, 2):
                row = []
                for x in range(w):
                    top = img.getpixel((x, y))
                    bot = img.getpixel((x, y+1))
                    row.append(ansi_fg_bg(top, bot, use_upper=upper_half, use_csi=use_csi))
                
                ansi_lines.append("".join(row))
            out_h_chars = h // 2
        else:
            for y in range(h):
                row = [ansi_single(img.getpixel((x, y)), char=char_full, use_csi=use_csi) 
                       for x in range(w)]
                ansi_lines.append("".join(row))
            out_h_chars = h

        # 6. Format-specific output
        final_format = resolve_output_format(output_format, output_file)

        if final_format == "verilog":
            display_lines = [f'$display("{escape_verilog_string(line)}");' for line in ansi_lines]

            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("//============================================================================\n")
                    f.write(f"// Auto-generated image display code - {os.path.basename(image_path)}\n")
                    f.write(f"// Source size: {src_w}x{src_h}\n")
                    f.write(f"// Output size: {width}x{out_h_chars}\n")
                    f.write(f"// Output format: {final_format}\n")
                    f.write(f"// Options: resize_method={resize_method} sharpen={sharpen}\n")
                    f.write(f"//          denoise={denoise} saturation={saturation} contrast={contrast}\n")
                    f.write("//============================================================================\n\n")
                    f.write(f"task {module_name};\nbegin\n")
                    for line in display_lines:
                        f.write(f"  {line}\n")
                    f.write("end\nendtask\n")
                print(f"Wrote output file: {output_file} (format={final_format})")
            else:
                for line in display_lines:
                    print(line)
        else:
            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    for line in ansi_lines:
                        f.write(f"{line}\n")
                print(f"Wrote output file: {output_file} (format={final_format})")
            else:
                for line in ansi_lines:
                    print(line)
        
        return True
        
    except Exception as e:
        print(f"Error while processing image: {e}")
        import traceback
        traceback.print_exc()
        return False

def build_argparser():
    p = argparse.ArgumentParser(
        description="Image -> ANSI color output (default .ans, optional Verilog $display)",
        epilog=("Effective defaults: half-block mode is enabled; "
                "when neither --upper-half nor --lower-half is set, upper half block (▀) is used."),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    # Basic arguments
    p.add_argument("image", help="Input image path")
    p.add_argument("-w","--width", type=int, default=60, help="Output width (characters)")
    p.add_argument("-o","--output", help="Output file path (default: <image>.ans, or <image>.sv for verilog)")
    p.add_argument("-n","--name", default="display_image", help="Task name")
    p.add_argument("-f","--format", choices=["verilog", "ansi", "auto"], default="auto",
                   help="Output format (default: auto, inferred from output extension)")

    # Render options
    render = p.add_argument_group('Render Options')
    render.add_argument("--no-csi", action="store_true", help="Disable ESC CSI prefix")
    render.add_argument("--no-half-block", action="store_true",
                        help="Use full block instead of half block (effective default: half-block enabled)")
    render.add_argument("--upper-half", action="store_true",
                        help="Use upper half block ▀ (effective default when neither half option is set)")
    render.add_argument("--lower-half", action="store_true", help="Use lower half block ▄")
    render.add_argument("--char", default="█",
                        help="Character used in full-block mode (ignored in half-block mode)")
    render.add_argument("--cell-aspect", type=float, default=2.0, help="Character cell height/width ratio")

    # Resize options
    resize = p.add_argument_group('Resize Options')
    resize.add_argument("--resize-method", 
                       choices=['linear_lanczos', 'linear_bicubic', 'lanczos', 'bicubic'],
                       default='linear_bicubic',
                       help="Resize method (recommended: linear_bicubic)")

    # Quality options
    quality = p.add_argument_group('Quality Options')
    quality.add_argument("--sharpen", 
                        choices=['none', 'light', 'medium', 'strong'],
                        default='light',
                        help="Sharpen strength")
    quality.add_argument("--denoise", type=int, default=0,
                        help="Denoise strength (0-3, 0=disabled)")

    # Color adjustment
    color = p.add_argument_group('Color Adjustment')
    color.add_argument("--saturation", type=float, default=1.0,
                      help="Saturation (0.8-1.2)")
    color.add_argument("--contrast", type=float, default=1.0,
                      help="Contrast (0.9-1.1)")

    return p

def main():
    args = build_argparser().parse_args()
    
    if args.width <= 0 or args.width > 200:
        print("Warning: width should be in 1-200; value has been clamped.")
        args.width = max(1, min(200, args.width))
    
    half_block = not args.no_half_block
    upper = True if (args.upper_half or not args.lower_half) else False
    output_path = args.output if args.output else default_output_path(args.image, args.format)
    
    ok = image_to_verilog_display(
        image_path=args.image, 
        width=args.width, 
        output_file=output_path, 
        module_name=args.name,
        half_block=half_block, 
        upper_half=upper, 
        char_full=args.char, 
        use_csi=not args.no_csi,
        output_format=args.format,
        resize_method=args.resize_method,
        sharpen=args.sharpen,
        denoise=args.denoise,
        saturation=args.saturation,
        contrast=args.contrast,
        cell_aspect=args.cell_aspect
    )
    
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()

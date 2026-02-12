<div align="center">
  <h1>pic_to_ansi.py</h1>
  <p><strong>Convert images to ANSI true-color art<code>$display</code> tasks.</strong></p>
  <p>
    <img alt="Python" src="https://img.shields.io/badge/python-3.8%2B-blue.svg">
    <img alt="Output" src="https://img.shields.io/badge/output-ANSI%20%7C%20Verilog-2ea44f">
    <img alt="Default mode" src="https://img.shields.io/badge/default-auto-orange">
    <img alt="Default file" src="https://img.shields.io/badge/default_file-.ans-8a2be2">
  </p>
</div>

---

## Table of Contents

- [What It Does](#what-it-does)
- [Highlights](#highlights)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Default Behavior](#default-behavior)
- [Output Modes](#output-modes)
- [Examples](#examples)
- [CLI Reference](#cli-reference)
- [Verilog Integration Example](#verilog-integration-example)
- [Terminal Tips](#terminal-tips)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## What It Does

`pic_to_ansi.py` converts an input image into terminal-friendly ANSI true-color output.

You can generate:
- Plain ANSI text lines (for terminal display).
- Verilog/SystemVerilog task code with `$display("...");` lines.

## Highlights

- True-color ANSI output (`38;2;r;g;b` + `48;2;r;g;b`).
- Half-block rendering (`▀` / `▄`) for better vertical detail.
- Optional full-block mode (`█` or custom character).
- Multiple resize methods, including linear-light variants.
- Optional denoise, sharpening, saturation, and contrast tuning.
- Smart output format selection (`ansi`, `verilog`, `auto`).

## Requirements

- Python 3.8+
- `numpy`
- `Pillow`

Install:

```bash
pip install numpy pillow
```

## Quick Start

Generate ANSI output with default naming:

```bash
python pic_to_ansi.py input.jpg
```

Preview in terminal:

```bash
cat input.ans
```

Generate Verilog task output:

```bash
python pic_to_ansi.py input.jpg -o output.sv
```

## Default Behavior

- Format default is `-f auto`.
- If `-o` is not provided, output file defaults to:
  - `<image_basename>.ans` for `ansi/auto`
  - `<image_basename>.sv` for `verilog`
- Effective render defaults:
  - Half-block mode is enabled.
  - If neither `--upper-half` nor `--lower-half` is set, upper half block `▀` is used.

## Output Modes

| Mode | How to set | Output |
| --- | --- | --- |
| `ansi` | `-f ansi` | Plain ANSI lines |
| `verilog` | `-f verilog` | Task with `$display("...");` |
| `auto` (default) | `-f auto` | Inferred from `-o` extension |

`auto` with `-o`:
- `.sv`, `.v`, `.svh`, `.vh` -> `verilog`
- everything else -> `ansi`

`auto` without `-o`:
- defaults to `<image>.ans`

## Examples

Force ANSI output to a `.txt` file:

```bash
python pic_to_ansi.py input.jpg -o frame.txt -f ansi
```

Force Verilog output without specifying output filename:

```bash
python pic_to_ansi.py input.jpg -f verilog
```

Use full-block mode:

```bash
python pic_to_ansi.py input.jpg --no-half-block --char "█"
```

Use lower half block:

```bash
python pic_to_ansi.py input.jpg --lower-half
```

High-quality tuning example:

```bash
python pic_to_ansi.py input.jpg -w 120 \
  --resize-method linear_bicubic \
  --sharpen light \
  --denoise 1 \
  --saturation 1.05 \
  --contrast 1.02
```

## CLI Reference

```text
python pic_to_ansi.py IMAGE [options]
```

### Core options

| Option | Description | Default |
| --- | --- | --- |
| `image` | Input image path | required |
| `-w, --width` | Output width in characters | `60` |
| `-o, --output` | Output file path | auto naming |
| `-n, --name` | Verilog task name | `display_image` |
| `-f, --format {verilog,ansi,auto}` | Output mode | `auto` |

### Render options

| Option | Description | Default |
| --- | --- | --- |
| `--no-csi` | Disable `ESC[` prefix | `False` |
| `--no-half-block` | Use full-block mode instead of half-block | `False` |
| `--upper-half` | Use `▀` | `False` |
| `--lower-half` | Use `▄` | `False` |
| `--char CHAR` | Character for full-block mode | `█` |
| `--cell-aspect` | Character cell height/width ratio | `2.0` |

Notes:
- `--char` is ignored in half-block mode.
- If both half flags are omitted, upper half block is used.

### Resize options

| Option | Description | Default |
| --- | --- | --- |
| `--resize-method {linear_lanczos,linear_bicubic,lanczos,bicubic}` | Resize algorithm | `linear_bicubic` |

### Quality options

| Option | Description | Default |
| --- | --- | --- |
| `--sharpen {none,light,medium,strong}` | Sharpen strength | `light` |
| `--denoise` | Denoise strength (`0-3`) | `0` |

### Color options

| Option | Description | Default |
| --- | --- | --- |
| `--saturation` | Saturation multiplier | `1.0` |
| `--contrast` | Contrast multiplier | `1.0` |

## Verilog Integration Example

Generated `output.sv` contains a task:

```verilog
task display_image;
begin
  $display("...");
  $display("...");
end
endtask
```

Usage in your testbench:

```verilog
`include "output.sv"

module demo;
  initial begin
    display_image();
    $finish;
  end
endmodule
```

## Terminal Tips

- Use a terminal that supports true color.
- Display ANSI output with `cat`, not editors that strip escape sequences.
- Large `--width` values can generate very large files, especially in Verilog mode.

## Troubleshooting

- `Error: image file not found`  
  Check the input path and current working directory.
- Colors look wrong  
  Verify terminal true-color support.
- Output is larger than expected  
  Reduce `--width` or use ANSI output instead of Verilog.

## License


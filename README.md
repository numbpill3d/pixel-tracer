# Pixel Tracer for GIMP

Turn a photo into a deliberately imperfect, low-resolution drawing that looks
like it was made in classic MS Paint, then continue editing the PNG in GIMP.

![Original demo image](assets/demo-input.png)

![Pixel trace output](assets/demo-trace.png)

The faint-underlay mode is useful when you want a guide while finishing the
piece in GIMP:

![Trace with underlay](assets/demo-underlay.png)

The output uses a small working canvas, limited palette, charcoal pixel ink,
nearest-neighbour scaling, and subtle stroke jitter. It is intentionally an
interpretation of hand tracing rather than a claim that an LLM physically drew
the image.

## Use

```bash
python3 pixel_tracer.py /path/to/source.jpg -o /path/to/trace.png --open-gimp
```

Or launch the small desktop picker:

```bash
python3 pixel_tracer_gui.py
```

Useful controls:

```text
--width 120        stronger pixelation
--threshold 0.24  fewer, simpler contour lines
--jitter 0.8      more hand-like wobble
--underlay        retain a faint source-image guide beneath the ink
--seed 12         repeatable variation
--paper gray      use a gray Paint-like canvas
--ink navy        use navy pixel ink
```

The program does not require GIMP to generate the PNG. `--open-gimp` is an
optional convenience for systems where GIMP is installed. Install dependencies
with Pillow and NumPy available in the active Python environment.

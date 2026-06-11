# ComfyUI JXL Support

Load and save JPEG XL (`.jxl`) images in ComfyUI with lossy/lossless compression and optional workflow metadata embedding.

## Nodes

### Save Image (JXL)

| Input | Type | Default | Description |
|---|---|---|---|
| `images` | `IMAGE` | — | Batch of images to save |
| `filename_prefix` | `STRING` | `ComfyUI` | Output filename prefix |
| `quality` | `INT` (0–100) | `100` | 100 = lossless; lower = smaller file |
| `compress_metadata` | `BOOLEAN` | `True` | Brotli-compress embedded workflow metadata |

### Load Image (JXL)

Loads `.jxl` from the input directory. Returns image + optional alpha mask. Reads embedded workflow metadata for drag-and-drop recovery.

## Feature highlights

- **Lossless at quality=100** — pixel-perfect output, ~40% smaller than PNG.
- **Lossy at quality < 100** — distance-based compression via `imagecodecs` (`butteraugli` distance mapped as `(100 - quality) × 0.15`).
- **Metadata compression toggle** — disable `compress_metadata` to compare file size with uncompressed vs Brotli-compressed workflow metadata.
- **Drag-and-drop restore** — JS extension embeds workflow data for one-click recovery.

## Size comparison (real-world example)

### Format comparison (1024×1024 render)

| Format | Size |
|---|---|
| PNG (lossless) | 1.58 MB |
| JXL lossless (quality=100) | 0.99 MB |
| JXL lossy (quality=40) | 99 KB |

### Metadata compression impact (quality=40)

| `compress_metadata` | File size |
|---|---|
| `True` (Brotli) | 99 KB |
| `False` (raw JSON) | 206 KB |

> Metadata compression is most noticeable on lossy files — workflow JSON can be tens of KB uncompressed, but shrinks to ~1–2 KB with Brotli.

## Dependencies

Installed via `requirements.txt`:
| Package | Purpose |
|---|---|
| `imagecodecs` | JXL encode / decode |
| `brotli` | Workflow metadata compression |

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

- **Lossless at quality=100** — pixel-perfect output, ~40 % smaller than PNG.
- **Lossy at quality < 100** — distance-based compression via `imagecodecs` (`butteraugli` distance mapped as `(100 - quality) × 0.15`).
- **Metadata compression toggle** — disable `compress_metadata` to compare file size with uncompressed vs Brotli-compressed workflow metadata.
- **Brotli-compressed workflow** — metadata stored in a `brob` ISOBMFF box.
- **Drag-and-drop restore** — JS extension embeds workflow data for one-click recovery.

## Dependencies

Installed via `requirements.txt`:
| Package | Purpose |
|---|---|
| `imagecodecs` | JXL encode / decode |
| `brotli` | Workflow metadata compression |

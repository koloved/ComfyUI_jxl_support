import os
import json
import torch
import numpy as np
import folder_paths
from PIL import Image, ImageOps
from .jxl_io import encode_jxl, decode_jxl


# ── Load Image (JXL) ────────────────────────────────────────────────────


class LoadImageJXL:
    """Load a JXL image file and return (IMAGE, MASK) tensors."""

    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if f.lower().endswith('.jxl')]
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_image"
    CATEGORY = "image"
    INPUT_IS_LIST = False

    def load_image(self, image):
        image_path = folder_paths.get_annotated_filepath(image)
        with open(image_path, 'rb') as f:
            data = f.read()
        np_image, _ = decode_jxl(data)

        if np_image.ndim == 3 and np_image.shape[2] == 4:
            image_np = np_image[:, :, :3].astype(np.float32) / 255.0
            alpha = np_image[:, :, 3].astype(np.float32) / 255.0
            mask = 1.0 - torch.from_numpy(alpha)
        else:
            image_np = np_image.astype(np.float32) / 255.0
            mask = torch.zeros((image_np.shape[0], image_np.shape[1]), dtype=torch.float32)

        image_t = torch.from_numpy(image_np)[None,]
        return (image_t, mask)

    @classmethod
    def IS_CHANGED(cls, image):
        image_path = folder_paths.get_annotated_filepath(image)
        if os.path.isfile(image_path):
            return os.path.getmtime(image_path)
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, image):
        if not os.path.isfile(folder_paths.get_annotated_filepath(image)):
            return f"JXL file not found: {image}"
        return True


# ── Save Image (JXL) ────────────────────────────────────────────────────


class SaveImageJXL:
    """Save images in lossless JPEG XL format with Brotli-compressed metadata."""

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "ComfyUI"}),
                "quality": ("INT", {"default": 100, "min": 0, "max": 100, "step": 1}),
                "compress_metadata": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "image"

    def save_images(self, images, filename_prefix="ComfyUI", quality=100, compress_metadata=True,
                    prompt=None, extra_pnginfo=None):
        full_output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0]
        )

        results = []
        for batch_number, image_tensor in enumerate(images):
            np_image = (255.0 * image_tensor.cpu().numpy()).clip(0, 255).astype(np.uint8)
            encoded = encode_jxl(
                np_image,
                quality=quality,
                compress_metadata=compress_metadata,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )
            name = filename.replace("%batch_num%", str(batch_number))
            file = f"{name}_{counter:05}_.jxl"
            with open(os.path.join(full_output_folder, file), "wb") as f:
                f.write(encoded)
            results.append({"filename": file, "subfolder": subfolder, "type": self.type})
            counter += 1

        return {"ui": {"images": results}}

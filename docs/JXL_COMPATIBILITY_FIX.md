# JPEG XL Compatibility Fix

## Summary

This patch corrects two problems in ComfyUI_jxl_support:

1. JPEG XL container decoding failures.
2. Incorrect normalization of 16-bit RGB images.

The changes were originally tested with ComfyUI running
through Stability Matrix on Windows.

## 1. JPEG XL Container Decoding

### Original error

    ValueError: not a JPEG XL codestream

### Root cause

The extension extracted a JPEG XL codestream before passing
it to imagecodecs.

For the tested JPEG XL container, that intermediate extraction
produced data rejected by the JPEG XL decoder.

The imagecodecs decoder successfully processed the original
complete JPEG XL container.

### Correction

File: jxl_io.py

Original:

    image = imagecodecs.jpegxl_decode(codestream)

Corrected:

    image = imagecodecs.jpegxl_decode(data)

The complete original JPEG XL file is now passed to imagecodecs.

Existing metadata handling remains unchanged.

## 2. 16-bit Image Normalization

### Root cause

The LoadImageJXL node normalized RGB image data using:

    np_image.astype(np.float32) / 255.0

This is correct for unsigned 8-bit image data, but incorrect
for unsigned 16-bit images.

16-bit unsigned images contain values from 0 through 65535.

Dividing these values by 255 produces image tensors outside
ComfyUI's expected normalized range of 0.0 through 1.0.

### Correction

File: nodes.py

Original:

    np_image.astype(np.float32) / 255.0

Corrected:

    np_image.astype(np.float32) / float(np.iinfo(np_image.dtype).max)

This normalizes unsigned integer images according to
their actual NumPy data type.

- uint8: divide by 255
- uint16: divide by 65535

## 3. Original Test Image

The original test image was a Topaz-enhanced JPEG XL file.

Properties:

- Format: JPEG XL container
- Size: 41,652,921 bytes
- Width: 2826 pixels
- Height: 4240 pixels
- Channels: 3 (RGB)
- Data type: uint16

Direct decoding with imagecodecs succeeded.

The user subsequently confirmed that the patched
ComfyUI loader worked with the image.

The image is private and is not included in this repository.

## 4. Validation

The patch installation script performs:

- Exact source-code match verification
- Python syntax validation
- Git whitespace validation
- Verification that both corrected expressions exist
- Validation of uint8 and uint16 normalization arithmetic

The original image was manually tested in ComfyUI.

The installation script does not run the full ComfyUI
application or decode private test images.

## 5. Compatibility

The original verified environment was:

- Windows
- Stability Matrix
- ComfyUI 0.44.0
- Python 3.12.10
- NVIDIA RTX 2060
- imagecodecs JPEG XL decoder

The patch itself is Python source code and is not
specific to Windows.

Other environments require independent verification.

## 6. Known Limitations

The 16-bit normalization correction currently applies
to the non-RGBA image branch.

The RGBA branch requires additional handling and testing.

The integer normalization implementation assumes an
integer NumPy dtype. Floating-point representations
require separate handling.

The existing JPEG XL metadata parsing implementation
has not been comprehensively validated.

Additional testing is needed for:

- Raw JPEG XL codestreams
- Different JPEG XL container structures
- 8-bit RGB
- 16-bit RGB
- 8-bit RGBA
- 16-bit RGBA
- Grayscale images
- Lossless and lossy encoding
- Metadata preservation
- Corrupted or truncated images
- Multi-frame JPEG XL images

## 7. Rollback

To revert the commit after it is created:

    git revert <commit-hash>

Review the resulting changes before deploying.

## 8. Future Development

Recommended improvements:

1. Add automated JPEG XL regression fixtures.
2. Correct 16-bit RGBA normalization.
3. Add metadata preservation tests.
4. Support unusual image data types safely.
5. Add malformed-container handling tests.
6. Validate decoding across Linux, Windows, and macOS.

Development and CI testing should run on locally
managed, self-hosted infrastructure.

No GitHub-hosted runners are required.

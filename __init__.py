from .nodes import LoadImageJXL, SaveImageJXL

WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "LoadImageJXL": LoadImageJXL,
    "SaveImageJXL": SaveImageJXL,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageJXL": "Load Image (JXL)",
    "SaveImageJXL": "Save Image (JXL)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

# ── Server route for JXL metadata extraction ──────────────────────────────

import math
import logging
from aiohttp import web

try:
    from server import PromptServer

    def _clean(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        if isinstance(v, dict):
            return {k: _clean(v2) for k, v2 in v.items()}
        if isinstance(v, (list, tuple)):
            return [_clean(v2) for v2 in v]
        return v

    @PromptServer.instance.routes.post("/api/jxl_metadata")
    async def jxl_metadata(request):
        """Extract ComfyUI metadata (prompt/workflow) from an uploaded JXL file."""
        try:
            body = await request.read()
            if len(body) < 12:
                return web.json_response({})
            from .jxl_io import extract_jxl_metadata
            meta = extract_jxl_metadata(body)
            return web.json_response(_clean(meta))
        except Exception:
            logging.warning("[JXL] Failed to extract JXL metadata", exc_info=True)
            return web.json_response({}, status=400)

except Exception:
    logging.warning("[JXL] Could not register server route; PromptServer not ready yet")

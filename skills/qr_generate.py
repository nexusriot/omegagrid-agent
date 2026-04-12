from __future__ import annotations

import base64
import io
from typing import Any, Dict

from skills.base import BaseSkill

try:
    import qrcode
    from qrcode.constants import (
        ERROR_CORRECT_L,
        ERROR_CORRECT_M,
        ERROR_CORRECT_Q,
        ERROR_CORRECT_H,
    )
    _QRCODE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QRCODE_AVAILABLE = False


_ERROR_LEVELS = {
    "L": "ERROR_CORRECT_L",
    "M": "ERROR_CORRECT_M",
    "Q": "ERROR_CORRECT_Q",
    "H": "ERROR_CORRECT_H",
}


class QrGenerateSkill(BaseSkill):
    """Generate a QR code image (base64 PNG) from arbitrary text."""

    name = "qr_generate"
    description = (
        "Generate a QR code from arbitrary text/URL and return it as a base64-encoded "
        "PNG image. Configurable error-correction level (L/M/Q/H), box size, and border."
    )
    parameters = {
        "data": {
            "type": "string",
            "description": "Text, URL, or any string to encode in the QR code",
            "required": True,
        },
        "error_correction": {
            "type": "string",
            "description": "Error correction level: L (~7%), M (~15%, default), Q (~25%), H (~30%)",
            "required": False,
        },
        "box_size": {
            "type": "integer",
            "description": "Pixels per QR module (1-40, default 10)",
            "required": False,
        },
        "border": {
            "type": "integer",
            "description": "Border width in modules (1-20, default 4)",
            "required": False,
        },
    }

    def execute(
        self,
        data: str = "",
        error_correction: str = "M",
        box_size: int = 10,
        border: int = 4,
        **kwargs,
    ) -> Dict[str, Any]:
        if not _QRCODE_AVAILABLE:
            return {
                "error": "qrcode library not installed. Install with: pip install qrcode[pil]"
            }

        data = data or ""
        if not data:
            return {"error": "data is required"}
        if len(data) > 4000:
            return {"error": "data too long (max 4000 chars)"}

        level_key = (error_correction or "M").strip().upper()
        if level_key not in _ERROR_LEVELS:
            return {"error": f"invalid error_correction: {error_correction}. Use L, M, Q, or H"}

        levels = {
            "L": ERROR_CORRECT_L,
            "M": ERROR_CORRECT_M,
            "Q": ERROR_CORRECT_Q,
            "H": ERROR_CORRECT_H,
        }

        try:
            box_size = int(box_size)
            border = int(border)
        except (TypeError, ValueError):
            return {"error": "box_size and border must be integers"}
        if box_size < 1 or box_size > 40:
            return {"error": "box_size must be between 1 and 40"}
        if border < 1 or border > 20:
            return {"error": "border must be between 1 and 20"}

        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=levels[level_key],
                box_size=box_size,
                border=border,
            )
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
        except Exception as e:
            return {"error": f"QR generation failed: {e}"}

        b64 = base64.b64encode(png_bytes).decode("ascii")

        return {
            "data": data,
            "data_length": len(data),
            "error_correction": level_key,
            "box_size": box_size,
            "border": border,
            "version": qr.version,
            "modules": qr.modules_count,
            "image_format": "png",
            "image_base64": b64,
            "data_uri": f"data:image/png;base64,{b64}",
            "size_bytes": len(png_bytes),
        }

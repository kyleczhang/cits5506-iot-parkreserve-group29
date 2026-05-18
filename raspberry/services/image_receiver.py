# =============================================================================
# services/image_receiver.py  —  Receive JPEG images uploaded by ESP32
# =============================================================================
"""
Aligned with ESP32 interface documentation:

  POST /api/v1/bays/<bay_id>/image
  Headers:
    Content-Type: image/jpeg
    X-API-Key: ParkReserve-Group29-SuperSecret
    X-Timestamp: 20260510_180126   (optional, auto-generated if absent)
  Body: raw binary JPEG data

  Response 202:
    {"message": "Image securely received", "file": "bay_1_20260510_180126.jpg"}

bay_id supports both:
  integer string "1"/"2"/"3"  → automatically mapped to A1/A2/A3
  code string "A1"/"A2"/"A3" → used directly
"""

import logging
import asyncio
import time as _time
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

logger = logging.getLogger(__name__)

API_KEY = "ParkReserve-Group29-SuperSecret"

BAY_ID_TO_CODE = {1: "A1", 2: "A2", 3: "A3"}


class ImageReceiverService:
    def __init__(
        self,
        upload_dir: str,
        on_image_received: Callable[[str, str], None],  # (code, image_path)
        on_get_status: Callable[[], dict],
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.upload_dir       = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.on_image_received = on_image_received
        self.on_get_status     = on_get_status
        self.host = host
        self.port = port

        self.app = FastAPI(title="ParkReserve Image Receiver")
        self._register_routes()

    def _register_routes(self):

        @self.app.post("/api/v1/bays/{bay_id}/image", status_code=202)
        async def upload_image(bay_id: str, request: Request):
            # ── Validate API Key ──────────────────────────────────────────────
            api_key = request.headers.get("X-API-Key")
            if api_key != API_KEY:
                logger.warning(f"[ImageReceiver] Unauthorized request, invalid API Key: {api_key}")
                raise HTTPException(status_code=401, detail="Unauthorized")

            # ── Parse bay_id → code (supports both "A1" and "1" formats) ─────
            if bay_id in BAY_ID_TO_CODE.values():
                code = bay_id
            else:
                try:
                    code = BAY_ID_TO_CODE.get(int(bay_id))
                except ValueError:
                    code = None
            if code is None:
                raise HTTPException(status_code=400, detail=f"Unknown bay_id: {bay_id}")

            # ── Timestamp (optional) ──────────────────────────────────────────
            timestamp = request.headers.get("X-Timestamp") or str(int(_time.time()))

            # ── Read image data ───────────────────────────────────────────────
            content = await request.body()
            if not content:
                raise HTTPException(status_code=400, detail="No image data provided")

            # ── Save file ─────────────────────────────────────────────────────
            filename  = f"bay_{bay_id}_{timestamp}.jpg"
            save_path = self.upload_dir / filename
            try:
                save_path.write_bytes(content)
                logger.info(f"[ImageReceiver] Saved: {save_path} ({len(content)} bytes)")
            except Exception as e:
                logger.error(f"[ImageReceiver] Save failed: {e}")
                raise HTTPException(status_code=500, detail="Failed to save image")

            # ── Trigger LPR asynchronously (non-blocking) ─────────────────────
            asyncio.get_event_loop().run_in_executor(
                None, self.on_image_received, code, str(save_path)
            )

            return JSONResponse(
                status_code=202,
                content={"message": "Image securely received", "file": filename},
            )

        @self.app.get("/health")
        async def health():
            return {"status": "ok"}

        @self.app.get("/status")
        async def get_status():
            """View current status and reservation data for all bays (for debugging)"""
            return JSONResponse(self.on_get_status())

    def run(self):
        import threading

        def _run():
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")

        t = threading.Thread(target=_run, daemon=True, name="image-receiver")
        t.start()
        logger.info(f"[ImageReceiver] Started at http://{self.host}:{self.port}")

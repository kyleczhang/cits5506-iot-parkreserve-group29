# =============================================================================
# services/image_receiver.py  —  接收 ESP32 上传的 JPEG 图片（FastAPI HTTP）
# =============================================================================
"""
ESP32 在车辆到达时触发：
    POST http://<pi_ip>:8080/upload?bay=A1
    Content-Type: multipart/form-data
    Body: file=<jpeg_bytes>
"""

import os
import time
import logging
import asyncio
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

logger = logging.getLogger(__name__)


class ImageReceiverService:
    def __init__(
        self,
        upload_dir: str,
        on_image_received: Callable[[str, str], None],  # (code, image_path)
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.on_image_received = on_image_received
        self.host = host
        self.port = port

        self.app = FastAPI(title="ParkReserve Image Receiver")
        self._register_routes()

    def _register_routes(self):

        @self.app.post("/upload")
        async def upload_image(
            bay: str = Query(..., description="车位 code，如 A1"),
            file: UploadFile = File(...),
        ):
            if not bay.replace("_", "").isalnum():
                raise HTTPException(status_code=400, detail="非法 bay code")

            timestamp = int(time.time() * 1000)
            filename  = f"{bay}_{timestamp}.jpg"
            save_path = self.upload_dir / filename

            try:
                content = await file.read()
                if len(content) == 0:
                    raise HTTPException(status_code=400, detail="空文件")
                save_path.write_bytes(content)
                logger.info(f"[ImageReceiver] 保存：{save_path}（{len(content)} bytes）")
            except Exception as e:
                logger.error(f"[ImageReceiver] 保存失败：{e}")
                raise HTTPException(status_code=500, detail="保存失败")

            asyncio.get_event_loop().run_in_executor(
                None, self.on_image_received, bay, str(save_path)
            )
            return JSONResponse({"status": "ok", "saved": filename})

        @self.app.get("/health")
        async def health():
            return {"status": "ok"}
        
        @self.app.get("/status")
        async def get_status():
            return JSONResponse(self._get_status_callback())

    def run(self):
        import threading

        def _run():
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")

        t = threading.Thread(target=_run, daemon=True, name="image-receiver")
        t.start()
        logger.info(f"[ImageReceiver] 启动在 http://{self.host}:{self.port}")

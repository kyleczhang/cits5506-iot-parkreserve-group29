# =============================================================================
# services/image_receiver.py  —  接收 ESP32 上传的 JPEG 图片
# =============================================================================
"""
对齐 ESP32 接口文档：

  POST /api/v1/bays/<bay_id>/image
  Headers:
    Content-Type: image/jpeg
    X-API-Key: ParkReserve-Group29-SuperSecret
    X-Timestamp: 20260510_180126   （可选，缺省自动生成）
  Body: 纯二进制 JPEG 数据

  Response 202:
    {"message": "Image securely received", "file": "bay_1_20260510_180126.jpg"}

bay_id 同时支持：
  整数字符串 "1"/"2"/"3"  → 自动转为 A1/A2/A3
  code 字符串 "A1"/"A2"/"A3" → 直接使用
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
            # ── 验证 API Key ──────────────────────────────────────────────
            api_key = request.headers.get("X-API-Key")
            if api_key != API_KEY:
                logger.warning(f"[ImageReceiver] 非法请求，API Key 错误：{api_key}")
                raise HTTPException(status_code=401, detail="Unauthorized")

            # ── 解析 bay_id → code（支持 "A1" 和 "1" 两种格式）─────────────
            if bay_id in BAY_ID_TO_CODE.values():
                code = bay_id
            else:
                try:
                    code = BAY_ID_TO_CODE.get(int(bay_id))
                except ValueError:
                    code = None
            if code is None:
                raise HTTPException(status_code=400, detail=f"Unknown bay_id: {bay_id}")

            # ── 时间戳（可选）────────────────────────────────────────────
            timestamp = request.headers.get("X-Timestamp") or str(int(_time.time()))

            # ── 读取图片数据 ──────────────────────────────────────────────
            content = await request.body()
            if not content:
                raise HTTPException(status_code=400, detail="No image data provided")

            # ── 保存文件 ──────────────────────────────────────────────────
            filename  = f"bay_{bay_id}_{timestamp}.jpg"
            save_path = self.upload_dir / filename
            try:
                save_path.write_bytes(content)
                logger.info(f"[ImageReceiver] 保存：{save_path}（{len(content)} bytes）")
            except Exception as e:
                logger.error(f"[ImageReceiver] 保存失败：{e}")
                raise HTTPException(status_code=500, detail="Failed to save image")

            # ── 异步触发 LPR（不阻塞响应）────────────────────────────────
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
            """查看当前所有车位状态和预约数据（调试用）"""
            return JSONResponse(self.on_get_status())

    def run(self):
        import threading

        def _run():
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")

        t = threading.Thread(target=_run, daemon=True, name="image-receiver")
        t.start()
        logger.info(f"[ImageReceiver] 启动在 http://{self.host}:{self.port}")
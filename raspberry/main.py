# =============================================================================
# main.py  —  Raspberry Pi Gateway Entry Point
# =============================================================================

import logging
import os
import signal
import sys
import time

os.makedirs("./tmp/parkReserve/images", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("./tmp/parkReserve/gateway.log"),
    ],
)

from services.control_service import ControlService


def main():
    service = ControlService()
    service.start()

    def _signal_handler(sig, frame):
        logging.info("Received exit signal, stopping...")
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()

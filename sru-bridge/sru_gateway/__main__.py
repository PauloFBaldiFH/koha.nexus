"""python -m sru_gateway: serve on 127.0.0.1:5000 (SRU_GATEWAY_HOST / SRU_GATEWAY_PORT)."""

import logging
import os

import uvicorn


def main() -> None:
    logging.basicConfig(level=os.environ.get("SRU_GATEWAY_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    uvicorn.run("sru_gateway.app:app",
                host=os.environ.get("SRU_GATEWAY_HOST", "127.0.0.1"),
                port=int(os.environ.get("SRU_GATEWAY_PORT", "5000")),
                workers=int(os.environ.get("SRU_GATEWAY_WORKERS", "1")),
                proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()

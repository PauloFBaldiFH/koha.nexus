"""python -m zeus_sru: serve on 127.0.0.1:5000 (ZEUS_SRU_HOST / ZEUS_SRU_PORT)."""

import logging
import os

import uvicorn


def main() -> None:
    logging.basicConfig(level=os.environ.get("ZEUS_SRU_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    uvicorn.run("zeus_sru.app:app",
                host=os.environ.get("ZEUS_SRU_HOST", "127.0.0.1"),
                port=int(os.environ.get("ZEUS_SRU_PORT", "5000")),
                workers=int(os.environ.get("ZEUS_SRU_WORKERS", "1")),
                proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()

"""python -m pergamum_sru: serve on 127.0.0.1:5006 (PERGAMUM_SRU_HOST / PERGAMUM_SRU_PORT)."""

import logging
import os

import uvicorn


def main() -> None:
    logging.basicConfig(level=os.environ.get("PERGAMUM_SRU_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    uvicorn.run("pergamum_sru.app:app",
                host=os.environ.get("PERGAMUM_SRU_HOST", "127.0.0.1"),
                port=int(os.environ.get("PERGAMUM_SRU_PORT", "5006")),
                workers=int(os.environ.get("PERGAMUM_SRU_WORKERS", "1")),
                proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()

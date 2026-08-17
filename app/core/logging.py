import json
import logging
import logging.handlers
import os
import time
from pathlib import Path

from app.core.config import get_settings


class JsonFileFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    settings = get_settings()
    Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("faq_service")
    root.setLevel(settings.log_level)

    if root.handlers:
        return

    # 회전을 두는 이유: 로그 파일은 지우는 사람이 없다. 질문 1건에 여러 줄이 쌓이고 서버는
    # 몇 달씩 떠 있으므로, 상한이 없으면 파일 하나가 수 GB가 된다. 5MB × 5개면 최근 며칠은
    # 남으면서 디스크는 25MB 를 넘지 않는다.
    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(JsonFileFormatter())
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"faq_service.{name}")


def log_event(logger: logging.Logger, message: str, **fields) -> None:
    logger.info(message, extra={"extra_fields": fields})

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


@dataclass
class GoldenItem:
    question: str
    lang: str
    expected_answer_summary: str
    expected_source: str
    category: str
    is_confusion_test: bool = False


def load_golden_set(path: str | None = None) -> list[GoldenItem]:
    settings = get_settings()
    file_path = Path(path or settings.golden_set_file)
    items: list[GoldenItem] = []
    with file_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            items.append(
                GoldenItem(
                    question=row["question"],
                    lang=row.get("lang", "ko"),
                    expected_answer_summary=row.get("expected_answer_summary", ""),
                    expected_source=row.get("expected_source", ""),
                    category=row.get("category", ""),
                    is_confusion_test=row.get("is_confusion_test", False),
                )
            )
    return items

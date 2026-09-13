from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionTxtPreview:
    source_path: str
    original_text: str
    captions: list[str]


def parse_caption_text(content: str) -> list[str]:
    pattern = r"\[\d{1,2}.*?\].*?:\s*(.*?)(?=\s*\[\d{1,2}|$)"
    blocks = re.findall(pattern, content, flags=re.DOTALL)
    captions = [block.strip() for block in blocks if block.strip()]
    if captions:
        return captions

    paragraphs = [
        block.strip()
        for block in re.split(r"\r?\n\s*\r?\n", content)
        if block.strip()
    ]
    captions = []
    pending = []
    for paragraph in paragraphs:
        pending.append(paragraph)
        if re.search(r"#\w+", paragraph):
            captions.append("\n\n".join(pending))
            pending = []
    if pending:
        captions.append("\n\n".join(pending))
    return captions


def preview_txt(path: str) -> CaptionTxtPreview:
    if not path or not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        original = handle.read()
    return CaptionTxtPreview(
        source_path=str(path),
        original_text=original,
        captions=parse_caption_text(original),
    )

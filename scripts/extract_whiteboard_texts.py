import json
from pathlib import Path


def extract_texts(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    texts: list[str] = []

    def walk(obj):
        if isinstance(obj, dict):
            if "text" in obj and isinstance(obj["text"], str) and obj["text"].strip():
                texts.append(obj["text"].strip())
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    seen: list[str] = []
    for t in texts:
        if t not in seen:
            seen.append(t)
    return seen


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "docs" / "feishu_import"
    out = root / "whiteboard-texts.md"
    lines = ["# 画板文本提取\n"]
    for name in ["whiteboard1-raw.json", "whiteboard2-raw.json"]:
        texts = extract_texts(root / name)
        lines.append(f"## {name} ({len(texts)} labels)\n")
        for t in texts:
            lines.append(f"- {t.replace(chr(10), ' / ')}\n")
        lines.append("\n")
    out.write_text("".join(lines), encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()

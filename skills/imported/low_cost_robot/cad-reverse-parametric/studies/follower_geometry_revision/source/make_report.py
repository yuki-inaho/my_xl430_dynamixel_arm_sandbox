"""Produce the self-contained Japanese report using the actual CAD render images."""

import base64
import json
import os
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CAD_RELEASE_DIR", str(SOURCE_DIR.parent))).resolve()


def main():
    report = json.loads((ROOT / "reports/validation.json").read_text())
    if not report["geometry_checks_passed"]:
        raise ValueError("Report requires accepted geometry")
    content = (SOURCE_DIR / "report_template.html").read_text()
    replacements = {
        "__ASSEMBLY__": "assembly.png",
        "__BEFORE__": "extension_before.png",
        "__AFTER__": "extension_after.png",
        "__WRIST__": "wrist_standoffs.png",
        "__BASE__": "base_clearance.png",
    }
    for token, filename in replacements.items():
        encoded = base64.b64encode((ROOT / "images" / filename).read_bytes()).decode()
        content = content.replace(token, "data:image/png;base64," + encoded)
    (ROOT / "CAD_review_ja.html").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()

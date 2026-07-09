"""추출 CLI — `python -m admeta.extract <platform> [...]` 또는 `--active`.

예:
    py -3 -m admeta.extract google_ads meta
    py -3 -m admeta.extract --active
"""
from __future__ import annotations

import sys

from admeta.extract.engine import PARSERS, extract_platform
from admeta.platforms import active_platforms


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("파서 구현된 플랫폼:", ", ".join(PARSERS))
        return 0

    keys = [p.key for p in active_platforms()] if argv[0] == "--active" else argv
    for key in keys:
        if key not in PARSERS:
            print(f"[{key}] 파서 미구현 — 스킵")
            continue
        print(f"\n추출: {key}")
        extract_platform(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

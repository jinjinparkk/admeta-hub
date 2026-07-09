"""크롤 CLI — `python -m admeta.crawler <platform>` 또는 `--active` 로 활성 전체.

예:
    py -3 -m admeta.crawler google_ads
    py -3 -m admeta.crawler meta
    py -3 -m admeta.crawler --active     # active=True 인 플랫폼 전부
    py -3 -m admeta.crawler --list       # 등록된 플랫폼 목록
"""
from __future__ import annotations

import sys

from admeta.crawler.engine import crawl_platform
from admeta.platforms import PLATFORMS, active_platforms


def _print_list() -> None:
    print("등록된 플랫폼:")
    for p in PLATFORMS.values():
        flag = "●" if p.active else "○"
        print(f"  {flag} {p.key:12s} {p.fetch:8s} {p.name}")
    print("  (● = Wave 0 active)")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        _print_list()
        return 0

    if argv[0] == "--list":
        _print_list()
        return 0

    if argv[0] == "--active":
        specs = active_platforms()
    else:
        specs = []
        for key in argv:
            if key not in PLATFORMS:
                print(f"알 수 없는 플랫폼: {key}")
                _print_list()
                return 2
            specs.append(PLATFORMS[key])

    for spec in specs:
        print(f"\n크롤: {spec.name} ({spec.key}, fetch={spec.fetch})")
        crawl_platform(spec.key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

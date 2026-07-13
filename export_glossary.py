# -*- coding: utf-8 -*-
"""
용어사전 폴백 스냅샷 생성기
==========================
웹·앱은 평소엔 GET /v1/glossary 로 사전을 받아온다. 하지만 엔진이 죽거나(웹) 비행기
모드거나 첫 실행(앱)이면 받을 수 없다 — 그때 툴팁이 통째로 사라지면 안 되므로 폴백이 필요하다.

그 폴백을 **손으로 쓰면 또 두 벌이 된다**(바로 이 사태를 없애려는 작업인데). 그래서
폴백도 엔진에서 뽑는다. 사전을 고쳤으면 이 스크립트를 돌려 스냅샷을 갱신할 것:

    py engine/export_glossary.py

만들어지는 것:
    web/app/lib/glossaryFallback.ts   — 웹이 엔진 호출 실패 시 쓰는 스냅샷
    app/assets/glossary.json          — 앱이 첫 실행·오프라인에 쓰는 번들 스냅샷
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from glossary import payload, _assert_covers_engine_vocabulary  # noqa: E402

WEB_OUT = os.path.join(ROOT, "web", "app", "lib", "glossaryFallback.ts")
APP_OUT = os.path.join(ROOT, "app", "assets", "glossary.json")

BANNER = "engine/glossary.py 에서 자동 생성됨 — 직접 고치지 말 것 (py engine/export_glossary.py)"


def main():
    _assert_covers_engine_vocabulary()
    data = payload()

    # ── 웹: TS 모듈 ──
    ts = (
        "// %s\n"
        "// 엔진(GET /v1/glossary) 이 진실의 원천이다. 이 파일은 엔진을 못 부를 때만 쓰는 폴백.\n"
        "import type { GlossaryData } from \"./glossary\";\n\n"
        "export const GLOSSARY_FALLBACK: GlossaryData = %s;\n"
    ) % (BANNER, json.dumps(data, ensure_ascii=False, indent=2))
    os.makedirs(os.path.dirname(WEB_OUT), exist_ok=True)
    with open(WEB_OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(ts)

    # ── 앱: 번들 에셋 JSON ──
    os.makedirs(os.path.dirname(APP_OUT), exist_ok=True)
    with open(APP_OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"_note": BANNER, **data}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("용어 %d개 스냅샷 생성" % data["count"])
    print("  웹: %s" % os.path.relpath(WEB_OUT, ROOT))
    print("  앱: %s" % os.path.relpath(APP_OUT, ROOT))


if __name__ == "__main__":
    main()

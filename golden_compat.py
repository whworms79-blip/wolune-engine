# -*- coding: utf-8 -*-
"""
궁합 회귀 테스트 — 고정 케이스 + 불변식 + 분포 가드
====================================================
    py engine/golden_compat.py

궁합은 오랫동안 **검증되지 않은 채** 돌아갔다. 규칙표가 엔진·웹·앱 세 벌로 복제돼 있었고
골든셋이 지키는 건 엔진 것뿐이었다. 이제 계산이 엔진 한 곳에 있으니, 회귀 테스트를 건다.

세 가지를 지킨다:

1. 고정 케이스 8개 — "이 두 생일 → 이 점수, 이 근거 줄". 값이 바뀌면 바로 잡힌다.
   ★ 특히 banghe·sanxing 케이스: 클라이언트 규칙표엔 아예 없던 관계다. 엔진화의 이유 그 자체라
     이게 깨지면 규칙 통일이 되돌아간 것이다.

2. 불변식 — base + 모든 delta 의 합 == score. 무작위 2,000쌍에서 예외 0건이어야 한다.
   근거가 점수와 어긋나면, 점수를 정직하게 밝히겠다는 카드가 거짓말을 하는 것이다.

3. ★ 분포 가드 — 무작위 3,000쌍의 평균·표준편차·하한 클램프 비율.
   옛 공식은 평균 84.1점 / 표준편차 7.4 로 **사실상 모두가 80점대**였다(변별력 없음).
   누군가 가중치를 잘못 건드려 다시 그 상태가 되면 여기서 깨진다. 이 가드가 없어서
   "다들 87점"인 걸 아무도 모른 채 몇 달을 보냈다.
"""

import io
import os
import random
import statistics
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from saju_pillars import compute_chart, compute_relations  # noqa: E402
from compatibility import (                                # noqa: E402
    compute_compatibility, branch_relation, BASE, SCORE_MIN,
)


# ══════════════════════════════════════════════════════════════════
# 1) 고정 케이스
# ══════════════════════════════════════════════════════════════════
CASES = [
    {
        "id": "gen-spouse-he",
        "desc": "상생 + 일지 육합 — 높은 쪽",
        "a": {"birth_date": "1978-02-03", "birth_time": "15:54", "gender": "female"},
        "b": {"birth_date": "2000-08-03", "birth_time": "11:51", "gender": "male"},
        "score": 91,
        "summary_key": "generate",
        "rows": [
            ("ten_god", "he", "일간 정관·정재", +6),
            ("spouse", "he", "일지 육합", +8),
            ("branches", "he", "지지 전반", +3),
            ("elements", "he", "오행 보완", +0),
        ],
    },
    {
        "id": "floor-58",
        "desc": "일지 육충 + 충·파 다수 — 하한 58 보정이 실제로 뜨는가(궁합에 '나쁨'은 없다)",
        "a": {"birth_date": "1998-01-27", "birth_time": "15:16", "gender": "female"},
        "b": {"birth_date": "1995-04-07", "birth_time": "22:30", "gender": "male"},
        "score": 58,
        "summary_key": "same",
        "rows": [
            ("ten_god", "minor", "일간 편재·편관", -2),
            ("spouse", "chong", "일지 육충", -10),
            ("branches", "chong", "지지 전반", -7),
            ("elements", "minor", "오행 보완", -1),
            ("clamp", "neutral", "하한 보정", +4),
        ],
    },
    {
        "id": "cap-96",
        "desc": "합이 잔뜩 — 상한 96 보정(완벽한 궁합은 없다)",
        "a": {"birth_date": "1996-06-01", "birth_time": "14:21", "gender": "female"},
        "b": {"birth_date": "1968-09-11", "birth_time": "17:56", "gender": "male"},
        "score": 96,
        "summary_key": "control",
        "rows": [
            ("ten_god", "he", "일간 정관·정재", +6),
            ("spouse", "he", "일지 육합", +8),
            ("branches", "he", "지지 전반", +10),
            ("elements", "he", "오행 보완", +0),
            ("clamp", "neutral", "상한 보정", -2),
        ],
    },
    {
        "id": "banghe",
        "desc": "★ 방합 포함 — 클라이언트 규칙표엔 아예 없던 관계(엔진화의 이유 그 자체)",
        "a": {"birth_date": "1975-10-18", "birth_time": "04:23", "gender": "female"},
        "b": {"birth_date": "1998-08-21", "birth_time": "18:04", "gender": "male"},
        "score": 72,
        "summary_key": "control",
        "rows": [
            ("ten_god", "he", "일간 정재·정관", +6),
            ("spouse", "minor", "일지 파", -3),
            ("branches", "chong", "지지 전반", -2),
            ("elements", "minor", "오행 보완", -2),
            ("clamp", "neutral", "반올림", -1),
        ],
        "must_contain": ["방합"],   # 근거 note 에 실제로 방합이 적혀야 한다
    },
    {
        "id": "sanxing",
        "desc": "★ 삼형(丑戌未) — 두 사람이 나눠 가져 완성. 한 사람만으론 안 보이는 관계",
        # A 의 지지에 未, B 의 지지에 丑·戌 → 합쳐야 삼형이 선다. 명식은 세 글자가 다 있을
        # 때만 삼형으로 보므로(잠긴 규칙), 궁합도 두 사람 지지를 합쳐 판정한다.
        "a": {"birth_date": "1998-04-25", "birth_time": "14:40", "gender": "female"},
        "b": {"birth_date": "2000-10-22", "birth_time": "23:54", "gender": "male"},
        "score": 62,
        "summary_key": "same",
        "rows": [
            ("ten_god", "minor", "일간 겁재", -7),
            ("spouse", "neutral", "일지 무관계", -1),
            ("branches", "chong", "지지 전반", -3),
            ("elements", "minor", "오행 보완", -1),
        ],
        "must_contain": ["형"],
    },
    {
        "id": "hour-unknown",
        "desc": "한쪽 시간 미상 — 시주 제외(3지지), 자리 가중이 시주 없이도 맞는가",
        "a": {"birth_date": "1996-03-14", "birth_time": "11:11", "gender": "female"},
        "b": {"birth_date": "1994-07-02", "birth_time": None, "gender": "male"},
        "score": 76,
        "summary_key": "generate",
        "rows": [
            ("ten_god", "he", "일간 정인·상관", +0),
            ("spouse", "neutral", "일지 무관계", -1),
            ("branches", "he", "지지 전반", +2),
            ("elements", "he", "오행 보완", +0),
            ("clamp", "neutral", "반올림", +1),
        ],
    },
    {
        "id": "lunar-leap",
        "desc": "음력 + 윤달 입력",
        "a": {"birth_date": "1987-06-15", "birth_time": "08:00", "gender": "female",
              "calendar": "lunar", "is_leap_month": True},
        "b": {"birth_date": "1990-05-08", "birth_time": "20:15", "gender": "male"},
        "score": 74,
        "summary_key": "same",
        "rows": [
            ("ten_god", "he", "일간 상관·정인", +0),
            ("spouse", "neutral", "일지 무관계", -1),
            ("branches", "he", "지지 전반", +1),
            ("elements", "minor", "오행 보완", -1),
            ("clamp", "neutral", "반올림", +1),
        ],
    },
    {
        "id": "same-birth",
        "desc": "생일이 같은 두 사람 — 비화 + 자형 경로",
        "a": {"birth_date": "1993-02-17", "birth_time": "12:00", "gender": "female"},
        "b": {"birth_date": "1993-02-17", "birth_time": "12:00", "gender": "male"},
        "score": 69,
        "summary_key": "same",
        "rows": [
            ("ten_god", "minor", "일간 비견", -2),
            ("spouse", "neutral", "일지 무관계", -1),
            ("branches", "minor", "지지 전반", -1),
            ("elements", "minor", "오행 보완", -1),
        ],
    },
]

# 분포 가드의 목표치 — 2026-07-15 재설계 시 5,000쌍 실측(평균 74.0 / sd 7.9 / 하한 2.7%).
# 여유를 두되, "다들 80점대"로 되돌아가면 반드시 깨지도록 좁게 잡는다.
DIST_N = 3000
DIST_MEAN = (72.5, 75.5)
DIST_SD = (7.0, 9.0)
DIST_P10_MIN = 60          # 하위 10%가 60 이상이면 변별력이 죽은 것
DIST_FLOOR_MAX = 0.05      # 하한에 5% 넘게 몰리면 바닥에 뭉친 것
INVARIANT_N = 2000


def _chart(p):
    t = p.get("birth_time")
    hour_known = bool(t)
    dt = datetime.strptime(p["birth_date"] + " " + (t or "12:00"), "%Y-%m-%d %H:%M")
    return compute_chart(dt, city=p.get("city", "서울"), gender=p["gender"],
                         hour_known=hour_known, calendar=p.get("calendar", "solar"),
                         is_leap_month=p.get("is_leap_month", False))


def run_cases(verbose=False):
    ok = 0
    for c in CASES:
        r = compute_compatibility(_chart(c["a"]), _chart(c["b"]), "가", "나")
        sb = r["score_basis"]
        got = [(row["key"], row["kind"], row["chips"][0]["label"], row["chips"][0]["delta"])
               for row in sb["rows"]]
        fails = []
        if r["score"] != c["score"]:
            fails.append("점수 %s (기대 %s)" % (r["score"], c["score"]))
        if r["summary"]["key"] != c["summary_key"]:
            fails.append("summary %s (기대 %s)" % (r["summary"]["key"], c["summary_key"]))
        if got != c["rows"]:
            fails.append("근거 줄이 다름:\n        기대 %s\n        실제 %s" % (c["rows"], got))
        # 근거의 합 == 점수 (이 케이스에서도)
        total = sb["base"] + sum(ch["delta"] for row in sb["rows"] for ch in row["chips"])
        if total != r["score"]:
            fails.append("덧셈 불일치: %d + Σdelta = %d ≠ %d" % (sb["base"], total, r["score"]))
        for word in c.get("must_contain", []):
            blob = " ".join(row["note"] for row in sb["rows"])
            if word not in blob:
                fails.append("근거 note 에 '%s' 가 없다 — 규칙 통일이 되돌아갔다" % word)

        mark = "PASS" if not fails else "FAIL"
        print("[%s] %-14s %s" % (mark, c["id"], c["desc"]))
        if fails:
            for f in fails:
                print("       · %s" % f)
        elif verbose:
            print("       %d점 — %s" % (r["score"], sb["disclosure"][:40]))
        ok += not fails
    return ok, len(CASES)


def _rnd_person(rng, gender):
    return {
        "birth_date": "%04d-%02d-%02d" % (rng.randint(1955, 2010), rng.randint(1, 12),
                                          rng.randint(1, 28)),
        "birth_time": "%02d:%02d" % (rng.randint(0, 23), rng.randint(0, 59)),
        "gender": gender,
    }


def run_invariant():
    """★ base + Σdelta == score. 근거 카드가 거짓말을 못 하게."""
    rng = random.Random(1015)
    bad = 0
    for _ in range(INVARIANT_N):
        r = compute_compatibility(_chart(_rnd_person(rng, "female")),
                                  _chart(_rnd_person(rng, "male")), "가", "나")
        sb = r["score_basis"]
        total = sb["base"] + sum(c["delta"] for row in sb["rows"] for c in row["chips"])
        if total != r["score"] or sb["base"] != BASE:
            bad += 1
    mark = "PASS" if bad == 0 else "FAIL"
    print("[%s] 불변식      base + Σdelta == score  (무작위 %d쌍, 불일치 %d건)"
          % (mark, INVARIANT_N, bad))
    return bad == 0


def run_distribution():
    """★ 점수가 실제로 분포하는가. '다들 87점'으로 되돌아가면 여기서 깨진다."""
    rng = random.Random(777)
    scores = []
    for _ in range(DIST_N):
        r = compute_compatibility(_chart(_rnd_person(rng, "female")),
                                  _chart(_rnd_person(rng, "male")), "가", "나")
        scores.append(r["score"])
    scores.sort()
    mean = statistics.mean(scores)
    sd = statistics.pstdev(scores)
    p10 = scores[int(0.10 * (len(scores) - 1))]
    floor_ratio = sum(1 for s in scores if s == SCORE_MIN) / len(scores)

    checks = [
        ("평균", DIST_MEAN[0] <= mean <= DIST_MEAN[1], "%.1f (기대 %.1f~%.1f)" % (mean, *DIST_MEAN)),
        ("표준편차", DIST_SD[0] <= sd <= DIST_SD[1], "%.1f (기대 %.1f~%.1f)" % (sd, *DIST_SD)),
        ("p10", p10 >= DIST_P10_MIN, "%d (기대 ≥%d — 낮으면 변별력 죽음)" % (p10, DIST_P10_MIN)),
        ("하한 클램프", floor_ratio <= DIST_FLOOR_MAX,
         "%.1f%% (기대 ≤%.0f%%)" % (floor_ratio * 100, DIST_FLOOR_MAX * 100)),
    ]
    all_ok = all(c[1] for c in checks)
    print("[%s] 분포 가드    무작위 %d쌍 — 최저 %d / 중앙 %d / 최고 %d"
          % ("PASS" if all_ok else "FAIL", DIST_N, scores[0],
             scores[len(scores) // 2], scores[-1]))
    for name, good, detail in checks:
        print("       %s %-8s %s" % ("·" if good else "✗", name, detail))
    return all_ok


ZHI = "子丑寅卯辰巳午未申酉戌亥"


def run_rule_parity():
    """★ 명식과 궁합이 **같은 두 글자를 같은 이름으로 부르는가.**

    엔진화의 이유 그 자체다. 예전엔 명식 화면이 "방합"이라 부르는 관계를 궁합 화면은
    관계 없음으로 봤다. 이제 규칙표가 한 벌이니, 판정도 한 벌이어야 한다.

    ⚠ 삼형(寅巳申·丑戌未)은 여기서 대조하지 않는다 — 명식도 궁합도 '세 지지가 다 있을 때만'
      성립시키므로, 두 글자만 넣는 이 검사에선 양쪽 다 관계 없음이 정답이다.
      (실제로 이 검사가 丑戌 쌍의 불일치를 잡아냈다: 궁합이 두 글자만 보고 형이라 불렀다.)
    """
    bad = []
    for a in ZHI:
        for b in ZHI:
            # 명식: 두 지지를 두 기둥에 넣고 관계를 뽑는다(같은 지지면 자형 경로)
            pillars = {"year": {"zhi": a}, "month": {"zhi": b}}
            names = {r["type"] for r in compute_relations(pillars)}
            got = branch_relation(a, b)
            if got is None:
                if names:
                    bad.append((a, b, "궁합=없음", sorted(names)))
            elif got not in names:
                bad.append((a, b, "궁합=%s" % got, sorted(names) or ["없음"]))

    n = len(ZHI) * len(ZHI)
    mark = "PASS" if not bad else "FAIL"
    print("[%s] 규칙 일치    명식 ↔ 궁합, 지지 %d쌍 전부 같은 이름 (불일치 %d개)"
          % (mark, n, len(bad)))
    for x in bad[:8]:
        print("       ✗ %s%s → %s / 명식=%s" % (x[0], x[1], x[2], x[3]))
    return not bad


def main():
    line = "=" * 64
    print(line)
    print("  Wolune 궁합 — 회귀 테스트 (규칙 일치 + 고정 케이스 + 불변식 + 분포)")
    print(line)
    ok, total = run_cases(verbose="-v" in sys.argv)
    print("-" * 64)
    parity = run_rule_parity()
    inv = run_invariant()
    dist = run_distribution()
    print(line)
    passed = ok == total and parity and inv and dist
    print("  요약: 고정 %d/%d · 규칙일치 %s · 불변식 %s · 분포 %s  →  %s"
          % (ok, total, "OK" if parity else "실패", "OK" if inv else "실패",
             "OK" if dist else "실패", "✅ 전부 통과" if passed else "❌ 실패"))
    print(line)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

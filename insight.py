# -*- coding: utf-8 -*-
"""
무드 통찰(B3) — 누적 무드 기록 × 그날의 사주 기운의 경향
========================================================
앱 lib/data/mood_insight.dart 에만 있던 로직을 엔진으로 올린 것. 웹에 복사하면 또 두 벌이
되고 언젠가 어긋난다(용어사전이 그랬듯이).

원칙(무드저널 PRD §4.4·§7):
    · 단정 금지 · "경향/힌트"로만 · 상관 ≠ 인과.
    · 데이터 부족 시 억지 패턴 만들지 않음(과적합 방지) → 임계치 이상만 잠금 해제.
    · 부정 강화 금지 · 돌봄 톤.

**무상태**: 받은 배열로 계산만 하고 돌려준다. 저장하지 않는다.

**개인정보**: 계산에 필요한 건 mood / score / day_ganzhi 셋뿐이다. 메모(note)와 태그는
계산에 쓰이지 않으므로 **아예 받지 않는다** — 가장 민감한 자유 서술은 엔진에 오지도 않는다.
날짜도 현재 로직에 불필요해 받지 않는다. 액세스 로그도 경로만 남긴다(server.py 참고).
"""

import math

from saju_pillars import STEM_ELEMENT, ELEMENT_EN  # noqa: E402

# 통찰 잠금 해제에 필요한 최소 기록 수(사주 스냅샷이 있는 기록).
#
# 앱은 7, 웹은 10(연속 기록일)이라 어긋나 있었다. 둘은 임계값이 다른 게 아니라 **지표가
# 달랐다** — 앱은 기록 수, 웹은 연속일. 그래서 하루 걸러 20일 쓴 사람이 앱에선 패턴이
# 열리는데 웹은 "며칠 더"라고 말했다.
#
# 지표는 "스냅샷 있는 기록 수"(연속 무관)로 통일한다. 통계가 필요로 하는 건 연속성이 아니라
# 표본 수이고, 하루 빠뜨렸다고 진척이 0으로 리셋되는 건 무드저널에서 특히 가혹하다.
# 임계값은 10 — n=7 에서 r=0.3 은 우연히 나올 확률이 절반에 가깝다(너무 얇다).
INSIGHT_THRESHOLD = 10

_EL_HANJA = {"목": "木", "화": "火", "토": "土", "금": "金", "수": "水"}

# 오행 경향으로 결론내는 문턱: 표본 3건 이상인 오행만 신뢰, 최고-최저 평균차 0.7 이상.
#
# 2 → 3 으로 올렸다(2026-07-15). 2건이면 "우연히 기분 좋았던 이틀"이 그대로 패턴이 된다.
# 기록 10건이면 오행 다섯에 평균 2건씩 흩어지니, 문턱이 2일 땐 사실상 아무 필터도 아니었다.
# 이건 우리가 사용자에게 "당신만의 패턴"이라며 내놓는 문장이다 — 노이즈를 패턴이라 부르면
# 그 순간 신뢰를 잃는다. 못 여는 것보다 틀리게 여는 게 나쁘다.
#
# 대신 패턴이 덜 열린다: 무작위 시뮬레이션에서 오행 분기 적중률이 크게 줄고, 그만큼
# 상관(Pearson) 분기와 "아직 뚜렷한 패턴은 보이지 않아요"로 넘어간다(3단 폴백은 그대로).
# 기록이 쌓이면 다시 열리므로, 허탈함보다 정확함을 택한다.
_MIN_SAMPLES_PER_ELEMENT = 3
_MIN_ELEMENT_GAP = 0.8
# 간격이 표본오차의 몇 배 이상이어야 하는가(_beats_noise 참고). 이게 거짓양성을 실제로 막는 축이다.
_SE_FACTOR = 2.5
_MIN_CORRELATION = 0.3

_SUPPORT_HINT = "이 느낌이 맞나요? 상관은 인과가 아니에요 — 자기이해의 힌트로 살펴봐 주세요."


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sxx = syy = 0.0
    for x, y in zip(xs, ys):
        dx, dy = x - mx, y - my
        sxy += dx * dy
        sxx += dx * dx
        syy += dy * dy
    if sxx == 0 or syy == 0:
        return 0.0
    return sxy / (math.sqrt(sxx) * math.sqrt(syy))


def _beats_noise(high_moods, low_moods, gap):
    """그 간격이 **표본오차보다 충분히 큰가.**

    왜 필요한가 — 표본 문턱만으로는 안 걸러진다:
        오행 다섯의 평균 중 **최고와 최저를 골라** 그 차이를 본다. 다섯 중 극단 둘을 뽑는
        행위 자체가 차이를 부풀린다(다중비교). 그래서 기분이 완전히 무작위인 사람에게도
        간격 0.7 은 거의 항상 넘어간다 — 시뮬레이션(띄엄띄엄 기록, 4,000명):

            표본2·간격0.7 (옛것)  → 무작위 기분인 사람의 88~96% 에게 오행 패턴 선언
            표본3·간격0.7        → 기록 10건에선 22% 로 줄지만, 20건 이상에선 다시 92%
            표본3·간격0.8·2.5×SE → 3~25% (진짜 경향은 80~100% 그대로 잡음)  ← 채택

        즉 표본을 늘려도 최고-최저 간격은 줄지 않는다. 노이즈를 직접 봐야 한다.

    표본오차 SE = sqrt(s_high²/n_high + s_low²/n_low).
    기분이 들쭉날쭉하거나 표본이 적으면 SE 가 커져, 문턱이 저절로 높아진다.

    ⚠ 이건 우리가 "당신만의 패턴"이라며 내놓는 문장이다. 못 여는 것보다 틀리게 여는 게 나쁘다.
    """
    def _var(v):
        m = sum(v) / len(v)
        return sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)

    se = math.sqrt(_var(high_moods) / len(high_moods) + _var(low_moods) / len(low_moods))
    if se == 0:
        return True  # 두 무리 안이 완전히 균일 → 노이즈가 없다
    return gap >= _SE_FACTOR * se


def compute_insight(entries):
    """entries: [{"mood": 1~5, "score": int, "day_ganzhi": "甲子"}, ...]

    day_ganzhi 가 없는 기록은 대상에서 빠진다(그날의 기운을 모르면 대조할 게 없다).
    """
    with_fortune = [e for e in entries if (e.get("day_ganzhi") or "").strip()]
    n = len(with_fortune)

    if n < INSIGHT_THRESHOLD:
        return {
            "unlocked": False,
            "count": n,
            "needed": INSIGHT_THRESHOLD,
            "remaining": INSIGHT_THRESHOLD - n,
            "pattern": "locked",
            "headline": None,
            "support": None,
            "detail": None,
        }

    base = {"unlocked": True, "count": n, "needed": INSIGHT_THRESHOLD, "remaining": 0}

    # ── ① 일진 오행 ↔ 기분 : 오행별 평균 기분 ──
    # dict 는 삽입 순서를 지킨다 → 동점일 때 '먼저 나온 오행이 이긴다'(Dart 와 같은 결과).
    moods = {}
    for e in with_fortune:
        el = STEM_ELEMENT.get((e["day_ganzhi"] or "")[0])
        if el is None:
            continue
        moods.setdefault(el, []).append(e["mood"])

    ok = {el: v for el, v in moods.items() if len(v) >= _MIN_SAMPLES_PER_ELEMENT}
    avg = {el: sum(v) / len(v) for el, v in ok.items()}

    high = low = None
    for el, a in avg.items():
        if high is None or a > avg[high]:
            high = el
        if low is None or a < avg[low]:
            low = el

    if high is not None and low is not None and high != low \
            and (avg[high] - avg[low]) >= _MIN_ELEMENT_GAP \
            and _beats_noise(ok[high], ok[low], avg[high] - avg[low]):
        return {
            **base,
            "pattern": "element",
            "headline": (
                "%s(%s) 기운이 도는 날 마음이 차오르는 편이고, "
                "%s(%s) 기운의 날엔 차분히 가라앉는 편이에요."
                % (high, _EL_HANJA[high], low, _EL_HANJA[low])
            ),
            "support": _SUPPORT_HINT,
            "detail": {
                "high_element": ELEMENT_EN[high],
                "low_element": ELEMENT_EN[low],
                "gap": round(avg[high] - avg[low], 4),
            },
        }

    # ── ② 운세 점수 ↔ 기분 상관(부호) ──
    r = _pearson([float(e["score"]) for e in with_fortune],
                 [float(e["mood"]) for e in with_fortune])

    if r >= _MIN_CORRELATION:
        return {
            **base,
            "pattern": "fortune_positive",
            "headline": "사주 흐름이 좋은 날, 실제 기분도 함께 오르는 편이에요.",
            "support": _SUPPORT_HINT,
            "detail": {"r": round(r, 4)},
        }
    if r <= -_MIN_CORRELATION:
        return {
            **base,
            "pattern": "fortune_independent",
            "headline": "사주 흐름과 무관하게, 당신만의 리듬으로 마음이 움직이는 편이에요.",
            "support": "이 느낌이 맞나요? 기록이 쌓일수록 당신의 리듬이 더 선명해져요.",
            "detail": {"r": round(r, 4)},
        }

    # 뚜렷한 신호가 없으면 억지로 만들지 않는다(과적합 방지).
    return {
        **base,
        "pattern": "none",
        "headline": "아직 뚜렷한 패턴은 보이지 않아요.",
        "support": "기록이 더 쌓이면 당신만의 감정×기운 리듬이 선명해질 거예요.",
        "detail": {"r": round(r, 4)},
    }


def parse_entries(body):
    """요청 바디 → 계산에 쓸 최소 필드만 추린다. 형식이 아니면 ValueError."""
    if not isinstance(body, dict):
        raise ValueError("JSON 객체여야 합니다.")
    raw = body.get("entries")
    if not isinstance(raw, list):
        raise ValueError("entries 는 배열이어야 합니다.")
    if len(raw) > 1000:
        raise ValueError("entries 는 1000건 이하여야 합니다.")

    out = []
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            raise ValueError("entries[%d] 는 객체여야 합니다." % i)
        mood = e.get("mood")
        if not isinstance(mood, (int, float)) or not (1 <= mood <= 5):
            raise ValueError("entries[%d].mood 는 1~5 여야 합니다." % i)
        score = e.get("score", 0)
        if not isinstance(score, (int, float)):
            raise ValueError("entries[%d].score 는 숫자여야 합니다." % i)
        gz = e.get("day_ganzhi") or e.get("dayGanzhi") or ""
        # 계산에 쓰는 것만 남긴다 — note/tags/date 는 받아도 버린다(애초에 보내지 않는다).
        out.append({"mood": int(mood), "score": float(score), "day_ganzhi": str(gz)})
    return out

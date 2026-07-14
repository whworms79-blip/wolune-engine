# -*- coding: utf-8 -*-
"""
Wolune 궁합(宮合) — 점수·근거·문구의 진실의 원천
================================================

왜 엔진에 두는가 (2026-07-15 결정, 원래 기획으로 복귀)
------------------------------------------------------
예전엔 육합·삼합·육충·형·파 규칙표가 **엔진 1벌 + 웹 1벌 + 앱 1벌, 총 3벌**이었다.
그리고 이미 어긋나 있었다 — 클라이언트엔 방합(方合)이 통째로 없고 형(刑)은 子卯 하나뿐이라,
**명식 화면이 "방합"이라 부르는 관계를 궁합 화면은 관계 없음으로 봤다.** 골든셋이 지키는 건
엔진 1벌뿐이고 나머지 2벌은 아무도 검증하지 않았다. 그 상태로 사용자에겐 점수와
"이 점수는 이렇게 나왔어요" 근거까지 보여주고 있었다.

규칙을 만드는 쪽이 점수도, 그 근거도, 그 문구도 말한다(용어사전 glossary.py 와 같은 원칙).
클라이언트는 색·아이콘·픽셀만 정한다 — 응답의 kind 는 he/chong/minor/neutral 이라는
**의미**만 주고, 그게 라벤더인지 화(火)인지는 화면이 정한다.

⚠ 옛 주석이 "엔진에 궁합 계산을 두지 않는다"고 금지했으나 아키텍처적 근거가 없었고
  (적힌 이유는 '단정하지 않는 톤' — 계산 위치와 무관하다), 기획 문서
  files1/Wolune_만세력엔진_기술명세.md 는 처음부터 POST /v1/compatibility 를 명시했다.

점수 공식 (2026-07-15 재설계)
-----------------------------
옛 공식은 60에서 시작해 항목을 더했고, 두 사람의 지지 4×4=16쌍을 **평평하게** 셌다.
그러면 합(合)이 안 잡히는 게 오히려 이상해서, 무작위 5,000쌍 시뮬레이션에서
**평균 84.1점 / 표준편차 7.4** — 사실상 모두가 80점대였다. 규칙을 엔진으로 통일하면
방합까지 세므로 평균 85.6점으로 **더 나빠진다**. 다들 87점이면 숫자를 아무도 안 믿는다.

그래서 카운트 누적을 버리고 **네 축의 가중 평균 + 모집단 보정**으로 바꿨다:

  · 자리 가중 — 일(日) 3 · 월 2 · 연 1 · 시 1. 쌍의 무게는 두 기둥 무게의 곱이라
    일지-일지(9)가 연지-시지(1)의 9배다. 궁합의 핵심은 배우자궁(일지)이다.
  · 합에 등급 — 육합 > 삼합 > 방합. 방합은 "같은 계절"이라 결이 닮은 정도이지
    육합처럼 맞물리는 게 아니다. 이게 있어야 규칙을 통일해도 점수가 부풀지 않는다.
  · 모집단 보정 — 지지 전반 축은 평균이 양(+)으로 치우쳐 있어(_MU3) 그 평균을 뺀다.
    "합이 기본으로 깔려 점수가 뜨는" 편향을 없애는 부분이다.

결과: 평균 74.0 / 표준편차 7.9 / p10 62 / p90 84 — 58~96 구간을 실제로 쓴다.

하한 58은 **철학이다.** 사주엔 본래 궁합 점수가 없고 '나쁜 궁합'도 없다. 재료가 아무리
어긋나도 58 아래로 내리지 않고, 그 보정마저 근거에 정직하게 드러낸다.

★ 불변식: base + 모든 delta 의 합 == score. **항상.** (하한·상한 보정, 반올림 오차도
  한 줄로 드러내기 때문.) 근거가 점수와 어긋나면, 점수를 정직하게 밝히겠다는 카드가
  거짓말을 하는 것이다. golden_set.py 가 이걸 무작위 2,000쌍으로 지킨다.
★ 분포 가드: golden_set.py 가 무작위 3,000쌍의 평균·표준편차·하한 클램프 비율을 검사한다.
  누군가 가중치를 잘못 건드려 다시 "다들 87점"이 되면 CI 가 깨진다.
"""

from saju_pillars import (
    _ten_god,
    _LIUHE, _LIUCHONG, _LIUHAI, _PO, _XIANGXING, _ZIXING,
    _SANHE, _BANGHE, _SANXING,
)

PILLAR_KEYS = ("year", "month", "day", "hour")

EL_KO = {"wood": "목", "fire": "화", "earth": "토", "metal": "금", "water": "수"}
EL_HANJA = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}
# 상생(生): A 가 GEN[A] 를 낳는다. 상극(剋): A 가 CTRL[A] 를 이긴다.
GEN = {"wood": "fire", "fire": "earth", "earth": "metal", "metal": "water", "water": "wood"}
CTRL = {"wood": "earth", "earth": "water", "water": "fire", "fire": "metal", "metal": "wood"}

# 관계에 순한 십성일수록 높게(짝 관계에서 안정적으로 통하는 결). 단정 아님 — 가중치일 뿐.
TEN_GOD_FAVOR = {
    "정재": 8, "정관": 8, "정인": 8, "식신": 7,
    "편재": 6, "편인": 5, "비견": 5,
    "편관": 4, "상관": 4, "겁재": 3,
}

# ── 조사(助詞) — "이(가)" 같은 이중표기는 사람이 쓴 문장으로 안 읽힌다 ──
def _jong(w):
    c = ord(w[-1])
    return 0xAC00 <= c <= 0xD7A3 and (c - 0xAC00) % 28 != 0


def _josa(word, with_jong, no_jong):
    return with_jong if _jong(word) else no_jong


def _el(k):
    return "%s(%s)" % (EL_KO[k], EL_HANJA[k])


# ══════════════════════════════════════════════════════════════════════════
# 지지 관계 — 엔진의 단일 규칙표(saju_pillars 의 것을 그대로 쓴다)
# ══════════════════════════════════════════════════════════════════════════
# 관계값. 합에 등급을 둔다 — 육합(맞물림) > 삼합(뜻이 같음) > 방합(같은 계절, 결이 닮음).
REL_VALUE = {
    "육합": 1.0, "삼합": 0.7, "방합": 0.4,
    "육충": -1.0, "육해": -0.5, "형": -0.5, "파": -0.3,
}
# 화면 색은 의미 키로만 준다(색·픽셀은 클라이언트가 정한다).
REL_KIND = {
    "육합": "he", "삼합": "he", "방합": "he",
    "육충": "chong", "육해": "minor", "형": "minor", "파": "minor",
}
# 자리 가중 — 궁합의 핵심은 배우자궁(일지)이다. 곁가지 합이 배우자궁의 충과 같은 무게를
# 가지면 안 된다. 시주는 시간 미상이면 아예 없다.
PILLAR_WEIGHT = {"year": 1.0, "month": 2.0, "day": 3.0, "hour": 1.0}


def branch_relation(a, b):
    """두 지지 사이의 쌍(pair) 관계 하나(가장 강한 것). 없으면 None.

    ⚠ 명식(compute_relations)과 **같은 규칙표·같은 판정**이어야 한다. 같은 두 글자를 두
      화면이 다르게 부르면, 사용자는 어느 쪽을 믿어야 할지 알 수 없다. 그게 엔진화의 이유다.
      golden_compat 의 rule-parity 검사가 132개 지지 쌍 전부를 대조해 이걸 지킨다.

    ⚠ 삼형(寅巳申·丑戌未)은 여기서 판정하지 않는다. 명식은 **세 지지가 다 있을 때만** 삼형으로
      본다(잠긴 명리 규칙). 두 글자만 보고 형이라 부르면 丑戌 같은 쌍에서 명식과 어긋난다.
      → 삼형은 branch_pairs() 가 두 사람의 지지를 **합쳐** 세 글자가 다 모였는지 보고 판정한다.
    """
    ps = frozenset((a, b))
    if a == b:
        return "형" if a in _ZIXING else None          # 자형(自刑)
    if ps in _LIUHE:
        return "육합"
    for triple in _SANHE.values():
        if a in triple and b in triple:
            return "삼합"                               # 반합(두 글자)
    for triple in _BANGHE.values():
        if a in triple and b in triple:
            return "방합"                               # ← 클라엔 아예 없던 규칙
    if ps in _LIUCHONG:
        return "육충"
    if ps in _LIUHAI:
        return "육해"
    if ps == _XIANGXING:
        return "형"                                     # 상형(相刑)
    if ps in _PO:
        return "파"
    return None


def branch_pairs(pa, pb):
    """두 사람의 지지 쌍(최대 4×4=16). 관계가 있는 것만, 자리 가중과 함께."""
    a_keys = [k for k in PILLAR_KEYS if k in pa]
    b_keys = [k for k in PILLAR_KEYS if k in pb]

    # 삼형(三刑): 두 사람의 지지를 **합쳐** 세 글자가 다 모였을 때만 성립한다(명식과 동일).
    # 예: A 에 寅·巳, B 에 申 → 세 사람 몫이 아니라 두 사람이 함께 만든 삼형이다.
    sanxing_hit = set()
    all_zhi = {pa[k]["branch"] for k in a_keys} | {pb[k]["branch"] for k in b_keys}
    for triple in _SANXING:
        if all(z in all_zhi for z in triple):
            sanxing_hit |= set(triple)

    out = []
    for ka in a_keys:
        for kb in b_keys:
            za, zb = pa[ka]["branch"], pb[kb]["branch"]
            t = branch_relation(za, zb)
            # 쌍 관계가 따로 없고, 둘 다 완성된 삼형의 구성 지지라면 형(刑)이다.
            if t is None and za != zb and za in sanxing_hit and zb in sanxing_hit:
                t = "형"
            if t is None:
                continue
            out.append({
                "a_pillar": ka, "b_pillar": kb, "branches": [za, zb],
                "type": t, "kind": REL_KIND[t],
                "weight": PILLAR_WEIGHT[ka] * PILLAR_WEIGHT[kb],
            })
    return out


# ══════════════════════════════════════════════════════════════════════════
# 네 축 (각각 0~100)
# ══════════════════════════════════════════════════════════════════════════
# 모집단 상수 — 1955~2010 무작위 5,000쌍 실측(compat_sim). 이 값이 바뀌면 점수 분포가
# 통째로 움직이므로, golden_set 의 분포 가드가 지킨다. 함부로 고치지 말 것.
_MU3, _SD3 = 0.1004, 0.1709          # 지지 전반 축의 원시 ratio 평균/표준편차
_AXIS_MEAN = (56.2, 55.2, 50.0, 60.2)  # 축별 모집단 평균(일간·배우자궁·지지전반·오행보완)
_RAW_MEAN, _RAW_SD = 54.96, 13.87      # 가중합의 모집단 평균/표준편차

WEIGHTS = (0.22, 0.30, 0.28, 0.20)   # 일간 / 배우자궁 / 지지 전반 / 오행 보완
BASE = 74                             # "평균적인 두 사람"의 점수 — 임의의 60이 아니라 실제 기준점
SPREAD = 8                            # 1σ = 8점
SCORE_MIN, SCORE_MAX = 58, 96


def _axis_ten_god(day_a, day_b):
    """축1) 서로를 어떤 십성으로 보는가. 3~8 → 0~100."""
    g_ab = _ten_god(day_a, day_b)     # A(일간)가 본 B
    g_ba = _ten_god(day_b, day_a)     # B(일간)가 본 A
    favor = (TEN_GOD_FAVOR.get(g_ab, 4) + TEN_GOD_FAVOR.get(g_ba, 4)) / 2.0
    return (favor - 3) / 5.0 * 100, g_ab, g_ba


def _axis_spouse(pairs):
    """축2) 배우자궁 — 일지끼리의 관계 하나. 육합 100 / 무관계 50 / 육충 0.
    ⚠ branch_pairs 가 낸 판정을 그대로 쓴다 — 같은 일지 쌍을 근거의 두 줄이 다르게 부르면 안 된다
      (삼형은 두 사람 지지를 합쳐야 성립하므로, 쌍 단위로 다시 계산하면 어긋난다)."""
    for p in pairs:
        if p["a_pillar"] == "day" and p["b_pillar"] == "day":
            return 50 + REL_VALUE[p["type"]] * 50, p["type"]
    return 50.0, None


def _axis_branches(pa, pb):
    """축3) 지지 전반 — 16쌍을 자리 가중으로. 모집단 평균을 빼 중심을 잡는다."""
    total = 0.0
    for ka in PILLAR_KEYS:
        if ka not in pa:
            continue
        for kb in PILLAR_KEYS:
            if kb in pb:
                total += PILLAR_WEIGHT[ka] * PILLAR_WEIGHT[kb]
    num = sum(p["weight"] * REL_VALUE[p["type"]] for p in branch_pairs(pa, pb))
    ratio = num / total if total else 0.0
    return 50 + (ratio - _MU3) / _SD3 * 18


def _dominant(fe):
    return max(fe, key=lambda k: fe[k]["pct"])


def _weakest(fe):
    return min(fe, key=lambda k: fe[k]["pct"])


def _axis_elements(fa, fb):
    """축4) 오행 보완 — 상생/비화/상극 + 서로의 빈 곳을 채우는가."""
    dom_a, dom_b = _dominant(fa), _dominant(fb)
    weak_a, weak_b = _weakest(fa), _weakest(fb)
    if dom_a == dom_b:
        harmony = "same"
    elif GEN[dom_a] == dom_b or GEN[dom_b] == dom_a:
        harmony = "generate"
    else:
        harmony = "control"
    base = {"generate": 62, "same": 50, "control": 44}[harmony]
    fill = (1 if dom_a == weak_b else 0) + (1 if dom_b == weak_a else 0)
    return min(100.0, base + fill * 19), harmony, dom_a, dom_b, weak_a, weak_b


# ══════════════════════════════════════════════════════════════════════════
# 문구 — 웹·앱에 두 벌로 복제하면 언젠가 어긋난다(용어사전과 같은 이유)
# ══════════════════════════════════════════════════════════════════════════
SUMMARY = {
    "generate": {"title": "서로를 키우는 두 사람", "en": "The Nurturing Pair",
                 "tagline": "곁에 있을수록, 서로를 자라게 하는 사이예요."},
    "same": {"title": "닮은 결의 두 사람", "en": "The Kindred Pair",
             "tagline": "말하지 않아도 통하는 지점이 많은 사이예요."},
    "control": {"title": "끌어당기는 두 사람", "en": "The Magnetic Pair",
                "tagline": "다르기에 오히려 서로에게 끌리는 사이예요."},
}

# 신살 접점 — 흉살(백호·양인·괴강)도 겁주지 않는다. 강점의 언어로만(용어사전과 같은 톤).
# mid = 문장 중간(…-고), end = 문장 끝(…-는). 신살이 하나뿐이면 end 만 쓴다.
SHENSHA_TONE = {
    "천을귀인": {"gist": "도움", "mid": "서로에게 기댈 언덕이 되고", "end": "어려울 때 먼저 손을 내미는"},
    "월덕귀인": {"gist": "온기", "mid": "서로의 모난 데를 감싸고", "end": "함께 있으면 마음이 눅어지는"},
    "문창귀인": {"gist": "배움", "mid": "이야기가 길어지고", "end": "같이 배우고 나누게 되는"},
    "역마": {"gist": "움직임", "mid": "자주 밖으로 나서게 되고", "end": "함께 있으면 어디론가 떠나고 싶어지는"},
    "화개": {"gist": "깊이", "mid": "말없이도 깊어지고", "end": "둘만의 세계가 조용히 깊어지는"},
    "도화": {"gist": "매력", "mid": "서로에게 자꾸 눈길이 가고", "end": "서로에게 자꾸 눈길이 가는"},
    "백호": {"gist": "기세", "mid": "서로의 기세를 부추기고", "end": "함께라면 겁 없이 밀어붙이는"},
    "양인": {"gist": "결단", "mid": "결정이 빨라지고", "end": "머뭇거림을 오래 두지 않는"},
    "괴강": {"gist": "강단", "mid": "서로의 심지를 알아보고", "end": "각자 단단해서 오히려 편안한"},
}

DISCLOSURE_BODY = ("사주엔 원래 궁합 점수가 없어요. 두 분의 재료를 규칙으로 수치화한 보조 지표일 뿐이고, "
                   "낮아도 나쁜 궁합이 아니라 서로 더 배려하면 좋은 사이예요.")
REFLECTION = "최근 두 사람 사이, 가장 좋았던 순간은 언제였나요?"


def _shensha_meet(a_name, b_name, ss_a, ss_b):
    ss_a = [s for s in ss_a if s in SHENSHA_TONE]
    ss_b = [s for s in ss_b if s in SHENSHA_TONE]
    if not ss_a and not ss_b:
        return None
    rep_a = ss_a[0] if ss_a else None
    rep_b = ss_b[0] if ss_b else None
    tag = lambda n: "%s(%s)" % (n, SHENSHA_TONE[n]["gist"])
    gist = lambda n: SHENSHA_TONE[n]["gist"]

    if rep_a and rep_b and rep_a != rep_b:
        line = "%s%s %s%s 만나 — %s %s 사이예요." % (
            tag(rep_a), _josa(gist(rep_a), "과", "와"),
            tag(rep_b), _josa(gist(rep_b), "이", "가"),
            SHENSHA_TONE[rep_a]["mid"], SHENSHA_TONE[rep_b]["end"])
    elif rep_a and rep_b:
        line = "두 분 다 %s%s 지녀 — %s 사이예요." % (
            tag(rep_a), _josa(gist(rep_a), "을", "를"), SHENSHA_TONE[rep_a]["end"])
    else:
        only = rep_a or rep_b
        who = a_name if rep_a else b_name
        line = "%s님의 %s%s 두 분 사이에 놓여 — %s 결이 돼요." % (
            who, tag(only), _josa(gist(only), "이", "가"), SHENSHA_TONE[only]["end"])
    return {"a": ss_a, "b": ss_b, "line": line}


def _branch_note(pairs):
    """지지 전반 축의 설명 — 무엇이 몇 쌍인지 사람 말로."""
    order = ["육합", "삼합", "방합", "육충", "육해", "형", "파"]
    cnt = {}
    for p in pairs:
        cnt[p["type"]] = cnt.get(p["type"], 0) + 1
    plus = [(t, cnt[t]) for t in order[:3] if t in cnt]
    minus = [(t, cnt[t]) for t in order[3:] if t in cnt]
    fmt = lambda xs: "·".join("%s %d쌍" % (t, n) for t, n in xs)
    if plus and minus:
        return "%s이 통하지만, %s이 부딪혀요" % (fmt(plus), fmt(minus))
    if plus:
        return "%s — 편안하게 통하는 자리가 있어요" % fmt(plus)
    if minus:
        return "%s — 급할 때 부딪힐 수 있어요" % fmt(minus)
    return "서로의 지지가 특별히 얽히지 않아요 — 각자의 결로 담담한 사이"


def _good_line(harmony, dom_a, dom_b, weak_a, weak_b, spouse_rel, pairs, a_name, b_name):
    if harmony == "generate":
        giver_is_a = GEN[dom_a] == dom_b
        giver, receiver = (a_name, b_name) if giver_is_a else (b_name, a_name)
        gel = dom_a if giver_is_a else dom_b
        return "%s님의 %s 기운이 %s님을 북돋아, 함께일수록 서로를 자라게 해요." % (giver, _el(gel), receiver)
    if spouse_rel in ("육합", "삼합", "방합"):
        return "두 분의 일지(日支)가 서로 맞물려(합), 마음 깊은 곳에서 자연스레 손발이 맞는 사이예요."
    if any(p["kind"] == "he" for p in pairs):
        return "두 분의 지지에 서로를 끌어안는 합(合)이 있어, 함께 있으면 편안하게 통하는 순간이 많아요."
    if harmony == "same":
        return "두 분 다 %s의 결이 뚜렷해, 취향과 속도가 닮아 말이 잘 통해요." % _el(dom_a)
    if dom_a == weak_b or dom_b == weak_a:
        rich_is_a = dom_a == weak_b
        rich, need = (a_name, b_name) if rich_is_a else (b_name, a_name)
        el = dom_a if rich_is_a else dom_b
        return "%s님에게 옅은 %s 기운을 %s님이 지니고 있어, 서로의 빈자리를 채워줘요." % (need, _el(el), rich)
    return "서로 다른 기운을 지녀, 함께할 때 시야가 넓어지는 사이예요."


def _tension_line(harmony, dom_a, dom_b, spouse_rel, pairs):
    if harmony == "control":
        return ("%s%s %s처럼 방식이 다를 수 있어요 — 다름을 틀림으로 읽지 않으면, "
                "그 다름이 오히려 끌림이 됩니다."
                % (_el(dom_a), _josa(EL_KO[dom_a], "과", "와"), _el(dom_b)))
    if spouse_rel == "육충":
        return ("두 분의 일지가 부딪히는(충) 자리가 있어, 가까운 사이일수록 사소한 데서 마찰이 날 수 있어요. "
                "한 박자 쉬어 주면 그 긴장이 서로를 깨우는 힘이 됩니다.")
    if any(p["kind"] == "chong" for p in pairs):
        return ("지지에 서로 밀어내는 충(沖)의 기운이 있어, 급할 땐 부딪힐 수 있어요. "
                "속도를 맞춰 주면 그 긴장이 관계를 더 단단하게 만들어요.")
    if harmony == "same":
        return "닮은 만큼 고집도 닮아, 같은 자리에서 서로 물러서지 않을 때가 있어요. 번갈아 기대 주면 돼요."
    if any(p["kind"] == "minor" for p in pairs):
        return "가끔 결이 어긋나는 순간이 있을 수 있어요. 서로의 방식을 먼저 물어봐 주면 금세 풀려요."
    return "서로의 속도가 다를 수 있으니, 기다려 주는 마음이 두 분을 더 가깝게 해요."


# ══════════════════════════════════════════════════════════════════════════
# 본체
# ══════════════════════════════════════════════════════════════════════════
def compute_compatibility(chart_a, chart_b, a_name="", b_name=""):
    """두 chart(compute_chart 결과) → 궁합 응답 dict.

    ★ 점수와 근거를 **한 번에** 만든다. 근거를 나중에 따로 재구성하면 언젠가 어긋나고,
      그러면 정직하게 밝히겠다는 카드가 거짓말을 한다.
      base + 모든 delta 의 합 == score 가 **항상** 성립한다(보정 줄까지 포함해서).
    """
    a_name = (a_name or "").strip() or "나"
    b_name = (b_name or "").strip() or "상대"
    pa, pb = chart_a["pillars"], chart_b["pillars"]
    fa, fb = chart_a["five_elements"], chart_b["five_elements"]

    # ── 네 축 ──
    pairs = branch_pairs(pa, pb)   # 지지 판정은 한 번만 — 두 줄이 다르게 부르지 않도록
    ax1, god_ab, god_ba = _axis_ten_god(pa["day"]["stem"], pb["day"]["stem"])
    ax2, spouse_rel = _axis_spouse(pairs)
    ax3 = _axis_branches(pa, pb)
    ax4, harmony, dom_a, dom_b, weak_a, weak_b = _axis_elements(fa, fb)
    axis = (ax1, ax2, ax3, ax4)

    # ── 점수: 가중 평균 → 모집단 기준으로 펼침 ──
    raw = sum(w * x for w, x in zip(WEIGHTS, axis))
    exact = BASE + (raw - _RAW_MEAN) / _RAW_SD * SPREAD
    score = max(SCORE_MIN, min(SCORE_MAX, int(round(exact))))

    # ── 근거: 축별 기여도. 선형이라 정확히 분해된다 ──
    #   점수 = BASE + Σ [ w * SPREAD/_RAW_SD * (축 - 축평균) ]
    k = SPREAD / _RAW_SD
    contrib = [int(round(WEIGHTS[i] * k * (axis[i] - _AXIS_MEAN[i]))) for i in range(4)]

    god_pair = god_ab if god_ab == god_ba else "%s·%s" % (god_ab, god_ba)
    if contrib[0] >= 2:
        god_note = "서로에게 순한 관계"
    elif contrib[0] >= -1:
        god_note = "무난하게 통하는 관계"
    else:
        god_note = "서로를 자극하는 관계 — 그 자극이 서로를 키우기도 해요"

    if spouse_rel is None:
        spouse_label, spouse_note = "일지 무관계", "배우자궁이 특별히 얽히지 않아요"
    elif REL_VALUE[spouse_rel] > 0:
        spouse_label, spouse_note = "일지 %s" % spouse_rel, "배우자궁이 맞물림"
    else:
        spouse_label = "일지 %s" % spouse_rel
        spouse_note = "배우자궁이 부딪힘 — 가까울수록 한 박자 쉬어 주면 돼요"

    fill = (1 if dom_a == weak_b else 0) + (1 if dom_b == weak_a else 0)
    if fill and dom_a == weak_b:
        el_note = "%s님이 %s님에게 옅은 %s%s 채워 줌" % (
            a_name, b_name, _el(dom_a), _josa(EL_KO[dom_a], "을", "를"))
    elif fill:
        el_note = "%s님이 %s님에게 옅은 %s%s 채워 줌" % (
            b_name, a_name, _el(dom_b), _josa(EL_KO[dom_b], "을", "를"))
    elif harmony == "generate":
        giver, receiver = (dom_a, dom_b) if GEN[dom_a] == dom_b else (dom_b, dom_a)
        el_note = "%s%s %s%s 낳는 사이(상생)" % (
            _el(giver), _josa(EL_KO[giver], "이", "가"),
            _el(receiver), _josa(EL_KO[receiver], "을", "를"))
    elif harmony == "same":
        el_note = "둘 다 %s의 결 — 닮은 기운끼리(비화)" % _el(dom_a)
    else:
        el_note = "%s%s %s — 서로를 다잡아 주는 결(상극)" % (
            _el(dom_a), _josa(EL_KO[dom_a], "과", "와"), _el(dom_b))

    def kind_of(delta, positive="he", negative="minor"):
        return positive if delta >= 0 else negative

    rows = [
        {"key": "ten_god", "kind": kind_of(contrib[0]),
         "chips": [{"label": "일간 %s" % god_pair, "delta": contrib[0]}], "note": god_note},
        # 일지에 아무 관계도 없으면 '중립'이다 — 관계 없음은 긴장이 아니다(로즈로 칠하지 않는다).
        {"key": "spouse",
         "kind": "neutral" if spouse_rel is None else
                 ("he" if REL_VALUE[spouse_rel] > 0 else
                  ("chong" if spouse_rel == "육충" else "minor")),
         "chips": [{"label": spouse_label, "delta": contrib[1]}], "note": spouse_note},
        {"key": "branches",
         "kind": "he" if contrib[2] >= 0 else
                 ("chong" if any(p["kind"] == "chong" for p in pairs) else "minor"),
         "chips": [{"label": "지지 전반", "delta": contrib[2]}], "note": _branch_note(pairs)},
        {"key": "elements", "kind": kind_of(contrib[3]),
         "chips": [{"label": "오행 보완", "delta": contrib[3]}], "note": el_note},
    ]

    # ★ 보정 줄 — 반올림 오차와 하한·상한 클램프를 숨기지 않는다.
    #   이 줄이 있어야 화면의 덧셈이 **실제로** 맞는다.
    adj = score - (BASE + sum(contrib))
    if adj:
        clamped_low = exact < SCORE_MIN
        clamped_high = exact > SCORE_MAX
        if clamped_low:
            note = "궁합에 '나쁨'은 없어서 %d 아래로는 내리지 않아요" % SCORE_MIN
            label = "하한 보정"
        elif clamped_high:
            note = "아무리 잘 맞아도 %d까지만 — 완벽한 궁합은 없으니까요" % SCORE_MAX
            label = "상한 보정"
        else:
            note = "소수점을 정수로 맞추며 생긴 차이예요"
            label = "반올림"
        rows.append({"key": "clamp", "kind": "neutral",
                     "chips": [{"label": label, "delta": adj}], "note": note})

    assert BASE + sum(c["delta"] for r in rows for c in r["chips"]) == score, \
        "근거의 합이 점수와 다르다 — 이건 절대 나오면 안 되는 상태다"

    def person(name, chart, dom):
        ss = [s["name"] for s in chart.get("shensha", [])]
        ch = chart.get("character") or {}
        return {
            "name": name,
            "dominant_element": dom,
            "el_label": "%s 강" % _el(dom),
            "character": {"name_ko": ch.get("name_ko"), "name_en": ch.get("name_en"),
                          "tagline": ch.get("tagline")},
            "shensha": ss,
        }

    return {
        "score": score,
        "summary": dict(SUMMARY[harmony], key=harmony),
        "score_basis": {
            "base": BASE,
            "rows": rows,
            "score": score,
            "disclosure": "%d에서 시작해 %d — %s" % (BASE, score, DISCLOSURE_BODY),
        },
        "good": _good_line(harmony, dom_a, dom_b, weak_a, weak_b, spouse_rel, pairs, a_name, b_name),
        "tension": _tension_line(harmony, dom_a, dom_b, spouse_rel, pairs),
        "reflection": REFLECTION,
        "shensha_meet": _shensha_meet(
            a_name, b_name,
            [s["name"] for s in chart_a.get("shensha", [])],
            [s["name"] for s in chart_b.get("shensha", [])]),
        "persons": [person(a_name, chart_a, dom_a), person(b_name, chart_b, dom_b)],
        # 2순위(지지 관계 표)의 재료 — 어차피 같은 계산이라 지금 담아 둔다.
        "branch_relations": [
            {kk: p[kk] for kk in ("a_pillar", "b_pillar", "branches", "type", "kind")}
            for p in pairs
        ],
        "true_solar_time_applied": bool(chart_a["input"]["true_solar_time_applied"]
                                        and chart_b["input"]["true_solar_time_applied"]),
        "engine_version": chart_a.get("engine_version"),
    }

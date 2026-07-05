# -*- coding: utf-8 -*-
"""
Wolune 만세력 엔진 — 골든셋 회귀 테스트 (기술명세 §9)
=====================================================
§9.1  (입력 → 기대 팔자/오행/신살/캐릭터) 케이스를 박제하고,
§9.3  "회귀 테스트로 박제" — 한 번 검증한 결과를 잠가 회귀를 막는다.
§9.4  합격 기준: 골든셋 100% 일치.

이 파일은 1단계 — **검증 틀(러너) + 이미 검증한 기존 케이스**만 담는다.
경계 케이스(입춘 연주 전환·절입 ±1분·자시 경계·DST 등 §9.2)는 다음 단계에서 추가한다.

실행:
    python engine/golden_set.py          # 전체 케이스 검사 (실패 시 종료코드 1)
    python engine/golden_set.py -v       # 통과 케이스도 필드별로 상세 출력

케이스 출처(source) 표기:
    posteller-verified : 상용 만세력(포스텔러)과 교차검증한 기준값
    engine-baseline    : 현재 엔진 출력을 회귀 기준선으로 박제(외부 검증 전, §9.3)
"""

import sys
from datetime import datetime

# 콘솔 코드페이지(cp949 등)와 무관하게 한자/한글이 깨지지 않도록 UTF-8 고정
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 같은 디렉터리의 엔진 모듈. `python engine/golden_set.py`로 실행 시 sys.path[0]가 engine/.
from saju_pillars import compute_chart


# ============================================================================
# 1) 골든 케이스 — {입력, 기대값}
#    expected 에 적힌 필드만 검사한다(부분 명세 허용). 새 케이스는 여기에 추가.
# ============================================================================
GOLDEN_CASES = [
    {
        "id": "golden-1996-solar-seoul",
        "desc": "1996-03-14 11:11 서울(양력) — 포스텔러 교차검증 기준 케이스",
        "source": "posteller-verified",
        "input": {"date": "1996-03-14", "time": "11:11", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            "eight_char": "丙子 辛卯 庚戌 辛巳",
            "pillars": {"year": "丙子", "month": "辛卯", "day": "庚戌", "hour": "辛巳"},
            "day_master": "庚",
            "five_elements_pct": {"metal": 37.5, "fire": 25.0, "wood": 12.5,
                                  "earth": 12.5, "water": 12.5},
            "five_elements_count": {"metal": 3, "fire": 2, "wood": 1, "earth": 1, "water": 1},
            "shensha": ["괴강", "도화", "화개"],
            "character_ko": "고요한 호수",
            "character_en": "The Still Lake",
            "character_rep": "화개",
            "year_ganzhi": "丙子",
            "true_solar_time_applied": True,
            # 원국 8글자 십성(十星) 회귀 감시 — 일간 庚 기준. 십성 로직 변경 시 잡힌다.
            #   (일주 천간은 기준점이라 "일원". 지지는 본기 기준 십성.)
            "pillars_ten_god": {
                "year":  {"stem": "편관", "branch": "상관"},
                "month": {"stem": "겁재", "branch": "정재"},
                "day":   {"stem": "일원", "branch": "편인"},
                "hour":  {"stem": "겁재", "branch": "편관"},
            },
            # 원국 4지지 12운성(十二運星) 회귀 감시 — 일간 庚 기준(음간 역행설).
            #   子=사, 卯=태, 戌=쇠, 巳=장생. 포태법 로직 변경 시 잡힌다.
            "pillars_twelve_stage": {
                "year": "사", "month": "태", "day": "쇠", "hour": "장생",
            },
            # 공망(空亡) 회귀 감시 — 일주 庚戌 → 甲辰순 → 공망 寅卯 → 월주(卯) 공망.
            "gongmang": {"xun": "甲辰", "void_branches": ["寅", "卯"],
                         "void_pillars": ["month"]},
            # 형충회합 회귀 감시 — 卯戌 육합(월-일), 子卯 상형(년-월). (type, subtype, 정렬지지) 집합.
            "relations_set": [("육합", "", "卯戌"), ("형", "상형", "卯子")],
        },
    },
    {
        "id": "golden-1996-lunar-seoul",
        "desc": "음력 1996-01-25 11:11 서울 — 양력 1996-03-14와 동일 결과(음↔양 변환 검증)",
        "source": "posteller-verified",
        "input": {"date": "1996-01-25", "time": "11:11", "city": "서울",
                  "gender": "female", "calendar": "lunar", "is_leap_month": False},
        "expected": {
            # 음력 입력이 양력으로 정확히 환산되는지 + 이후 팔자가 양력 케이스와 일치하는지
            "converted_solar": "1996-03-14",
            "eight_char": "丙子 辛卯 庚戌 辛巳",
            "pillars": {"year": "丙子", "month": "辛卯", "day": "庚戌", "hour": "辛巳"},
            "five_elements_pct": {"metal": 37.5, "fire": 25.0},
            "shensha": ["괴강", "도화", "화개"],
            "character_ko": "고요한 호수",
            "character_en": "The Still Lake",
        },
    },
    {
        "id": "golden-2000-newyear-seoul",
        "desc": "2000-01-01 12:00 서울(양력) — 엔진 회귀 기준선(성별 무관: 팔자·오행·신살·캐릭터 동일)",
        "source": "engine-baseline",
        "input": {"date": "2000-01-01", "time": "12:00", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            "eight_char": "己卯 丙子 戊午 戊午",
            "pillars": {"year": "己卯", "month": "丙子", "day": "戊午", "hour": "戊午"},
            "day_master": "戊",
            "five_elements_pct": {"fire": 37.5, "earth": 37.5, "wood": 12.5,
                                  "water": 12.5, "metal": 0.0},
            "five_elements_count": {"fire": 3, "earth": 3, "wood": 1, "water": 1, "metal": 0},
            "shensha": ["도화", "양인"],
            "character_ko": "피어나는 꽃",
            "character_en": "The Blooming Flower",
            "character_rep": "도화",
            "year_ganzhi": "己卯",
        },
    },
    {
        "id": "golden-2024-ipchun-before",
        "desc": "2024-02-04 09:00 서울(양력) — 입춘(2024년 2/4 저녁) 이전 → 연주 계묘(癸卯). "
                "하루 뒤 케이스와 짝을 이뤄 입춘 연주 전환을 검증한다.",
        "source": "posteller-verified",
        "input": {"date": "2024-02-04", "time": "09:00", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            # 입춘 전이므로 아직 전년(계묘년) — 하루 차이로 갑진이 되면 입춘 처리 오류.
            # year_ganzhi 는 이제 입춘 기준(ec.getYear())이라 pillars.year 와 항상 일치.
            "pillars": {"year": "癸卯"},
            "year_ganzhi": "癸卯",
        },
    },
    {
        "id": "golden-2024-ipchun-after",
        "desc": "2024-02-05 09:00 서울(양력) — 입춘(2024년 2/4 저녁) 이후 → 연주 갑진(甲辰). "
                "하루 전 케이스와 짝을 이뤄 입춘 연주 전환을 검증한다.",
        "source": "posteller-verified",
        "input": {"date": "2024-02-05", "time": "09:00", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            # 입춘 후이므로 갑진년 — 하루 앞 케이스가 계묘여야 전환이 정확.
            # year_ganzhi 는 이제 입춘 기준이라 입춘~설날 구간에서도 갑진으로 pillars.year 와 일치.
            "pillars": {"year": "甲辰"},
            "year_ganzhi": "甲辰",
        },
    },
    # ------------------------------------------------------------------------
    # 자시(子時) 경계 케이스 (§9.2)
    #   우리 엔진의 규칙(검증됨): ① 진태양시 보정 먼저 → ② 팔자 계산.
    #     · 시주 子시 시작 = 23:00
    #     · 일주 전환 = 00:00(자정)  → **야자시(夜子時)설**
    #       (23:00~24:00 야자시 구간은 子시 간지를 쓰되 일주는 전날 유지, 자정에 넘어감)
    #   자시 경계는 학파마다 정답이 갈리는 영역이라, "일관된 규칙 유지"를 회귀로 박제한다.
    #   두 케이스는 진태양시 보정 후 23:30~24:00 구간을 찌른다(A=23:12, B=23:42).
    {
        "id": "golden-2024-jasi-before-midnight",
        "desc": "2024-06-15 23:45 서울(양력) → 진태양시 6/15 23:12(자정 전) → 일주 庚戌. "
                "포스텔러(庚戌)와 값 일치 → 교차검증.",
        "source": "posteller-verified",
        "input": {"date": "2024-06-15", "time": "23:45", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            # 보정 후 23:12 — 자정 전이므로 일주는 6/15(庚戌). 포스텔러도 庚戌 → 일치.
            "pillars": {"day": "庚戌", "hour": "戊子"},
            "true_solar_time_applied": True,
        },
    },
    {
        "id": "golden-2024-jasi-after-midnight",
        "desc": "2024-06-16 00:15 서울(양력) → 진태양시 6/15 23:42(야자시) → 일주 庚戌(야자시설). "
                "학파 분기점: 포스텔러는 자시중앙(~23:30) 기준으로 넘겨 辛亥. "
                "우리 엔진의 야자시(자정 전환) 규칙을 회귀로 박제한다.",
        "source": "engine-baseline",
        "input": {"date": "2024-06-16", "time": "00:15", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            # 보정 후 6/15 23:42 = 야자시(23:00~24:00). 야자시설이라 일주는 전날(庚戌) 유지.
            # 포스텔러=辛亥(자시중앙 23:30 기준) — 학파 차이. 우리 규칙 일관성 회귀 가드.
            "pillars": {"day": "庚戌", "hour": "戊子"},
            "true_solar_time_applied": True,
        },
    },
    # ------------------------------------------------------------------------
    # 절기(節氣) 경계 케이스 (§9.2) — 청명(2024년 4/4) 전후로 월주가 갈리는지 검증.
    #   자시와 달리 절기는 학파 차이가 거의 없다(천문학적 절입 시각 기준) → 포스텔러와 일치해야 정상.
    #   이틀 차이로 丁卯(묘월) → 戊辰(진월): 지지는 절기(청명=진월 시작), 천간은 오호둔.
    {
        "id": "golden-2024-cheongmyeong-before",
        "desc": "2024-04-03 12:00 서울(양력) — 청명(2024년 4/4) 이전 → 월주 정묘(丁卯), 묘월. "
                "청명 이후 케이스와 짝을 이뤄 절입 월주 전환을 검증한다.",
        "source": "posteller-verified",
        "input": {"date": "2024-04-03", "time": "12:00", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            # 청명 전이라 아직 묘월(丁卯) — 이틀 뒤 케이스가 戊辰이어야 절입 전환이 정확.
            "pillars": {"month": "丁卯"},
        },
    },
    {
        "id": "golden-2024-cheongmyeong-after",
        "desc": "2024-04-05 12:00 서울(양력) — 청명(2024년 4/4) 이후 → 월주 무진(戊辰), 진월. "
                "이틀 전 케이스와 짝을 이뤄 절입 월주 전환을 검증한다.",
        "source": "posteller-verified",
        "input": {"date": "2024-04-05", "time": "12:00", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            # 청명 후라 진월(戊辰) — 이틀 앞 케이스가 丁卯여야 절입 전환이 정확.
            "pillars": {"month": "戊辰"},
        },
    },
    # ------------------------------------------------------------------------
    # 음력 윤달 경계 케이스 (§9.2) — 2023년은 윤2월이 있는 해. 같은 "2월 15일"이라도
    #   평2월(is_leap_month=False)=양력 3/6, 윤2월(True)=양력 4/5 로 갈려 팔자가 달라져야 한다.
    #   is_leap_month 를 무시하면 두 케이스가 같은 결과 → 버그. 윤달은 천문학적으로 정해져 학파 차 없음.
    {
        "id": "golden-2023-leap2-normal",
        "desc": "음력 2023-02-15(평2월) 12:00 서울 → 양력 3/6. 윤2월 케이스와 짝을 이뤄 "
                "is_leap_month 반영을 검증한다.",
        "source": "posteller-verified",
        "input": {"date": "2023-02-15", "time": "12:00", "city": "서울",
                  "gender": "female", "calendar": "lunar", "is_leap_month": False},
        "expected": {
            # 평2월 → 양력 3/6. 윤달 케이스(4/5)와 월주·일주가 달라야 정상.
            "converted_solar": "2023-03-06",
            "eight_char": "癸卯 乙卯 癸亥 戊午",
            "pillars": {"year": "癸卯", "month": "乙卯", "day": "癸亥", "hour": "戊午"},
        },
    },
    {
        "id": "golden-2023-leap2-leap",
        "desc": "음력 2023-윤2월-15(윤달) 12:00 서울 → 양력 4/5. 평2월 케이스와 짝을 이뤄 "
                "is_leap_month 반영을 검증한다.",
        "source": "posteller-verified",
        "input": {"date": "2023-02-15", "time": "12:00", "city": "서울",
                  "gender": "female", "calendar": "lunar", "is_leap_month": True},
        "expected": {
            # 윤2월 → 양력 4/5. 평달(3/6)과 달라야 is_leap_month 가 실제 반영된 것.
            "converted_solar": "2023-04-05",
            "eight_char": "癸卯 丙辰 癸巳 戊午",
            "pillars": {"year": "癸卯", "month": "丙辰", "day": "癸巳", "hour": "戊午"},
        },
    },
    # ------------------------------------------------------------------------
    # 균시차(EoT) 취약 구간 감시 케이스 (§9.2)
    #   균시차 근사식은 늦가을~초겨울(12월 ~1.4분, 9~10월 ~1분)에서 가장 벗어난다.
    #   여기서 진태양시 보정 시각과 시주를 engine-baseline 으로 박제한다.
    #   → 포스텔러 교차검증이 아니라 "회귀 감시"용: 이 값이 바뀌면 균시차 계산이 변경된 것이다.
    #   정밀판(Skyfield/DE440)으로 교체하면 이 케이스들이 변할 것 → 그때 "의도한 변경"인지 확인하는 지점.
    {
        "id": "golden-2023-eot-dec-watch",
        "desc": "2023-12-22 12:00 서울 — 균시차 취약 구간(12월, 근사식 최대오차 ~1.4분) 감시. "
                "이 케이스(진태양시 시각·시주)가 바뀌면 균시차 계산이 변경된 것.",
        "source": "engine-baseline",
        "input": {"date": "2023-12-22", "time": "12:00", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            # 현재 근사식 기준 박제(EoT +0.56분 포함). 정밀판 교체 시 변할 것 → 의도 확인 지점.
            "true_solar_after": "2023-12-22 11:28:28",
            "equation_of_time_min": 0.56,
            "pillars": {"hour": "庚午"},
        },
    },
    {
        "id": "golden-2023-eot-sep-watch",
        "desc": "2023-09-23 12:00 서울 — 균시차 취약 구간(9월, 근사식 오차 ~+1분) 감시. "
                "이 케이스(진태양시 시각·시주)가 바뀌면 균시차 계산이 변경된 것.",
        "source": "engine-baseline",
        "input": {"date": "2023-09-23", "time": "12:00", "city": "서울",
                  "gender": "female", "calendar": "solar"},
        "expected": {
            # 현재 근사식 기준 박제(EoT +8.62분 포함). 정밀판 교체 시 변할 것 → 의도 확인 지점.
            "true_solar_after": "2023-09-23 11:36:31",
            "equation_of_time_min": 8.62,
            "pillars": {"hour": "庚午"},
        },
    },
]


# ============================================================================
# 2) 입력 → compute_chart 호출
# ============================================================================
def _to_datetime(date_str, time_str):
    """'YYYY-MM-DD' + 'HH:MM' → datetime. 시간 미입력이면 00:00."""
    y, mo, d = (int(x) for x in date_str.split("-"))
    hh, mm = (0, 0)
    if time_str:
        hh, mm = (int(x) for x in time_str.split(":"))
    return datetime(y, mo, d, hh, mm, 0)


def compute_for_case(case):
    """케이스의 input(생일·시간·도시·성별·양음력)을 그대로 엔진에 태운다."""
    inp = case["input"]
    dt = _to_datetime(inp["date"], inp.get("time"))
    return compute_chart(
        dt,
        city=inp.get("city"),
        gender=inp.get("gender", "female"),
        calendar=inp.get("calendar", "solar"),
        is_leap_month=inp.get("is_leap_month", False),
    )


# ============================================================================
# 3) 기대 필드 → 실제값 추출기
#    expected 의 각 키가 chart 의 어디서 나오는지 한곳에 모은다.
# ============================================================================
def _eight_char(chart):
    p = chart["pillars"]
    return " ".join(p[k]["ganzhi"] for k in ("year", "month", "day", "hour"))


def _pillars(chart):
    return {k: chart["pillars"][k]["ganzhi"] for k in ("year", "month", "day", "hour")}


def _five_pct(chart):
    return {el: chart["five_elements"][el]["pct"] for el in chart["five_elements"]}


def _five_count(chart):
    return {el: chart["five_elements"][el]["count"] for el in chart["five_elements"]}


def _shensha(chart):
    return sorted(s["name"] for s in chart["shensha"])


def _converted_solar(chart):
    li = chart["input"].get("lunar_input")
    return li["converted_solar"] if li else None


EXTRACTORS = {
    "eight_char":               _eight_char,
    "pillars":                  _pillars,
    "day_master":               lambda c: c["pillars"]["day"]["stem"],
    "five_elements_pct":        _five_pct,
    "five_elements_count":      _five_count,
    "shensha":                  _shensha,
    "character_ko":             lambda c: c["character"]["name_ko"],
    "character_en":             lambda c: c["character"]["name_en"],
    "character_rep":            lambda c: c["character"]["representative_shensha"],
    "year_ganzhi":              lambda c: c["calc_meta"]["year_ganzhi"],
    "true_solar_time_applied":  lambda c: c["input"]["true_solar_time_applied"],
    "converted_solar":          _converted_solar,
    "true_solar_after":         lambda c: c["true_solar_time"]["after_true_solar"],
    "equation_of_time_min":     lambda c: c["true_solar_time"]["equation_of_time_min"],
    "pillars_ten_god":          lambda c: {k: c["pillars"][k]["ten_god"]
                                           for k in ("year", "month", "day", "hour")},
    "pillars_twelve_stage":     lambda c: {k: c["pillars"][k]["twelve_stage"]
                                           for k in ("year", "month", "day", "hour")},
    "gongmang":                 lambda c: c["gongmang"],
    # 형충회합: 회귀 감시는 (type, subtype, 지지집합) 집합으로 비교(기둥 순서·중복 무관).
    "relations_set":            lambda c: sorted(
        (r["type"], r["subtype"] or "", "".join(sorted(r["branches"])))
        for r in c["relations"]),
}

PCT_TOL = 0.05  # 비율은 소수1자리 반올림값 비교(부동소수 오차 흡수)


# ============================================================================
# 4) 비교 — 기대 필드별로 실제값과 대조, 불일치 목록 반환
# ============================================================================
def compare_field(field, expected, actual):
    """(subfield, expected, actual) 형태의 불일치 리스트를 돌려준다. 빈 리스트면 통과."""
    diffs = []
    if field == "shensha":
        exp, act = sorted(expected), sorted(actual)
        if exp != act:
            diffs.append((field, exp, act))
    elif field == "converted_solar":
        # 기대는 날짜만('YYYY-MM-DD'), 실제는 'YYYY-MM-DD HH:MM:SS' → 앞부분만 비교
        act = (actual or "")[:len(expected)]
        if act != expected:
            diffs.append((field, expected, actual))
    elif field in ("pillars", "five_elements_count", "pillars_twelve_stage"):
        for sub, ev in expected.items():            # 부분 명세: 적힌 키만 검사
            av = actual.get(sub)
            if av != ev:
                diffs.append((f"{field}.{sub}", ev, av))
    elif field == "gongmang":                       # 공망: 적힌 키만(부분 명세)
        for sub, ev in expected.items():
            av = actual.get(sub)
            if av != ev:
                diffs.append((f"{field}.{sub}", ev, av))
    elif field == "pillars_ten_god":                # 기둥별 {stem, branch} 십성(중첩 부분 명세)
        for pil, ev in expected.items():            # 적힌 기둥만
            av = actual.get(pil, {})
            for slot, evv in ev.items():            # 적힌 slot(stem/branch)만
                avv = av.get(slot)
                if avv != evv:
                    diffs.append((f"{field}.{pil}.{slot}", evv, avv))
    elif field == "five_elements_pct":
        for sub, ev in expected.items():
            av = actual.get(sub)
            if av is None or abs(av - ev) > PCT_TOL:
                diffs.append((f"{field}.{sub}", ev, av))
    else:                                            # 단순 스칼라
        if actual != expected:
            diffs.append((field, expected, actual))
    return diffs


def check_case(case, verbose=False):
    """한 케이스 계산 → 기대값 대조. (passed, diffs, checked_fields) 반환."""
    try:
        chart = compute_for_case(case)
    except Exception as e:
        return False, [("<compute_chart 예외>", "정상 계산", f"{type(e).__name__}: {e}")], 0

    diffs = []
    expected = case["expected"]
    for field, exp_val in expected.items():
        extractor = EXTRACTORS.get(field)
        if extractor is None:
            diffs.append((field, "<지원되는 기대 필드>", "알 수 없는 필드(러너 미지원)"))
            continue
        actual = extractor(chart)
        field_diffs = compare_field(field, exp_val, actual)
        diffs += field_diffs
        if verbose and not field_diffs:
            print(f"      · {field}: OK ({_short(actual)})")
    return (len(diffs) == 0), diffs, len(expected)


def _short(v):
    """상세 출력용 짧은 표현."""
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


# ============================================================================
# 5) 러너 — 전체 케이스 실행 + 통과/실패 요약
# ============================================================================
def run(cases=GOLDEN_CASES, verbose=False):
    line = "=" * 64
    print(line)
    print("  Wolune 만세력 엔진 — 골든셋 회귀 테스트 (기술명세 §9)")
    print(line)

    passed_n = 0
    for case in cases:
        inp = case["input"]
        cal = "음력" if inp.get("calendar") == "lunar" else "양력"
        sig = f"{inp['date']} {inp.get('time', '--:--')} {inp.get('city', '?')}/" \
              f"{inp.get('gender', 'female')}/{cal}"

        passed, diffs, n = check_case(case, verbose=verbose)
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {case['id']}  ({case['source']})")
        print(f"       {sig}  — 기대필드 {n}개")
        if verbose:
            print(f"       {case['desc']}")
        if passed:
            passed_n += 1
        else:
            for field, exp, act in diffs:
                print(f"   ✗ {field}")
                print(f"       기대: {exp!r}")
                print(f"       실제: {act!r}")
        print("  " + "-" * 60)

    total = len(cases)
    print(f"  요약: {passed_n}/{total} 통과", "✅ 전부 통과" if passed_n == total else "❌ 실패 있음")
    print(line)
    return passed_n == total


if __name__ == "__main__":
    verbose = ("-v" in sys.argv) or ("--verbose" in sys.argv)
    ok = run(verbose=verbose)
    sys.exit(0 if ok else 1)

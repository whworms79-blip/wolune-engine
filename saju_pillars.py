# -*- coding: utf-8 -*-
"""
Wolune 만세력 엔진 — 사주팔자 + 진태양시 보정 (v0.2)
=====================================================
생년월일시(양력) -> 사주팔자 8글자(천간·지지)를 계산하고,
기술명세 §5.2(진태양시)에 따라 시주(時柱)를 보정한다.

기술명세(Wolune_만세력엔진_기술명세.md) 대비 이번 범위:
  [O] 양력/음력 변환        : lunar-python (검증된 라이브러리)에 위임
  [O] 일주(60갑자) 앵커     : lunar-python 내부 epoch 앵커 사용
  [O] 월주(절기 경계)        : lunar-python이 24절기 테이블로 처리(검증은 다음 단계)
  [O] 진태양시 보정          : 경도차(× 4분/도) + 균시차(equation of time)  ← 이번에 추가
  [X] 시간대/DST/표준자오선  : 미적용(입력을 KST로 가정)
  [X] 자시(子時) 경계 룰셋   : 미적용(lunar-python 기본값)
  [X] 십성·지장간·신살·대운  : 범위 밖

진태양시 = 표준시 + 경도차 보정 + 균시차
  · 경도차 보정 = (출생지 경도 − 표준자오선) × 4분/도
  · 균시차      = 천문 근사식(아래). 정밀판은 다음 단계에서 천체력으로 교체.

의존성: pip install lunar-python
"""

import json
import math
from datetime import datetime, timedelta

from lunar_python import Solar, Lunar
from lunar_python.util import LunarUtil

# 세운·월운 해석 문구(웹·앱 공용 단일 출처). 계산이 아니라 '사람 말'만 여기서 온다.
from fortune_copy import year_copy, month_copy

ENGINE_VERSION = "0.4.0"

# --- 룰셋/상수 (명세 §6: 추후 config화. 지금은 한국 기본값) -------------------
KST_STANDARD_MERIDIAN = 135.0          # 한국 표준자오선 (135°E, KST 기준)
SEOUL_LONGITUDE = 126.9780             # 서울 경도 (명세 §7.2 예시값)
SEOUL_LATITUDE = 37.5665               # 서울 위도 (기본 폴백)
MIN_PER_DEGREE = 4.0                   # 경도 1° = 시간 4분


def longitude_correction_min(longitude, meridian=KST_STANDARD_MERIDIAN):
    """경도차 보정(분). 표준자오선보다 서쪽(경도 작음)이면 음수 → 시계를 늦춘다."""
    return (longitude - meridian) * MIN_PER_DEGREE


def equation_of_time_min(dt):
    """
    균시차(분) 근사식. apparent − mean (양수면 진태양이 앞섬).
    표준 근사: B = 2π(N-81)/364, EoT = 9.87 sin2B − 7.53 cosB − 1.5 sinB

    실측 정확도(각 달 15일 정오, 천문 표준 균시차 대비):
        · 최대 오차 ~1.4분(12월, −1:22), 다음으로 9~10월 ~+1분
        · RMS ~38초, 5~6월은 <5초로 매우 정확 / 늦가을~초겨울에서 가장 벗어남
        · 시진(자시 23:00 등) 경계에서 ±1.4분 안쪽에 걸친 출생은 시주 판정이 뒤집힐 수 있음
    정밀판은 천체력(Skyfield/DE440)으로 교체 예정 → 오차 <1초(명세 §4).
    """
    n = dt.timetuple().tm_yday
    b = 2.0 * math.pi * (n - 81) / 364.0
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def true_solar_time(dt, longitude=SEOUL_LONGITUDE, meridian=KST_STANDARD_MERIDIAN):
    """표준시 datetime -> 진태양시 datetime + 보정 내역."""
    lon_corr = longitude_correction_min(longitude, meridian)
    eot = equation_of_time_min(dt)
    total = lon_corr + eot
    corrected = dt + timedelta(minutes=total)
    return corrected, {"longitude": lon_corr, "eot": eot, "total": total}


def compute_pillars(dt):
    """양력 datetime -> 사주 4기둥(천간·지지). lunar-python에 계산을 위임한다."""
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()  # 八字 = 사주팔자

    pillars = {
        "year":  {"name": "년주(年柱)", "gan": ec.getYearGan(),  "zhi": ec.getYearZhi(),  "ganzhi": ec.getYear()},
        "month": {"name": "월주(月柱)", "gan": ec.getMonthGan(), "zhi": ec.getMonthZhi(), "ganzhi": ec.getMonth()},
        "day":   {"name": "일주(日柱)", "gan": ec.getDayGan(),   "zhi": ec.getDayZhi(),   "ganzhi": ec.getDay()},
        "hour":  {"name": "시주(時柱)", "gan": ec.getTimeGan(),  "zhi": ec.getTimeZhi(),  "ganzhi": ec.getTime()},
    }
    return solar, lunar, pillars


# --- 오행(五行) 매핑: 명세 §8 도출 규칙 ---------------------------------------
# 천간(天干) 오행
STEM_ELEMENT = {
    "甲": "목", "乙": "목", "丙": "화", "丁": "화", "戊": "토",
    "己": "토", "庚": "금", "辛": "금", "壬": "수", "癸": "수",
}
# 지지(地支) 오행 (지장간 미반영, 지지 본기 오행만)
BRANCH_ELEMENT = {
    "寅": "목", "卯": "목", "巳": "화", "午": "화",
    "辰": "토", "戌": "토", "丑": "토", "未": "토",
    "申": "금", "酉": "금", "子": "수", "亥": "수",
}
ELEMENT_ORDER = ["목", "화", "토", "금", "수"]


def compute_five_elements(pillars):
    """
    8글자(천간 4 + 지지 4)의 오행 분포를 센다. 지장간 미포함.
    return: { 오행: {"count": n, "pct": float}, ... } 와 글자별 내역
    """
    counts = {e: 0 for e in ELEMENT_ORDER}
    detail = []  # (글자, 오행) — 시주 있으면 8건, 시간 미상이면 6건
    for key in ("year", "month", "day", "hour"):
        if key not in pillars:   # 시간 미상 → 시주(時柱) 제외
            continue
        gan, zhi = pillars[key]["gan"], pillars[key]["zhi"]
        counts[STEM_ELEMENT[gan]] += 1
        counts[BRANCH_ELEMENT[zhi]] += 1
        detail.append((gan, STEM_ELEMENT[gan]))
        detail.append((zhi, BRANCH_ELEMENT[zhi]))

    total = sum(counts.values())  # 8(시주 있음) 또는 6(시간 미상)
    dist = {e: {"count": counts[e], "pct": counts[e] / total * 100} for e in ELEMENT_ORDER}
    return dist, detail


# --- 신살(神殺) 판별: 명세 §8 (lunar-python 미지원 → 명리 표준 규칙 직접 구현) ----
# 라이브러리(lunar-python/sxtwl)는 사주용 신살(천을귀인·도화·역마 등)을 제공하지 않음.
# 공망/황력 귀인 방위만 있어 캐릭터 매핑용 핵심 신살은 아래 규칙으로 판별한다.
PILLAR_LABEL = {"year": "년주", "month": "월주", "day": "일주", "hour": "시주"}

# 삼합국(三合局): 지지 -> 국(局). 역마·화개·도화·월덕의 기준.
BRANCH_GROUP = {
    "申": "수", "子": "수", "辰": "수",
    "寅": "화", "午": "화", "戌": "화",
    "巳": "금", "酉": "금", "丑": "금",
    "亥": "목", "卯": "목", "未": "목",
}
# 국별 신살 대상 글자
GROUP_SHEN = {
    "수": {"역마": "寅", "화개": "辰", "도화": "酉", "월덕": "壬"},  # 申子辰
    "화": {"역마": "申", "화개": "戌", "도화": "卯", "월덕": "丙"},  # 寅午戌
    "금": {"역마": "亥", "화개": "丑", "도화": "午", "월덕": "庚"},  # 巳酉丑
    "목": {"역마": "巳", "화개": "未", "도화": "子", "월덕": "甲"},  # 亥卯未
}
# 천을귀인(天乙貴人): 일간 기준 → 지지. (甲戊庚牛羊 통용본)
TIANYI = {
    "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
    "乙": ["子", "申"], "己": ["子", "申"],
    "丙": ["亥", "酉"], "丁": ["亥", "酉"],
    "壬": ["卯", "巳"], "癸": ["卯", "巳"],
    "辛": ["午", "寅"],
}
# 문창귀인(文昌貴人): 일간 기준 → 지지.
WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
            "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
# 양인(羊刃): 일간(양간) 기준 → 지지(제왕지).
YANGIN = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}
# 괴강(魁罡): 일주 간지. / 백호(白虎): 간지(어느 기둥이든).
KUIGANG = {"庚辰", "庚戌", "壬辰", "戊戌"}
BAIHU = {"甲辰", "乙未", "丙戌", "丁丑", "戊辰", "壬戌", "癸丑"}

# 캐릭터 매핑용 핵심 신살(출력 순서)
SHENSHA_ORDER = ["천을귀인", "문창귀인", "역마", "화개", "도화", "백호", "양인", "괴강", "월덕귀인"]


def _zhi_in(pillars, targets):
    """지지가 targets(집합/리스트)에 드는 기둥 라벨 목록."""
    ts = targets if isinstance(targets, (set, list, tuple)) else [targets]
    return [PILLAR_LABEL[k] for k in ("year", "month", "day", "hour")
            if k in pillars and pillars[k]["zhi"] in ts]


def _gan_in(pillars, target):
    return [PILLAR_LABEL[k] for k in ("year", "month", "day", "hour")
            if k in pillars and pillars[k]["gan"] == target]


def compute_shensha(pillars):
    """핵심 신살 판별. return: { 신살명: {"hit": bool, "pillars": [...], "basis": str} }."""
    yg, yz = pillars["year"]["gan"], pillars["year"]["zhi"]
    mz = pillars["month"]["zhi"]
    dg, dz = pillars["day"]["gan"], pillars["day"]["zhi"]
    day_ganzhi = pillars["day"]["ganzhi"]

    res = {}

    # 일간 기준(지지에서 찾는) 신살: 천을·문창·양인
    res["천을귀인"] = {"pillars": _zhi_in(pillars, TIANYI.get(dg, [])), "basis": f"일간 {dg} → 지지"}
    res["문창귀인"] = {"pillars": _zhi_in(pillars, WENCHANG.get(dg)), "basis": f"일간 {dg} → 지지"}
    res["양인"]     = {"pillars": _zhi_in(pillars, YANGIN.get(dg)), "basis": f"일간 {dg}(양간) → 제왕지"}

    # 삼합 기준(연지·일지 둘 다 참조) 신살: 역마·화개·도화
    for shen in ("역마", "화개", "도화"):
        hits, refs = [], []
        for ref_label, zhi in (("연지 " + yz, yz), ("일지 " + dz, dz)):
            target = GROUP_SHEN[BRANCH_GROUP[zhi]][shen]
            refs.append(f"{ref_label}→{target}")
            hits += _zhi_in(pillars, target)
        res[shen] = {"pillars": sorted(set(hits), key=lambda x: list(PILLAR_LABEL.values()).index(x)),
                     "basis": " / ".join(refs)}

    # 월덕귀인: 월지 삼합국 → 천간
    yd_target = GROUP_SHEN[BRANCH_GROUP[mz]]["월덕"]
    res["월덕귀인"] = {"pillars": _gan_in(pillars, yd_target), "basis": f"월지 {mz}국 → 천간 {yd_target}"}

    # 괴강(일주 간지) / 백호(어느 기둥이든)
    res["괴강"] = {"pillars": [PILLAR_LABEL["day"]] if day_ganzhi in KUIGANG else [],
                   "basis": f"일주 {day_ganzhi}"}
    baihu_hits = [PILLAR_LABEL[k] for k in ("year", "month", "day", "hour")
                  if k in pillars and pillars[k]["ganzhi"] in BAIHU]
    res["백호"] = {"pillars": baihu_hits, "basis": "간지(백호대살 7간지)"}

    for name in res:
        res[name]["hit"] = len(res[name]["pillars"]) > 0
    return res


# --- 캐릭터 매핑: Wolune_신살캐릭터_콘텐츠.md §2~§3 -----------------------------
# 표상 신살(또는 콤보) -> 캐릭터. 한 줄 정의는 §3 각 캐릭터 인용구.
CHARACTERS = {
    "역마+백호": {"ko": "거침없는 개척자", "en": "The Trailblazer",
                "tagline": "머무름보다 나아감으로 자신을 증명하는 사람.", "tone": "화·금"},
    "천을귀인": {"ko": "따뜻한 등불", "en": "The Warm Lantern",
              "tagline": "곁에 있는 사람을 환하게 밝히고, 또 밝힘을 받는 사람.", "tone": "화"},
    "화개":   {"ko": "고요한 호수", "en": "The Still Lake",
              "tagline": "깊이 사유하고, 천천히, 그러나 단단하게 흐르는 사람.", "tone": "수"},
    "문창귀인": {"ko": "깊은 뿌리", "en": "The Deep Root",
              "tagline": "흔들리지 않고 깊이 아는, 신뢰의 중심이 되는 사람.", "tone": "토"},
    "월덕귀인": {"ko": "너른 나무", "en": "The Sheltering Tree",
              "tagline": "곁에 있으면 자라게 하는, 품이 넓은 사람.", "tone": "목"},
    "도화":   {"ko": "피어나는 꽃", "en": "The Blooming Flower",
              "tagline": "존재만으로 사람을 끌어당기는, 빛을 가진 사람.", "tone": "목·화"},
    "양인":   {"ko": "빛나는 검", "en": "The Bright Blade",
              "tagline": "옳다고 믿는 것을 끝까지 지키는 사람.", "tone": "금"},
    "괴강":   {"ko": "흔들리지 않는 산", "en": "The Unmoving Mountain",
              "tagline": "어떤 풍파에도 무너지지 않는, 단단한 중심을 가진 사람.", "tone": "토·금"},
}

# 표상 신살 우선순위(§2 line 29). 콤보 먼저, 그다음 단일 신살.
CHARACTER_PRIORITY = ["천을귀인", "화개", "문창귀인", "월덕귀인", "도화", "양인", "괴강"]

# 신살이 하나도 없을 때 일간 오행 기반 fallback.
# (문서 §2-5는 "일간 오행 기반"만 명시하고 표는 안 줌 → §3 '기본 톤' 컬럼과 일치하도록 유도)
FALLBACK_BY_ELEMENT = {"수": "화개", "화": "천을귀인", "토": "문창귀인", "금": "양인", "목": "월덕귀인"}
ELEMENT_HANJA = {"목": "木", "화": "火", "토": "土", "금": "金", "수": "水"}


def compute_character(shensha, day_gan):
    """
    신살 판별 결과 + 일간 -> 캐릭터 1개를 결정론적으로 선택한다.
    같은 입력이면 항상 같은 캐릭터(순수 함수, 우선순위 고정).
    """
    present = {name for name, d in shensha.items() if d["hit"]}
    day_element = STEM_ELEMENT[day_gan]

    if "역마" in present and "백호" in present:                  # 1) 콤보 최우선
        key, basis = "역마+백호", "콤보(역마+백호)"
    else:
        key = next((p for p in CHARACTER_PRIORITY if p in present), None)  # 2) 단일 신살 우선순위
        if key is not None:
            where = ", ".join(shensha[key]["pillars"])
            basis = f"표상 신살 '{key}' ({where})"
        else:                                                    # 3) fallback
            key = FALLBACK_BY_ELEMENT[day_element]
            basis = f"신살 없음 → 일간 오행({day_element}) fallback"

    char = CHARACTERS[key]
    return {
        "rep": key,                      # 표상 신살(또는 콤보/ fallback 키)
        "char": char,
        "basis": basis,
        "day_element": day_element,      # 일간 오행(보조 톤)
        "present": present,
    }


# --- JSON 구조화: 기술명세 §7.3 (/v1/chart 응답) ------------------------------
# 화면/대화 레이어가 가져다 쓰는 결정론적 사실(facts) 출력.
ELEMENT_EN = {"목": "wood", "화": "fire", "토": "earth", "금": "metal", "수": "water"}
SHENSHA_HANJA = {
    "천을귀인": "天乙貴人", "문창귀인": "文昌貴人", "역마": "驛馬", "화개": "華蓋",
    "도화": "桃花", "백호": "白虎", "양인": "羊刃", "괴강": "魁罡", "월덕귀인": "月德貴人",
}
PILLAR_KEYS = ("year", "month", "day", "hour")


# --- 대운(大運): 기술명세 §8 (lunar-python DaYun 활용) -------------------------
# 방향: 양남음녀 순행 / 음남양녀 역행  (연간 음양 + 성별로 결정 → gender 필요).
# 시작나이: 출생 → 직전(역행)/다음(순행) 절입까지 거리(3일=1년 환산)를 lunar-python Yun이 계산.
# 월주를 기준으로 60갑자를 순/역행 전개 → DaYun 배열. (검증된 라이브러리에 위임)
# gender 코드: 남=1, 여=0 (lunar-python getYun 관례).
YANG_STEM_SET = {"甲", "丙", "戊", "庚", "壬"}


def _gender_to_int(gender):
    """gender 입력 → lunar-python getYun 코드(남=1, 여=0). 미상/기타는 여성(0)."""
    s = str(gender).strip().lower()
    if s in ("1", "m", "male", "남", "남자", "남성"):
        return 1
    return 0  # female / 여 / 기본


def compute_luck_pillars(dt, gender):
    """대운 배열 계산(명세 §8). 방향·시작나이·간지 전개는 검증된 DaYun에 위임."""
    g = _gender_to_int(gender)
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    ec = solar.getLunar().getEightChar()
    yun = ec.getYun(g)
    forward = yun.isForward()

    out = []
    for d in yun.getDaYun():
        gz = d.getGanZhi()
        if not gz:                          # idx0: 출생~첫 대운 전(간지 없음) → 제외
            continue
        gan, zhi = gz[0], gz[1]
        out.append({
            "index": d.getIndex(),
            "start_age": d.getStartAge() - 1,   # 만 나이(출생=0세 기준)
            "start_year": d.getStartYear(),     # 해당 대운이 시작되는 실제 연도
            "ganzhi": gz,
            "stem": gan,
            "branch": zhi,
            "stem_element": ELEMENT_EN[STEM_ELEMENT[gan]],
            "branch_element": ELEMENT_EN[BRANCH_ELEMENT[zhi]],
        })

    year_gan = ec.getYearGan()
    yy = "양" if year_gan in YANG_STEM_SET else "음"
    gender_ko = "남성" if g == 1 else "여성"
    return {
        "direction": "forward" if forward else "reverse",
        "direction_ko": "순행" if forward else "역행",
        "gender": gender_ko,
        "start_age": out[0]["start_age"] if out else None,   # 첫 대운 시작 나이(만)
        "rule": "연간 %s(%s) + %s → %s (양남음녀 순행 / 음남양녀 역행)"
                % (year_gan, yy, gender_ko, "순행" if forward else "역행"),
        "count": len(out),
        "pillars": out,
    }


def _fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _lunar_to_solar(dt, is_leap_month=False):
    """
    음력 datetime → 양력 datetime 변환(검증된 lunar-python에 위임).
    윤달은 lunar-python 관례대로 month를 음수로 넘긴다(예: 윤2월 → -2).
    시각(시·분·초)은 그대로 보존하고 날짜만 환산한다.
    return: (양력 datetime, 음력 표기 문자열)
    """
    month = -abs(dt.month) if is_leap_month else dt.month
    lunar = Lunar.fromYmdHms(dt.year, month, dt.day, dt.hour, dt.minute, dt.second)
    s = lunar.getSolar()
    solar_dt = datetime(s.getYear(), s.getMonth(), s.getDay(), dt.hour, dt.minute, dt.second)
    return solar_dt, lunar.toString()


# --- 출생지(도시) → 위경도: 진태양시 경도 보정용 (명세 §5.2/§7.2) -------------
# 한국 주요 도시(광역시 + 도청소재지 + 주요 시) 위경도. 진태양시는 경도(lng)만 사용하나
# 위도(lat)도 함께 보관(향후 일출/절기 정밀화 대비). 좌표는 시청/도심 기준 근삿값.
KR_CITIES = {
    # 특별시·광역시·특별자치시
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "대구": (35.8714, 128.6014),
    "인천": (37.4563, 126.7052), "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "세종": (36.4800, 127.2890),
    # 경기
    "수원": (37.2636, 127.0286), "성남": (37.4200, 127.1378), "고양": (37.6584, 126.8320),
    "용인": (37.2411, 127.1776), "부천": (37.5034, 126.7660), "안산": (37.3219, 126.8309),
    "안양": (37.3943, 126.9568), "평택": (36.9921, 127.1129), "의정부": (37.7381, 127.0337),
    # 강원
    "춘천": (37.8813, 127.7300), "원주": (37.3422, 127.9202), "강릉": (37.7519, 128.8761),
    # 충청
    "청주": (36.6424, 127.4890), "충주": (36.9910, 127.9259), "천안": (36.8151, 127.1139),
    # 전라
    "전주": (35.8242, 127.1480), "군산": (35.9676, 126.7369), "익산": (35.9483, 126.9576),
    "목포": (34.8118, 126.3922), "여수": (34.7604, 127.6622), "순천": (34.9506, 127.4872),
    # 경상
    "포항": (36.0190, 129.3435), "경주": (35.8562, 129.2247), "구미": (36.1196, 128.3441),
    "안동": (36.5684, 128.7294), "창원": (35.2280, 128.6811), "진주": (35.1800, 128.1076),
    "김해": (35.2285, 128.8894),
    # 제주
    "제주": (33.4996, 126.5312), "서귀포": (33.2541, 126.5601),
}
# 영문/별칭 → 표준 한글 키
CITY_ALIASES = {
    "seoul": "서울", "busan": "부산", "pusan": "부산", "daegu": "대구", "incheon": "인천",
    "gwangju": "광주", "daejeon": "대전", "ulsan": "울산", "sejong": "세종", "suwon": "수원",
    "chuncheon": "춘천", "gangneung": "강릉", "wonju": "원주", "cheongju": "청주",
    "jeonju": "전주", "pohang": "포항", "jeju": "제주", "changwon": "창원", "jinju": "진주",
}
# 행정구역 접미사(매칭 시 제거)
_CITY_SUFFIXES = ("특별자치시", "특별자치도", "특별시", "광역시", "자치시", "시", "군")


def lookup_city(name):
    """
    도시 이름 → (표준명, lat, lng). 표에 없으면 None.
    '서울', '서울특별시', '서울시', 'Seoul', ' busan ' 등 관대하게 매칭.
    """
    if not name:
        return None
    key = str(name).strip().replace(" ", "")
    # 1) 정확 매치(한글)
    if key in KR_CITIES:
        return (key,) + KR_CITIES[key]
    # 2) 행정구역 접미사 제거 후 매치 (서울특별시→서울, 수원시→수원)
    for suf in _CITY_SUFFIXES:
        if key.endswith(suf):
            base = key[: -len(suf)]
            if base in KR_CITIES:
                return (base,) + KR_CITIES[base]
    # 3) 영문/별칭(대소문자 무시)
    low = key.lower()
    if low in CITY_ALIASES:
        ko = CITY_ALIASES[low]
        return (ko,) + KR_CITIES[ko]
    return None


# --- 세운(歲運)·월운(月運): 기술명세 §8 (lunar-python 간지/십성 활용) -----------
# 세운: 그 해(입춘 기준)의 연간지. 월운: 그 달(절기 기준)의 월간지(오호둔).
# 십성(十神): 일간 대비 대상 천간의 관계. lunar-python SHI_SHEN 테이블(한자) → 한글 변환.
SHISHEN_KO = {
    "比肩": "비견", "劫财": "겁재", "食神": "식신", "伤官": "상관", "偏财": "편재",
    "正财": "정재", "七杀": "편관", "正官": "정관", "偏印": "편인", "正印": "정인",
}
# 지지 본기(本氣, 정기) 천간 — 지지의 십성 산출용
BRANCH_MAIN_QI = {
    "子": "癸", "丑": "己", "寅": "甲", "卯": "乙", "辰": "戊", "巳": "丙",
    "午": "丁", "未": "己", "申": "庚", "酉": "辛", "戌": "戊", "亥": "壬",
}

# 지장간(支藏干) — 지지 속에 숨은 천간. (position, 천간) 순서 = 여기(餘氣)→중기(中氣)→정기(正氣).
#   · 왕지(子卯酉)는 여기·정기 2개, 나머지는 3개. 정기(마지막)는 곧 본기 = BRANCH_MAIN_QI.
#   · 생지(寅申巳亥)의 여기는 모두 戊, 고지(辰戌丑未)는 여기·중기·정기 3원소 방식(전통 지장간 표).
HIDDEN_STEMS = {
    "子": [("여기", "壬"), ("정기", "癸")],
    "丑": [("여기", "癸"), ("중기", "辛"), ("정기", "己")],
    "寅": [("여기", "戊"), ("중기", "丙"), ("정기", "甲")],
    "卯": [("여기", "甲"), ("정기", "乙")],
    "辰": [("여기", "乙"), ("중기", "癸"), ("정기", "戊")],
    "巳": [("여기", "戊"), ("중기", "庚"), ("정기", "丙")],
    "午": [("여기", "丙"), ("중기", "己"), ("정기", "丁")],
    "未": [("여기", "丁"), ("중기", "乙"), ("정기", "己")],
    "申": [("여기", "戊"), ("중기", "壬"), ("정기", "庚")],
    "酉": [("여기", "庚"), ("정기", "辛")],
    "戌": [("여기", "辛"), ("중기", "丁"), ("정기", "戊")],
    "亥": [("여기", "戊"), ("중기", "甲"), ("정기", "壬")],
}
ROLE_EN = {"여기": "residual", "중기": "middle", "정기": "primary"}
# 정합성 보증: 지장간 정기(마지막 원소) == 본기(BRANCH_MAIN_QI). 어긋나면 import 시 즉시 실패.
assert all(HIDDEN_STEMS[z][-1][1] == BRANCH_MAIN_QI[z] for z in BRANCH_MAIN_QI), \
    "지장간 정기와 BRANCH_MAIN_QI 불일치"

# --- 12운성(十二運星): 일간이 각 지지에서 갖는 포태(胞胎) 단계 ---------------------
# 학파 선택: **음간 역행설(전통 포태법)**. 양간은 장생궁부터 순행, 음간은 장생궁부터 역행.
#   (음간 순행설 = 양간과 같은 순행으로 도는 학파도 있으나, 여기선 전통 역행설을 채택.)
# 각 천간의 장생(長生) 지지 → 거기서 12단계를 순/역으로 배치.
#   예: 甲 장생 亥, 乙 장생 午, 庚 장생 巳. (화토동법: 戊=丙, 己=丁)
_STAGES_12 = ["장생", "목욕", "관대", "건록", "제왕", "쇠",
              "병", "사", "묘", "절", "태", "양"]
_BRANCHES_ORDER = list("子丑寅卯辰巳午未申酉戌亥")
_CHANGSHENG = {  # 각 천간의 장생 지지
    "甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申",   # 양간(순행)
    "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯",   # 음간(역행)
}
_YANG_STEMS = set("甲丙戊庚壬")


def _build_twelve_stage():
    """일간×지지 → 12운성 표. 양간 순행 / 음간 역행(전통 포태법)."""
    table = {}
    for stem, sheng in _CHANGSHENG.items():
        start = _BRANCHES_ORDER.index(sheng)
        step = 1 if stem in _YANG_STEMS else -1        # 양간 순행, 음간 역행
        table[stem] = {_BRANCHES_ORDER[(start + step * i) % 12]: _STAGES_12[i]
                       for i in range(12)}
    return table


TWELVE_STAGE = _build_twelve_stage()
# 정합성 보증: 표준 포태법 기준점(甲 장생 亥, 乙 장생 午, 庚 장생 巳). 어긋나면 import 즉시 실패.
assert (TWELVE_STAGE["甲"]["亥"] == "장생" and TWELVE_STAGE["乙"]["午"] == "장생"
        and TWELVE_STAGE["庚"]["巳"] == "장생"), "12운성 장생 기준점 불일치"


# --- 공망(空亡): 일주 60갑자 순중(旬中)에서 빠지는 2지지 ----------------------------
# 60갑자를 甲으로 시작하는 6순(旬)×10으로 나누면, 각 순은 12지지 중 10개만 쓰고 2개가 빠진다.
#   그 빠진 2지지가 공망. 일주 간지로 그 순을 판별해 공망 2지지를 구한다.
#   예: 甲子순(甲子~癸酉) 공망=戌亥 / 甲辰순(甲辰~癸丑) 공망=寅卯.
_STEMS_ORDER = list("甲乙丙丁戊己庚辛壬癸")


def compute_gongmang(day_gan, day_zhi):
    """일주(간+지) → (순두 간지 '甲X', 공망 2지지 리스트). 순 안의 甲 지지에서 +10,+11 위치가 공망."""
    gi = _STEMS_ORDER.index(day_gan)
    zi = _BRANCHES_ORDER.index(day_zhi)
    jia = (zi - gi) % 12                         # 이 순(旬)의 甲이 놓인 지지 index
    xun_head = "甲" + _BRANCHES_ORDER[jia]        # 순두(旬首), 예: 甲辰
    voids = [_BRANCHES_ORDER[(jia + 10) % 12],    # 순이 쓰지 않는 2지지 = 공망
             _BRANCHES_ORDER[(jia + 11) % 12]]
    return xun_head, voids


# 정합성 보증: 대표 순의 공망(甲子순→戌亥, 甲辰순→寅卯). 어긋나면 import 즉시 실패.
assert compute_gongmang("甲", "子")[1] == ["戌", "亥"], "공망 산출 오류(甲子순)"
assert compute_gongmang("庚", "戌")[1] == ["寅", "卯"], "공망 산출 오류(庚戌/甲辰순)"


# --- 형충회합(刑沖會合): 네 지지 사이의 관계 ------------------------------------
# 참고: 한 지지쌍이 여러 범주에 동시 해당할 수 있음(예: 巳申은 육합이자 파, 寅亥도 육합이자 파).
#   → 카테고리별로 독립 판별해 모두 보고한다(상호배타 아님).
_ALL_BRANCHES = set("子丑寅卯辰巳午未申酉戌亥")
_JI_LABEL = {"year": "년지", "month": "월지", "day": "일지", "hour": "시지"}

# 쌍(2지지) 관계 — 순서 무관이라 frozenset으로 저장(대칭 보장).
_LIUHE_RAW   = ["子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未"]           # 육합
_LIUCHONG_RAW = ["子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"]          # 육충
_LIUHAI_RAW  = ["子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌"]           # 육해
_PO_RAW      = ["子酉", "午卯", "申巳", "寅亥", "辰丑", "戌未"]           # 파
_XIANGXING_RAW = "子卯"                                                  # 상형(형)

_LIUHE    = {frozenset(p) for p in _LIUHE_RAW}
_LIUCHONG = {frozenset(p) for p in _LIUCHONG_RAW}
_LIUHAI   = {frozenset(p) for p in _LIUHAI_RAW}
_PO       = {frozenset(p) for p in _PO_RAW}
_XIANGXING = frozenset(_XIANGXING_RAW)
_ZIXING   = set("辰午酉亥")            # 자형(형): 같은 지지가 둘 이상

# 3지지 조합 — 완전(3) / 반합(2)
_SANHE  = {"수국": "申子辰", "목국": "亥卯未", "화국": "寅午戌", "금국": "巳酉丑"}   # 삼합
_BANGHE = {"목": "寅卯辰", "화": "巳午未", "금": "申酉戌", "수": "亥子丑"}          # 방합
_SANXING = ["寅巳申", "丑戌未"]          # 삼형(형): 세 지지 모두 있을 때

# 출력 정렬용 카테고리 우선순위
_REL_ORDER = {"육합": 0, "삼합": 1, "방합": 2, "육충": 3, "육해": 4, "형": 5, "파": 6}

# ── 규칙 표 자체 검증(import-time) ──────────────────────────────────────────
def _pair_ok(raw_list):
    return all(len(set(p)) == 2 and set(p) <= _ALL_BRANCHES for p in raw_list)
# 각 쌍 관계는 6쌍, 두 지지가 서로 다르고 유효 지지
assert all(len(g) == 6 for g in (_LIUHE, _LIUCHONG, _LIUHAI, _PO)), "쌍 관계 개수 오류"
assert all(_pair_ok(r) for r in (_LIUHE_RAW, _LIUCHONG_RAW, _LIUHAI_RAW, _PO_RAW)), "쌍 관계 지지 오류"
# 대칭성: 순서를 뒤집어도 같은 frozenset(표현 자체가 대칭)
assert all(frozenset(p) == frozenset(p[::-1])
           for r in (_LIUHE_RAW, _LIUCHONG_RAW, _LIUHAI_RAW, _PO_RAW) for p in r), "쌍 관계 비대칭"
# 삼합·방합: 각 4국, 세 지지 서로 다름. 방합 4국의 합집합은 12지지 전체.
assert all(len(set(v)) == 3 and set(v) <= _ALL_BRANCHES for v in _SANHE.values()), "삼합 표 오류"
assert all(len(set(v)) == 3 and set(v) <= _ALL_BRANCHES for v in _BANGHE.values()), "방합 표 오류"
assert set("".join(_BANGHE.values())) == _ALL_BRANCHES, "방합 4국이 12지지를 덮지 않음"
# 삼형: 세 지지 서로 다름
assert all(len(set(t)) == 3 and set(t) <= _ALL_BRANCHES for t in _SANXING), "삼형 표 오류"


def _rel(type_, subtype, pillar_keys, branches):
    """관계 1건 → dict. pillars는 한글 라벨(년지…), pillar_keys는 원본 키."""
    return {
        "type": type_,
        "subtype": subtype,                       # None 또는 '완전'/'반합'/'상형'/'자형'/'수국 완전' 등
        "pillars": [_JI_LABEL[k] for k in pillar_keys],
        "pillar_keys": list(pillar_keys),
        "branches": list(branches),
    }


def compute_relations(pillars):
    """네 지지(년·월·일·시) 사이의 형충회합. 실제 존재하는 쌍/조합만 반환.
    시간 미상이면 시지(時支)가 없어 년·월·일 3지지만 본다."""
    keys = tuple(k for k in ("year", "month", "day", "hour") if k in pillars)
    zhi = {k: pillars[k]["zhi"] for k in keys}
    present = {}                                    # 지지 → 그 지지를 가진 기둥 키들
    for k in keys:
        present.setdefault(zhi[k], []).append(k)

    rels = []
    pair_cats = [("육합", _LIUHE), ("육충", _LIUCHONG), ("육해", _LIUHAI), ("파", _PO)]

    # 1) 쌍 관계: 서로 다른 두 기둥의 모든 조합
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            ps = frozenset((zhi[a], zhi[b]))
            if len(ps) == 2:
                for name, table in pair_cats:      # 여러 범주 동시 가능 → 모두 기록
                    if ps in table:
                        rels.append(_rel(name, None, [a, b], [zhi[a], zhi[b]]))
                if ps == _XIANGXING:               # 상형(형)
                    rels.append(_rel("형", "상형", [a, b], [zhi[a], zhi[b]]))
            elif zhi[a] in _ZIXING:                # 같은 지지 + 辰午酉亥 → 자형(형)
                rels.append(_rel("형", "자형", [a, b], [zhi[a], zhi[b]]))

    # 2) 삼합·방합: 완전(3지지)·반합(2지지)
    for grp, table in (("삼합", _SANHE), ("방합", _BANGHE)):
        for guk, triple in table.items():
            uniq = [x for x in triple if x in present]      # 존재하는 구성 지지(삼합 순서 유지)
            if len(uniq) == 3:
                sub = "완전"
            elif len(uniq) == 2:
                sub = "반합"
            else:
                continue
            pil = [k for x in uniq for k in present[x]]      # 관련 기둥
            rels.append(_rel(grp, f"{guk} {sub}", pil, uniq))

    # 3) 삼형(형): 세 지지가 모두 존재
    for triple in _SANXING:
        if all(x in present for x in triple):
            pil = [k for x in triple for k in present[x]]
            rels.append(_rel("형", "삼형", pil, list(triple)))

    rels.sort(key=lambda r: _REL_ORDER[r["type"]])
    return rels


# 동작 자체 검증: 1996 지지(子卯戌巳) → 卯戌 육합(월-일) + 子卯 상형(년-월)이 잡혀야 함.
_rel_test = compute_relations({"year": {"zhi": "子"}, "month": {"zhi": "卯"},
                               "day": {"zhi": "戌"}, "hour": {"zhi": "巳"}})
_rel_keys = {(r["type"], r["subtype"], frozenset(r["branches"])) for r in _rel_test}
assert ("육합", None, frozenset("卯戌")) in _rel_keys, "형충회합 검증 실패(卯戌 육합)"
assert ("형", "상형", frozenset("子卯")) in _rel_keys, "형충회합 검증 실패(子卯 상형)"


def _ten_god(day_gan, other_gan):
    """일간(day_gan) 대비 other_gan의 십성(한글). 미상이면 None."""
    cn = LunarUtil.SHI_SHEN.get(day_gan + other_gan)
    return SHISHEN_KO.get(cn, cn) if cn else None


def _year_pillar_ganzhi(year):
    """그 해(입춘 기준)의 연간지. 7월 1일(입춘 한참 후)로 안전하게 추출."""
    ec = Solar.fromYmdHms(year, 7, 1, 12, 0, 0).getLunar().getEightChar()
    return ec.getYearGan(), ec.getYearZhi()


def _month_pillar_ganzhi(year, month):
    """그 연-월(절기 기준)의 월간지(오호둔). 15일 정오(절기 경계 사이)로 대표 추출."""
    ec = Solar.fromYmdHms(year, month, 15, 12, 0, 0).getLunar().getEightChar()
    return ec.getMonthGan(), ec.getMonthZhi()


def _fortune_block(gan, zhi, day_gan):
    """간지 + 오행 + (일간 대비) 천간·지지 십성 공통 블록."""
    return {
        "ganzhi": gan + zhi,
        "stem": gan, "branch": zhi,
        "stem_element": ELEMENT_EN[STEM_ELEMENT[gan]],
        "branch_element": ELEMENT_EN[BRANCH_ELEMENT[zhi]],
        "stem_ten_god": _ten_god(day_gan, gan),
        "branch_ten_god": _ten_god(day_gan, BRANCH_MAIN_QI[zhi]),  # 지지 본기 기준
    }


def compute_annual_fortune(day_gan, base_year, dist, span=5):
    """세운: base_year부터 span년치 연간지 + 오행 + 십성 + 분야별 점수(재물·애정·건강·성장).
    분야 점수는 일운과 동일한 _field_scores 규칙(세운 간지 ↔ 내 사주)으로 산출."""
    out = []
    for y in range(base_year, base_year + span):
        gan, zhi = _year_pillar_ganzhi(y)
        block = {"year": y}
        block.update(_fortune_block(gan, zhi, day_gan))
        fs = _field_scores(day_gan, gan, zhi, dist)
        block["fields"] = fs["fields"]
        block["matched_field"] = fs["matched"]
        block["overall_score"] = fs["overall"]
        # 해석 문구는 엔진이 준다 — 예전엔 웹(chart.ts)과 앱(saju_view.dart)이 같은
        # 십성 문구 테이블을 각자 하드코딩하고 있었다(두 벌).
        block["copy"] = year_copy(block["stem_ten_god"])
        out.append(block)
    return out


# 12절(節) — 월간지가 바뀌는 경계. lunar-python 이 내보내는 표기(간체 포함) → 한글.
# ⚠ 중기(中氣: 우수·춘분·곡우…)는 월을 나누지 않는다. 여기 없는 게 맞다.
JIE_KO = {
    "立春": "입춘", "惊蛰": "경칩", "驚蟄": "경칩", "清明": "청명", "立夏": "입하",
    "芒种": "망종", "芒種": "망종", "小暑": "소서", "立秋": "입추", "白露": "백로",
    "寒露": "한로", "立冬": "입동", "大雪": "대설", "小寒": "소한",
}


def _month_term_range(year, month):
    """그 (연-월)의 월간지가 실제로 유효한 **절기 구간**.

    왜 필요한가: 월간지는 양력 달이 아니라 절기로 나뉜다. 2026년 8월의 월간지는 丙申인데,
    丙申월은 사실 **입추(8/7)부터 백로(9/7)까지**다 — 8월 1~6일은 아직 乙未월이다.
    화면이 "8월 = 丙申"이라고만 적으면 월초 며칠이 어긋난다. '정확한 만세력'을 내세우면서
    표시가 며칠 틀리는 건 앞뒤가 안 맞는다. 그래서 구간을 함께 내보내 정직하게 밝힌다.

    기준일은 _month_pillar_ganzhi 와 같은 15일 정오다(그 달의 간지를 대표하는 날).
    """
    lunar = Solar.fromYmdHms(year, month, 15, 12, 0, 0).getLunar()
    jie = lunar.getPrevJie()      # 이 월간지를 연 절
    nxt = lunar.getNextJie()      # 다음 월간지가 시작되는 절
    s, e = jie.getSolar(), nxt.getSolar()
    name = jie.getName()
    return {
        "term_name": JIE_KO.get(name, name),          # 입추
        "term_hanja": name,                            # 立秋
        "start": s.toYmd(),                            # 2026-08-07
        "end": e.toYmd(),                              # 2026-09-07 (다음 절 = 이 달의 끝)
        "label": "%d.%d~%d.%d" % (s.getMonth(), s.getDay(), e.getMonth(), e.getDay()),
    }


def compute_monthly_fortune(day_gan, base_year, base_month, span=6):
    """월운: base 연-월부터 span개월치 월간지 + 오행 + 십성 + 해석 문구 + 절기 구간.

    ※ 월운엔 점수를 매기지 않는다. 달마다 점수를 매기면 '나쁜 달'이 생긴다.
      좋은 달/나쁜 달이 아니라 '각기 다른 결의 달'로만 말한다(fortune_copy.py 참고).
    """
    out = []
    y, m = base_year, base_month
    for _ in range(span):
        gan, zhi = _month_pillar_ganzhi(y, m)
        block = {"year": y, "month": m}
        block.update(_fortune_block(gan, zhi, day_gan))
        # 이 월간지가 실제로 유효한 절기 구간(양력 달과 며칠 어긋난다는 걸 화면이 밝히도록).
        block["term"] = _month_term_range(y, m)
        # 해석 문구는 엔진이 준다 — 웹·앱이 각자 문구 테이블을 갖지 않도록.
        block["copy"] = month_copy(block["stem_ten_god"])
        out.append(block)
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


# --- 오늘의 운세 점수(daily_fortune): 근거 있는 규칙 기반 ----------------------
# ⚠ 사주엔 본래 '점수' 개념이 없음. 아래는 (오늘 일진 ↔ 내 사주) 관계를 명시적 규칙으로
#    수치화한 보조 지표. 50=중립이며, 낮아도 '나쁜 날'이 아니라 '안으로 다지는 날'.
# 십성 가중치: 순한 십성(정인·식신·정재 등) +, 도전적 십성(편관·상관·겁재)은 중립~약간-(나쁨 아님)
TEN_GOD_WEIGHT = {
    "정인": 12, "편인": 6, "식신": 12, "상관": -4, "정재": 10,
    "편재": 6, "정관": 6, "편관": -6, "비견": 4, "겁재": -4,
}
# 십성 → 분야: 재성→재물, 관성+인성→애정/관계, 식상→건강/표현, 비겁→성장/자기
TEN_GOD_FIELD = {
    "정재": "wealth", "편재": "wealth",
    "정관": "love", "편관": "love", "정인": "love", "편인": "love",
    "식신": "health", "상관": "health",
    "비견": "growth", "겁재": "growth",
}
FIELDS = ("wealth", "love", "health", "growth")
FIELD_KO = {"wealth": "재물", "love": "애정·관계", "health": "건강·표현", "growth": "성장·자기"}


def _day_pillar_ganzhi(year, month, day):
    """그 날짜의 일진(日辰) 간지. 정오 기준(자시 경계 영향 회피)."""
    ec = Solar.fromYmdHms(year, month, day, 12, 0, 0).getLunar().getEightChar()
    return ec.getDayGan(), ec.getDayZhi()


def _element_balance_points(pct):
    """오행 균형 기여: 부족(20%↓)이면 +, 과다(30%↑)이면 -, 적정이면 0. (label 동반)"""
    if pct < 10:  return 18, "매우 부족"
    if pct < 20:  return 12, "부족"
    if pct <= 30: return 0,  "적정"
    if pct <= 40: return -10, "과다"
    return -16, "매우 과다"


def _daily_tone_line(overall, el_pts):
    """그날의 '결' 한 줄. 단정·공포 금지, 경향 언어. 낮아도 '안으로 다지는 날'."""
    if el_pts > 0:
        return ("부족했던 기운이 차오르는 날 — 한 걸음 내딛기 좋아요" if overall >= 58
                else "조금씩 채워지는 흐름이 도는 날이에요")
    if el_pts < 0:
        return "넘치던 기운을 차분히 다지기 좋은 날 — 안으로 머물러도 좋아요"
    return ("고르게 트이는 잔잔한 흐름의 날이에요" if overall >= 58
            else "평온히 머무는 날 — 천천히 흘려보내요")


def _field_scores(day_gan, gan, zhi, dist):
    """간지 하나(오늘 일진·올해 세운 등)가 내 사주와 만나 만드는 분야별 점수(0~100, 50 중립).
    daily(일운)·annual(세운) 공용 단일 소스 — 두 곳의 점수 규칙이 어긋나지 않게 한다.
    dist: compute_five_elements 결과({한글오행: {count,pct}}).
    반환 dict에 설명 생성용 중간값(라벨·기여점수·십성)도 함께 담는다."""
    stem_el, branch_el = STEM_ELEMENT[gan], BRANCH_ELEMENT[zhi]   # 한글 오행
    stem_pct, branch_pct = dist[stem_el]["pct"], dist[branch_el]["pct"]

    # 1) 오행 균형 기여 (천간 오행 + 지지 오행 평균)
    sp, slabel = _element_balance_points(stem_pct)
    bp, blabel = _element_balance_points(branch_pct)
    el_pts = round((sp + bp) / 2.0)

    # 2) 십성 기여 (천간 십성 + 지지 본기 십성 절반 가중)
    stem_god = _ten_god(day_gan, gan)
    branch_god = _ten_god(day_gan, BRANCH_MAIN_QI[zhi])
    tg_pts = round(TEN_GOD_WEIGHT.get(stem_god, 0) + 0.5 * TEN_GOD_WEIGHT.get(branch_god, 0))

    # 3) 종합 (50 기준 합산 → 0~100 정규화)
    overall = max(0, min(100, round(50 + el_pts + tg_pts)))

    # 4) 분야별: 대상 간지의 십성이 속한 분야가 높아짐, 나머지는 종합 흐름을 약하게 반영
    matched = TEN_GOD_FIELD.get(stem_god)
    fields = {}
    for f in FIELDS:
        if f == matched:
            fields[f] = max(0, min(100, round(50 + 22 + el_pts)))
        else:
            fields[f] = max(0, min(100, round(50 + (overall - 50) * 0.3)))

    return {
        "fields": fields, "matched": matched, "overall": overall, "el_pts": el_pts,
        "stem_el": stem_el, "branch_el": branch_el, "stem_pct": stem_pct, "branch_pct": branch_pct,
        "slabel": slabel, "blabel": blabel, "stem_god": stem_god, "branch_god": branch_god,
        "tg_pts": tg_pts,
    }


def compute_daily_fortune(day_gan, dist, dt):
    """
    오늘의 운세 점수(0~100, 50 중립)와 분야별 점수.
    재료: 오늘 일진 간지 ↔ 내 일간(십성) + 내 오행 분포(균형 기여).
    dist: compute_five_elements 결과({한글오행: {count,pct}}).
    """
    gan, zhi = _day_pillar_ganzhi(dt.year, dt.month, dt.day)
    s = _field_scores(day_gan, gan, zhi, dist)
    el_pts, overall, matched, fields = s["el_pts"], s["overall"], s["matched"], s["fields"]

    # 설명 가능한 근거 + 결 한 줄
    basis = (
        "오늘 일진은 {gan}{zhi}. "
        "천간 {gan}({sel}·{shan})는 내 분포에서 {sl}({sel} {sp:.0f}%), "
        "지지 {zhi}({bel}·{bhan})는 {bl}({bel} {bp:.0f}%) → 오행 균형 기여 {ep:+d}. "
        "일간 {dm} 대비 십성은 천간 '{sg}'(지지 '{bg}') → 십성 기여 {tp:+d}. "
        "→ 50(중립) 기준 종합 {ov}점. 오늘의 기운은 '{fk}' 쪽으로 모이는 흐름이에요."
    ).format(
        gan=gan, zhi=zhi, sel=s["stem_el"], shan=ELEMENT_HANJA[s["stem_el"]], bel=s["branch_el"],
        bhan=ELEMENT_HANJA[s["branch_el"]], sl=s["slabel"], bl=s["blabel"],
        sp=s["stem_pct"], bp=s["branch_pct"], ep=el_pts, dm=day_gan,
        sg=s["stem_god"], bg=s["branch_god"], tp=s["tg_pts"], ov=overall,
        fk=FIELD_KO.get(matched, "—"),
    )

    return {
        "date": _fmt_dt(dt)[:10],
        "day_ganzhi": gan + zhi,
        "day_stem": gan, "day_branch": zhi,
        "day_stem_element": ELEMENT_EN[s["stem_el"]],
        "day_branch_element": ELEMENT_EN[s["branch_el"]],
        "ten_god": s["stem_god"],
        "matched_field": matched,
        "overall_score": overall,
        "score_basis": basis,
        "tone_line": _daily_tone_line(overall, el_pts),
        "fields": fields,
    }


def compute_chart(dt_raw, lat=None, lng=None,
                  apply_tst=True, timezone="Asia/Seoul", ruleset="kr_saju",
                  gender="female", calendar="solar", is_leap_month=False, city=None,
                  target_year=None, target_month=None, target_date=None,
                  reference_date=None, hour_known=True):
    """
    전체 파이프라인을 돌려 기술명세 §7.3 형태의 구조화된 dict를 반환한다.
    화면이 그대로 소비할 /v1/chart 응답 후보.

    결정론: 세운/월운/오늘운세의 기본 기준시점만 "현재 시각"에 의존한다.
    reference_date(datetime)를 주면 그 시점을 기준으로 삼아 완전히 결정론적으로 동작한다
    (테스트·캐시용). 생략하면 datetime.now()를 사용한다. target_year/month/date를
    모두 지정하면 reference_date 없이도 해당 파생값은 결정론적이다.

    calendar="lunar" 이면 dt_raw 를 음력으로 보고 양력으로 환산한 뒤
    (is_leap_month=True 면 윤달) 이후 파이프라인은 양력 기준 그대로 태운다.

    출생지: city 도시명이 표에 있으면 그 위경도로 진태양시 보정.
    표에 없거나 미입력이면 → 직접 준 lat/lng → 둘 다 없으면 서울(기본).
    """
    # 0) 음력 입력이면 양력으로 환산 → 이후 전 과정은 양력(dt_raw) 기준
    input_calendar = str(calendar).strip().lower()
    lunar_input = None
    if input_calendar == "lunar":
        orig = dt_raw
        dt_raw, lunar_label = _lunar_to_solar(dt_raw, is_leap_month)
        lunar_input = {
            "year": orig.year, "month": orig.month, "day": orig.day,
            "is_leap_month": bool(is_leap_month),
            "lunar_label": lunar_label,
            "converted_solar": _fmt_dt(dt_raw),
        }

    # 0.5) 출생지 해석: 도시명(우선) → lat/lng(직접) → 서울(기본)
    name_in = city
    resolved = lookup_city(name_in) if name_in else None
    city_fallback = False
    if resolved:                                   # 표에 있는 도시
        place_label, lat, lng = resolved
    elif lat is not None and lng is not None:       # 위경도 직접 지정
        place_label = name_in or "사용자 지정"
    else:                                           # 폴백: 서울
        if name_in:                                 # 도시명 줬지만 표에 없음
            city_fallback = True
        place_label, lat, lng = "서울", SEOUL_LATITUDE, SEOUL_LONGITUDE

    # 1) 보정 전/후 팔자
    _, raw_lunar, raw_pillars = compute_pillars(dt_raw)
    dt_tst, corr = true_solar_time(dt_raw, lng)
    _, _, tst_pillars = compute_pillars(dt_tst)

    chart_pillars = tst_pillars if apply_tst else raw_pillars
    dt_chart = dt_tst if apply_tst else dt_raw

    # 시간 미상(hour_known=False): 시주(時柱)를 아예 제외한다(PRD §6.1).
    # 오행·신살·형충회합·명식이 모두 년·월·일 6글자/3지지 기준으로 계산됨.
    # (서버는 이때 정오 12:00으로 넘겨 일주가 자시·진태양시 경계에 흔들리지 않게 한다)
    if not hour_known:
        chart_pillars = {k: v for k, v in chart_pillars.items() if k != "hour"}

    # 2) 파생: 오행·신살·캐릭터·대운
    dist, _ = compute_five_elements(chart_pillars)
    ss = compute_shensha(chart_pillars)
    cr = compute_character(ss, chart_pillars["day"]["gan"])
    luck = compute_luck_pillars(dt_chart, gender)   # 대운(명세 §8)

    # 세운(歲運)·월운(月運): 기본=올해/이번 달 (명세 §8)
    day_gan = chart_pillars["day"]["gan"]
    now = reference_date if reference_date is not None else datetime.now()
    base_year = target_year if target_year is not None else now.year
    base_month = target_month if target_month is not None else now.month
    annual = compute_annual_fortune(day_gan, base_year, dist, span=5)
    monthly = compute_monthly_fortune(day_gan, base_year, base_month, span=6)

    # 오늘의 운세 점수: 기본=오늘, target_date="YYYY-MM-DD"면 그 날짜
    target_dt = datetime.strptime(str(target_date)[:10], "%Y-%m-%d") if target_date else now
    daily = compute_daily_fortune(day_gan, dist, target_dt)

    # 공망(空亡): 일주 기준 순중에서 빠지는 2지지. 각 기둥 지지가 여기 속하면 is_void.
    gm_xun, gm_voids = compute_gongmang(day_gan, chart_pillars["day"]["zhi"])

    # 3) pillars 블록 (시간 미상이면 hour 키 없음)
    pillars_out = {}
    for k in PILLAR_KEYS:
        if k not in chart_pillars:
            continue
        p = chart_pillars[k]
        block = {
            "stem": p["gan"],
            "branch": p["zhi"],
            "ganzhi": p["ganzhi"],
            "stem_element": ELEMENT_EN[STEM_ELEMENT[p["gan"]]],
            "branch_element": ELEMENT_EN[BRANCH_ELEMENT[p["zhi"]]],
            # 십성(十星): 일간 대비 관계. 세운/일진과 동일한 _ten_god·본기 로직(단일 소스).
            #   · 천간: 일간과 대상 천간의 오행·음양 관계
            #   · 지지: 지지 본기(정기) 천간 기준
            #   · 일간 자신(일주 천간)은 기준점이므로 "일원"(日元)으로 표기
            "ten_god": {
                "stem": "일원" if k == "day" else _ten_god(day_gan, p["gan"]),
                "branch": _ten_god(day_gan, BRANCH_MAIN_QI[p["zhi"]]),
            },
            # 지장간(支藏干): 지지 속 천간(여기·중기·정기) + 각각의 십성(일간 기준, _ten_god 재사용).
            "hidden_stems": [
                {"stem": s, "position": pos, "position_en": ROLE_EN[pos],
                 "ten_god": _ten_god(day_gan, s)}
                for pos, s in HIDDEN_STEMS[p["zhi"]]
            ],
            # 12운성(十二運星): 일간이 이 지지에서 갖는 포태 단계(음간 역행설).
            "twelve_stage": TWELVE_STAGE[day_gan][p["zhi"]],
            # 공망(空亡) 여부: 이 기둥 지지가 일주 순중의 공망 2지지에 속하는가.
            "is_void": p["zhi"] in gm_voids,
        }
        if k == "day":
            block["day_master"] = True
        pillars_out[k] = block

    # 4) five_elements 블록 (영문 키, count + pct)
    five_out = {ELEMENT_EN[el]: {"count": dist[el]["count"], "pct": round(dist[el]["pct"], 1)}
                for el in ELEMENT_ORDER}

    # 5) shensha 블록 (해당된 것만, 기둥·한자 포함)
    shensha_out = [
        {"name": name, "hanja": SHENSHA_HANJA[name], "pillars": ss[name]["pillars"], "rule": ss[name]["basis"]}
        for name in SHENSHA_ORDER if ss[name]["hit"]
    ]

    # 6) character 블록
    c = cr["char"]
    character_out = {
        "name_ko": c["ko"],
        "name_en": c["en"],
        "tagline": c["tagline"],
        "representative_shensha": cr["rep"],
        "day_master_element": ELEMENT_EN[cr["day_element"]],
        "base_tone": c["tone"],
        "selection_basis": cr["basis"],
    }

    chart = {
        "engine_version": ENGINE_VERSION,
        "input": {
            "birth_datetime_local": _fmt_dt(dt_raw),   # 양력 기준(음력 입력은 환산 후)
            "calendar": input_calendar,                # 사용자가 입력한 기준(solar/lunar)
            "lunar_input": lunar_input,                # 음력 입력일 때만 채워짐(아니면 null)
            "birth_place": {"name": place_label, "lat": lat, "lng": lng,
                            "city_fallback": city_fallback},
            "timezone": timezone,
            "true_solar_time_applied": apply_tst,
            "gender": luck["gender"],
            "hour_known": hour_known,                  # 시간 미상이면 False(시주 제외)
        },
        "pillars": pillars_out,
        # 공망(空亡): 일주 순중(旬中)에서 빠진 2지지 + 해당되는 기둥.
        "gongmang": {
            "xun": gm_xun,                                  # 순두(旬首), 예: 甲辰
            "void_branches": gm_voids,                      # 공망 2지지, 예: ["寅","卯"]
            "void_pillars": [k for k in PILLAR_KEYS         # 지지가 공망인 기둥
                             if k in chart_pillars and chart_pillars[k]["zhi"] in gm_voids],
        },
        # 형충회합(刑沖會合): 네 지지 사이 관계(육합·삼합·방합·육충·육해·형·파).
        "relations": compute_relations(chart_pillars),
        "true_solar_time": {
            "before_local": _fmt_dt(dt_raw),
            "after_true_solar": _fmt_dt(dt_chart),
            "longitude_correction_min": round(corr["longitude"], 2),
            "equation_of_time_min": round(corr["eot"], 2),
            "total_correction_min": round(corr["total"], 2),
        },
        "five_elements": five_out,
        "shensha": shensha_out,
        "character": character_out,
        "luck_pillars": luck,
        "annual_fortune": {
            "base_year": base_year,
            "day_master": day_gan,
            "pillars": annual,
        },
        "monthly_fortune": {
            "base_year": base_year,
            "base_month": base_month,
            "day_master": day_gan,
            "pillars": monthly,
        },
        "daily_fortune": daily,
        "calc_meta": {
            "timezone": timezone,
            "birth_city": place_label,
            "latitude_used": lat,
            "longitude_used": lng,
            "standard_meridian": KST_STANDARD_MERIDIAN,
            "true_solar_time_applied": apply_tst,
            "ruleset": ruleset,
            "lunar_date": raw_lunar.toString(),
            # 사주 앱이므로 연간지는 입춘 기준으로 통일 — 실제 년주(pillars.year)와 동일 소스(ec.getYear()).
            # (lunar-python getYearInGanZhi()는 설날 기준이라 입춘~설날 구간에서 년주와 어긋남)
            # 설날 기준 음력 연간지가 필요해지면 lunar_year_ganzhi 같은 별도 필드로 분리할 것.
            "year_ganzhi": chart_pillars["year"]["ganzhi"],
            "engine_version": ENGINE_VERSION,
            "limitations": [
                "균시차 근사식(실측 최대 ~1.4분·12월, RMS ~38초), 정밀 천체력 미적용",
                "시간대/DST·한국 표준자오선 이력 미반영",
                "자시(子時) 경계 룰셋 미적용",
                "오행 분포는 지장간 미포함(천간·지지 8글자)",
            ],
        },
    }
    # 시간 미상: 시주 제외로 오행이 6글자 기준임을 명시(정직한 한계 공개).
    if not hour_known:
        chart["calc_meta"]["limitations"].insert(
            0, "출생시간 미상 — 시주(時柱) 제외, 오행은 천간·지지 6글자 기준")
    return chart


def to_json(chart, indent=2):
    """구조화된 chart dict -> 한글/한자 보존 JSON 문자열."""
    return json.dumps(chart, ensure_ascii=False, indent=indent)


def render(dt_raw, dt_tst, corr, raw_pillars, tst_pillars, raw_lunar):
    """콘솔 보기 좋게 출력 — 보정 전/후 시각과 시주 변화를 함께 보여준다."""
    line = "=" * 52
    sub = "  " + "-" * 44

    def fmt(dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    print(line)
    print("  Wolune 만세력 엔진 — 사주팔자 + 진태양시 (v0.2)")
    print(line)
    print(f"  양력 입력 : {fmt(dt_raw)}  (KST, 서울)")
    print(f"  음력 변환 : {raw_lunar.toString()}  ({raw_lunar.getYearInGanZhi()}년)")
    print(line)

    # --- 진태양시 보정 내역 ---
    print("  [진태양시 보정 — 명세 §5.2]")
    print(f"  · 경도차 보정 : ({SEOUL_LONGITUDE}°E − {KST_STANDARD_MERIDIAN}°E) × 4분")
    print(f"                = {corr['longitude']:+.1f}분")
    print(f"  · 균시차(EoT) : {corr['eot']:+.1f}분")
    print(f"  · 합계 보정   : {corr['total']:+.1f}분")
    print(sub)
    print(f"  보정 전(표준시)   : {fmt(dt_raw)}")
    print(f"  보정 후(진태양시) : {fmt(dt_tst)}")
    print(line)

    # --- 보정 전/후 시주 비교 ---
    rh, th = raw_pillars["hour"], tst_pillars["hour"]
    changed = rh["ganzhi"] != th["ganzhi"]
    print("  [시주(時柱) 변화]")
    print(f"  보정 전 : {rh['ganzhi']}  ({rh['zhi']}時)")
    print(f"  보정 후 : {th['ganzhi']}  ({th['zhi']}時)")
    if changed:
        print(f"  => 시주가 바뀜!  {rh['ganzhi']} → {th['ganzhi']}  "
              f"(지지 {rh['zhi']} → {th['zhi']})")
    else:
        print(f"  => 시주 그대로  ({rh['ganzhi']})")
    print(line)

    # --- 최종 팔자 (진태양시 적용) ---
    print("  [최종 사주팔자 — 진태양시 적용]")
    print("  구분        천간   지지   간지")
    print(sub)
    for key in ("year", "month", "day", "hour"):
        p = tst_pillars[key]
        mark = "  ← 일간(日干)" if key == "day" else ""
        print(f"  {p['name']}   {p['gan']}      {p['zhi']}      {p['ganzhi']}{mark}")
    eight = " ".join(tst_pillars[k]["ganzhi"] for k in ("year", "month", "day", "hour"))
    print(sub)
    print(f"  팔자 8글자 : {eight}")
    print(line)

    # --- 오행 분포 (8글자 기준, 지장간 미포함) ---
    dist, detail = compute_five_elements(tst_pillars)
    print("  [오행(五行) 분포 — 8글자 기준, 지장간 미포함]")
    chars = "  ".join(f"{ch}({el})" for ch, el in detail)
    print(f"  글자별 : {chars}")
    print(sub)
    print("  오행   개수   비율")
    for el in ELEMENT_ORDER:
        d = dist[el]
        bar = "■" * d["count"]
        print(f"  {el}     {d['count']}개   {d['pct']:>5.1f}%  {bar}")
    print(line)

    # --- 신살(神殺) — 캐릭터 매핑용 핵심 9종 ---
    ss = compute_shensha(tst_pillars)
    print("  [신살(神殺) — 캐릭터 매핑용 핵심 9종]")
    print("  신살        해당  기둥        판별기준")
    print(sub)
    present = []
    for name in SHENSHA_ORDER:
        d = ss[name]
        if d["hit"]:
            mark = "O"
            where = ", ".join(d["pillars"])
            present.append(f"{name}({where})")
        else:
            mark = "·"
            where = "—"
        print(f"  {name:<8}  {mark}    {where:<10}  {d['basis']}")
    print(sub)
    print(f"  => 이 사주의 신살: {', '.join(present) if present else '없음'}")
    print(line)

    # --- 캐릭터 결정 (신살 우선순위 + 일간) ---
    day_gan = tst_pillars["day"]["gan"]
    cr = compute_character(ss, day_gan)
    c = cr["char"]
    print("  [캐릭터 — 신살+일간 결정론적 매핑]")
    print(f"  선택 근거 : {cr['basis']}")
    print(f"  우선순위  : 콤보 > 천을귀인 > 화개 > 문창귀인 > 월덕귀인 > 도화 > 양인 > 괴강")
    print(sub)
    print(f"  ★ 캐릭터  : {c['ko']} / {c['en']}")
    print(f"    한 줄 정의 : \"{c['tagline']}\"")
    print(f"    표상 신살  : {cr['rep']}")
    de = cr["day_element"]
    print(f"    일간 오행  : {de}({ELEMENT_HANJA[de]}) — 일간 {day_gan} · 보조 톤/강조색")
    print(f"    (캐릭터 기본 톤: {c['tone']})")
    print(line)
    print("  ※ 신살은 lunar-python 미지원 → 명리 표준 규칙 직접 구현.")
    print("    천을귀인은 '甲戊庚牛羊' 통용본 기준(학파별 이설 있음).")
    print("    균시차 근사식(±0.5분)·자시 경계·지장간은 미적용.")
    print(line)


if __name__ == "__main__":
    # 샘플: 1996-03-14 11:11 (양력, 서울)
    dt_raw = datetime(1996, 3, 14, 11, 11, 0)

    # 1) 보정 전 사주
    _, raw_lunar, raw_pillars = compute_pillars(dt_raw)

    # 2) 진태양시 보정 후 사주
    dt_tst, corr = true_solar_time(dt_raw)
    _, _, tst_pillars = compute_pillars(dt_tst)

    render(dt_raw, dt_tst, corr, raw_pillars, tst_pillars, raw_lunar)

    # --- 결정론 자기검증: 같은 입력 -> 항상 같은 캐릭터 ---
    ss = compute_shensha(tst_pillars)
    dg = tst_pillars["day"]["gan"]
    picks = {compute_character(ss, dg)["char"]["ko"] for _ in range(5)}
    assert len(picks) == 1, f"결정론 위반: {picks}"
    print(f"  [결정론 확인] 5회 반복 모두 동일 캐릭터: {picks.pop()}")

    # --- 구조화된 JSON 출력 (/v1/chart 응답 후보, 기술명세 §7.3) ---
    print("\n" + "=" * 52)
    print("  [구조화 JSON — /v1/chart 응답 후보]")
    print("=" * 52)
    chart = compute_chart(dt_raw)
    print(to_json(chart))

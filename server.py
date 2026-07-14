# -*- coding: utf-8 -*-
"""
Wolune 만세력 엔진 — 로컬 API 서버 (v0.1)
==========================================
engine/saju_pillars.py 의 compute_chart() 를 HTTP 로 노출하는 최소 서버.
표준 라이브러리(http.server)만 사용 → 추가 설치 불필요(엔진 의존성 lunar-python 제외).

엔드포인트:
  GET /v1/chart?date=1996-03-14&time=11:11&lat=37.5665&lng=126.978
    - date  (필수) : 양력 생년월일  YYYY-MM-DD
    - time  (선택) : 생시 HH:MM 또는 HH:MM:SS   (기본 00:00:00)
    - lat   (선택) : 위도   (기본 37.5665, 서울)
    - lng   (선택) : 경도   (기본 126.978, 서울)
    - city/place (선택): 출생 도시명(예: 부산, 서울특별시, busan). 표에 있으면 그 위경도로 보정.
                         표에 없거나 미입력 → lat/lng → 둘 다 없으면 서울(기본).
    - lat/lng (선택): 위경도 직접 지정(도시명이 우선)
    - gender(선택) : 성별 male/female (기본 female) — 대운 방향(양남음녀 순행…) 결정에 사용
    - calendar(선택): solar(양력, 기본) | lunar(음력) — 음력이면 내부에서 양력으로 환산
    - is_leap_month(선택): 음력 윤달 여부 1/0/true/false (기본 0)
    - target_year (선택): 세운 대상 연도(기본 올해)
    - target_month(선택): 월운 대상 월(기본 이번 달)
    - target_date (선택): 오늘의 운세 점수 날짜 YYYY-MM-DD(기본 오늘)
    - tst   (선택) : 진태양시 보정 적용 여부 1/0/true/false (기본 1)
  -> compute_chart() 결과를 JSON(ensure_ascii=False)으로 반환.

  GET  /v1/glossary
    - 용어사전 전체(웹·앱 공용 진실의 원천). 자주 안 바뀌므로 클라이언트가 오래 캐시해도 된다.

  POST /v1/insight   body: {"entries": [{"mood":1~5, "score":int, "day_ganzhi":"甲子"}, ...]}
    - 무드 통찰(무드 기록 × 그날의 기운의 경향). **무상태 — 저장하지 않는다.**
    - 계산에 필요한 값만 받는다: 메모·태그·날짜는 받지 않는다.

개인정보: 액세스 로그에 **쿼리스트링을 남기지 않는다**(생년월일·출생지가 로그에 쌓이지
      않도록). POST 바디도 로그에 남지 않는다.

실행:
  python engine/server.py            # 기본 포트 8000
  PORT=9001 python engine/server.py  # 포트 변경(환경변수)

CORS: 기본 허용 출처는 localhost:3000(개발용 프런트). WOLUNE_ALLOW_ORIGIN 로 조정(예: "*").
      운영 웹앱은 브라우저에서 직접 호출하지 않고 Next 서버 프록시(/api/engine/chart)를 거친다.
"""

import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# 같은 폴더의 엔진 모듈을 직접 임포트(서버를 어디서 실행하든 동작하도록 경로 보정)
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from saju_pillars import compute_chart, to_json, SEOUL_LONGITUDE  # noqa: E402
from glossary import payload as glossary_payload, _assert_covers_engine_vocabulary  # noqa: E402
from insight import compute_insight, parse_entries  # noqa: E402
from compatibility import compute_compatibility  # noqa: E402

# POST 바디 상한 — 통찰 요청이 커봐야 수십 KB다. 그 이상은 읽지 않는다.
MAX_BODY_BYTES = 256 * 1024

# 액세스 로그에서 쿼리스트링을 잘라낸다: `"GET /v1/chart?date=…&city=…" 200` → `"GET /v1/chart" 200`
_QUERY_RE = re.compile(r'(\s/[^\s?"]*)\?[^\s"]*')

from fortune_copy import _assert_covers_ten_gods  # noqa: E402

# 사전이 엔진 어휘(십성·12운성·형충회합·지장간 위치)를 다 덮는지 기동 시 확인.
# 빠진 게 있으면 여기서 죽는다 — 조용히 넘어가면 사용자 화면에 뜻 없는 생 한자가 뜬다.
_assert_covers_engine_vocabulary()
# 세운·월운 문구가 십성 10종을 다 덮는지도 같은 이유로 확인(빠지면 빈 문구가 뜬다).
_assert_covers_ten_gods()

DEFAULT_PORT = 8000
DEFAULT_LAT = 37.5665
DEFAULT_LNG = SEOUL_LONGITUDE  # 126.978

# CORS 허용 출처. 웹앱은 브라우저에서 엔진을 직접 부르지 않고 Next 서버 프록시(/api/engine/chart)를
# 거치므로, 기본값을 개발용 프런트(localhost:3000)로 좁힌다. 필요 시 env 로 덮어쓴다(예: "*").
ALLOW_ORIGIN = os.environ.get("WOLUNE_ALLOW_ORIGIN", "http://localhost:3000")

# lunar-python 이 신뢰할 수 있는 대략적 연도 범위(이 밖은 값이 부정확할 수 있어 거부).
MIN_YEAR, MAX_YEAR = 1900, 2100


def _parse_dt(date_str, time_str):
    """date=YYYY-MM-DD, time=HH:MM[:SS] -> datetime. 잘못된 형식이면 ValueError."""
    if not date_str:
        raise ValueError("필수 파라미터 'date'(YYYY-MM-DD)가 없습니다.")
    time_str = (time_str or "00:00:00").strip()
    # HH:MM 도 허용 → 초 보충
    if time_str.count(":") == 1:
        time_str += ":00"
    return datetime.strptime(date_str.strip() + " " + time_str, "%Y-%m-%d %H:%M:%S")


def _truthy(val, default=True):
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


def _first(qs, key, default=None):
    v = qs.get(key)
    return v[0] if v else default


def _chart_from_person(p, who):
    """궁합 요청의 사람 블록 하나 → compute_chart 결과.

    필드 이름은 GET /v1/chart 의 쿼리 파라미터와 **일부러 똑같이** 맞췄다. 이름이 어긋나면
    나중에 반드시 사고가 난다(같은 뜻을 두 이름으로 부르는 순간부터).
    ⚠ 예외 메시지에 사용자 값을 담지 않는다 — 로그·응답에 생년월일이 새면 안 된다.
    """
    if not isinstance(p, dict):
        raise ValueError("'%s' 는 객체여야 합니다." % who)

    time_raw = p.get("birth_time")
    hour_known = bool(time_raw and str(time_raw).strip())
    # 시간 미상이면 시주 제외 + 일주가 자시·진태양시 경계에 흔들리지 않게 정오 기준(PRD §6.1).
    dt = _parse_dt(p.get("birth_date"), time_raw if hour_known else "12:00:00")
    if not (MIN_YEAR <= dt.year <= MAX_YEAR):
        raise ValueError("'%s' 의 birth_date 연도는 %d~%d 범위여야 합니다." % (who, MIN_YEAR, MAX_YEAR))

    lat, lng = p.get("lat"), p.get("lng")
    if (lat is None) != (lng is None):
        raise ValueError("'%s' 의 lat 와 lng 는 함께 지정해야 합니다." % who)
    if lat is not None:
        lat, lng = float(lat), float(lng)
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
            raise ValueError("'%s' 의 lat/lng 가 범위를 벗어났습니다." % who)

    return compute_chart(
        dt,
        city=p.get("city") or p.get("place"),
        lat=lat, lng=lng,
        apply_tst=bool(p.get("tst", True)),
        gender=p.get("gender") or "female",
        hour_known=hour_known,
        calendar=p.get("calendar") or "solar",
        is_leap_month=bool(p.get("is_leap_month", False)),
    )


class ChartHandler(BaseHTTPRequestHandler):
    server_version = "WoluneEngine/0.1"

    # ---- 공통 응답 헬퍼 ----
    def _send(self, status, body_bytes, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        # CORS: 허용 출처만(기본 localhost:3000, env 로 조정)
        self.send_header("Access-Control-Allow-Origin", ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_json(self, status, obj):
        # ensure_ascii=False → 한글/한자 그대로
        self._send(status, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))

    # ---- CORS preflight ----
    def do_OPTIONS(self):
        self._send(204, b"")

    # ---- POST: 무드 통찰 / 궁합 (둘 다 무상태) ----
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/v1/insight", "/v1/compatibility"):
            self._send_json(404, {"error": "not_found",
                                  "message": "POST 는 /v1/insight 또는 /v1/compatibility 만 지원합니다.",
                                  "path": parsed.path})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._send_json(400, {"error": "bad_request", "message": "본문이 비어 있습니다."})
            return
        if length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "payload_too_large",
                                  "message": "본문이 너무 큽니다."})
            return

        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "bad_request", "message": "JSON 을 읽을 수 없습니다."})
            return

        # ── 궁합 — 점수·근거·문구를 엔진이 만든다(compatibility.py 상단 주석 참고) ──
        if parsed.path == "/v1/compatibility":
            try:
                a = _chart_from_person(body.get("a"), "a")
                b = _chart_from_person(body.get("b"), "b")
            except ValueError as e:
                self._send_json(400, {"error": "bad_request", "message": str(e)})
                return
            except Exception:
                self._send_json(400, {"error": "bad_request",
                                      "message": "a / b 사람 정보를 읽을 수 없습니다."})
                return
            try:
                name_a = (body.get("a") or {}).get("name") or ""
                name_b = (body.get("b") or {}).get("name") or ""
                result = compute_compatibility(a, b, name_a, name_b)
            except Exception as e:
                self._send_json(500, {"error": "engine_error", "message": str(e)})
                return
            # 무상태 — 계산만 하고 버린다. 저장하지 않는다.
            self._send_json(200, result)
            return

        # ── 무드 통찰 ──
        try:
            entries = parse_entries(body)
        except ValueError as e:
            # ⚠️ 예외 메시지에 사용자 값을 담지 않는다(로그·응답에 무드가 새지 않도록).
            self._send_json(400, {"error": "bad_request", "message": str(e)})
            return
        except Exception:
            self._send_json(400, {"error": "bad_request", "message": "JSON 을 읽을 수 없습니다."})
            return

        # 무상태 — 계산만 하고 버린다. 저장하지 않는다.
        self._send_json(200, compute_insight(entries))

    # ---- 라우팅 ----
    def do_GET(self):
        parsed = urlparse(self.path)
        # 헬스체크(Render/Cloud Run 등 플랫폼이 / 에 200을 기대) — 가볍게 응답.
        if parsed.path in ("/", "/healthz"):
            self._send_json(200, {"ok": True, "service": "wolune-engine",
                                  "endpoints": ["GET /v1/chart", "GET /v1/glossary",
                                                "POST /v1/insight", "POST /v1/compatibility"]})
            return

        # 용어사전 — 웹·앱 공용 진실의 원천. 자주 안 바뀌므로 클라이언트가 오래 캐시해도 된다.
        if parsed.path == "/v1/glossary":
            self._send_json(200, glossary_payload())
            return

        if parsed.path != "/v1/chart":
            self._send_json(404, {"error": "not_found",
                                  "message": "GET /v1/chart 또는 GET /v1/glossary 만 지원합니다.",
                                  "path": parsed.path})
            return

        qs = parse_qs(parsed.query)
        try:
            # 시간 미상(time 미제공)이면 시주(時柱) 제외 + 일주가 자시·진태양시 경계에
            # 흔들리지 않게 정오(12:00) 기준으로 계산한다(PRD §6.1).
            time_raw = _first(qs, "time")
            hour_known = bool(time_raw and str(time_raw).strip())
            dt = _parse_dt(_first(qs, "date"), time_raw if hour_known else "12:00:00")
            # 검증 범위 밖 연도는 lunar-python 값이 부정확할 수 있어 거부(무음 오답 방지)
            if not (MIN_YEAR <= dt.year <= MAX_YEAR):
                raise ValueError("date 의 연도는 %d~%d 범위여야 합니다." % (MIN_YEAR, MAX_YEAR))
            # 출생지: city/place(도시명) 우선, 없으면 lat/lng(직접), 둘 다 없으면 엔진이 서울 폴백
            city = _first(qs, "city") or _first(qs, "place")    # 둘 다 alias, 기본값 없음
            lat_raw, lng_raw = _first(qs, "lat"), _first(qs, "lng")
            # lat/lng 는 둘 다 있거나 둘 다 없어야 함(한쪽만 오면 조용히 서울로 오인되므로 거부)
            if (lat_raw is None) != (lng_raw is None):
                raise ValueError("lat 와 lng 는 함께 지정해야 합니다(한쪽만 불가).")
            lat = float(lat_raw) if lat_raw is not None else None
            lng = float(lng_raw) if lng_raw is not None else None
            # 범위 밖 위경도는 진태양시 보정을 왜곡해 사주 전체를 조용히 오염시키므로 거부
            if lat is not None and not (-90.0 <= lat <= 90.0):
                raise ValueError("lat 는 -90~90 범위여야 합니다.")
            if lng is not None and not (-180.0 <= lng <= 180.0):
                raise ValueError("lng 는 -180~180 범위여야 합니다.")
            gender = _first(qs, "gender", "female")   # 대운 방향 결정에 필요(양남음녀…)
            calendar = _first(qs, "calendar", "solar")          # solar(기본) | lunar
            is_leap = _truthy(_first(qs, "is_leap_month"), default=False)  # 음력 윤달 여부
            apply_tst = _truthy(_first(qs, "tst"), default=True)
            ty_raw, tm_raw = _first(qs, "target_year"), _first(qs, "target_month")
            target_year = int(ty_raw) if ty_raw is not None else None    # 세운 대상연도(기본 올해)
            target_month = int(tm_raw) if tm_raw is not None else None   # 월운 대상월(기본 이번달)
            # 범위 밖 세운/월운 값은 엔진 내부에서 예외(→500)가 되므로 여기서 400 으로 걸러낸다
            if target_month is not None and not (1 <= target_month <= 12):
                raise ValueError("target_month 는 1~12 여야 합니다.")
            if target_year is not None and not (1900 <= target_year <= 2200):
                raise ValueError("target_year 는 1900~2200 범위여야 합니다.")
            target_date = _first(qs, "target_date")                      # 오늘의 운세 날짜(기본 오늘)
            # target_date 는 엔진 내부에서 strptime 되므로(→잘못되면 500), 여기서 형식 검증(→400)
            if target_date is not None:
                datetime.strptime(target_date.strip(), "%Y-%m-%d")
        except ValueError as e:
            self._send_json(400, {"error": "bad_request", "message": str(e)})
            return

        try:
            chart = compute_chart(dt, city=city, lat=lat, lng=lng,
                                  apply_tst=apply_tst, gender=gender, hour_known=hour_known,
                                  calendar=calendar, is_leap_month=is_leap,
                                  target_year=target_year, target_month=target_month,
                                  target_date=target_date)
        except Exception as e:  # 엔진 내부 오류는 500 으로
            self._send_json(500, {"error": "engine_error", "message": str(e)})
            return

        # to_json()을 거쳐 동일 직렬화(ensure_ascii=False) → 바이트로 전송
        self._send(200, to_json(chart).encode("utf-8"))

    # 액세스 로그 — **쿼리스트링을 남기지 않는다.**
    #
    # 기본 구현은 요청 라인을 통째로 찍는다. 그러면 /v1/chart?date=1996-03-14&city=서울…
    # 처럼 **생년월일·출생지·성별이 Render 로그에 그대로 쌓인다.** 디버깅에 필요하지도 않다.
    # 경로와 상태코드만 남긴다. (POST 바디는 원래 안 찍히므로 무드 기록도 남지 않는다.)
    def log_message(self, fmt, *args):
        line = fmt % args
        safe = _QUERY_RE.sub(r"\1", line)
        sys.stderr.write("  %s - %s\n" % (self.address_string(), safe))


def main():
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    # 로컬은 127.0.0.1(안전), 컨테이너(Cloud Run)는 HOST=0.0.0.0 으로 외부 트래픽 수신.
    host = os.environ.get("HOST", "127.0.0.1")
    httpd = ThreadingHTTPServer((host, port), ChartHandler)
    print("=" * 56)
    print("  Wolune 엔진 API 서버 실행 중")
    print("  http://%s:%d/v1/chart" % (host, port))
    print("  예) http://127.0.0.1:%d/v1/chart?date=1996-03-14&time=11:11"
          "&lat=37.5665&lng=126.978" % port)
    print("  종료: Ctrl+C")
    print("=" * 56)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

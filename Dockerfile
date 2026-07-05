# Wolune 만세력 엔진 — Cloud Run용 컨테이너
# 표준 라이브러리 http.server 기반이라 의존성은 lunar-python 하나뿐.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Cloud Run은 컨테이너 외부에서 접속하므로 0.0.0.0 바인딩 필수.
# PORT는 Cloud Run이 주입(기본 8080). server.py가 PORT env를 읽는다.
ENV HOST=0.0.0.0
EXPOSE 8080

CMD ["python", "server.py"]

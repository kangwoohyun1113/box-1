import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회 KOBIS 일별 박스오피스")

# --------------------------------------------------
# 2. 한국 시간 기준으로 어제 날짜 계산
# --------------------------------------------------
try:
    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
except Exception:
    # tzdata 라이브러리가 없는 환경 대응
    korea_now = datetime.utcnow() + timedelta(hours=9)

yesterday = (korea_now - timedelta(days=1)).date()

target_dt = yesterday.strftime("%Y%m%d")
display_date = yesterday.strftime("%Y년 %m월 %d일")

st.subheader(f"📅 조회 날짜: {display_date}")
st.caption("한국 시간 기준 어제의 집계 결과입니다.")

# --------------------------------------------------
# 3. API 인증키 읽기
# --------------------------------------------------
try:
    api_key = st.secrets["KOBIS_KEY"]
except Exception:
    st.error("🔑 인증키를 찾을 수 없습니다.")
    st.markdown("""
    **확인 방법**
    1. Streamlit Cloud에서 앱의 Settings를 엽니다.
    2. Secrets 메뉴로 이동합니다.
    3. `KOBIS_KEY = "발급받은키"` 형태로 입력 후 저장하세요.
    """)
    st.stop()

if not str(api_key).strip():
    st.error("🔑 KOBIS_KEY 값이 비어 있습니다.")
    st.info("Streamlit Cloud의 Secrets에 올바른 인증키를 입력하세요.")
    st.stop()

# --------------------------------------------------
# 4. KOBIS API 요청
# --------------------------------------------------
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

try:
    response = requests.get(
        API_URL,
        params={
            "key": str(api_key).strip(),
            "targetDt": target_dt
        },
        timeout=20
    )
    response.raise_for_status()
    data = response.json()

except requests.exceptions.Timeout:
    st.error("⏱️ KOBIS API 응답 시간이 초과되었습니다.")
    st.stop()
except requests.exceptions.RequestException:
    st.error("🌐 KOBIS API 서버에 연결하지 못했습니다.")
    st.stop()
except ValueError:
    st.error("📄 API 응답을 JSON으로 해석할 수 없습니다.")
    st.stop()

# --------------------------------------------------
# 5. API 자체 오류 검증
# --------------------------------------------------
if not isinstance(data, dict):
    st.error("API 응답의 형식이 올바르지 않습니다.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo", {})
    if isinstance(fault, dict):
        fault_code = fault.get("errorCode", "확인 불가")
        fault_message = fault.get("message", "상세 오류 메시지가 없습니다.")
    else:
        fault_code = "확인 불가"
        fault_message = str(fault)

    st.error("🚨 KOBIS API에서 오류를 반환했습니다.")
    st.write(f"**오류 코드:** {fault_code}")
    st.write(f"**오류 내용:** {fault_message}")
    st.stop()

# --------------------------------------------------
# 6. 영화 목록 가져오기 및 데이터 정제
# --------------------------------------------------
box_office_result = data.get("boxOfficeResult", {})
movie_list = box_office_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning(f"{display_date}의 영화 목록이 비어 있습니다.")
    st.stop()

df = pd.DataFrame(movie_list)

required_columns = ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
for col in required_columns:
    if col not in df.columns:
        df[col] = 0

number_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in number_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

df["movieNm"] = df["movieNm"].fillna("영화명 없음")
df["openDt"] = df["openDt"].fillna("")
df = df.sort_values("rank").reset_index(drop=True)

# --------------------------------------------------
# 7. 1위 영화 지표 카드
# --------------------------------------------------
st.divider()
st.header("🏆 오늘의 주인공")

first_movie = df.iloc[0]
st.subheader(f"🥇 {first_movie['movieNm']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="당일 관객수", value=f"{first_movie['audiCnt']:,}명")
with col2:
    st.metric(label="누적 관객수", value=f"{first_movie['audiAcc']:,}명")
with col3:
    st.metric(label="스크린수", value=f"{first_movie['scrnCnt']:,}개")

# --------------------------------------------------
# 8. 관객수 상위 5편 막대그래프
# --------------------------------------------------
st.divider()
st.header("📊 관객수 상위 5편")

top5 = df.nlargest(5, "audiCnt").copy()
chart_df = top5[["movieNm", "audiCnt"]].copy()
chart_df = chart_df.sort_values("audiCnt", ascending=True)

# Streamlit 호환성을 위한 차트 설정
st.bar_chart(chart_df, x="movieNm", y="audiCnt")

# --------------------------------------------------
# 9. 전체 박스오피스 표
# --------------------------------------------------
st.divider()
st.header("🎞️ 전체 박스오피스 순위")

table_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

table_df["개봉일"] = table_df["개봉일"].replace("", "정보 없음")
for col in ["관객수", "누적관객", "스크린수"]:
    table_df[col] = table_df[col].map(lambda v: f"{v:,}")

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)

st.caption("데이터 출처: 영화진흥위원회(KOBIS) 일별 박스오피스 API")

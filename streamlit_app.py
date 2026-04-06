import pandas as pd
import streamlit as st
import requests
from io import StringIO

st.set_page_config(
    page_title="코스피/코스닥 시총 TOP100",
    page_icon="📈",
    layout="wide",
)

BASE_URL = "https://finance.naver.com/sise/sise_market_sum.naver"


@st.cache_data(ttl=60 * 30)
def get_top100_from_naver(market: str) -> pd.DataFrame:
    # KOSPI=0, KOSDAQ=1
    sosok = 0 if market == "KOSPI" else 1

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    all_rows = []

    # 네이버 금융 시총 페이지는 페이지네이션이 있어서
    # 1~4페이지 정도 수집하면 TOP100 확보 가능
    for page in range(1, 5):
        url = f"{BASE_URL}?sosok={sosok}&page={page}"

        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        r.encoding = "euc-kr"

        # HTML 표 읽기
        tables = pd.read_html(StringIO(r.text))
        df = tables[1]   # 보통 두 번째 표가 메인 데이터 표

        # 빈 줄 제거
        df = df.dropna(how="all")
        df = df[df["종목명"] != "종목명"]

        all_rows.append(df)

    df = pd.concat(all_rows, ignore_index=True)

    # 필요한 컬럼만 정리
    keep_cols = ["N", "종목명", "현재가", "전일비", "등락률", "액면가", "시가총액", "상장주식수", "외국인비율", "거래량", "PER", "ROE"]
    df = df[[c for c in keep_cols if c in df.columns]]

    # 순위 100위까지만
    if "N" in df.columns:
        df = df.rename(columns={"N": "순위"})
        df["순위"] = pd.to_numeric(df["순위"], errors="coerce")
        df = df.dropna(subset=["순위"])
        df["순위"] = df["순위"].astype(int)
        df = df[df["순위"] <= 100]

    return df.reset_index(drop=True)


st.title("📈 코스피 / 코스닥 시총 TOP100")

market = st.sidebar.radio(
    "시장 선택",
    ["KOSPI", "KOSDAQ"],
    format_func=lambda x: "코스피" if x == "KOSPI" else "코스닥"
)

search = st.text_input("종목명 검색", placeholder="예: 삼성, 에코, 알테오젠")

try:
    df = get_top100_from_naver(market)

    if search:
        df = df[df["종목명"].astype(str).str.contains(search, case=False, na=False)]

    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "CSV 다운로드",
        csv,
        file_name=f"{market.lower()}_top100.csv",
        mime="text/csv"
    )

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")

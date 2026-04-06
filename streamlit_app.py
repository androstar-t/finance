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

    # 페이지 1~4 수집하면 보통 TOP100 확보 가능
    for page in range(1, 5):
        url = f"{BASE_URL}?sosok={sosok}&page={page}"

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = "euc-kr"

        tables = pd.read_html(StringIO(response.text))
        if len(tables) < 2:
            raise ValueError("네이버 금융 표를 찾지 못했습니다.")

        df = tables[1]

        # 빈 행 제거
        df = df.dropna(how="all")

        # 헤더 중복행 제거
        if "종목명" in df.columns:
            df = df[df["종목명"] != "종목명"]

        all_rows.append(df)

    df = pd.concat(all_rows, ignore_index=True)

    # 필요한 컬럼만 남기기
    keep_cols = [
        "N", "종목명", "현재가", "전일비", "등락률",
        "액면가", "시가총액", "상장주식수", "외국인비율",
        "거래량", "PER", "ROE"
    ]
    df = df[[col for col in keep_cols if col in df.columns]]

    # 순위 컬럼 정리
    if "N" in df.columns:
        df = df.rename(columns={"N": "순위"})
        df["순위"] = pd.to_numeric(df["순위"], errors="coerce")
        df = df.dropna(subset=["순위"])
        df["순위"] = df["순위"].astype(int)
        df = df[df["순위"] <= 100]

    # 보기 좋게 다시 정렬
    ordered_cols = [
        "순위", "종목명", "현재가", "전일비", "등락률",
        "시가총액", "상장주식수", "거래량", "외국인비율",
        "PER", "ROE", "액면가"
    ]
    df = df[[col for col in ordered_cols if col in df.columns]]

    return df.reset_index(drop=True)


st.title("📈 코스피 / 코스닥 시가총액 TOP100")
st.caption("네이버 금융 기준 시가총액 상위 100개 종목")

with st.sidebar:
    market = st.radio(
        "시장 선택",
        ["KOSPI", "KOSDAQ"],
        format_func=lambda x: "코스피" if x == "KOSPI" else "코스닥"
    )

search = st.text_input("종목명 검색", placeholder="예: 삼성, 에코, 셀트리온")

try:
    df = get_top100_from_naver(market)

    if search:
        df = df[df["종목명"].astype(str).str.contains(search, case=False, na=False)]

    # CSV 다운로드 버튼을 표 위에 배치
    st.download_button(
        label="CSV 다운로드",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{market.lower()}_top100.csv",
        mime="text/csv"
    )

    # 100개가 한 번에 더 잘 보이도록 높이 크게 설정
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=3200
    )

    # 엑셀 복사용 텍스트
    excel_text = df.to_csv(index=False, sep="\t")

    st.subheader("📋 엑셀 복사용")
    st.text_area(
        "아래 내용을 복사해서 엑셀에 붙여넣기",
        value=excel_text,
        height=500
    )

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")

import datetime as dt
import pandas as pd
import streamlit as st
from pykrx import stock

st.set_page_config(
    page_title="KOSPI/KOSDAQ 시총 TOP100 현재 주가",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(ttl=60 * 10)
def get_latest_business_day_str() -> str:
    """가장 최근 영업일(오늘 포함)을 YYYYMMDD 형식으로 찾습니다."""
    today = dt.date.today()

    for offset in range(0, 15):
        target = today - dt.timedelta(days=offset)
        date_str = target.strftime("%Y%m%d")
        try:
            df = stock.get_market_cap(date_str, market="KOSPI")
            if df is not None and not df.empty:
                return date_str
        except Exception:
            pass

    raise RuntimeError("최근 영업일을 찾지 못했습니다.")


@st.cache_data(ttl=60 * 10)
def load_top100(market: str) -> pd.DataFrame:
    """선택한 시장의 시가총액 상위 100개 종목 데이터를 반환합니다."""
    date_str = get_latest_business_day_str()

    df = stock.get_market_cap(date_str, market=market).copy()
    if df.empty:
        raise ValueError(f"{market} 데이터가 비어 있습니다.")

    # 인덱스(티커)를 컬럼으로 이동
    df = df.reset_index().rename(columns={"티커": "종목코드"})

    # pykrx 버전에 따라 종목코드 컬럼명이 종목코드일 수 있어 보정
    if "종목코드" not in df.columns:
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "종목코드"})

    # 종목명 추가
    df["종목명"] = df["종목코드"].apply(stock.get_market_ticker_name)

    # 현재가(최근 종가) 추가
    price_df = stock.get_market_ohlcv(date_str, market=market).copy().reset_index()
    if "티커" in price_df.columns:
        price_df = price_df.rename(columns={"티커": "종목코드"})
    elif "종목코드" not in price_df.columns:
        first_col = price_df.columns[0]
        price_df = price_df.rename(columns={first_col: "종목코드"})

    keep_cols = [col for col in ["종목코드", "종가", "등락률", "거래량"] if col in price_df.columns]
    price_df = price_df[keep_cols]

    merged = pd.merge(df, price_df, on="종목코드", how="left")

    # 시총 기준 정렬 후 TOP100 추출
    merged = merged.sort_values("시가총액", ascending=False).head(100).copy()
    merged.insert(0, "순위", range(1, len(merged) + 1))

    # 표시용 컬럼 정리
    final_cols = [
        col for col in [
            "순위",
            "종목명",
            "종목코드",
            "종가",
            "등락률",
            "시가총액",
            "상장주식수",
            "거래량",
            "거래대금",
        ]
        if col in merged.columns
    ]
    merged = merged[final_cols]

    return merged, date_str


# --------- UI ---------
st.title("📈 코스피 / 코스닥 시총 TOP100 현재 주가")
st.caption("최근 영업일 기준으로 시가총액 상위 100개 종목과 현재가(종가)를 보여줍니다.")

with st.sidebar:
    st.header("조회 설정")
    market_label = st.radio(
        "시장 선택",
        options=["KOSPI", "KOSDAQ"],
        format_func=lambda x: "코스피" if x == "KOSPI" else "코스닥",
    )

    st.markdown("---")
    st.write("- 데이터 출처: KRX 기반 pykrx")
    st.write("- 표는 최근 영업일 기준")

try:
    top100_df, base_date = load_top100(market_label)

    market_kor = "코스피" if market_label == "KOSPI" else "코스닥"
    display_date = dt.datetime.strptime(base_date, "%Y%m%d").strftime("%Y-%m-%d")

    col1, col2, col3 = st.columns(3)
    col1.metric("선택 시장", market_kor)
    col2.metric("기준일", display_date)
    col3.metric("표시 종목 수", f"{len(top100_df)}개")

    st.subheader(f"{market_kor} 시가총액 상위 100개")

    search_text = st.text_input("종목명 검색", placeholder="예: 삼성, 에코, 셀트리온")

    filtered_df = top100_df.copy()
    if search_text:
        filtered_df = filtered_df[
            filtered_df["종목명"].astype(str).str.contains(search_text, case=False, na=False)
        ]

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "순위": st.column_config.NumberColumn("순위", format="%d"),
            "종목명": st.column_config.TextColumn("종목명"),
            "종목코드": st.column_config.TextColumn("종목코드"),
            "종가": st.column_config.NumberColumn("현재가(종가)", format="₩%d"),
            "등락률": st.column_config.NumberColumn("등락률(%)", format="%.2f%%"),
            "시가총액": st.column_config.NumberColumn("시가총액", format="₩%d"),
            "상장주식수": st.column_config.NumberColumn("상장주식수", format="%d"),
            "거래량": st.column_config.NumberColumn("거래량", format="%d"),
            "거래대금": st.column_config.NumberColumn("거래대금", format="₩%d"),
        },
    )

    csv_data = filtered_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="CSV 다운로드",
        data=csv_data,
        file_name=f"{market_label.lower()}_top100_{base_date}.csv",
        mime="text/csv",
    )

    st.info(
        "실시간 체결가가 아니라 최근 영업일 종가 기준입니다. 장중 실시간 데이터가 필요하면 KRX/OpenAPI 또는 증권사 API 연동으로 바꾸면 됩니다."
    )

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.warning("배포 환경에서 pykrx 호출이 일시적으로 실패할 수 있으니 잠시 후 새로고침해 보세요.")

import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime, timedelta, timezone

# 1. 페이지 설정
st.set_page_config(page_title="상삼 인베스트먼트 주도주 분석기", layout="wide")

# 2. 한국 시간 기준값 설정
kst = timezone(timedelta(hours=9))
default_now = datetime.now(kst)

# 3. 세션 상태 초기화 (사용자 선택값 보존용)
if 'target_date' not in st.session_state:
    st.session_state.target_date = default_now.date()
if 'target_time' not in st.session_state:
    st.session_state.target_time = default_now.time()

# 4. 섹터 정의
SECTOR_MAP = {
    '반도체': ['삼성전자', 'SK하이닉스', '한미반도체', '리노공업', 'HPSP', 'DB하이텍', '테크윙', '이오테크닉스', '가온칩스', '에이디테크놀로지'],
    '이차전지': ['LG에너지솔루션', '삼성SDI', '포스코퓨처엠', '에코프로비엠', '에코프로', '엘앤에프', '금양', '엔켐'],
    '자동차': ['현대차', '기아', '현대모비스', '현대위아', '성우하이텍', '서연이화'],
    '전력기기/변압기': ['HD현대일렉트릭', 'LS ELECTRIC', '효성중공업', '제룡전기', '산일전기', '일진전기'],
    '로봇/AI': ['두산로보틱스', '레인보우로보틱스', '솔트룩스', '알체라', '이스트소프트']
}

@st.cache_data(ttl=60)
def get_market_data(sosok=0):
    url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page=1"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        res.encoding = 'euc-kr'
        df = pd.read_html(StringIO(res.text))[1]
        df = df.dropna(subset=[df.columns[1]]) 
        return pd.DataFrame({
            '종목명': df.iloc[:, 1].values, '현재가': df.iloc[:, 2].values,
            '등락률': df.iloc[:, 4].values, '거래대금': df.iloc[:, 7].values, '외인비율': df.iloc[:, 10].values
        })
    except: return None

def process_and_score(df):
    df['등락률'] = df['등락률'].astype(str).str.replace('%', '').str.replace('+', '', regex=False).astype(float)
    df['거래대금'] = pd.to_numeric(df['거래대금'], errors='coerce').fillna(0)
    df['외인비율'] = df['외인비율'].astype(str).str.replace('%', '').astype(float)
    df['섹터'] = df['종목명'].apply(lambda x: next((k for k, v in SECTOR_MAP.items() if x in v), '기타'))
    df['Score'] = (df['등락률'] * 2.5) + (df['거래대금'] * 0.001) + (df['외인비율'] * 0.3)
    return df

# --- 사이드바: 입력 설정 ---
st.sidebar.header("🔍 분석 설정")

# key값을 지정하여 사용자의 입력을 세션 상태에 저장함
target_date = st.sidebar.date_input("분석 날짜", value=st.session_state.target_date, key='d_input')
target_time = st.sidebar.time_input("분석 시간", value=st.session_state.target_time, key='t_input')

# 선택된 값을 세션에 업데이트
st.session_state.target_date = target_date
st.session_state.target_time = target_time

if st.sidebar.button("🚀 분석 시작"):
    st.title(f"📈 주도주 분석 리포트")
    # 사용자가 선택한 시간이 정확히 출력됨
    st.info(f"분석 기준 시각: {st.session_state.target_date} {st.session_state.target_time.strftime('%H:%M')}")
    
    with st.spinner('데이터 분석 중...'):
        k_raw = get_market_data(0)
        kd_raw = get_market_data(1)

        if k_raw is not None and kd_raw is not None:
            combined = pd.concat([process_and_score(k_raw), process_and_score(kd_raw)])

            # [1] 시장 수급 상위
            st.subheader("📊 시장 수급 상황")
            tab1, tab2 = st.tabs(["KOSPI", "KOSDAQ"])
            with tab1: st.dataframe(combined[combined['종목명'].isin(k_raw['종목명'])].sort_values('거래대금', ascending=False).head(10)[['섹터', '종목명', '등락률', '거래대금']], use_container_width=True)
            with tab2: st.dataframe(combined[combined['종목명'].isin(kd_raw['종목명'])].sort_values('거래대금', ascending=False).head(10)[['섹터', '종목명', '등락률', '거래대금']], use_container_width=True)

            # [2] 주도 섹터 랭킹
            st.divider()
            sector_flow = combined[combined['섹터'] != '기타'].groupby('섹터')['거래대금'].sum().sort_values(ascending=False)
            st.subheader("🔥 자금 집중 주도 섹터 TOP 3")
            cols = st.columns(3)
            top_sectors = sector_flow.head(3).index.tolist()
            for i, sector in enumerate(top_sectors):
                cols[i].metric(f"{i+1}위: {sector}", f"{int(sector_flow[sector]):,} 억", "유입중")

            # [3] 기술적 분석 추천
            st.divider()
            st.subheader("💡 메이저 수급 및 기술적 분석 추천")
            for sector in top_sectors:
                with st.expander(f"★ {sector} 분석 결과", expanded=True):
                    recom = combined[combined['섹터'] == sector].sort_values('Score', ascending=False).head(5)
                    recom['신호'] = recom['등락률'].apply(lambda x: "⚡ 강세" if x > 4 else "📈 우상향")
                    st.table(recom[['종목명', '현재가', '등락률', '거래대금', '외인비율', '신호']])
    st.caption("※ 분석 데이터는 네이버 금융 실시간 시세를 기반으로 합니다.")
else:
    st.info("원하시는 과거 날짜와 시간을 선택한 후 [🚀 분석 시작] 버튼을 클릭해 주세요.")

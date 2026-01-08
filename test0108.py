import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 頁面配置 ---
st.set_page_config(page_title="科技感股票追蹤器 Pro", layout="wide")

# 深色主題 CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #161b22; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- 獲取即時匯率 (美金兌台幣) ---
@st.cache_data(ttl=3600)
def get_usd_twd():
    try:
        rate = yf.Ticker("TWD=X").history(period="1d")['Close'].iloc[-1]
        return rate
    except:
        return 32.0  # 預設保底匯率

usd_twd_rate = get_usd_twd()

# --- 初始化持股資料 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=['代號', '成本價', '股數', '幣別'])

# --- 側邊欄 ---
with st.sidebar:
    st.title("🚀 資產管理")
    with st.form("add_stock_form"):
        ticker_input = st.text_input("股票代號 (台股直接輸數字，美股輸代碼)", "").upper()
        # 自動處理台股格式
        if ticker_input.isdigit():
            ticker = f"{ticker_input}.TW"
            currency = "TWD"
        else:
            ticker = ticker_input
            currency = "USD" if ticker else "TWD"
            
        buy_price = st.number_input(f"成本價 ({currency})", min_value=0.01)
        shares = st.number_input("持有股數", min_value=1)
        submit = st.form_submit_button("加入持股")

        if submit and ticker:
            new_row = pd.DataFrame([[ticker, buy_price, shares, currency]], 
                                 columns=['代號', '成本價', '股數', '幣別'])
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row], ignore_index=True)
            st.success(f"已加入 {ticker}")

    st.info(f"當前參考匯率 USD/TWD: {usd_twd_rate:.2f}")

# --- 主畫面 ---
st.title("📊 全球資產損益看板")

if not st.session_state.portfolio.empty:
    total_twd_value = 0.0
    total_twd_profit = 0.0
    
    for idx, row in st.session_state.portfolio.iterrows():
        stock = yf.Ticker(row['代號'])
        hist = stock.history(period="1mo")
        if hist.empty: continue
        
        info = stock.info
        current_price = hist['Close'].iloc[-1]
        
        # 幣別轉換計算
        multiplier = usd_twd_rate if row['幣別'] == "USD" else 1.0
        
        market_value_local = current_price * row['股數']
        market_value_twd = market_value_local * multiplier
        cost_twd = (row['成本價'] * row['股數']) * multiplier
        profit_twd = market_value_twd - cost_twd
        pl_pct = (profit_twd / cost_twd) * 100
        
        total_twd_value += market_value_twd
        total_twd_profit += profit_twd

        # 顯示各股卡片
        with st.expander(f"📌 {row['代號']} | {info.get('shortName','')} ({row['幣別']})"):
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                # 顯示 Logo
                domain = info.get('website', '').replace('http://','').replace('https://','').split('/')[0]
                if domain: st.image(f"https://logo.clearbit.com/{domain}", width=60)
                st.write(f"**幣別:** {row['幣別']}")

            with col2:
                st.metric("現價", f"{current_price:.2f}")
                st.metric("換算台幣市值", f"NT$ {market_value_twd:,.0f}")
                
            with col3:
                st.metric("持有損益 (TWD)", f"{profit_twd:,.0f}", f"{pl_pct:.2f}%")
                st.write(f"**公司簡介:** {info.get('longBusinessSummary', '無資料')[:150]}...")

            # 趨勢圖
            fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], 
                            high=hist['High'], low=hist['Low'], close=hist['Close'])])
            fig.update_layout(template="plotly_dark", height=250, margin=dict(l=0,r=0,b=0,t=0))
            st.plotly_chart(fig, use_container_width=True)

    # --- 總結算 ---
    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("總資產價值 (換算台幣)", f"NT$ {total_twd_value:,.0f}")
    m2.metric("總累計損益 (換算台幣)", f"NT$ {total_twd_profit:,.0f}", 
              f"{(total_twd_profit/total_twd_value*100 if total_twd_value !=0 else 0):.2f}%")

else:
    st.info("請在側邊欄輸入股票資訊。台股範例：2330 / 美股範例：NVDA")
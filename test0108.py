import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. 頁面配置與深色風格 ---
st.set_page_config(page_title="科技感資產追蹤器", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1b212c; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }
    [data-testid="stExpander"] { background-color: #161b22; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 匯率獲取 (加入快取避免被封鎖) ---
@st.cache_data(ttl=3600)
def get_usd_twd_rate():
    try:
        # 抓取美金對台幣匯率
        data = yf.download("TWD=X", period="1d", interval="1m")
        if not data.empty:
            return data['Close'].iloc[-1]
        return 32.5 # 萬一失敗的保底匯率
    except:
        return 32.5

current_rate = get_usd_twd_rate()

# --- 3. 初始化 Session State ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=['代號', '成本價', '股數', '幣別'])

# --- 4. 側邊欄：輸入區 ---
with st.sidebar:
    st.title("🛰️ 持股倉位管理")
    with st.form("stock_input", clear_on_submit=True):
        raw_ticker = st.text_input("股票代號 (台股輸入數字, 美股輸入代碼)").upper().strip()
        
        # 自動判斷台美股
        if raw_ticker.isdigit():
            final_ticker = f"{raw_ticker}.TW"
            default_curr = "TWD"
        else:
            final_ticker = raw_ticker
            default_curr = "USD"
            
        buy_p = st.number_input(f"買入成本 ({default_curr})", min_value=0.0)
        shares = st.number_input("持有股數", min_value=1)
        
        if st.form_submit_button("🚀 加入/更新清單"):
            if final_ticker:
                new_data = pd.DataFrame([[final_ticker, buy_p, shares, default_curr]], 
                                       columns=['代號', '成本價', '股數', '幣別'])
                # 更新機制：若重複則覆蓋
                st.session_state.portfolio = pd.concat([
                    st.session_state.portfolio[st.session_state.portfolio['代號'] != final_ticker], 
                    new_data
                ], ignore_index=True)
                st.rerun()

    if st.button("🗑️ 清空所有數據"):
        st.session_state.portfolio = pd.DataFrame(columns=['代號', '成本價', '股數', '幣別'])
        st.rerun()
    
    st.write(f"📊 當前匯率 USD/TWD: **{current_rate:.2f}**")

# --- 5. 主畫面：資產總覽 ---
st.title("🌌 全球資產即時監測")

if st.session_state.portfolio.empty:
    st.info("目前清單空空如也，請先從左側選單加入股票。")
else:
    total_value_twd = 0.0
    total_profit_twd = 0.0
    
    # 用於最後統計的容器
    summary_placeholder = st.empty()
    st.divider()

    # 逐一處理持股
    for idx, row in st.session_state.portfolio.iterrows():
        t = row['代號']
        stock = yf.Ticker(t)
        
        # 抓取股價 (核心資料，若失敗則跳過該股)
        try:
            df = stock.history(period="1mo")
            if df.empty:
                st.warning(f"⚠️ 無法取得 {t} 股價資訊")
                continue
            now_price = df['Close'].iloc[-1]
        except:
            st.error(f"❌ 連接 Yahoo 失敗: {t}")
            continue

        # 抓取公司資訊 (非核心資料，失敗不影響計算)
        c_name = t
        c_desc = "暫無簡介（可能觸發 API 限制）"
        logo_url = ""
        try:
            info = stock.info
            c_name = info.get('longName', t)
            c_desc = info.get('longBusinessSummary', '無資料')[:200]
            domain = info.get('website', '').replace('http://','').replace('https://','').split('/')[0]
            logo_url = f"https://logo.clearbit.com/{domain}" if domain else ""
        except:
            pass # 保持預設值

        # 損益計算
        fx = current_rate if row['幣別'] == "USD" else 1.0
        val_twd = (now_price * row['股數']) * fx
        cost_twd = (row['成本價'] * row['股數']) * fx
        diff_twd = val_twd - cost_twd
        diff_pct = (diff_twd / cost_twd * 100) if cost_twd != 0 else 0
        
        total_value_twd += val_twd
        total_profit_twd += diff_twd

        # 顯示 UI
        with st.expander(f"📌 {c_name} ({t}) - 當前價: {now_price:.2f} {row['幣別']}"):
            col1, col2 = st.columns([1, 2])
            with col1:
                if logo_url: st.image(logo_url, width=80)
                st.metric("損益 (TWD)", f"{diff_twd:,.0f}", f"{diff_pct:.2f}%")
                st.write(f"**持倉:** {row['股數']} 股")
            with col2:
                st.write(f"**公司簡介:** {c_desc}...")
            
            # K 線圖
            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], 
                            high=df['High'], low=df['Low'], close=df['Close'])])
            fig.update_layout(template="plotly_dark", height=250, margin=dict(l=5,r=5,b=5,t=5))
            st.plotly_chart(fig, use_container_width=True)

    # 填充上方總結算區
    with summary_placeholder.container():
        c1, c2 = st.columns(2)
        c1.metric("總資產價值 (換算台幣)", f"NT$ {total_value_twd:,.0f}")
        c2.metric("預估總損益 (換算台幣)", f"NT$ {total_profit_twd:,.0f}", 
                  f"{(total_profit_twd/total_value_twd*100 if total_value_twd !=0 else 0):.2f}%")
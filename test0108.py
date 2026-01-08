import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. 頁面配置與深色風格 ---
st.set_page_config(page_title="Galaxy Stock Tracker", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1b212c; border-radius: 10px; padding: 15px; border: 1px solid #30363d; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    [data-testid="stExpander"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
    .stTextInput>div>div>input { background-color: #0e1117; color: white; border-color: #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 匯率獲取 (優化抓取邏輯) ---
@st.cache_data(ttl=1800) # 每半小時更新一次匯率
def get_usd_twd_rate():
    try:
        ticker = yf.Ticker("TWD=X")
        data = ticker.history(period="1d")
        if not data.empty:
            return data['Close'].iloc[-1]
        return 32.5
    except:
        return 32.5

current_rate = get_usd_twd_rate()

# --- 3. 初始化 Session State ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=['代號', '成本價', '股數', '幣別'])

# --- 4. 側邊欄 ---
with st.sidebar:
    st.title("🛰️ 持股管理中心")
    with st.form("stock_input", clear_on_submit=True):
        raw_ticker = st.text_input("股票代號", placeholder="例如: 2330 或 NVDA").upper().strip()
        
        # 自動識別
        if raw_ticker.isdigit():
            final_ticker = f"{raw_ticker}.TW"
            default_curr = "TWD"
        else:
            final_ticker = raw_ticker
            default_curr = "USD"
            
        buy_p = st.number_input(f"買入成本", min_value=0.0, format="%.2f")
        shares = st.number_input("持有股數", min_value=1, step=1)
        
        if st.form_submit_button("🚀 同步至終端"):
            if final_ticker:
                new_data = pd.DataFrame([[final_ticker, buy_p, shares, default_curr]], 
                                       columns=['代號', '成本價', '股數', '幣別'])
                st.session_state.portfolio = pd.concat([
                    st.session_state.portfolio[st.session_state.portfolio['代號'] != final_ticker], 
                    new_data
                ], ignore_index=True)
                st.rerun()

    if st.button("🗑️ 清空所有數據庫"):
        st.session_state.portfolio = pd.DataFrame(columns=['代號', '成本價', '股數', '幣別'])
        st.rerun()
    
    st.markdown(f"---")
    st.write(f"🌍 現時匯率 **1 USD = {current_rate:.2f} TWD**")

# --- 5. 主畫面 ---
st.title("🌌 全球資產即時監測終端")

if st.session_state.portfolio.empty:
    st.info("請從左側選單輸入代號以啟動追蹤系統。")
else:
    total_value_twd = 0.0
    total_profit_twd = 0.0
    
    summary_placeholder = st.empty()
    st.divider()

    # 執行進度條
    with st.spinner('正在同步全球股市數據...'):
        for idx, row in st.session_state.portfolio.iterrows():
            t = row['代號']
            stock = yf.Ticker(t)
            
            try:
                # 抓取股價與歷史
                df = stock.history(period="1mo")
                if df.empty: continue
                now_price = df['Close'].iloc[-1]
                
                # 安全獲取基本資料
                c_name, c_desc, logo_url = t, "無公司資訊", ""
                try:
                    info = stock.info
                    c_name = info.get('longName', t)
                    c_desc = info.get('longBusinessSummary', '暫無簡介')[:180]
                    domain = info.get('website', '').split('//')[-1].split('/')[0]
                    if domain: logo_url = f"https://logo.clearbit.com/{domain}"
                except: pass

                # 計算
                fx = current_rate if row['幣別'] == "USD" else 1.0
                val_twd = (now_price * row['股數']) * fx
                cost_twd = (row['成本價'] * row['股數']) * fx
                diff_twd = val_twd - cost_twd
                diff_pct = (diff_twd / cost_twd * 100) if cost_twd != 0 else 0
                
                total_value_twd += val_twd
                total_profit_twd += diff_twd

                # UI 渲染
                with st.expander(f"📌 {c_name} | {now_price:.2f} {row['幣別']}"):
                    c1, c2, c3 = st.columns([1, 1.5, 2.5])
                    with c1:
                        if logo_url: st.image(logo_url, width=70)
                        else: st.write("🏢")
                        st.caption(f"代號: {t}")
                    with c2:
                        st.metric("損益 (TWD)", f"{diff_twd:,.0f}", f"{diff_pct:.2f}%")
                        st.write(f"市值: NT$ {val_twd:,.0f}")
                    with c3:
                        st.write(f"**情報摘要:**")
                        st.write(f"{c_desc}...")

                    fig = go.Figure(data=[go.Candlestick(
                        x=df.index, open=df['Open'], high=df['High'], 
                        low=df['Low'], close=df['Close'],
                        increasing_line_color= '#00ff88', decreasing_line_color= '#ff3366'
                    )])
                    fig.update_layout(template="plotly_dark", height=250, margin=dict(l=0,r=0,b=0,t=0),
                                      xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"數據讀取失敗 {t}: {e}")

    # 顯示頂部總計
    with summary_placeholder.container():
        m1, m2 = st.columns(2)
        m1.metric("總資產現值 (TWD)", f"NT$ {total_value_twd:,.0f}")
        m2.metric("預估累計損益 (TWD)", f"NT$ {total_profit_twd:,.0f}", 
                  f"{(total_profit_twd/total_value_twd*100 if total_value_twd !=0 else 0):.2f}%")

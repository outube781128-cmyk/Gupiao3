import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- 1. 頁面配置與淺色風格 ---
st.set_page_config(page_title="股票資產追蹤器 (Light Mode)", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    /* 淺色背景與科技感元件 */
    .stApp { background-color: #f8f9fa; color: #212529; }
    .stMetric { 
        background-color: #ffffff; 
        border-radius: 12px; 
        padding: 20px; 
        border: 1px solid #dee2e6; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
    }
    [data-testid="stExpander"] { 
        background-color: #ffffff; 
        border: 1px solid #dee2e6; 
        border-radius: 10px; 
    }
    .stButton>button { border-radius: 20px; }
    h1, h2 { color: #003566; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 匯率獲取 ---
@st.cache_data(ttl=1800)
def get_usd_twd_rate():
    try:
        ticker = yf.Ticker("TWD=X")
        data = ticker.history(period="1d")
        return data['Close'].iloc[-1] if not data.empty else 32.5
    except:
        return 32.5

current_rate = get_usd_twd_rate()

# --- 3. 初始化 Session State ---
if 'portfolio' not in st.session_state:
    # 欄位：代號, 成本價, 股數, 幣別
    st.session_state.portfolio = pd.DataFrame(columns=['代號', '成本價', '股數', '幣別'])

# --- 4. 側邊欄 ---
with st.sidebar:
    st.header("➕ 新增持股")
    with st.form("stock_input", clear_on_submit=True):
        raw_ticker = st.text_input("股票代號", placeholder="例如: 2330 或 TSLA").upper().strip()
        
        if raw_ticker.isdigit():
            final_ticker, default_curr = f"{raw_ticker}.TW", "TWD"
        else:
            final_ticker, default_curr = raw_ticker, "USD"
            
        buy_p = st.number_input("平均成本", min_value=0.0, format="%.2f")
        shares = st.number_input("持有股數", min_value=1, step=1)
        
        if st.form_submit_button("確認加入"):
            if final_ticker:
                new_row = pd.DataFrame([[final_ticker, buy_p, shares, default_curr]], 
                                     columns=['代號', '成本價', '股數', '幣別'])
                # 更新機制
                st.session_state.portfolio = pd.concat([
                    st.session_state.portfolio[st.session_state.portfolio['代號'] != final_ticker], 
                    new_row
                ], ignore_index=True)
                st.rerun()
    
    st.write(f"💵 匯率參考: **1 USD = {current_rate:.2f} TWD**")

# --- 5. 主畫面 ---
st.title("🛡️ 投資組合追蹤系統")

if st.session_state.portfolio.empty:
    st.info("目前沒有持股數據。請利用左側選單新增股票。")
else:
    # 準備整理匯總表格的列表
    summary_list = []
    total_val_twd = 0.0
    total_prof_twd = 0.0

    # 頂部即時數據區
    col_stat1, col_stat2 = st.columns(2)
    stat_placeholder1 = col_stat1.empty()
    stat_placeholder2 = col_stat2.empty()

    st.subheader("📋 各股詳細趨勢")
    
    # 逐一處理持股
    for idx, row in st.session_state.portfolio.iterrows():
        t = row['代號']
        stock = yf.Ticker(t)
        
        try:
            df = stock.history(period="1mo")
            if df.empty: continue
            now_p = df['Close'].iloc[-1]
            
            # 計算損益
            fx = current_rate if row['幣別'] == "USD" else 1.0
            mkt_val_twd = (now_p * row['股數']) * fx
            cost_twd = (row['成本價'] * row['股數']) * fx
            p_l_twd = mkt_val_twd - cost_twd
            p_l_pct = (p_l_twd / cost_twd * 100) if cost_twd != 0 else 0
            
            total_val_twd += mkt_val_twd
            total_prof_twd += p_l_twd

            # 收集表格數據
            summary_list.append({
                "股票代號": t,
                "幣別": row['幣別'],
                "持有股數": row['股數'],
                "平均成本": f"{row['成本價']:.2f}",
                "目前市價": f"{now_p:.2f}",
                "損益 (TWD)": round(p_l_twd, 0),
                "報酬率 (%)": f"{p_l_pct:.2f}%"
            })

            # UI 面板
            with st.expander(f"📍 {t} - 現價: {now_p:.2f} {row['幣別']}"):
                c1, c2, c3 = st.columns([1.5, 2, 1])
                with c1:
                    st.metric("持有損益", f"{p_l_twd:,.0f} TWD", f"{p_l_pct:.2f}%")
                with c2:
                    # K線圖
                    fig = go.Figure(data=[go.Candlestick(
                        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']
                    )])
                    fig.update_layout(template="plotly_white", height=200, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                with c3:
                    # --- 刪除功能 ---
                    st.write("") 
                    if st.button(f"🗑️ 刪除 {t}", key=f"del_{t}"):
                        st.session_state.portfolio = st.session_state.portfolio[st.session_state.portfolio['代號'] != t]
                        st.rerun()

        except Exception as e:
            st.error(f"讀取 {t} 出錯")

    # 更新頂部指標
    stat_placeholder1.metric("總資產價值 (TWD)", f"NT$ {total_val_twd:,.0f}")
    stat_placeholder2.metric("總累計損益 (TWD)", f"NT$ {total_prof_twd:,.0f}", f"{(total_prof_twd/total_val_twd*100 if total_val_twd!=0 else 0):.2f}%")

    # --- 6. 底部匯總表格 ---
    st.divider()
    st.subheader("📊 投資組合彙整表")
    if summary_list:
        summary_df = pd.DataFrame(summary_list)
        # 設定顏色高亮
        def color_profit(val):
            if isinstance(val, (int, float)):
                color = '#d00000' if val < 0 else '#008000'
                return f'color: {color}'
            return ''
            
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    # 資產分佈圓餅圖
    st.write("")
    if summary_list:
        fig_pie = px.pie(summary_df, values='損益 (TWD)', names='股票代號', title='各股損益佔比圖', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_layout(template="plotly_white")
        st.plotly_chart(fig_pie, use_container_width=True)



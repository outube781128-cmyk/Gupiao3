import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px # 新增 Plotly Express 用於圓餅圖

# --- 1. 頁面配置與動態深色風格 ---
st.set_page_config(page_title="Galaxy Stock Tracker", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    /* 動態漸層背景 */
    body {
        background: linear-gradient(-45deg, #0e1117, #1a2233, #0a101d, #1f2a3a);
        background-size: 400% 400%;
        animation: gradientBG 15s ease infinite;
        color: #ffffff;
    }
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* Streamlit 元素基礎樣式 */
    .main { background-color: rgba(14, 17, 23, 0.7); border-radius: 10px; padding: 20px; box-shadow: 0 8px 16px rgba(0,0,0,0.5); }
    .stMetric { background-color: #1b212c; border-radius: 10px; padding: 15px; border: 1px solid #30363d; box-shadow: 0 4px 8px rgba(0,0,0,0.4); }
    [data-testid="stExpander"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 10px; }
    .stTextInput>div>div>input { background-color: #0e1117; color: white; border-color: #30363d; }
    .stButton>button { background-color: #2e86de; color: white; border: none; border-radius: 5px; padding: 10px 20px; font-weight: bold; }
    .stButton>button:hover { background-color: #1e6ec7; }
    h1, h2, h3, h4, h5, h6 { color: #00bcd4; } /* 標題顏色 */
    </style>
    """, unsafe_allow_html=True)

# --- 2. 匯率獲取 (加入快取避免被封鎖) ---
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
    st.markdown("---") # 分隔線
    st.markdown("💡 <span style='color:#00bcd4;'>輸入台股代號 (如: 2330) 將自動設為 TWD。</span>", unsafe_allow_html=True)
    st.markdown("💡 <span style='color:#00bcd4;'>輸入美股代號 (如: NVDA) 將自動設為 USD。</span>", unsafe_allow_html=True)


# --- 5. 主畫面：資產總覽與分佈圖 ---
st.title("🌌 全球資產即時監測終端")

if st.session_state.portfolio.empty:
    st.info("請從左側選單輸入代號以啟動追蹤系統。")
else:
    total_value_twd = 0.0
    total_profit_twd = 0.0
    
    # 用於資產分佈圖的資料
    currency_distribution = {"USD": 0.0, "TWD": 0.0}
    
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
                if df.empty: 
                    st.warning(f"⚠️ 無法取得 {t} 股價資訊或資料為空。")
                    continue
                now_price = df['Close'].iloc[-1]
                
                # 安全獲取基本資料
                c_name, c_desc, logo_url = t, "無公司資訊", ""
                try:
                    info = stock.info
                    c_name = info.get('longName', t)
                    c_desc = info.get('longBusinessSummary', '暫無簡介')[:180] + "..." if info.get('longBusinessSummary') else "暫無簡介"
                    domain = info.get('website', '').split('//')[-1].split('/')[0] if info.get('website') else ""
                    if domain: logo_url = f"https://logo.clearbit.com/{domain}"
                except: pass

                # 損益計算
                fx = current_rate if row['幣別'] == "USD" else 1.0
                val_twd = (now_price * row['股數']) * fx
                cost_twd = (row['成本價'] * row['股數']) * fx
                diff_twd = val_twd - cost_twd
                diff_pct = (diff_twd / cost_twd * 100) if cost_twd != 0 else 0
                
                total_value_twd += val_twd
                total_profit_twd += diff_twd

                # 更新資產分佈資料
                currency_distribution[row['幣別']] += val_twd

                # UI 渲染
                with st.expander(f"📌 {c_name} | {now_price:.2f} {row['幣別']}"):
                    c1, c2, c3 = st.columns([1, 1.5, 2.5])
                    with c1:
                        if logo_url: st.image(logo_url, width=70)
                        else: st.write("🏢")
                        st.caption(f"代號: {t}")
                    with c2:
                        st.metric("損益 (TWD)", f"{diff_twd:,.0f}", f"{diff_pct:.2f}%")
                        st.write(f"現值: NT$ {val_twd:,.0f}")
                    with c3:
                        st.write(f"**情報摘要:**")
                        st.markdown(f"<p style='font-size: 0.9em; color: #bbbbbb;'>{c_desc}</p>", unsafe_allow_html=True)

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
        col_total_1, col_total_2, col_pie = st.columns([1, 1, 1.2]) # 分割為三個欄位

        with col_total_1:
            st.metric("總資產現值 (TWD)", f"NT$ {total_value_twd:,.0f}")
        with col_total_2:
            st.metric("預估累計損益 (TWD)", f"NT$ {total_profit_twd:,.0f}", 
                      f"{(total_profit_twd/total_value_twd*100 if total_value_twd !=0 else 0):.2f}%")
        
        with col_pie:
            # 資產分佈圓餅圖
            pie_data = pd.DataFrame(currency_distribution.items(), columns=['幣別', '市值'])
            # 過濾掉市值為 0 的幣別，防止圓餅圖出錯
            pie_data = pie_data[pie_data['市值'] > 0] 

            if not pie_data.empty:
                fig_pie = px.pie(pie_data, values='市值', names='幣別', 
                                 title='資產幣別分佈',
                                 color_discrete_sequence=['#00bcd4', '#FF5733']) # 自訂顏色
                fig_pie.update_layout(template="plotly_dark", margin=dict(l=0,r=0,b=0,t=30), height=250,
                                      title_font_color="#00bcd4")
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("尚無資產分佈數據。")


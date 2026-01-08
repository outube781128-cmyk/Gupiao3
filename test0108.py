import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os

# --- 1. 頁面配置與風格 ---
st.set_page_config(page_title="全球全資產管理終端", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; color: #212529; }
    .stMetric { background-color: #ffffff; border-radius: 12px; padding: 20px; border: 1px solid #dee2e6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stExpander"] { background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 10px; }
    .logo-img { border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 持久化儲存邏輯 (CSV) ---
DB_FILE = "portfolio_db.csv"

def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=['代號', '自訂名稱', '成本價', '股數', '幣別', '模式', '手動市價'])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# --- 3. 匯率獲取 ---
@st.cache_data(ttl=3600)
def get_usd_twd():
    try:
        return yf.Ticker("TWD=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 32.5

usd_twd_rate = get_usd_twd()

# --- 4. 初始化數據 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# --- 5. 側邊欄 ---
with st.sidebar:
    st.title("🏛️ 資產終端")
    with st.form("input_form", clear_on_submit=True):
        raw_in = st.text_input("股票代號", placeholder="2330 / NVDA / 興櫃代碼").strip()
        c_name = st.text_input("公司名稱 (可填中文)")
        mode = st.selectbox("追蹤模式", ["自動 (Yahoo Finance)", "手動 (興櫃/自訂)"])
        
        if mode == "自動 (Yahoo Finance)":
            final_t, curr = (f"{raw_in}.TW", "TWD") if raw_in.isdigit() else (raw_in.upper(), "USD")
            manual_p = 0.0
        else:
            final_t, curr = raw_in, st.selectbox("幣別", ["TWD", "USD"])
            manual_p = st.number_input("目前市價 (手動)", min_value=0.0)

        buy_p = st.number_input("買入成本", min_value=0.0)
        shares = st.number_input("持有股數", min_value=1)
        
        if st.form_submit_button("存入數據庫"):
            if final_t:
                new_row = pd.DataFrame([[final_t, c_name, buy_p, shares, curr, mode, manual_p]], 
                                     columns=['代號', '自訂名稱', '成本價', '股數', '幣別', '模式', '手動市價'])
                st.session_state.portfolio = pd.concat([st.session_state.portfolio[st.session_state.portfolio['代號'] != final_t], new_row], ignore_index=True)
                save_data(st.session_state.portfolio) # 永久儲存
                st.rerun()

    if st.button("🔥 格式化所有數據"):
        st.session_state.portfolio = pd.DataFrame(columns=['代號', '自訂名稱', '成本價', '股數', '幣別', '模式', '手動市價'])
        save_data(st.session_state.portfolio)
        st.rerun()

# --- 6. 主畫面與數據運算 ---
st.title("🌌 投資組合全景追蹤")

if st.session_state.portfolio.empty:
    st.info("👋 歡迎！請在側邊欄登錄您的第一筆資產。資料將自動儲存於本地數據庫。")
else:
    summary_data = []
    total_val_twd = 0.0
    total_cost_twd = 0.0

    st.subheader("📋 個股詳細情報")
    
    for idx, row in st.session_state.portfolio.iterrows():
        t = row['代號']
        is_manual = row['模式'] == "手動 (興櫃/自訂)"
        now_p, disp_name, logo_url = 0.0, row['自訂名稱'], ""
        df_hist = pd.DataFrame()

        # 獲取價格與 Logo 邏輯
        if not is_manual:
            try:
                stock = yf.Ticker(t)
                df_hist = stock.history(period="1mo")
                if not df_hist.empty:
                    now_p = df_hist['Close'].iloc[-1]
                    info = stock.info
                    disp_name = disp_name or info.get('shortName') or t
                    domain = info.get('website', '').split('//')[-1].split('/')[0]
                    if domain: logo_url = f"https://logo.clearbit.com/{domain}"
            except: is_manual = True

        if is_manual:
            now_p = row['手動市價']
            disp_name = disp_name or t

        # 計算
        fx = usd_twd_rate if row['幣別'] == "USD" else 1.0
        m_val = (now_p * row['股數']) * fx
        c_val = (row['成本價'] * row['股數']) * fx
        profit = m_val - c_val
        roi = (profit / c_val * 100) if c_val != 0 else 0
        total_val_twd += m_val
        total_cost_twd += c_val

        # UI: 個股卡片
        with st.expander(f"{'🔴' if is_manual else '🔵'} {disp_name} ({t})"):
            c1, c2, c3 = st.columns([1, 3, 1])
            with c1:
                if logo_url: st.image(logo_url, width=80)
                st.metric("損益", f"{profit:,.0f} TWD", f"{roi:.2f}%")
            with c2:
                if not df_hist.empty:
                    fig = go.Figure(data=[go.Candlestick(x=df_hist.index, open=df_hist['Open'], high=df_hist['High'], low=df_hist['Low'], close=df_hist['Close'])])
                    fig.update_layout(template="plotly_white", height=180, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.write("手動模式無圖表")
            with c3:
                if st.button("🗑️ 刪除", key=f"d_{t}"):
                    st.session_state.portfolio = st.session_state.portfolio.drop(idx)
                    save_data(st.session_state.portfolio)
                    st.rerun()

        # 彙整表數據 (包含 Logo 網址)
        summary_data.append({
            "Logo": logo_url if logo_url else "🏢",
            "資產名稱": disp_name,
            "代號": t,
            "成本": row['成本價'],
            "現價": now_p,
            "損益 (TWD)": round(profit, 0),
            "報酬率": f"{roi:.2f}%"
        })

    # 總指標
    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("總市值 (TWD)", f"NT$ {total_val_twd:,.0f}")
    t_roi = (total_val_twd - total_cost_twd) / total_cost_twd * 100 if total_cost_twd != 0 else 0
    m2.metric("累計損益", f"NT$ {(total_val_twd - total_cost_twd):,.0f}", f"{t_roi:.2f}%")

    # --- 最終匯總表 (帶有 Logo 顯示) ---
    st.subheader("📊 投資組合彙整清單")
    summary_df = pd.DataFrame(summary_data)
    
    # 使用 st.column_config 在表格中渲染圖片
    st.dataframe(
        summary_df,
        column_config={
            "Logo": st.column_config.ImageColumn("標誌", help="公司 Logo"),
            "損益 (TWD)": st.column_config.NumberColumn(format="%d"),
        },
        use_container_width=True,
        hide_index=True
    )
    
    # 分佈圖
    fig_pie = px.pie(summary_df, values='損益 (TWD)', names='資產名稱', hole=0.4, title="資產獲利分佈")
    st.plotly_chart(fig_pie, use_container_width=True)


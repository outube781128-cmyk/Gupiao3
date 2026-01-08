import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os

# --- 1. 頁面配置與風格 ---
st.set_page_config(page_title="全球資產即時監控中心", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; color: #212529; }
    .stMetric { background-color: #ffffff; border-radius: 12px; padding: 20px; border: 1px solid #dee2e6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stExpander"] { background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 10px; }
    .stDataFrame { background-color: #ffffff; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 持久化儲存 (CSV) ---
DB_FILE = "portfolio_db.csv"

def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=['代號', '自訂名稱', '成本價', '股數', '幣別', '模式', '手動市價'])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# --- 3. 即時匯率獲取 (追蹤最新匯價) ---
@st.cache_data(ttl=300) # 每 5 分鐘自動更新一次最新匯率
def get_live_usd_twd():
    try:
        # 抓取即時匯率 (TWD=X)
        ticker = yf.Ticker("TWD=X")
        # 抓取最近 1 天內、1 分鐘層級的資料
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            # 取得最後一筆成交價
            return data['Close'].iloc[-1]
        return 32.5
    except:
        return 32.5

latest_rate = get_live_usd_twd()

# --- 4. 初始化 Session State ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# --- 5. 側邊欄：資產登錄 ---
with st.sidebar:
    st.title("🏛️ 資產終端")
    st.markdown(f"🕒 **即時匯率 USD/TWD: `{latest_rate:.4f}`**")
    
    with st.form("input_form", clear_on_submit=True):
        raw_in = st.text_input("股票代號", placeholder="台股數字 / 美股代碼 / 興櫃號碼").strip()
        c_name = st.text_input("公司名稱 (可填中文)")
        
        is_numeric = raw_in.isdigit()
        mode = st.selectbox("追蹤模式", ["自動 (Yahoo Finance)", "手動 (興櫃/自訂)"])
        
        if mode == "自動 (Yahoo Finance)":
            if is_numeric:
                final_t, curr = f"{raw_in}.TW", "TWD"
            else:
                final_t, curr = raw_in.upper(), "USD"
            manual_p = 0.0
        else:
            final_t = raw_in
            if is_numeric:
                curr = "TWD"
                st.caption("✅ 已自動設為台幣計價")
            else:
                curr = st.selectbox("計價幣別", ["USD", "TWD"])
            manual_p = st.number_input("目前市價 (補登)", min_value=0.0, format="%.2f")

        buy_p = st.number_input("平均買入成本", min_value=0.0, format="%.2f")
        shares = st.number_input("持有股數", min_value=1, step=1)
        
        if st.form_submit_button("🚀 存入數據庫"):
            if final_t:
                new_row = pd.DataFrame([[final_t, c_name, buy_p, shares, curr, mode, manual_p]], 
                                     columns=['代號', '自訂名稱', '成本價', '股數', '幣別', '模式', '手動市價'])
                st.session_state.portfolio = pd.concat([st.session_state.portfolio[st.session_state.portfolio['代號'] != final_t], new_row], ignore_index=True)
                save_data(st.session_state.portfolio)
                st.rerun()

    if st.button("🗑️ 清空數據"):
        st.session_state.portfolio = pd.DataFrame(columns=['代號', '自訂名稱', '成本價', '股數', '幣別', '模式', '手動市價'])
        save_data(st.session_state.portfolio)
        st.rerun()

# --- 6. 主畫面運算 ---
st.title("🌌 投資全景監控")

if st.session_state.portfolio.empty:
    st.info("👋 系統就緒。請在側邊欄登錄資產，匯率每 5 分鐘自動同步最新報價。")
else:
    summary_data = []
    total_val_twd, total_cost_twd = 0.0, 0.0

    st.subheader("📑 詳細持股報告")
    
    for idx, row in st.session_state.portfolio.iterrows():
        t = row['代號']
        is_manual = row['模式'] == "手動 (興櫃/自訂)"
        now_p, disp_name, logo_url = 0.0, row['自訂名稱'], ""
        df_hist = pd.DataFrame()

        # 獲取價格與 Logo
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
                else: is_manual = True
            except: is_manual = True

        if is_manual:
            now_p = row['手動市價']
            disp_name = disp_name or t

        # 即時損益計算 (美金資產使用最新匯率換算)
        fx = latest_rate if row['幣別'] == "USD" else 1.0
        m_val_twd = (now_p * row['股數']) * fx
        c_val_twd = (row['成本價'] * row['股數']) * fx
        profit_twd = m_val_twd - c_val_twd
        roi = (profit_twd / c_val_twd * 100) if c_val_twd != 0 else 0
        
        total_val_twd += m_val_twd
        total_cost_twd += c_val_twd

        # 渲染單股 Expander
        with st.expander(f"{'🔴' if is_manual else '🔵'} {disp_name} ({t})"):
            c1, c2, c3 = st.columns([1, 3, 1.2])
            with c1:
                if logo_url: st.image(logo_url, width=60)
                st.metric("損益 (TWD)", f"{profit_twd:,.0f}", f"{roi:.2f}%")
            with c2:
                if not df_hist.empty:
                    fig = go.Figure(data=[go.Candlestick(x=df_hist.index, open=df_hist['Open'], high=df_hist['High'], low=df_hist['Low'], close=df_hist['Close'])])
                    fig.update_layout(template="plotly_white", height=180, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.caption("手動模式/興櫃股：無即時圖表")
            with c3:
                if is_manual:
                    new_p = st.number_input("更新市價", value=float(now_p), key=f"p_{t}")
                    if st.button("💾 更新", key=f"b_{t}"):
                        st.session_state.portfolio.at[idx, '手動市價'] = new_p
                        save_data(st.session_state.portfolio)
                        st.rerun()
                if st.button("🗑️ 刪除", key=f"d_{t}"):
                    st.session_state.portfolio = st.session_state.portfolio.drop(idx)
                    save_data(st.session_state.portfolio)
                    st.rerun()

        summary_data.append({
            "Logo": logo_url if logo_url else "🏢",
            "名稱": disp_name,
            "代號": t,
            "幣別": row['幣別'],
            "成本": row['成本價'],
            "現價": now_p,
            "損益 (TWD)": round(profit_twd, 0),
            "報酬率": f"{roi:.2f}%"
        })

    # 總結結算
    st.divider()
    col_a, col_b = st.columns(2)
    col_a.metric("總市值 (台幣折算)", f"NT$ {total_val_twd:,.0f}")
    t_roi = (total_val_twd - total_cost_twd) / total_cost_twd * 100 if total_cost_twd != 0 else 0
    col_b.metric("累計總損益", f"NT$ {(total_val_twd - total_cost_twd):,.0f}", f"{t_roi:.2f}%")

    # --- 最終匯總表 (帶 Logo) ---
    st.subheader("📊 投資組合彙整清單")
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(
        summary_df,
        column_config={
            "Logo": st.column_config.ImageColumn("標誌"),
            "現價": st.column_config.NumberColumn(format="%.2f"),
            "損益 (TWD)": st.column_config.NumberColumn(format="%d"),
        },
        use_container_width=True, hide_index=True
    )
    
    # 佔比圖
    fig_pie = px.pie(summary_df, values='損益 (TWD)', names='名稱', hole=0.3, title="獲利貢獻分佈")
    st.plotly_chart(fig_pie, use_container_width=True)


import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import requests
from bs4 import BeautifulSoup

# --- 1. 頁面配置與視覺風格 ---
st.set_page_config(page_title="全球資產即時監控中心", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; color: #212529; }
    .stMetric { background-color: #ffffff; border-radius: 12px; padding: 20px; border: 1px solid #dee2e6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    [data-testid="stExpander"] { background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 10px; margin-bottom: 10px; }
    .comp-name { font-size: 1.3rem; font-weight: 700; color: #1a365d; }
    .ticker-tag { background-color: #edf2f7; padding: 2px 8px; border-radius: 6px; font-family: monospace; color: #4a5568; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心功能：台股中文名稱與智慧 Logo 抓取 ---
@st.cache_data(ttl=86400)
def fetch_tw_stock_name(ticker_id):
    """從雅虎奇摩股市爬取中文簡稱"""
    clean_id = ticker_id.split('.')[0]
    url = f"https://tw.stock.yahoo.com/quote/{clean_id}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        name_tag = soup.find('h1', class_='C($c-link-text)')
        return name_tag.get_text().strip() if name_tag else None
    except:
        return None

def get_smart_logo(ticker_obj, ticker_id):
    """智慧偵測 Logo 連結"""
    try:
        # 優先從 Yahoo 提供的官網抓取
        domain = ticker_obj.info.get('website', '').split('//')[-1].split('/')[0]
        if domain: return f"https://logo.clearbit.com/{domain}"
    except: pass
    
    # 美股嘗試直接用代號.com
    if not ticker_id.isdigit() and ".TW" not in ticker_id:
        simple_id = ticker_id.split('.')[0].lower()
        return f"https://logo.clearbit.com/{simple_id}.com"
    return ""

# --- 3. 數據庫與匯率處理 ---
DB_FILE = "portfolio_master.csv"

def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        required = ['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價', 'Logo連結']
        for col in required:
            if col not in df.columns: df[col] = ""
        return df
    return pd.DataFrame(columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價', 'Logo連結'])

def save_db(df):
    df.to_csv(DB_FILE, index=False)

@st.cache_data(ttl=300)
def get_live_fx():
    try:
        data = yf.Ticker("TWD=X").history(period="1d", interval="1m")
        return data['Close'].iloc[-1] if not data.empty else 32.5
    except: return 32.5

live_fx = get_live_fx()

# --- 4. 初始化 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_db()

# --- 5. 側邊欄：資產管理 ---
with st.sidebar:
    st.title("🏛️ 資產配置")
    st.info(f"💵 即時匯率 USD/TWD: **{live_fx:.4f}**")
    
    with st.form("main_form", clear_on_submit=True):
        raw_id = st.text_input("股票代號", placeholder="例如: 2330 / 8069 / NVDA").strip()
        c_name = st.text_input("自訂名稱 (選填)", placeholder="留空將自動搜尋中文")
        c_logo = st.text_input("自訂 Logo 網址 (選填)", placeholder="可貼上圖片網址")
        
        is_tw = raw_id.isdigit() or raw_id.upper().endswith(('.TW', '.TWO'))
        mode = st.selectbox("模式", ["自動 (Yahoo Finance)", "手動 (興櫃/自訂)"])
        
        if mode == "自動 (Yahoo Finance)":
            final_ticker = f"{raw_id}.TW" if raw_id.isdigit() else raw_id.upper()
            currency = "TWD" if is_tw else "USD"
            manual_p = 0.0
        else:
            final_ticker = raw_id
            currency = "TWD" if is_tw else st.selectbox("幣別", ["TWD", "USD"])
            manual_p = st.number_input("目前市價 (補登)", min_value=0.0)

        buy_price = st.number_input("平均成本", min_value=0.0)
        shares = st.number_input("持有股數", min_value=1, step=1)
        
        if st.form_submit_button("🚀 加入投資組合"):
            if final_ticker:
                # 1. 抓取名稱
                if c_name: final_name = c_name
                elif is_tw:
                    with st.spinner('搜尋中文名稱...'):
                        final_name = fetch_tw_stock_name(raw_id) or final_ticker
                else:
                    try: final_name = yf.Ticker(final_ticker).info.get('shortName', final_ticker)
                    except: final_name = final_ticker
                
                # 2. 抓取 Logo
                if c_logo: final_logo = c_logo
                else: final_logo = get_smart_logo(yf.Ticker(final_ticker), final_ticker)

                new_row = pd.DataFrame([[final_ticker, final_name, buy_price, shares, currency, mode, manual_p, final_logo]], 
                                     columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價', 'Logo連結'])
                st.session_state.portfolio = pd.concat([
                    st.session_state.portfolio[st.session_state.portfolio['代號'] != final_ticker], 
                    new_row], ignore_index=True)
                save_db(st.session_state.portfolio)
                st.rerun()

    if st.button("🔥 清空數據"):
        st.session_state.portfolio = pd.DataFrame(columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價', 'Logo連結'])
        save_db(st.session_state.portfolio)
        st.rerun()

# --- 6. 主畫面顯示 ---
st.title("🛡️ 全球資產即時監控")

if st.session_state.portfolio.empty:
    st.info("👋 歡迎！請在左側登錄資產。輸入代號後，系統會自動處理中文名稱與 Logo。")
else:
    summary_data = []
    total_mkt_twd, total_cost_twd = 0.0, 0.0

    for idx, row in st.session_state.portfolio.iterrows():
        t, is_man = row['代號'], row['模式'] == "手動 (興櫃/自訂)"
        now_p, logo_url, hist_df = 0.0, row['Logo連結'], pd.DataFrame()

        if not is_man:
            try:
                stock = yf.Ticker(t)
                hist_df = stock.history(period="1mo")
                if not hist_df.empty: now_p = hist_df['Close'].iloc[-1]
                else: is_man = True
            except: is_man = True

        if is_man: now_p = row['手動市價']

        # 換算損益
        fx = live_fx if row['幣別'] == "USD" else 1.0
        m_val = (now_p * row['股數']) * fx
        c_val = (row['成本價'] * row['股數']) * fx
        profit = m_val - c_val
        roi = (profit / c_val * 100) if c_val != 0 else 0
        total_mkt_twd += m_val
        total_cost_twd += c_val

        with st.expander(f"{row['名稱']} ({t})"):
            st.markdown(f"<span class='comp-name'>{row['名稱']}</span> <span class='ticker-tag'>{t}</span>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns([1, 2.5, 1.2])
            with c1:
                if logo_url: st.image(logo_url, width=65)
                st.metric("損益 (TWD)", f"{profit:,.0f}", f"{roi:.2f}%")
                st.caption(f"計價: {row['幣別']}")
            with c2:
                if not hist_df.empty:
                    fig = go.Figure(data=[go.Candlestick(x=hist_df.index, open=hist_df['Open'], high=hist_df['High'], low=hist_df['Low'], close=hist_df['Close'])])
                    fig.update_layout(template="plotly_white", height=180, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
            with c3:
                if is_man:
                    new_p = st.number_input("更新市價", value=float(now_p), key=f"p_{t}")
                    if st.button("💾 更新", key=f"b_{t}"):
                        st.session_state.portfolio.at[idx, '手動市價'] = new_p
                        save_db(st.session_state.portfolio)
                        st.rerun()
                if st.button("🗑️ 刪除", key=f"d_{idx}"):
                    st.session_state.portfolio = st.session_state.portfolio.drop(idx)
                    save_db(st.session_state.portfolio)
                    st.rerun()

        summary_data.append({"Logo": logo_url if logo_url else "🏢", "名稱": row['名稱'], "代號": t, "成本": row['成本價'], "現價": now_p, "損益(TWD)": round(profit, 0), "報酬率": f"{roi:.2f}%"})

    # --- 總結算 ---
    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("總市值 (折算台幣)", f"NT$ {total_mkt_twd:,.0f}")
    t_roi = (total_mkt_twd - total_cost_twd) / total_cost_twd * 100 if total_cost_twd != 0 else 0
    m2.metric("總累計損益", f"NT$ {(total_mkt_twd - total_cost_twd):,.0f}", f"{t_roi:.2f}%")

    st.subheader("📊 投資組合清單")
    st.dataframe(pd.DataFrame(summary_data), column_config={"Logo": st.column_config.ImageColumn("標誌"), "損益(TWD)": st.column_config.NumberColumn(format="%d")}, use_container_width=True, hide_index=True)
    st.plotly_chart(px.pie(pd.DataFrame(summary_data), values='損益(TWD)', names='名稱', hole=0.3, title="資產獲利分佈"), use_container_width=True)

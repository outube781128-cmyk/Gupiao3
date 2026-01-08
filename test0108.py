import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import requests
from bs4 import BeautifulSoup

# --- 1. 頁面配置 ---
st.set_page_config(page_title="全球資產即時監控", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; color: #212529; }
    /* 加強置頂卡片的視覺效果 */
    .stMetric { 
        background-color: #ffffff; 
        border-radius: 12px; 
        padding: 25px; 
        border: 2px solid #e9ecef; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.08); 
    }
    [data-testid="stExpander"] { background-color: #ffffff; border-radius: 10px; margin-bottom: 8px; }
    .comp-name { font-size: 1.2rem; font-weight: 700; color: #1a365d; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心功能模組 ---
@st.cache_data(ttl=86400)
def fetch_tw_stock_name(ticker_id):
    clean_id = ticker_id.split('.')[0]
    url = f"https://tw.stock.yahoo.com/quote/{clean_id}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        name_tag = soup.find('h1', class_='C($c-link-text)')
        return name_tag.get_text().strip() if name_tag else None
    except: return None

def get_smart_logo(ticker_obj, ticker_id):
    try:
        domain = ticker_obj.info.get('website', '').split('//')[-1].split('/')[0]
        if domain: return f"https://logo.clearbit.com/{domain}"
    except: pass
    if not ticker_id.isdigit() and ".TW" not in ticker_id:
        return f"https://logo.clearbit.com/{ticker_id.split('.')[0].lower()}.com"
    return ""

DB_FILE = "portfolio_master.csv"
def load_db():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        for col in ['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價', 'Logo連結']:
            if col not in df.columns: df[col] = ""
        return df
    return pd.DataFrame(columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價', 'Logo連結'])

def save_db(df): df.to_csv(DB_FILE, index=False)

@st.cache_data(ttl=300)
def get_live_fx():
    try:
        data = yf.Ticker("TWD=X").history(period="1d", interval="1m")
        return data['Close'].iloc[-1] if not data.empty else 32.5
    except: return 32.5

# --- 3. 數據預處理 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_db()

live_fx = get_live_fx()

# --- 4. 側邊欄 ---
with st.sidebar:
    st.title("🏛️ 配置終端")
    st.write(f"💵 匯率 USD/TWD: **{live_fx:.4f}**")
    with st.form("input_form", clear_on_submit=True):
        raw_id = st.text_input("股票代號", placeholder="例如: 2330, 8069, NVDA").strip()
        c_name = st.text_input("自訂名稱 (選填)")
        c_logo = st.text_input("自訂 Logo 網址 (選填)")
        is_tw = raw_id.isdigit() or raw_id.upper().endswith(('.TW', '.TWO'))
        mode = st.selectbox("模式", ["自動", "手動"])
        
        final_ticker = f"{raw_id}.TW" if raw_id.isdigit() else raw_id.upper()
        currency = "TWD" if is_tw else "USD"
        
        buy_p = st.number_input("平均成本", min_value=0.0)
        qty = st.number_input("股數", min_value=1)
        manual_p = st.number_input("目前市價 (手動模式才有效)", min_value=0.0)
        
        if st.form_submit_button("🚀 加入組合"):
            if final_ticker:
                if c_name: final_name = c_name
                elif is_tw: final_name = fetch_tw_stock_name(raw_id) or final_ticker
                else:
                    try: final_name = yf.Ticker(final_ticker).info.get('shortName', final_ticker)
                    except: final_name = final_ticker
                
                final_logo = c_logo if c_logo else get_smart_logo(yf.Ticker(final_ticker), final_ticker)
                
                new_row = pd.DataFrame([[final_ticker, final_name, buy_p, qty, currency, mode, manual_p, final_logo]], 
                                     columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價', 'Logo連結'])
                st.session_state.portfolio = pd.concat([st.session_state.portfolio[st.session_state.portfolio['代號'] != final_ticker], new_row], ignore_index=True)
                save_db(st.session_state.portfolio)
                st.rerun()

    if st.button("🔥 清空數據"):
        st.session_state.portfolio = pd.DataFrame(columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價', 'Logo連結'])
        save_db(st.session_state.portfolio)
        st.rerun()

# --- 5. 主畫面：計算與顯示 ---
st.title("🛡️ 全球資產監控儀表板")

if st.session_state.portfolio.empty:
    st.info("👋 請在左側側邊欄開始登錄您的第一筆資產。")
else:
    # --- 關鍵：先計算數據，再顯示 ---
    summary_list = []
    total_mkt_twd = 0.0
    total_cost_twd = 0.0

    for idx, row in st.session_state.portfolio.iterrows():
        t = row['代號']
        is_man = row['模式'] == "手動"
        now_p = 0.0
        hist_df = pd.DataFrame()

        if not is_man:
            try:
                stock = yf.Ticker(t)
                hist_df = stock.history(period="1mo")
                if not hist_df.empty: now_p = hist_df['Close'].iloc[-1]
                else: is_man = True
            except: is_man = True
        
        if is_man: now_p = row['手動市價']

        fx = live_fx if row['幣別'] == "USD" else 1.0
        m_val = (now_p * row['股數']) * fx
        c_val = (row['成本價'] * row['股數']) * fx
        profit = m_val - c_val
        roi = (profit / c_val * 100) if c_val != 0 else 0
        
        total_mkt_twd += m_val
        total_cost_twd += c_val

        summary_list.append({
            "idx": idx, "代號": t, "名稱": row['名稱'], "Logo": row['Logo連結'],
            "現價": now_p, "損益": profit, "報酬率": roi, "歷史資料": hist_df,
            "幣別": row['幣別'], "模式": row['模式']
        })

    # --- TOP METRICS (置頂核心數據) ---
    m1, m2 = st.columns(2)
    with m1:
        st.metric("💰 總資產市值 (TWD)", f"NT$ {total_mkt_twd:,.0f}")
    with m2:
        total_profit = total_mkt_twd - total_cost_twd
        total_roi = (total_profit / total_cost_twd * 100) if total_cost_twd != 0 else 0
        st.metric("📈 總累計損益", f"NT$ {total_profit:,.0f}", f"{total_roi:.2f}%")
    
    st.divider()

    # --- 持股詳情 ---
    st.subheader("📑 即時持股明細")
    for item in summary_list:
        with st.expander(f"{item['名稱']} ({item['代號']})"):
            c1, c2, c3 = st.columns([1, 2.5, 1.2])
            with c1:
                if item['Logo']: st.image(item['Logo'], width=65)
                st.metric("損益", f"{item['損益']:,.0f} TWD", f"{item['報酬率']:.2f}%")
            with c2:
                if not item['歷史資料'].empty:
                    fig = go.Figure(data=[go.Candlestick(x=item['歷史資料'].index, open=item['歷史資料']['Open'], high=item['歷史資料']['High'], low=item['歷史資料']['Low'], close=item['歷史資料']['Close'])])
                    fig.update_layout(template="plotly_white", height=180, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
            with c3:
                if st.button("🗑️ 刪除", key=f"del_{item['idx']}"):
                    st.session_state.portfolio = st.session_state.portfolio.drop(item['idx'])
                    save_db(st.session_state.portfolio)
                    st.rerun()

    # --- 彙整表與圖表 ---
    st.divider()
    sum_df = pd.DataFrame(summary_list).drop(columns=['歷史資料', 'idx'])
    st.dataframe(sum_df, column_config={"Logo": st.column_config.ImageColumn("標誌")}, use_container_width=True, hide_index=True)
    st.plotly_chart(px.pie(sum_df, values='損益', names='名稱', hole=0.3, title="獲利組成佔比"), use_container_width=True)

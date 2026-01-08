import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import requests
from bs4 import BeautifulSoup

# --- 1. 頁面配置與自定義樣式 ---
st.set_page_config(page_title="全球資產即時監控中心", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; color: #212529; }
    .stMetric { background-color: #ffffff; border-radius: 12px; padding: 18px; border: 1px solid #dee2e6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    [data-testid="stExpander"] { background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 10px; margin-bottom: 10px; }
    .comp-name { font-size: 1.3rem; font-weight: 700; color: #1a365d; }
    .ticker-tag { background-color: #edf2f7; padding: 2px 8px; border-radius: 6px; font-family: monospace; color: #4a5568; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 功能核心：自動抓取台股中文名稱 ---
@st.cache_data(ttl=86400) # 名稱快取 24 小時
def fetch_tw_stock_name(ticker_id):
    """
    爬取雅虎奇摩股市獲取正確的中文簡稱
    """
    clean_id = ticker_id.split('.')[0]
    url = f"https://tw.stock.yahoo.com/quote/{clean_id}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # 抓取 H1 標籤中的公司名稱
        name_tag = soup.find('h1', class_='C($c-link-text)')
        return name_tag.get_text().strip() if name_tag else None
    except:
        return None

# --- 3. 數據持久化與匯率 ---
DB_FILE = "portfolio_data.csv"

def load_db():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價'])

def save_db(df):
    df.to_csv(DB_FILE, index=False)

@st.cache_data(ttl=300) # 匯率 5 分鐘更新一次
def get_live_rate():
    try:
        data = yf.Ticker("TWD=X").history(period="1d", interval="1m")
        return data['Close'].iloc[-1] if not data.empty else 32.5
    except: return 32.5

live_fx = get_live_rate()

# --- 4. 初始化數據 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_db()

# --- 5. 側邊欄：資產登錄 ---
with st.sidebar:
    st.title("🏛️ 資產終端")
    st.info(f"💵 即時匯率 USD/TWD: **{live_fx:.4f}**")
    
    with st.form("add_asset_form", clear_on_submit=True):
        raw_id = st.text_input("股票代號", placeholder="例如: 2330 / 8069 / NVDA").strip()
        manual_name = st.text_input("自訂名稱 (選填)", placeholder="若留空將自動搜尋中文名")
        
        # 台股判定 (.TW / .TWO / 純數字)
        is_tw = raw_id.isdigit() or raw_id.upper().endswith(('.TW', '.TWO'))
        track_mode = st.selectbox("模式", ["自動 (Yahoo Finance)", "手動 (興櫃/自訂)"])
        
        if track_mode == "自動 (Yahoo Finance)":
            final_ticker = f"{raw_id}.TW" if raw_id.isdigit() else raw_id.upper()
            currency = "TWD" if is_tw else "USD"
            m_price = 0.0
        else:
            final_ticker = raw_id
            currency = "TWD" if is_tw else st.selectbox("結算幣別", ["TWD", "USD"])
            m_price = st.number_input("目前市價 (補登)", min_value=0.0)

        cost_price = st.number_input("平均成本", min_value=0.0)
        share_qty = st.number_input("持有股數", min_value=1, step=1)
        
        if st.form_submit_button("🚀 存入我的投資組合"):
            if final_ticker:
                # 智慧名稱搜尋邏輯
                if manual_name:
                    final_name = manual_name
                elif is_tw:
                    with st.spinner(f'正在搜尋 {raw_id} 的中文名稱...'):
                        fetched = fetch_tw_stock_name(raw_id)
                        final_name = fetched if fetched else final_ticker
                else:
                    try:
                        info = yf.Ticker(final_ticker).info
                        final_name = info.get('shortName') or final_ticker
                    except: final_name = final_ticker

                new_data = pd.DataFrame([[final_ticker, final_name, cost_price, share_qty, currency, track_mode, m_price]], 
                                      columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價'])
                
                # 覆蓋舊有的同代號資料
                st.session_state.portfolio = pd.concat([
                    st.session_state.portfolio[st.session_state.portfolio['代號'] != final_ticker], 
                    new_data], ignore_index=True)
                save_db(st.session_state.portfolio)
                st.rerun()

    if st.button("🗑️ 清空數據庫"):
        st.session_state.portfolio = pd.DataFrame(columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價'])
        save_db(st.session_state.portfolio)
        st.rerun()

# --- 6. 主畫面顯示 ---
st.title("🛡️ 全球資產即時監控")

if st.session_state.portfolio.empty:
    st.info("👋 歡迎！請在側邊欄登錄資產。輸入台股代號後，系統會自動搜尋對應的中文名稱。")
else:
    summary_table = []
    total_mkt_twd, total_cost_twd = 0.0, 0.0

    st.subheader("📑 詳細持股報表")
    
    for idx, row in st.session_state.portfolio.iterrows():
        t_code, is_manual_mode = row['代號'], row['模式'] == "手動 (興櫃/自訂)"
        current_p, logo_url, hist_data = 0.0, "", pd.DataFrame()

        # 抓取股價與 Logo
        if not is_manual_mode:
            try:
                stock_obj = yf.Ticker(t_code)
                hist_data = stock_obj.history(period="1mo")
                if not hist_data.empty:
                    current_p = hist_data['Close'].iloc[-1]
                    domain = stock_obj.info.get('website', '').split('//')[-1].split('/')[0]
                    if domain: logo_url = f"https://logo.clearbit.com/{domain}"
                else: is_manual_mode = True
            except: is_manual_mode = True

        if is_manual_mode:
            current_p = row['手動市價']

        # 損益換算邏輯
        fx_rate = live_fx if row['幣別'] == "USD" else 1.0
        m_val_twd = (current_p * row['股數']) * fx_rate
        c_val_twd = (row['成本價'] * row['股數']) * fx_rate
        profit_twd = m_val_twd - c_val_twd
        roi_ratio = (profit_twd / c_val_twd * 100) if c_val_twd != 0 else 0
        
        total_mkt_twd += m_val_twd
        total_cost_twd += c_val_twd

        # 渲染 Expandable Card
        with st.expander(f"{row['名稱']} ({t_code})"):
            st.markdown(f"<span class='comp-name'>{row['名稱']}</span> <span class='ticker-tag'>{t_code}</span>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns([1, 2.5, 1.2])
            with c1:
                if logo_url: st.image(logo_url, width=65)
                st.metric("持有損益 (TWD)", f"{profit_twd:,.0f}", f"{roi_ratio:.2f}%")
                st.caption(f"計價: {row['幣別']}")
            with c2:
                if not hist_data.empty:
                    fig = go.Figure(data=[go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'])])
                    fig.update_layout(template="plotly_white", height=180, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.caption("手動/興櫃模式：無即時圖表")
            with c3:
                if is_manual_mode:
                    new_val = st.number_input("更新市價", value=float(current_p), key=f"upd_{t_code}")
                    if st.button("💾 更新", key=f"btn_{t_code}"):
                        st.session_state.portfolio.at[idx, '手動市價'] = new_val
                        save_db(st.session_state.portfolio)
                        st.rerun()
                if st.button("🗑️ 刪除", key=f"del_{idx}"):
                    st.session_state.portfolio = st.session_state.portfolio.drop(idx)
                    save_db(st.session_state.portfolio)
                    st.rerun()

        summary_table.append({
            "Logo": logo_url if logo_url else "🏢",
            "名稱": row['名稱'],
            "代號": t_code,
            "成本價": row['成本價'],
            "目前市價": current_p,
            "損益 (TWD)": round(profit_twd, 0),
            "報酬率": f"{roi_ratio:.2f}%"
        })

    # --- 底部結算與彙整 ---
    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("總市值 (折算台幣)", f"NT$ {total_mkt_twd:,.0f}")
    total_roi = (total_mkt_twd - total_cost_twd) / total_cost_twd * 100 if total_cost_twd != 0 else 0
    m2.metric("總損益", f"NT$ {(total_mkt_twd - total_cost_twd):,.0f}", f"{total_roi:.2f}%")

    st.subheader("📊 投資組合清單")
    st.dataframe(
        pd.DataFrame(summary_table),
        column_config={
            "Logo": st.column_config.ImageColumn("標誌"),
            "目前市價": st.column_config.NumberColumn(format="%.2f"),
            "損益 (TWD)": st.column_config.NumberColumn(format="%d"),
        },
        use_container_width=True, hide_index=True
    )
    
    st.plotly_chart(px.pie(pd.DataFrame(summary_table), values='損益 (TWD)', names='名稱', hole=0.3, title="各股獲利貢獻分佈"), use_container_width=True)

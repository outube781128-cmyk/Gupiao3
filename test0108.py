import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os

# --- 1. 頁面配置與視覺風格 (Light Mode) ---
st.set_page_config(page_title="全球資產管理終端", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    /* 淺色背景與專業字體 */
    .stApp { background-color: #f8f9fa; color: #212529; }
    
    /* 指標卡片設計 */
    .stMetric { 
        background-color: #ffffff; 
        border-radius: 12px; 
        padding: 20px; 
        border: 1px solid #dee2e6; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
    }
    
    /* 展開面板樣式 */
    [data-testid="stExpander"] { 
        background-color: #ffffff; 
        border: 1px solid #dee2e6; 
        border-radius: 12px; 
        margin-bottom: 10px;
    }

    /* 文字強調 */
    .comp-name { font-size: 1.3rem; font-weight: 700; color: #1a365d; }
    .ticker-tag { background-color: #edf2f7; padding: 2px 8px; border-radius: 6px; font-family: monospace; color: #4a5568; font-size: 0.9rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 持久化數據庫 (CSV) ---
DB_FILE = "my_portfolio.csv"

def load_data():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        # 確保欄位完整
        required = ['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價']
        for col in required:
            if col not in df.columns: df[col] = ""
        return df
    return pd.DataFrame(columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價'])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# --- 3. 即時匯率 (每 5 分鐘自動更新) ---
@st.cache_data(ttl=300)
def get_live_usd_twd():
    try:
        ticker = yf.Ticker("TWD=X")
        data = ticker.history(period="1d", interval="1m")
        return data['Close'].iloc[-1] if not data.empty else 32.5
    except:
        return 32.5

live_rate = get_live_usd_twd()

# --- 4. 初始化 Session ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# --- 5. 側邊欄：資產登錄與管理 ---
with st.sidebar:
    st.title("🏛️ 資產配置")
    st.markdown(f"🕒 **最新匯率 USD/TWD: `{live_rate:.4f}`**")
    
    with st.form("add_stock_form", clear_on_submit=True):
        raw_id = st.text_input("股票代號", placeholder="例如: 2330 / 8069.TWO / NVDA").strip()
        custom_name = st.text_input("中文名稱 (可選)", placeholder="不填則自動抓取")
        
        # 判定是否為台灣資產 (純數字、.TW、.TWO)
        is_tw = raw_id.isdigit() or raw_id.upper().endswith(('.TW', '.TWO'))
        
        mode = st.selectbox("追蹤模式", ["自動 (Yahoo Finance)", "手動 (興櫃/自訂)"])
        
        if mode == "自動 (Yahoo Finance)":
            if raw_id.isdigit():
                final_ticker, currency = f"{raw_id}.TW", "TWD"
            else:
                final_ticker = raw_id.upper()
                currency = "TWD" if is_tw else "USD"
            manual_price = 0.0
        else:
            final_ticker = raw_id
            currency = "TWD" if is_tw else st.selectbox("計價幣別", ["TWD", "USD"])
            manual_price = st.number_input("目前市價 (補登)", min_value=0.0, format="%.2f")

        if is_tw:
            st.caption("✅ **偵測為台股/上櫃資產，已鎖定 TWD 計價**")

        cost = st.number_input("平均買入成本", min_value=0.0, format="%.2f")
        qty = st.number_input("持有股數", min_value=1, step=1)
        
        if st.form_submit_button("🚀 存入我的組合"):
            if final_ticker:
                # 自動名稱抓取邏輯
                final_name = custom_name
                if not final_name and mode == "自動 (Yahoo Finance)":
                    try:
                        info = yf.Ticker(final_ticker).info
                        final_name = info.get('shortName') or info.get('longName') or final_ticker
                    except: final_name = final_ticker
                
                new_entry = pd.DataFrame([[final_ticker, final_name, cost, qty, currency, mode, manual_price]], 
                                       columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價'])
                
                # 同代號覆蓋舊資料
                st.session_state.portfolio = pd.concat([
                    st.session_state.portfolio[st.session_state.portfolio['代號'] != final_ticker], 
                    new_entry], ignore_index=True)
                save_data(st.session_state.portfolio)
                st.rerun()

    if st.button("🗑️ 清空所有數據"):
        st.session_state.portfolio = pd.DataFrame(columns=['代號', '名稱', '成本價', '股數', '幣別', '模式', '手動市價'])
        save_data(st.session_state.portfolio)
        st.rerun()

# --- 6. 主畫面運算與顯示 ---
st.title("🛡️ 智慧資產監控看板")

if st.session_state.portfolio.empty:
    st.info("👋 歡迎使用！請在左側登錄資產。台股 (.TW/.TWO) 將自動以台幣結算並嘗試識別名稱。")
else:
    summary_list = []
    total_val_twd, total_cost_twd = 0.0, 0.0

    st.subheader("📑 即時持股明細")
    
    for idx, row in st.session_state.portfolio.iterrows():
        t = row['代號']
        is_man = row['模式'] == "手動 (興櫃/自訂)"
        now_p, logo_url = 0.0, ""
        hist_df = pd.DataFrame()

        # 價格與 Logo 抓取
        if not is_man:
            try:
                stock = yf.Ticker(t)
                hist_df = stock.history(period="1mo")
                if not hist_df.empty:
                    now_p = hist_df['Close'].iloc[-1]
                    domain = stock.info.get('website', '').split('//')[-1].split('/')[0]
                    if domain: logo_url = f"https://logo.clearbit.com/{domain}"
                else: is_man = True
            except: is_man = True

        if is_man: now_p = row['手動市價']

        # 損益計算 (美金資產使用最新匯率)
        fx_conv = live_rate if row['幣別'] == "USD" else 1.0
        val_twd = (now_p * row['股數']) * fx_conv
        cost_twd = (row['成本價'] * row['股數']) * fx_conv
        profit = val_twd - cost_twd
        roi_pct = (profit / cost_twd * 100) if cost_twd != 0 else 0
        
        total_val_twd += val_twd
        total_cost_twd += cost_twd

        # 渲染各股 Expander
        with st.expander(f"{row['名稱']} ({t})"):
            st.markdown(f"<span class='comp-name'>{row['名稱']}</span> <span class='ticker-tag'>{t}</span>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns([1, 2.5, 1.2])
            with c1:
                if logo_url: st.image(logo_url, width=65)
                st.metric("損益 (TWD)", f"{profit:,.0f}", f"{roi_pct:.2f}%")
                st.caption(f"幣別: {row['幣別']}")
            with c2:
                if not hist_df.empty:
                    fig = go.Figure(data=[go.Candlestick(x=hist_df.index, open=hist_df['Open'], high=hist_df['High'], low=hist_df['Low'], close=hist_df['Close'])])
                    fig.update_layout(template="plotly_white", height=180, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.caption("手動模式/興櫃資產：無即時線圖")
            with c3:
                if is_man:
                    new_p = st.number_input("更新市價", value=float(now_p), key=f"p_{t}")
                    if st.button("💾 更新價格", key=f"b_{t}"):
                        st.session_state.portfolio.at[idx, '手動市價'] = new_p
                        save_data(st.session_state.portfolio)
                        st.rerun()
                if st.button("🗑️ 刪除資產", key=f"d_{idx}"):
                    st.session_state.portfolio = st.session_state.portfolio.drop(idx)
                    save_data(st.session_state.portfolio)
                    st.rerun()

        summary_list.append({
            "Logo": logo_url if logo_url else "🏢",
            "名稱": row['名稱'],
            "代號": t,
            "成本": row['成本價'],
            "目前市價": now_p,
            "損益 (TWD)": round(profit, 0),
            "報酬率": f"{roi_pct:.2f}%"
        })

    # --- 總結算區 ---
    st.divider()
    m1, m2 = st.columns(2)
    m1.metric("總資產價值 (台幣)", f"NT$ {total_val_twd:,.0f}")
    total_roi = (total_val_twd - total_cost_twd) / total_cost_twd * 100 if total_cost_twd != 0 else 0
    m2.metric("總累計損益", f"NT$ {(total_val_twd - total_cost_twd):,.0f}", f"{total_roi:.2f}%")

    # --- 底部彙整表格 ---
    st.subheader("📊 投資組合彙整清單")
    sum_df = pd.DataFrame(summary_list)
    st.dataframe(
        sum_df,
        column_config={
            "Logo": st.column_config.ImageColumn("標誌"),
            "目前市價": st.column_config.NumberColumn(format="%.2f"),
            "損益 (TWD)": st.column_config.NumberColumn(format="%d"),
        },
        use_container_width=True, hide_index=True
    )
    
    # 圖表：資產佔比
    st.plotly_chart(px.pie(sum_df, values='損益 (TWD)', names='名稱', hole=0.3, title="獲利貢獻分佈"), use_container_width=True)


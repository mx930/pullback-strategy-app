import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# 設定網頁版面
st.set_page_config(
    page_title="股票與虛擬貨幣回踩策略回測工具", page_icon="📈", layout="wide"
)

st.title("📈 跨市場均線回踩（Pullback）策略回測儀表板")
st.markdown(
    "這個工具支援**美股、台股、虛擬貨幣**。您可以自行調整均線與回踩參數，"
    "即時檢視策略績效與互動式 K 線圖！"
)

# === 側邊欄參數設定 ===
st.sidebar.header("⚙️ 回測參數設定")

# 標的選擇
ticker_input = st.sidebar.text_input(
    "輸入標的代號 (Ticker)",
    value="BTC-USD",
    help=(
        "股票範例: AAPL, TSLA, SPY\n虛擬貨幣範例: BTC-USD, ETH-USD\n台股範例:"
        " 2330.TW"
    ),
)

# 日期區間
start_date = st.sidebar.date_input("開始日期", value=pd.to_datetime("2023-01-01"))
end_date = st.sidebar.date_input("結束日期", value=pd.to_datetime("2026-01-01"))

# 技術指標參數
ma_period = st.sidebar.slider("均線週期 (MA Period)", min_value=5, max_value=200, value=20)
pullback_pct = (
    st.sidebar.slider(
        "回踩容許誤差 (%)", min_value=0.0, max_value=5.0, value=1.0, step=0.1
    )
    / 100.0
)


# === 載入與處理數據 ===
@st.cache_data
def load_data(ticker, start, end):
  df = yf.download(ticker, start=start, end=end, progress=False)
  if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
  return df


if ticker_input:
  with st.spinner(f"正在載入 {ticker_input} 的歷史數據..."):
    df = load_data(ticker_input, start_date, end_date)

  if df.empty or len(df) < ma_period:
    st.error(
        "找不到該標的的數據，或數據量少於均線週期，請檢查代號或日期區間是否正確！"
    )
  else:
    # 計算均線與進場訊號
    df["MA"] = df["Close"].rolling(window=ma_period).mean()
    df["Near_MA"] = (df["Low"] <= df["MA"] * (1 + pullback_pct)) & (
        df["Close"] >= df["MA"]
    )
    df["MA_Up"] = df["MA"] > df["MA"].shift(5)

    df["Signal"] = 0
    df.loc[df["Near_MA"] & df["MA_Up"], "Signal"] = 1

    # 模擬報酬率
    df["Market_Return"] = df["Close"].pct_change()
    df["Strategy_Return"] = df["Market_Return"] * df["Signal"].shift(1)
    df["Buy_Hold"] = (1 + df["Market_Return"].fillna(0)).cumprod()
    df["Strategy"] = (1 + df["Strategy_Return"].fillna(0)).cumprod()

    # === 顯示核心指標 (KPIs) ===
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "買入持有 (Buy & Hold) 報酬倍數",
        f"{df['Buy_Hold'].iloc[-1]:.2f}x",
    )
    col2.metric(
        "回踩策略 (Strategy) 報酬倍數",
        f"{df['Strategy'].iloc[-1]:.2f}x",
    )
    total_signals = int(df["Signal"].sum())
    col3.metric("總進場次數", f"{total_signals} 次")

    st.markdown("---")

    # === 繪製互動式 K 線與均線圖 ===
    st.subheader(f"📊 {ticker_input} 價格與回踩進場點走勢圖")

    fig = go.Figure()
    # K 線圖
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="K線",
        )
    )
    # 均線
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MA"],
            line=dict(color="orange", width=1.5),
            name=f"MA {ma_period}",
        )
    )

    # 標註進場點
    signals_df = df[df["Signal"] == 1]
    fig.add_trace(
        go.Scatter(
            x=signals_df.index,
            y=signals_df["Low"] * 0.98,
            mode="markers",
            marker=dict(symbol="triangle-up", size=10, color="lime"),
            name="回踩進場訊號",
        )
    )

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=500,
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # === 顯示進場紀錄表格 ===
    st.subheader("📝 近期進場訊號紀錄")
    if not signals_df.empty:
      display_cols = ["Close", "MA"]
      st.dataframe(signals_df[display_cols].tail(10).sort_index(ascending=False))
    else:
      st.info("在此選定的區間與參數下，目前沒有符合條件的進場訊號。")

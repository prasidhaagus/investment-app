import streamlit as st
import yfinance as yf

st.title("Investment App")

ticker = st.text_input("Ticker symbol", value="AAPL").upper().strip()

if ticker:
    data = yf.Ticker(ticker).history(period="6mo")
    if data.empty:
        st.warning(f"No data found for '{ticker}'. Check the symbol and try again.")
    else:
        st.subheader(f"{ticker} — last 6 months")
        st.line_chart(data["Close"])
        st.dataframe(data[["Open", "High", "Low", "Close", "Volume"]].tail(20))
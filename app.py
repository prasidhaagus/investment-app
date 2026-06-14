import streamlit as st
import yfinance as yf
from supabase import create_client

# Connect to Supabase using the keys stored in Secrets
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

st.title("Investment App")

ticker = st.text_input("Ticker symbol", value="AAPL").upper().strip()

if ticker:
    data = yf.Ticker(ticker).history(period="6mo").dropna()
    if data.empty:
        st.warning(f"No data found for '{ticker}'. Check the symbol and try again.")
    else:
        st.subheader(f"{ticker} — last 6 months")
        st.line_chart(data["Close"])
        st.dataframe(data[["Open", "High", "Low", "Close", "Volume"]].tail(20))

        if st.button("💾 Save these prices to database"):
            # The ticker must exist in 'instruments' before saving prices
            # (price_history points back to it), so add it first.
            db.table("instruments").upsert({"ticker": ticker}).execute()

            rows = []
            for date, row in data.iterrows():
                rows.append({
                    "ticker": ticker,
                    "price_date": date.date().isoformat(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })

            db.table("price_history").upsert(rows).execute()
            st.success(f"Saved {len(rows)} days of {ticker} prices. ✅")
import streamlit as st
import yfinance as yf
from supabase import create_client

@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

st.title("Investment App")

page = st.sidebar.radio("Menu", ["Prices", "Add Transaction", "Portfolio"])

# ---------- PRICES ----------
if page == "Prices":
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

# ---------- ADD TRANSACTION ----------
elif page == "Add Transaction":
    st.subheader("Record a buy or sell")
    t_ticker = st.text_input("Ticker", value="").upper().strip()
    action = st.selectbox("Action", ["BUY", "SELL"])
    trade_date = st.date_input("Trade date")
    quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
    price = st.number_input("Price per share", min_value=0.0, step=0.01)
    fees = st.number_input("Fees", min_value=0.0, step=0.01, value=0.0)
    notes = st.text_input("Notes (optional)", value="")

    if st.button("➕ Save transaction"):
        if not t_ticker or quantity <= 0 or price <= 0:
            st.warning("Please enter a ticker, a quantity above 0, and a price above 0.")
        else:
            db.table("instruments").upsert({"ticker": t_ticker}).execute()
            db.table("transactions").insert({
                "ticker": t_ticker,
                "trade_date": trade_date.isoformat(),
                "action": action,
                "quantity": float(quantity),
                "price": float(price),
                "fees": float(fees),
                "notes": notes or None,
            }).execute()
            st.success(f"Saved: {action} {quantity:g} {t_ticker} @ {price:g}. ✅")

# ---------- PORTFOLIO ----------
elif page == "Portfolio":
    st.subheader("Portfolio")
    st.info("Coming next — we'll build this from your transactions.")
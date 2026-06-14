import streamlit as st
import yfinance as yf
import pandas as pd
from supabase import create_client

@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

st.title("Investment App")

page = st.sidebar.radio("Menu", ["Prices", "Add Transaction", "Portfolio", "Dividends"])

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
    txns = db.table("transactions").select("*").execute().data

    if not txns:
        st.info("No transactions yet. Add some on the 'Add Transaction' page.")
    else:
        df = pd.DataFrame(txns)
        df["quantity"] = df["quantity"].astype(float)
        df["price"] = df["price"].astype(float)
        df["fees"] = df["fees"].fillna(0).astype(float)

        holdings = []
        for ticker, group in df.groupby("ticker"):
            buys = group[group["action"] == "BUY"]
            sells = group[group["action"] == "SELL"]
            buy_qty = buys["quantity"].sum()
            shares = buy_qty - sells["quantity"].sum()
            if shares <= 0:
                continue

            buy_cost = (buys["quantity"] * buys["price"]).sum() + buys["fees"].sum()
            avg_cost = buy_cost / buy_qty if buy_qty else 0
            cost_basis = shares * avg_cost

            try:
                current_price = float(yf.Ticker(ticker).history(period="5d")["Close"].iloc[-1])
            except Exception:
                current_price = None

            if current_price is not None:
                market_value = shares * current_price
                gain = market_value - cost_basis
                gain_pct = (gain / cost_basis * 100) if cost_basis else 0
            else:
                market_value = gain = gain_pct = None

            holdings.append({
                "Ticker": ticker,
                "Shares": round(shares, 4),
                "Avg cost": round(avg_cost, 2),
                "Cost basis": round(cost_basis, 2),
                "Current price": round(current_price, 2) if current_price is not None else None,
                "Market value": round(market_value, 2) if market_value is not None else None,
                "Gain": round(gain, 2) if gain is not None else None,
                "Gain %": round(gain_pct, 2) if gain_pct is not None else None,
            })

        if not holdings:
            st.info("No open positions — everything has been sold.")
        else:
            st.dataframe(pd.DataFrame(holdings), use_container_width=True)
            total_cost = sum(h["Cost basis"] for h in holdings)
            mvs = [h["Market value"] for h in holdings if h["Market value"] is not None]
            total_value = sum(mvs) if mvs else None
            c1, c2, c3 = st.columns(3)
            c1.metric("Total cost basis", f"{total_cost:,.2f}")
            if total_value is not None:
                c2.metric("Total market value", f"{total_value:,.2f}")
                c3.metric("Total gain", f"{total_value - total_cost:,.2f}")

# ---------- DIVIDENDS ----------
elif page == "Dividends":
    st.subheader("Dividends")

    with st.expander("➕ Log a dividend"):
        d_ticker = st.text_input("Ticker", value="", key="div_ticker").upper().strip()
        pay_date = st.date_input("Pay date", key="div_date")
        amount = st.number_input("Amount received", min_value=0.0, step=0.01, key="div_amount")
        d_notes = st.text_input("Notes (optional)", value="", key="div_notes")

        if st.button("Save dividend"):
            if not d_ticker or amount <= 0:
                st.warning("Please enter a ticker and an amount above 0.")
            else:
                db.table("instruments").upsert({"ticker": d_ticker}).execute()
                db.table("dividends").insert({
                    "ticker": d_ticker,
                    "pay_date": pay_date.isoformat(),
                    "amount": float(amount),
                    "notes": d_notes or None,
                }).execute()
                st.success(f"Saved dividend: {d_ticker} {amount:g}. ✅")

    divs = db.table("dividends").select("*").order("pay_date", desc=True).execute().data
    if not divs:
        st.info("No dividends logged yet.")
    else:
        ddf = pd.DataFrame(divs)
        ddf["amount"] = ddf["amount"].astype(float)

        st.metric("Total dividend income", f"{ddf['amount'].sum():,.2f}")

        by_ticker = ddf.groupby("ticker")["amount"].sum().reset_index()
        by_ticker.columns = ["Ticker", "Total received"]
        st.write("**By ticker**")
        st.dataframe(by_ticker, use_container_width=True)

        st.write("**All dividend payments**")
        st.dataframe(
            ddf[["pay_date", "ticker", "amount", "notes"]].rename(
                columns={"pay_date": "Pay date", "ticker": "Ticker",
                         "amount": "Amount", "notes": "Notes"}
            ),
            use_container_width=True,
        )
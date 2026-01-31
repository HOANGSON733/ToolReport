import streamlit as st
import pandas as pd
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2 import service_account

# ================== CONFIG ==================
PROPERTY_ID = "464855282"  # 👉 THAY GA4 PROPERTY ID
CREDENTIALS_FILE = "credentials.json"

FIELDS = {
    "dimensions": ["date", "pagePath"],
    "metrics": ["sessions", "totalUsers", "screenPageViews"]
}
# ===========================================

st.set_page_config(page_title="GA4 Dashboard", layout="wide")
st.title("📊 Google Analytics 4 - Dashboard")

# ================== AUTH ==================
credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=["https://www.googleapis.com/auth/analytics.readonly"]
)

client = BetaAnalyticsDataClient(credentials=credentials)

# ================== UI ==================
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Từ ngày", pd.to_datetime("2024-01-01"))
with col2:
    end_date = st.date_input("📅 Đến ngày", pd.to_datetime("today"))

if st.button("🚀 Lấy dữ liệu"):
    with st.spinner("Đang lấy dữ liệu từ GA4..."):

        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name=d) for d in FIELDS["dimensions"]],
            metrics=[Metric(name=m) for m in FIELDS["metrics"]],
            date_ranges=[
                DateRange(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )
            ],
            limit=100000
        )

        response = client.run_report(request)

        # ================== PARSE DATA ==================
        rows = []
        for row in response.rows:
            record = {}
            for i, d in enumerate(FIELDS["dimensions"]):
                record[d] = row.dimension_values[i].value

            for i, m in enumerate(FIELDS["metrics"]):
                record[m] = int(row.metric_values[i].value)

            rows.append(record)

        df = pd.DataFrame(rows)

        if df.empty:
            st.warning("Không có dữ liệu")
        else:
            # ================== DISPLAY ==================
            st.success(f"✅ Lấy {len(df)} dòng dữ liệu")

            st.subheader("📋 Bảng dữ liệu")
            st.dataframe(df, use_container_width=True)

            # ================== SUMMARY ==================
            st.subheader("📈 Tổng quan")
            c1, c2, c3 = st.columns(3)
            c1.metric("Sessions", df["sessions"].sum())
            c2.metric("Users", df["totalUsers"].sum())
            c3.metric("Pageviews", df["screenPageViews"].sum())

            # ================== CHART ==================
            st.subheader("📊 Sessions theo ngày")
            chart_df = (
                df.groupby("date")["sessions"]
                .sum()
                .reset_index()
            )
            chart_df["date"] = pd.to_datetime(chart_df["date"])
            st.line_chart(chart_df, x="date", y="sessions")

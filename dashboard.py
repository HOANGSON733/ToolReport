import streamlit as st
import pandas as pd
import gspread
from sheets_config import SHEETS
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import numpy as np
from sklearn.linear_model import LinearRegression
import calendar
import json
import os
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2.service_account import Credentials
from google.oauth2 import service_account
# ===================== CONFIG =====================
st.set_page_config(
    page_title="SEO Rank Dashboard Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================== PERSISTENCE FUNCTIONS =====================
def save_session_state():
    """Save session state to JSON files"""
    from datetime import date
    
    # Build a JSON-serializable copy of the session state
    session_data = {
        'goals': {},
        'snapshots': {},
        'saved_filters': st.session_state.saved_filters,
        'theme': st.session_state.theme,
        'notes': st.session_state.notes
    }

    # Convert goals (which may contain date objects) into serializable form
    for goal_id, goal in st.session_state.goals.items():
        goal_serial = goal.copy()
        if 'deadline' in goal_serial and isinstance(goal_serial['deadline'], date):
            goal_serial['deadline'] = goal_serial['deadline'].isoformat()
        if 'created' in goal_serial and isinstance(goal_serial['created'], datetime):
            goal_serial['created'] = goal_serial['created'].isoformat()
        session_data['goals'][goal_id] = goal_serial

    # Convert snapshots (which may contain DataFrames) into serializable form
    for name, snap in st.session_state.snapshots.items():
        snap_serial = {}
        # Date -> ISO string
        date_val = snap.get('date')
        if isinstance(date_val, datetime):
            snap_serial['date'] = date_val.isoformat()
        elif isinstance(date_val, date):
            snap_serial['date'] = date_val.isoformat()
        else:
            snap_serial['date'] = str(date_val)

        snap_serial['score'] = snap.get('score')
        snap_serial['note'] = snap.get('note', '')

        data_val = snap.get('data')
        # If data is a DataFrame, convert to list of records
        if isinstance(data_val, pd.DataFrame):
            try:
                # Convert datetime columns to strings to make JSON serializable
                data_copy = data_val.copy()
                for col in data_copy.columns:
                    if pd.api.types.is_datetime64_any_dtype(data_copy[col]):
                        data_copy[col] = data_copy[col].astype(str)
                snap_serial['data'] = data_copy.to_dict(orient='records')
            except Exception:
                snap_serial['data'] = []
        elif isinstance(data_val, list):
            snap_serial['data'] = data_val
        else:
            # Fallback: stringify
            snap_serial['data'] = str(data_val)

        session_data['snapshots'][name] = snap_serial

    try:
        with open('dashboard_session.json', 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"❌ Lỗi khi lưu session: {e}")

def load_session_state():
    """Load session state from JSON files"""
    if os.path.exists('dashboard_session.json'):
        try:
            with open('dashboard_session.json', 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # Convert string dates back to datetime objects
            if 'goals' in session_data:
                for goal_id, goal in session_data['goals'].items():
                    if 'deadline' in goal and isinstance(goal['deadline'], str):
                        try:
                            goal['deadline'] = datetime.fromisoformat(goal['deadline']).date()
                        except Exception:
                            pass
                    if 'created' in goal and isinstance(goal['created'], str):
                        try:
                            goal['created'] = datetime.fromisoformat(goal['created'])
                        except Exception:
                            pass

            if 'snapshots' in session_data:
                for snap_name, snap_data in session_data['snapshots'].items():
                    # Convert date string back to datetime
                    if 'date' in snap_data and isinstance(snap_data['date'], str):
                        try:
                            snap_data['date'] = datetime.fromisoformat(snap_data['date'])
                        except Exception:
                            try:
                                snap_data['date'] = datetime.fromisoformat(snap_data['date'].replace(' ', 'T'))
                            except Exception:
                                # If all else fails, try to parse as date only
                                try:
                                    from datetime import date as date_type
                                    snap_data['date'] = datetime.fromisoformat(snap_data['date']).replace(hour=0, minute=0, second=0, microsecond=0)
                                except Exception:
                                    snap_data['date'] = datetime.now()

                    # Convert stored data (list of records) back to DataFrame
                    if 'data' in snap_data and isinstance(snap_data['data'], list):
                        try:
                            snap_data['data'] = pd.DataFrame(snap_data['data'])
                        except Exception:
                            snap_data['data'] = pd.DataFrame()

            return session_data
        except Exception as e:
            st.warning(f"⚠️ Không thể tải session đã lưu: {e}")
            return {}
    return {}

# Load saved session state
saved_session = load_session_state()

# Initialize session state with saved data
if 'goals' not in st.session_state:
    st.session_state.goals = saved_session.get('goals', {})
if 'snapshots' not in st.session_state:
    st.session_state.snapshots = saved_session.get('snapshots', {})
if 'saved_filters' not in st.session_state:
    st.session_state.saved_filters = saved_session.get('saved_filters', {})
if 'theme' not in st.session_state:
    st.session_state.theme = saved_session.get('theme', 'dark').lower()
if 'notes' not in st.session_state:
    st.session_state.notes = saved_session.get('notes', {})

# Theme colors
THEMES = {
    'light': {
        'bg': '#ffffff',
        'text': '#1e293b',
        'primary': '#667eea',
        'secondary': '#764ba2',
        'card_bg': '#f8fafc'
    },
    'dark': {
        'bg': '#0f172a',
        'text': '#e2e8f0',
        'primary': '#818cf8',
        'secondary': '#a78bfa',
        'card_bg': '#1e293b'
    }
}

current_theme = THEMES[st.session_state.theme]

# Custom CSS - Improved UI
st.markdown(f"""
<style>
    * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }}
    
    html, body {{
        background-color: {current_theme['bg']};
        color: {current_theme['text']};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    }}
    
    .main {{
        padding: 2rem 2rem;
        background-color: {current_theme['bg']};
        color: {current_theme['text']};
        max-width: 1600px;
        margin: 0 auto;
    }}
    
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {current_theme['card_bg']} 0%, {current_theme['bg']} 100%);
        border-right: 2px solid {current_theme['primary']};
    }}
    
    [data-testid="stSidebar"] h3 {{
        color: {current_theme['primary']};
        font-weight: 600;
        margin-top: 1.5rem;
    }}
    
    [data-testid="stSidebar"] p {{
        color: {current_theme['text']};
    }}
    
    [data-testid="stSidebar"] label {{
        color: {current_theme['text']};
    }}
    
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div > input {{
        background-color: {current_theme['card_bg']};
        color: {current_theme['text']};
        border: 1px solid {current_theme['primary']};
    }}
    
    [data-testid="stSidebar"] [data-testid="stDateInput"] > div > div > input {{
        background-color: {current_theme['card_bg']};
        color: {current_theme['text']};
        border: 1px solid {current_theme['primary']};
    }}
    
    [data-testid="stSidebar"] [data-testid="stTextInput"] > div > div > input {{
        background-color: {current_theme['card_bg']};
        color: {current_theme['text']};
        border: 1px solid {current_theme['primary']};
    }}
    
    .section-header {{
        color: {current_theme['primary']};
        font-size: 1.3rem;
        font-weight: 700;
        margin: 2rem 0 1rem 0;
        padding: 1rem 0 0.5rem 0;
        border-bottom: 3px solid {current_theme['primary']};
        letter-spacing: 0.5px;
    }}
    
    .stTabs [data-baseweb="tab-list"] {{
        border-bottom: 2px solid rgba(0,0,0,0.1);
    }}
    
    .stTabs [aria-selected="true"] {{
        color: {current_theme['primary']};
        border-bottom: 3px solid {current_theme['primary']};
    }}
    
    /* Metrics Cards */
    [data-testid="metric-container"] {{
        background: {current_theme['card_bg']};
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid rgba(0,0,0,0.05);
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}
    
    /* Alert Boxes */
    .alert-box {{
        padding: 1.25rem;
        border-radius: 10px;
        margin: 0.75rem 0;
        border-left: 5px solid;
        background-color: transparent;
        font-size: 0.95rem;
        line-height: 1.5;
    }}
    
    .alert-critical {{
        background: rgba(239, 68, 68, 0.08);
        border-color: #ef4444;
        color: #991b1b;
    }}
    
    .alert-warning {{
        background: rgba(245, 158, 11, 0.08);
        border-color: #f59e0b;
        color: #92400e;
    }}
    
    .alert-success {{
        background: rgba(16, 185, 129, 0.08);
        border-color: #10b981;
        color: #065f46;
    }}
    
    .alert-info {{
        background: rgba(59, 130, 246, 0.08);
        border-color: #3b82f6;
        color: #1e40af;
    }}
    
    /* Score Box */
    .score-box {{
        background: linear-gradient(135deg, {current_theme['primary']} 0%, {current_theme['secondary']} 100%);
        color: white;
        padding: 2.5rem 2rem;
        border-radius: 16px;
        text-align: center;
        box-shadow: 0 8px 16px rgba(0,0,0,0.15);
        border: 1px solid rgba(255,255,255,0.1);
    }}
    
    .score-number {{
        font-size: 3.5rem;
        font-weight: 800;
        margin: 1rem 0;
        letter-spacing: -1px;
    }}
    
    /* Buttons */
    .stButton > button {{
        background: {current_theme['primary']};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    
    .stButton > button:hover {{
        background: {current_theme['secondary']};
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transform: translateY(-2px);
    }}
    
    /* Input Fields */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {{
        border: 1px solid {current_theme['primary']} !important;
        border-radius: 8px;
        padding: 0.75rem;
        background: {current_theme['card_bg']} !important;
        color: {current_theme['text']} !important;
    }}
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus {{
        border-color: {current_theme['primary']} !important;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
    }}
    
    /* Selectbox & Multiselect */
    .stSelectbox > div,
    .stMultiSelect > div {{
        border-radius: 8px;
    }}
    
    .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="base-input"] {{
        border: 1px solid {current_theme['primary']} !important;
        border-radius: 8px;
        background: {current_theme['card_bg']} !important;
        color: {current_theme['text']} !important;
    }}
    
    .stSelectbox [data-baseweb="select"] > div > div,
    .stMultiSelect [data-baseweb="base-input"] input {{
        color: {current_theme['text']} !important;
    }}
    
    /* Selectbox dropdown */
    [role="listbox"] {{
        background: {current_theme['card_bg']} !important;
        border: 1px solid {current_theme['primary']} !important;
    }}
    
    [role="option"] {{
        color: {current_theme['text']} !important;
    }}
    
    [role="option"]:hover {{
        background: {current_theme['primary']} !important;
        color: {current_theme['bg']} !important;
    }}
    
    /* Expander */
    .streamlit-expanderHeader {{
        background: {current_theme['card_bg']};
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid rgba(0,0,0,0.05);
    }}
    
    .streamlit-expanderHeader:hover {{
        background: linear-gradient(90deg, {current_theme['card_bg']}, {current_theme['primary']}15);
    }}
    
    /* Dataframe */
    [data-testid="stDataFrame"] {{
        border-radius: 8px;
        overflow: hidden;
    }}
    
    /* Snapshot Card */
    .snapshot-card {{
        background: {current_theme['card_bg']};
        border-radius: 12px;
        padding: 1.5rem;
        margin: 0.75rem 0;
        border: 2px solid rgba(0,0,0,0.05);
        cursor: pointer;
        transition: all 0.3s ease;
    }}
    
    .snapshot-card:hover {{
        border-color: {current_theme['primary']};
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        background: linear-gradient(135deg, {current_theme['card_bg']}, {current_theme['primary']}08);
    }}
    
    /* Goal Progress */
    .goal-progress {{
        background: rgba(0,0,0,0.05);
        border-radius: 10px;
        height: 10px;
        overflow: hidden;
        margin: 0.75rem 0;
    }}
    
    .goal-progress-bar {{
        height: 100%;
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        transition: width 0.6s ease;
        border-radius: 10px;
    }}
    
    /* Divider */
    hr {{
        border: none;
        border-top: 1px solid rgba(0,0,0,0.08);
        margin: 2rem 0;
    }}
    
    /* Info/Success/Warning/Error boxes */
    .stAlert {{
        border-radius: 10px;
        padding: 1.25rem;
        border-left: 5px solid;
    }}
    
    /* Headings */
    h1, h2, h3, h4, h5, h6 {{
        letter-spacing: -0.5px;
    }}
    
    h4 {{
        color: {current_theme['text']};
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }}
    
    /* Responsive Design */
    @media (max-width: 768px) {{
        .main {{
            padding: 1rem 1rem;
        }}
        
        .score-number {{
            font-size: 2.5rem;
        }}
        
        .section-header {{
            font-size: 1.1rem;
        }}
    }}
    
    /* Smooth Scrolling */
    html {{
        scroll-behavior: smooth;
    }}
</style>
""", unsafe_allow_html=True)

# Dashboard Title with Emoji
st.markdown("""
    <div style='text-align: left; margin: 0; padding: 0;'>
        <h1 style='font-size: 2.5rem; font-weight: 800; margin: 0; padding: 0;'>SEO Rank</h1>
        <p style='font-size: 1rem; opacity: 0.7; margin: 0; padding: 0;'>Phân tích SEO toàn diện với AI Insights & Forecasting</p>
    </div>
""", unsafe_allow_html=True)

# ===================== GOOGLE AUTH =====================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Try to load credentials from Streamlit secrets first (for Streamlit Cloud)
# Otherwise fall back to local credentials.json file
try:
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
    else:
        # Fall back to local file
        with open('credentials.json', 'r') as f:
            creds_dict = json.load(f)
except Exception as e:
    st.error(f"❌ Không thể tải credentials: {e}")
    st.info("💡 Để sử dụng Streamlit Cloud, thêm [gcp_service_account] vào .streamlit/secrets.toml")
    st.stop()

creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)

client = gspread.authorize(creds)

# ===================== HELPERS =====================
def extract_date(sheet_name: str):
    try:
        return datetime.strptime(sheet_name.replace("Ngày_", ""), "%d_%m_%Y")
    except:
        return None

def get_date_worksheets(sheet):
    result = []
    for ws in sheet.worksheets():
        if ws.title.startswith("Ngày_"):
            dt = extract_date(ws.title)
            if dt:
                result.append((ws.title, dt))
    result.sort(key=lambda x: x[1])
    return result

def compare_ranks(old_rank, new_rank):
    if pd.isna(old_rank) and pd.isna(new_rank):
        return "Không đổi", 0, "⚪"
    elif pd.isna(old_rank) and not pd.isna(new_rank):
        return "Mới có rank", 0, "🆕"
    elif not pd.isna(old_rank) and pd.isna(new_rank):
        return "Mất rank", 0, "❌"
    else:
        change = old_rank - new_rank
        if change > 0:
            return "Tăng", change, "📈"
        elif change < 0:
            return "Giảm", change, "📉"
        else:
            return "Không đổi", 0, "➡️"

def extract_keyword_groups(keywords):
    groups = {}
    for kw in keywords:
        words = str(kw).lower().split()
        if len(words) >= 2:
            group = ' '.join(words[:2])
        else:
            group = words[0] if words else 'Khác'
        
        if group not in groups:
            groups[group] = []
        groups[group].append(kw)
    
    filtered_groups = {k: v for k, v in groups.items() if len(v) >= 3}
    grouped_kws = set([kw for kws in filtered_groups.values() for kw in kws])
    other_kws = [kw for kw in keywords if kw not in grouped_kws]
    
    if other_kws:
        filtered_groups['Khác'] = other_kws
    
    return filtered_groups

def calculate_seo_score(df):
    """
    Tính SEO Performance Score (0-100)
    - Top 3: 10 điểm
    - Top 10: 5 điểm
    - Top 20: 2 điểm
    - Không rank: 0.5 điểm
    - Max: 100 điểm (khi tất cả từ khóa trong Top 3)
    """
    if df.empty:
        return 0
    
    total = len(df)
    top3 = (df["Thứ hạng"] <= 3).sum()
    top10 = ((df["Thứ hạng"] > 3) & (df["Thứ hạng"] <= 10)).sum()
    top20 = ((df["Thứ hạng"] > 10) & (df["Thứ hạng"] <= 20)).sum()
    no_rank = df["Thứ hạng"].isna().sum()
    outside_top20 = total - top3 - top10 - top20 - no_rank
    
    score = (
        (top3 * 10) +
        (top10 * 5) +
        (top20 * 2) +
        (outside_top20 * 0.5) +
        (no_rank * 0)
    )
    
    # Max score = all keywords in Top 3
    max_score = total * 10
    
    # Normalize to 0-100
    final_score = (score / max_score * 100) if max_score > 0 else 0
    
    return round(min(final_score, 100), 1)

def forecast_rank(kw_data, days_ahead=7):
    """Dự báo thứ hạng sử dụng linear regression"""
    if len(kw_data) < 3:
        return None, None
    
    kw_data = kw_data.sort_values("Ngày_Sort")
    kw_data = kw_data[kw_data["Thứ hạng"].notna()]
    
    if len(kw_data) < 3:
        return None, None
    
    X = np.array(range(len(kw_data))).reshape(-1, 1)
    y = kw_data["Thứ hạng"].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    future_X = np.array(range(len(kw_data), len(kw_data) + days_ahead)).reshape(-1, 1)
    predictions = model.predict(future_X)
    
    trend = "up" if model.coef_[0] < 0 else "down" if model.coef_[0] > 0 else "stable"
    
    return predictions, trend

def generate_ai_insights(df, comparison_data=None):
    """Tạo AI insights tự động"""
    insights = []
    
    # Top performers
    top_kws = df[df["Thứ hạng"] <= 3].groupby("Từ khóa").size().nlargest(3)
    if not top_kws.empty:
        insights.append({
            "type": "success",
            "title": "🌟 Top Performers",
            "message": f"Từ khóa '{top_kws.index[0]}' đang có hiệu suất xuất sắc với {top_kws.values[0]} lần xuất hiện trong Top 3."
        })
    
    # Declining keywords
    if comparison_data is not None and not comparison_data.empty:
        declining = comparison_data[comparison_data["Thay đổi"] < -5]
        if len(declining) > 0:
            insights.append({
                "type": "warning",
                "title": "⚠️ Cần chú ý",
                "message": f"{len(declining)} từ khóa đang giảm >5 bậc. Cần review và tối ưu lại content."
            })
    
    # Opportunity
    near_top10 = df[(df["Thứ hạng"] > 10) & (df["Thứ hạng"] <= 15)]
    if len(near_top10) > 0:
        insights.append({
            "type": "info",
            "title": "💡 Cơ hội",
            "message": f"{len(near_top10)} từ khóa đang ở vị trí 11-15. Đây là cơ hội tốt để push vào Top 10!"
        })
    
    # URL analysis
    url_counts = df[df["URL"].notna() & (~df["URL"].str.contains("Không có kết quả", na=False))].groupby("URL").size()
    if not url_counts.empty and url_counts.max() > 10:
        top_url = url_counts.idxmax()
        insights.append({
            "type": "success",
            "title": "🔗 URL xuất sắc",
            "message": f"URL '{top_url[:50]}...' đang rank cho {url_counts.max()} từ khóa. Nên mở rộng nội dung liên quan."
        })
    
    return insights

def create_heatmap_calendar(df, year, month):
    """Tạo heatmap calendar"""
    cal = calendar.monthcalendar(year, month)
    
    # Calculate daily scores
    daily_scores = {}
    for _, row in df.iterrows():
        date = row["Ngày_Sort"]
        if date.year == year and date.month == month:
            day = date.day
            score = calculate_seo_score(df[df["Ngày_Sort"] == date])
            daily_scores[day] = score
    
    return cal, daily_scores

# ===================== SIDEBAR =====================
st.sidebar.markdown("""
    <style>
        [data-testid="stSidebar"] > div:first-child {{
            padding-top: 0rem !important;
            margin-top: -1rem !important;
        }}
    </style>
    <div style='display: flex; justify-content: center;'>
        <img src='data:image/png;base64,{}' width='180'>
    </div>
""".format(__import__('base64').b64encode(open('logo.png', 'rb').read()).decode()),
    unsafe_allow_html=True
)
# Domain selector
st.sidebar.markdown("**🌐 Domain**")
domains = list(SHEETS.keys())
selected_domain = st.sidebar.selectbox("🌐 Domain", domains, label_visibility="collapsed")
sheet_id = SHEETS[selected_domain]["sheet_id"]

# Theme selector
st.sidebar.markdown("**🎨 Giao diện**")
selected_theme = st.sidebar.selectbox(
    "Chế độ",
    options=['light', 'dark'],
    index=0 if st.session_state.theme == 'light' else 1,
    label_visibility="collapsed"
)
if selected_theme != st.session_state.theme:
    st.session_state.theme = selected_theme
    save_session_state()
    st.rerun()

# ===================== LOAD DATA =====================
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_sheet_data_cached(sheet_id, selected_days):
    """Load and cache Google Sheets data"""
    try:
        sh = client.open_by_key(sheet_id)
        date_sheets = get_date_worksheets(sh)

        if not date_sheets:
            return None, None

        sheet_map = {name: dt for name, dt in date_sheets}

        all_data = []
        for ws_name in selected_days:
            try:
                ws = sh.worksheet(ws_name)
                rows = ws.get_all_records()
                df_day = pd.DataFrame(rows)

                if df_day.empty:
                    continue

                df_day["Ngày"] = sheet_map[ws_name].strftime("%d-%m-%Y")
                df_day["Ngày_Sort"] = sheet_map[ws_name]
                all_data.append(df_day)
            except Exception as e:
                st.warning(f"⚠️ Lỗi tải sheet '{ws_name}': {str(e)}")
                continue

        if not all_data:
            return None, None

        df = pd.concat(all_data, ignore_index=True)

        # Normalize columns

        expected_columns = [
            "Từ khóa", "Trang", "Vị trí", "Thứ hạng", "URL",
            "Tiêu đề", "Domain mục tiêu", "Ngày tìm kiếm", "Ngày", "Ngày_Sort"
        ]

        for col in expected_columns:
            if col not in df.columns:
                df[col] = ""

        # Clean data
        df["Thứ hạng"] = (
            df["Thứ hạng"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df["Thứ hạng"] = pd.to_numeric(df["Thứ hạng"], errors="coerce")

        df["Trang"] = (
            df["Trang"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df["Trang"] = pd.to_numeric(df["Trang"], errors="coerce")

        df["Vị trí"] = (
            df["Vị trí"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df["Vị trí"] = pd.to_numeric(df["Vị trí"], errors="coerce")

        return df, sheet_map

    except Exception as e:
        st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
        return None, None

try:
    sh = client.open_by_key(sheet_id)
    date_sheets = get_date_worksheets(sh)

    if not date_sheets:
        st.error("❌ Không tìm thấy worksheet dạng Ngày_DD_MM_YYYY")
        st.stop()

    sheet_map = {name: dt for name, dt in date_sheets}

    # Saved filters
    st.sidebar.markdown("**💾 Bộ lọc đã lưu**")

    if st.session_state.saved_filters:
        filter_names = list(st.session_state.saved_filters.keys())
        selected_saved_filter = st.sidebar.selectbox("Chọn bộ lọc", ["Mới"] + filter_names)

        if selected_saved_filter != "Mới":
            saved = st.session_state.saved_filters[selected_saved_filter]
            selected_days = saved.get("days", [list(sheet_map.keys())[-1]])
            keyword_filter_default = saved.get("keyword", "")
            rank_limit_default = saved.get("rank_limit", 100)
        else:
            selected_days = [list(sheet_map.keys())[-1]]
            keyword_filter_default = ""
            rank_limit_default = 100
    else:
        selected_days = [list(sheet_map.keys())[-1]]
        keyword_filter_default = ""
        rank_limit_default = 100

    # Add day limit warning and suggestions
    max_days = 30  # Maximum recommended days
    total_available_days = len(sheet_map)

    if total_available_days > max_days:
        st.sidebar.warning(f"⚠️ Có {total_available_days} ngày dữ liệu. Khuyến nghị chọn ≤ {max_days} ngày để tránh quá tải.")

        # Quick selection options
        st.sidebar.markdown("#### 🚀 Chọn nhanh")
        col_quick1, col_quick2 = st.sidebar.columns(2)

        with col_quick1:
            if st.button("📅 7 ngày gần nhất"):
                recent_days = sorted(list(sheet_map.keys()), key=lambda x: sheet_map[x], reverse=True)[:7]
                selected_days = recent_days
                st.rerun()

            if st.button("📅 30 ngày gần nhất"):
                recent_days = sorted(list(sheet_map.keys()), key=lambda x: sheet_map[x], reverse=True)[:30]
                selected_days = recent_days
                st.rerun()

        with col_quick2:
            if st.button("📅 Tuần này"):
                today = datetime.now().date()
                start_of_week = today - timedelta(days=today.weekday())
                week_days = []
                for i in range(7):
                    day = start_of_week + timedelta(days=i)
                    day_str = f"Ngày_{day.day:02d}_{day.month:02d}_{day.year}"
                    if day_str in sheet_map:
                        week_days.append(day_str)
                if week_days:
                    selected_days = week_days
                    st.rerun()

            if st.button("📅 Tháng này"):
                today = datetime.now().date()
                month_days = [k for k, v in sheet_map.items() if v.year == today.year and v.month == today.month]
                if month_days:
                    selected_days = sorted(month_days, key=lambda x: sheet_map[x])
                    st.rerun()

    # Date range picker for easier selection of many consecutive days
    st.sidebar.markdown("**📅 Chọn khoảng thời gian**")
    use_date_range = st.sidebar.checkbox("Sử dụng bộ chọn khoảng", value=False)

    if use_date_range:
        col_start, col_end = st.sidebar.columns(2)
        with col_start:
            start_date = st.date_input(
                "Từ ngày",
                value=min(sheet_map.values()) if sheet_map else datetime.now().date(),
                min_value=min(sheet_map.values()) if sheet_map else None,
                max_value=max(sheet_map.values()) if sheet_map else None
            )
        with col_end:
            end_date = st.date_input(
                "Đến ngày",
                value=max(sheet_map.values()) if sheet_map else datetime.now().date(),
                min_value=min(sheet_map.values()) if sheet_map else None,
                max_value=max(sheet_map.values()) if sheet_map else None
            )

        if start_date <= end_date:
            # Filter days within the selected range
            range_days = [k for k, v in sheet_map.items() if start_date <= v.date() <= end_date]
            if range_days:
                selected_days = sorted(range_days, key=lambda x: sheet_map[x])
                st.sidebar.success(f"✅ Đã chọn {len(selected_days)} ngày trong khoảng thời gian")
            else:
                selected_days = []
                st.sidebar.warning("⚠️ Không có dữ liệu trong khoảng thời gian đã chọn")
        else:
            selected_days = []
            st.sidebar.error("❌ Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc")
    else:
        selected_days = st.sidebar.multiselect(
            "📅 Chọn khoảng thời gian",
            options=list(sheet_map.keys()),
            default=selected_days,
            max_selections=50  # Hard limit to prevent abuse
        )

    if not selected_days:
        st.warning("⚠️ Vui lòng chọn ít nhất một ngày")
        st.stop()

    # Performance warning for large selections
    if len(selected_days) > max_days:
        st.sidebar.error(f"⚠️ Đã chọn {len(selected_days)} ngày. Có thể gây chậm hoặc vượt quota API!")

        # Suggest alternatives
        with st.sidebar.expander("💡 Giải pháp thay thế", expanded=True):
            st.markdown("""
            **Khi chọn quá nhiều ngày, hãy thử:**

            1. **📸 Sử dụng Snapshots**: Tạo snapshot của các khoảng thời gian quan trọng
            2. **📊 Chế độ Lịch nhiệt**: Xem hiệu suất theo tháng thay vì từng ngày
            3. **🎯 Bộ lọc đã lưu**: Lưu các bộ lọc thường dùng
            4. **📅 Chọn nhanh**: Dùng các nút chọn nhanh ở trên
            5. **🔍 Phân tích theo nhóm**: Giảm số lượng từ khóa cần xử lý

            **Lợi ích:**
            - ⚡ Tải nhanh hơn
            - 💾 Tiết kiệm quota Google Sheets API
            - 📈 Hiệu suất tốt hơn
            """)

    elif len(selected_days) > 15:
        st.sidebar.warning(f"📊 Đã chọn {len(selected_days)} ngày. Hiệu suất có thể bị ảnh hưởng.")

    # Analysis mode
    st.sidebar.divider()
    st.sidebar.markdown("**📊 Chế độ phân tích**")
    analysis_mode = st.sidebar.radio(
        "Chọn chế độ",
        ["Tổng quan", "So sánh ngày", "Phân tích từ khóa", "Phân tích URL", 
         "Nhóm từ khóa", "Mục tiêu", "Dự báo", "📸 Snapshots", "Lịch nhiệt", "Google Analytics"],
        index=0,
        label_visibility="collapsed"
    )

    # Advanced filters
    st.sidebar.divider()
    with st.sidebar.expander("🔍 Bộ lọc nâng cao", expanded=False):
        keyword_filter = st.text_input("Tìm kiếm từ khóa", value=keyword_filter_default, placeholder="Nhập từ khóa...")
        rank_limit = st.slider("Hiển thị top ≤", min_value=1, max_value=100, value=rank_limit_default)
        
        col1, col2 = st.columns(2)
        with col1:
            only_no_rank = st.checkbox("Chưa có rank")
        with col2:
            only_with_rank = st.checkbox("Có rank")
        
    # Save filter
        filter_name = st.text_input("Tên bộ lọc", placeholder="VD: Top 10 only")
        if st.button("💾 Lưu bộ lọc"):
            if filter_name:
                st.session_state.saved_filters[filter_name] = {
                    "days": selected_days,
                    "keyword": keyword_filter,
                    "rank_limit": rank_limit
                }
                save_session_state()  # Save to file
                st.success(f"✅ Đã lưu bộ lọc '{filter_name}'")
            else:
                st.error("Vui lòng nhập tên bộ lọc")

    # Load data using cached function
    df, sheet_map = load_sheet_data_cached(sheet_id, selected_days)

    if df is None:
        st.warning("⚠️ Không có dữ liệu")
        st.stop()

    # Apply filters (this happens after caching since filters can change)
    filtered = df.copy()

    if keyword_filter:
        filtered = filtered[
            filtered["Từ khóa"]
            .astype(str)
            .str.contains(keyword_filter, case=False, na=False)
        ]

    if only_no_rank and only_with_rank:
        pass
    elif only_no_rank:
        filtered = filtered[filtered["Thứ hạng"].isna()]
    elif only_with_rank:
        filtered = filtered[filtered["Thứ hạng"].notna()]
    else:
        filtered = filtered[
            (filtered["Thứ hạng"].isna()) |
            (filtered["Thứ hạng"] <= rank_limit)
        ]

    # ===================== MODE: TỔNG QUAN =====================
    if analysis_mode == "Tổng quan":
        
        # Quick actions
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📧 Export Report (PDF)", width='stretch'):
                st.info("📄 Tính năng export PDF đang được phát triển...")
        with col2:
            if st.button("📊 Create Snapshot", width='stretch'):
                snapshot_name = f"Snapshot_{datetime.now().strftime('%Y%m%d_%H%M')}"
                st.session_state.snapshots[snapshot_name] = {
                    "date": datetime.now(),
                    "data": filtered.copy(),
                    "score": calculate_seo_score(filtered),
                    "note": ""
                }
                # Persist the new snapshot to disk and open it
                try:
                    save_session_state()
                except Exception:
                    pass
                st.session_state.selected_snapshot = snapshot_name
                st.success(f"✅ Đã tạo snapshot: {snapshot_name}")
        with col3:
            if st.button("🔄 Refresh Data", width='stretch'):
                st.rerun()
        
        # SEO Performance Score & AI Insights
        col1, col2 = st.columns([1, 2])
        
        with col1:
            score = calculate_seo_score(filtered)
            st.markdown(f"""
            <div class="score-box">
                <div>SEO Performance Score</div>
                <div class="score-number">{score}</div>
                <div>/ 100 điểm</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("### 🤖 AI Insights")
            
            # Generate comparison data if possible
            comparison_data = None
            if len(selected_days) >= 2:
                dates_sorted = sorted(selected_days, key=lambda x: sheet_map[x])
                latest_date = sheet_map[dates_sorted[-1]].strftime("%d-%m-%Y")
                prev_date = sheet_map[dates_sorted[-2]].strftime("%d-%m-%Y")
                
                df_latest = filtered[filtered["Ngày"] == latest_date][["Từ khóa", "Thứ hạng"]].copy()
                df_prev = filtered[filtered["Ngày"] == prev_date][["Từ khóa", "Thứ hạng"]].copy()
                
                df_latest.rename(columns={"Thứ hạng": "Rank_New"}, inplace=True)
                df_prev.rename(columns={"Thứ hạng": "Rank_Old"}, inplace=True)
                
                comparison_data = pd.merge(df_prev, df_latest, on="Từ khóa", how="inner")
                comparison_data["Thay đổi"] = comparison_data["Rank_Old"] - comparison_data["Rank_New"]
            
            insights = generate_ai_insights(filtered, comparison_data)
            
            for insight in insights:
                alert_class = f"alert-{insight['type']}"
                st.markdown(f"""
                <div class="alert-box {alert_class}">
                    <strong>{insight['title']}</strong><br/>
                    {insight['message']}
                </div>
                """, unsafe_allow_html=True)
        
        # Metrics
        st.markdown('<p class="section-header">📈 Tổng quan hiệu suất</p>', unsafe_allow_html=True)
        
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            st.metric("📌 Tổng từ khóa", f"{len(filtered):,}")
        with c2:
            top3_count = (filtered["Thứ hạng"] <= 3).sum()
            st.metric("🥇 Top 3", f"{top3_count:,}", 
                     delta=f"{(top3_count/len(filtered)*100):.1f}%" if len(filtered) > 0 else "0%")
        with c3:
            top10_count = (filtered["Thứ hạng"] <= 10).sum()
            st.metric("🏆 Top 10", f"{top10_count:,}",
                     delta=f"{(top10_count/len(filtered)*100):.1f}%" if len(filtered) > 0 else "0%")
        with c4:
            no_rank = filtered["Thứ hạng"].isna().sum()
            st.metric("❌ Chưa có rank", f"{no_rank:,}",
                     delta=f"{(no_rank/len(filtered)*100):.1f}%" if len(filtered) > 0 else "0%")

        # Alerts
        if len(selected_days) >= 2 and comparison_data is not None:
            st.markdown('<p class="section-header">🔔 Thông báo quan trọng</p>', unsafe_allow_html=True)
            
            critical_drop = comparison_data[comparison_data["Thay đổi"] < -10].nlargest(5, "Thay đổi", keep='all')
            big_jump = comparison_data[comparison_data["Thay đổi"] > 5].nlargest(5, "Thay đổi", keep='all')
            new_top3 = comparison_data[(comparison_data["Rank_New"] <= 3) & (comparison_data["Rank_Old"] > 3)]
            dropped_top10 = comparison_data[(comparison_data["Rank_Old"] <= 10) & (comparison_data["Rank_New"] > 10)]
            
            col1, col2 = st.columns(2)
            
            with col1:
                if not critical_drop.empty:
                    st.markdown('<div class="alert-box alert-critical">⚠️ <strong>Cảnh báo: Từ khóa giảm mạnh (>10 bậc)</strong></div>', unsafe_allow_html=True)
                    for _, row in critical_drop.iterrows():
                        st.write(f"• **{row['Từ khóa']}**: {row['Rank_Old']:.0f} → {row['Rank_New']:.0f} ({row['Thay đổi']:.0f})")
                
                if not dropped_top10.empty:
                    st.markdown('<div class="alert-box alert-warning">📉 <strong>Rơi khỏi Top 10</strong></div>', unsafe_allow_html=True)
                    for _, row in dropped_top10.iterrows():
                        st.write(f"• **{row['Từ khóa']}**: {row['Rank_Old']:.0f} → {row['Rank_New']:.0f}")
            
            with col2:
                if not big_jump.empty:
                    st.markdown('<div class="alert-box alert-success">🎉 <strong>Tăng hạng mạnh (>5 bậc)</strong></div>', unsafe_allow_html=True)
                    for _, row in big_jump.iterrows():
                        st.write(f"• **{row['Từ khóa']}**: {row['Rank_Old']:.0f} → {row['Rank_New']:.0f} (+{row['Thay đổi']:.0f})")
                
                if not new_top3.empty:
                    st.markdown('<div class="alert-box alert-info">🏆 <strong>Mới vào Top 3</strong></div>', unsafe_allow_html=True)
                    for _, row in new_top3.iterrows():
                        st.write(f"• **{row['Từ khóa']}**: {row['Rank_Old']:.0f} → {row['Rank_New']:.0f}")

        # Charts
        st.markdown('<p class="section-header">📊 Phân tích chi tiết</p>', unsafe_allow_html=True)

        def rank_group(rank):
            if pd.isna(rank):
                return "Chưa có rank"
            elif rank <= 3:
                return "Top 3"
            elif rank <= 10:
                return "Top 10"
            elif rank <= 20:
                return "Top 20"
            else:
                return "Ngoài Top 20"

        filtered["Nhóm hạng"] = filtered["Thứ hạng"].apply(rank_group)
        chart_rank = filtered.groupby("Nhóm hạng").size().reset_index(name="Số lượng")

        if not chart_rank.empty:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("#### 📊 Phân bố thứ hạng")
                fig_bar = px.bar(chart_rank, x="Nhóm hạng", y="Số lượng", color="Số lượng",
                                color_continuous_scale="Viridis", text="Số lượng")
                fig_bar.update_traces(textposition='outside')
                fig_bar.update_layout(showlegend=False, height=400, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_bar, width='stretch')
            
            with col2:
                st.markdown("#### 🥧 Tỷ lệ phân bố")
                fig_pie = px.pie(chart_rank, values="Số lượng", names="Nhóm hạng", hole=0.4,
                                color_discrete_sequence=px.colors.qualitative.Set3)
                fig_pie.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_pie, width='stretch')

        # Trend
        st.markdown("#### 📈 Xu hướng theo thời gian")
        
        trend_data = filtered[filtered["Thứ hạng"].notna()].copy()
        trend_data = trend_data.sort_values("Ngày_Sort")
        
        trend_top3 = trend_data[trend_data["Thứ hạng"] <= 3].groupby("Ngày")["Từ khóa"].count().reset_index(name="Top 3")
        trend_top10 = trend_data[trend_data["Thứ hạng"] <= 10].groupby("Ngày")["Từ khóa"].count().reset_index(name="Top 10")
        trend_top20 = trend_data[trend_data["Thứ hạng"] <= 20].groupby("Ngày")["Từ khóa"].count().reset_index(name="Top 20")
        
        trend = trend_top3.merge(trend_top10, on="Ngày", how="outer").merge(trend_top20, on="Ngày", how="outer").fillna(0)

        if not trend.empty:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=trend["Ngày"], y=trend["Top 3"], mode='lines+markers',
                                          name='Top 3', line=dict(color='#10b981', width=3), marker=dict(size=8)))
            fig_trend.add_trace(go.Scatter(x=trend["Ngày"], y=trend["Top 10"], mode='lines+markers',
                                          name='Top 10', line=dict(color='#3b82f6', width=3), marker=dict(size=8)))
            fig_trend.add_trace(go.Scatter(x=trend["Ngày"], y=trend["Top 20"], mode='lines+markers',
                                          name='Top 20', line=dict(color='#f59e0b', width=3), marker=dict(size=8)))
            fig_trend.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20), hovermode='x unified',
                                   legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_trend, width='stretch')

        # Danh sách từ khóa theo nhóm hạng
        st.markdown('<p class="section-header">📋 Danh sách từ khóa theo nhóm hạng</p>', unsafe_allow_html=True)

        # Tạo danh sách từ khóa cho mỗi nhóm
        top3_kws = filtered[(filtered["Thứ hạng"] <= 3) & (filtered["Thứ hạng"].notna())].sort_values("Thứ hạng")
        top10_kws = filtered[(filtered["Thứ hạng"] <= 10) & (filtered["Thứ hạng"] > 3) & (filtered["Thứ hạng"].notna())].sort_values("Thứ hạng")
        top20_kws = filtered[(filtered["Thứ hạng"] <= 20) & (filtered["Thứ hạng"] > 10) & (filtered["Thứ hạng"].notna())].sort_values("Thứ hạng")
        outside_top20_kws = filtered[(filtered["Thứ hạng"] > 20) & (filtered["Thứ hạng"].notna())].sort_values("Thứ hạng")
        no_rank_kws = filtered[filtered["Thứ hạng"].isna()]

        # Hiển thị danh sách với expander để tiết kiệm không gian
        col1, col2 = st.columns(2)

        with col1:
            with st.expander("🥇 Top 3", expanded=False):
                if not top3_kws.empty:
                    for _, row in top3_kws.iterrows():
                        st.markdown(f"• **{row['Từ khóa']}** - Hạng {row['Thứ hạng']:.0f}")
                else:
                    st.info("Không có từ khóa nào trong Top 3")

            with st.expander("🏆 Top 10", expanded=False):
                if not top10_kws.empty:
                    for _, row in top10_kws.iterrows():
                        st.markdown(f"• **{row['Từ khóa']}** - Hạng {row['Thứ hạng']:.0f}")
                else:
                    st.info("Không có từ khóa nào trong Top 10 (ngoài Top 3)")

            with st.expander("🎯 Top 20", expanded=False):
                if not top20_kws.empty:
                    for _, row in top20_kws.iterrows():
                        st.markdown(f"• **{row['Từ khóa']}** - Hạng {row['Thứ hạng']:.0f}")
                else:
                    st.info("Không có từ khóa nào trong Top 20 (ngoài Top 10)")

        with col2:
            with st.expander("📈 Ngoài Top 20", expanded=False):
                if not outside_top20_kws.empty:
                    # Hiển thị tối đa 50 từ khóa để tránh quá dài
                    display_kws = outside_top20_kws.head(50)
                    for _, row in display_kws.iterrows():
                        st.markdown(f"• **{row['Từ khóa']}** - Hạng {row['Thứ hạng']:.0f}")
                    if len(outside_top20_kws) > 50:
                        st.info(f"Chỉ hiển thị 50/ {len(outside_top20_kws)} từ khóa. Sử dụng bộ lọc để xem thêm.")
                else:
                    st.info("Không có từ khóa nào ngoài Top 20")

            with st.expander("❌ Chưa có rank", expanded=False):
                if not no_rank_kws.empty:
                    # Hiển thị tối đa 50 từ khóa
                    display_kws = no_rank_kws.head(50)
                    for _, row in display_kws.iterrows():
                        st.markdown(f"• **{row['Từ khóa']}**")
                    if len(no_rank_kws) > 50:
                        st.info(f"Chỉ hiển thị 50/ {len(no_rank_kws)} từ khóa. Sử dụng bộ lọc để xem thêm.")
                else:
                    st.info("Tất cả từ khóa đều có rank")

    # ===================== MODE: SO SÁNH NGÀY =====================
    elif analysis_mode == "So sánh ngày":
        st.markdown('<p class="section-header">🔄 So sánh thay đổi thứ hạng</p>', unsafe_allow_html=True)
        
        if len(selected_days) < 2:
            st.warning("⚠️ Cần chọn ít nhất 2 ngày để so sánh")
        else:
            col1, col2 = st.columns(2)
            with col1:
                compare_date1 = st.selectbox("Ngày cũ (baseline)", selected_days, index=0)
            with col2:
                compare_date2 = st.selectbox("Ngày mới (so sánh)", selected_days, index=len(selected_days)-1)
            
            date1_str = sheet_map[compare_date1].strftime("%d-%m-%Y")
            date2_str = sheet_map[compare_date2].strftime("%d-%m-%Y")
            
            df_date1 = filtered[filtered["Ngày"] == date1_str][["Từ khóa", "Thứ hạng"]].copy()
            df_date2 = filtered[filtered["Ngày"] == date2_str][["Từ khóa", "Thứ hạng"]].copy()
            
            df_date1.rename(columns={"Thứ hạng": "Rank_Old"}, inplace=True)
            df_date2.rename(columns={"Thứ hạng": "Rank_New"}, inplace=True)
            
            comparison = pd.merge(df_date1, df_date2, on="Từ khóa", how="outer")
            comparison[["Trạng thái", "Thay đổi", "Icon"]] = comparison.apply(
                lambda row: compare_ranks(row["Rank_Old"], row["Rank_New"]), axis=1, result_type="expand"
            )
            
            # Metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("📈 Tăng hạng", (comparison["Thay đổi"] > 0).sum())
            with col2:
                st.metric("📉 Giảm hạng", (comparison["Thay đổi"] < 0).sum())
            with col3:
                st.metric("🆕 Mới có rank", (comparison["Trạng thái"] == "Mới có rank").sum())
            with col4:
                st.metric("❌ Mất rank", (comparison["Trạng thái"] == "Mất rank").sum())
            with col5:
                st.metric("➡️ Không đổi", (comparison["Thay đổi"] == 0).sum())
            
            # Chart
            status_counts = comparison["Trạng thái"].value_counts().reset_index()
            status_counts.columns = ["Trạng thái", "Số lượng"]
            
            fig_comparison = px.bar(status_counts, x="Trạng thái", y="Số lượng", color="Trạng thái",
                                   color_discrete_map={"Tăng": "#10b981", "Giảm": "#ef4444",
                                                      "Mới có rank": "#3b82f6", "Mất rank": "#f59e0b",
                                                      "Không đổi": "#94a3b8"}, text="Số lượng")
            fig_comparison.update_traces(textposition='outside')
            fig_comparison.update_layout(showlegend=False, height=400, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_comparison, width='stretch')
            
            # Top changes
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏆 Top 10 từ khóa tăng mạnh nhất")
                top_improved = comparison[comparison["Thay đổi"] > 0].nlargest(10, "Thay đổi")
                if not top_improved.empty:
                    for _, row in top_improved.iterrows():
                        st.markdown(f"**{row['Từ khóa']}**: {row['Rank_Old']:.0f} → {row['Rank_New']:.0f} (+{row['Thay đổi']:.0f})")
                else:
                    st.info("Không có từ khóa tăng hạng")
            
            with col2:
                st.markdown("#### ⚠️ Top 10 từ khóa giảm mạnh nhất")
                top_declined = comparison[comparison["Thay đổi"] < 0].nsmallest(10, "Thay đổi")
                if not top_declined.empty:
                    for _, row in top_declined.iterrows():
                        st.markdown(f"**{row['Từ khóa']}**: {row['Rank_Old']:.0f} → {row['Rank_New']:.0f} ({row['Thay đổi']:.0f})")
                else:
                    st.info("Không có từ khóa giảm hạng")
            
            # Movement chart
            st.markdown("#### 📈 Biểu đồ di chuyển thứ hạng (Top 20)")
            
            movement_data = comparison[(comparison["Rank_Old"].notna()) & (comparison["Rank_New"].notna())].copy()
            
            if not movement_data.empty:
                movement_data = movement_data.nlargest(20, "Thay đổi")
                
                fig_movement = go.Figure()
                
                for _, row in movement_data.iterrows():
                    color = "#10b981" if row["Thay đổi"] > 0 else "#ef4444" if row["Thay đổi"] < 0 else "#94a3b8"
                    
                    fig_movement.add_trace(go.Scatter(
                        x=[date1_str, date2_str], y=[row["Rank_Old"], row["Rank_New"]],
                        mode='lines+markers', name=row["Từ khóa"],
                        line=dict(color=color, width=2), marker=dict(size=8)
                    ))
                
                fig_movement.update_yaxes(autorange="reversed", title="Thứ hạng")
                fig_movement.update_xaxes(title="Ngày")
                fig_movement.update_layout(height=500, hovermode='closest', margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_movement, width='stretch')

    # ===================== MODE: PHÂN TÍCH TỪ KHÓA =====================
    elif analysis_mode == "Phân tích từ khóa":
        st.markdown('<p class="section-header">🔍 Phân tích từ khóa cụ thể</p>', unsafe_allow_html=True)
        
        all_keywords = filtered["Từ khóa"].unique().tolist()
        
        selected_keyword = st.selectbox("Chọn từ khóa để phân tích", all_keywords)
        
        if selected_keyword:
            kw_data = df[df["Từ khóa"] == selected_keyword].sort_values("Ngày_Sort")
            
            if not kw_data.empty:
                col1, col2, col3, col4 = st.columns(4)
                
                latest_rank = kw_data.iloc[-1]["Thứ hạng"]
                best_rank = kw_data["Thứ hạng"].min() if kw_data["Thứ hạng"].notna().any() else None
                avg_rank = kw_data["Thứ hạng"].mean() if kw_data["Thứ hạng"].notna().any() else None
                
                with col1:
                    st.metric("📍 Hạng hiện tại", f"{latest_rank:.0f}" if pd.notna(latest_rank) else "N/A")
                with col2:
                    st.metric("🏆 Hạng tốt nhất", f"{best_rank:.0f}" if pd.notna(best_rank) else "N/A")
                with col3:
                    st.metric("📊 Hạng trung bình", f"{avg_rank:.1f}" if pd.notna(avg_rank) else "N/A")
                with col4:
                    trend_change = kw_data.iloc[-1]["Thứ hạng"] - kw_data.iloc[0]["Thứ hạng"] if len(kw_data) > 1 else 0
                    st.metric("📈 Thay đổi", f"{trend_change:+.0f}" if pd.notna(trend_change) else "N/A")
                
                # History chart
                st.markdown("#### 📈 Lịch sử thứ hạng")
                
                fig_kw = go.Figure()
                fig_kw.add_trace(go.Scatter(
                    x=kw_data["Ngày"], y=kw_data["Thứ hạng"],
                    mode='lines+markers', name=selected_keyword,
                    line=dict(color='#667eea', width=3), marker=dict(size=10, color='#764ba2')
                ))
                fig_kw.update_yaxes(autorange="reversed", title="Thứ hạng")
                fig_kw.update_xaxes(title="Ngày")
                fig_kw.update_layout(height=400, hovermode='x unified', margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_kw, width='stretch')
                
                # Detail table
                st.markdown("#### 📄 Chi tiết theo ngày")
                st.dataframe(kw_data[["Ngày", "Thứ hạng", "URL", "Tiêu đề"]], width='stretch')
        
        # Compare multiple keywords
        st.markdown("---")
        st.markdown("#### 🔀 So sánh nhiều từ khóa")
        
        compare_keywords = st.multiselect("Chọn từ khóa để so sánh (tối đa 5)", all_keywords, max_selections=5)
        
        if compare_keywords:
            fig_multi = go.Figure()
            
            colors = ['#667eea', '#10b981', '#ef4444', '#f59e0b', '#3b82f6']
            
            for idx, kw in enumerate(compare_keywords):
                kw_data = df[df["Từ khóa"] == kw].sort_values("Ngày_Sort")
                fig_multi.add_trace(go.Scatter(
                    x=kw_data["Ngày"], y=kw_data["Thứ hạng"],
                    mode='lines+markers', name=kw,
                    line=dict(color=colors[idx % len(colors)], width=2),
                    marker=dict(size=8)
                ))
            
            fig_multi.update_yaxes(autorange="reversed", title="Thứ hạng")
            fig_multi.update_xaxes(title="Ngày")
            fig_multi.update_layout(height=450, hovermode='x unified', 
                                   legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                   margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_multi, width='stretch')

    # ===================== MODE: PHÂN TÍCH URL =====================
    elif analysis_mode == "Phân tích URL":
        st.markdown('<p class="section-header">🔗 Phân tích hiệu suất URL</p>', unsafe_allow_html=True)
        
        url_data = filtered[filtered["URL"].notna() & (filtered["URL"] != "")].copy()
        
        if url_data.empty:
            st.warning("⚠️ Không có dữ liệu URL")
        else:
            # Top performing URLs
            url_stats = url_data.groupby("URL").agg({
                "Từ khóa": "count",
                "Thứ hạng": ["mean", "min"]
            }).reset_index()
            url_stats.columns = ["URL", "Số từ khóa", "Rank TB", "Rank tốt nhất"]
            url_stats = url_stats.sort_values("Số từ khóa", ascending=False)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("🔗 Tổng URL", len(url_stats))
            with col2:
                st.metric("⭐ URL tốt nhất", url_stats.iloc[0]["Số từ khóa"] if not url_stats.empty else 0)
            with col3:
                avg_kw_per_url = url_stats["Số từ khóa"].mean()
                st.metric("📊 TB từ khóa/URL", f"{avg_kw_per_url:.1f}")
            
            # Top 10 URLs
            st.markdown("#### 🏆 Top 10 URL có nhiều từ khóa nhất")
            
            top_urls = url_stats.head(10)
            fig_url = px.bar(top_urls, x="Số từ khóa", y="URL", orientation='h',
                            color="Rank TB", color_continuous_scale="RdYlGn_r", text="Số từ khóa")
            fig_url.update_traces(textposition='outside')
            fig_url.update_layout(height=500, margin=dict(l=20, r=20, t=20, b=20), yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_url, width='stretch')
            
            # URLs need optimization
            st.markdown("#### ⚠️ URL cần tối ưu (nhiều từ khóa giảm hạng)")
            
            if len(selected_days) >= 2:
                dates_sorted = sorted(selected_days, key=lambda x: sheet_map[x])
                latest_date = sheet_map[dates_sorted[-1]].strftime("%d-%m-%Y")
                prev_date = sheet_map[dates_sorted[-2]].strftime("%d-%m-%Y")
                
                url_latest = url_data[url_data["Ngày"] == latest_date][["URL", "Từ khóa", "Thứ hạng"]].copy()
                url_prev = url_data[url_data["Ngày"] == prev_date][["URL", "Từ khóa", "Thứ hạng"]].copy()
                
                url_latest.rename(columns={"Thứ hạng": "Rank_New"}, inplace=True)
                url_prev.rename(columns={"Thứ hạng": "Rank_Old"}, inplace=True)
                
                url_comp = pd.merge(url_prev, url_latest, on=["URL", "Từ khóa"], how="inner")
                url_comp["Change"] = url_comp["Rank_Old"] - url_comp["Rank_New"]
                
                url_decline = url_comp[url_comp["Change"] < 0].groupby("URL").agg({
                    "Từ khóa": "count",
                    "Change": "sum"
                }).reset_index()
                url_decline.columns = ["URL", "Số KW giảm", "Tổng giảm"]
                url_decline = url_decline.sort_values("Số KW giảm", ascending=False).head(10)
                
                if not url_decline.empty:
                    for _, row in url_decline.iterrows():
                        st.markdown(f"🔴 **{row['URL']}**: {row['Số KW giảm']} từ khóa giảm (tổng: {row['Tổng giảm']:.0f} bậc)")
                else:
                    st.success("✅ Không có URL nào có xu hướng giảm hạng")
            
            # Detail table
            st.markdown("#### 📋 Bảng chi tiết URL")
            st.dataframe(url_stats, width='stretch', height=400)

    # ===================== MODE: NHÓM TỪ KHÓA =====================
    elif analysis_mode == "Nhóm từ khóa":
        st.markdown('<p class="section-header">🏷️ Phân tích theo nhóm từ khóa</p>', unsafe_allow_html=True)
        
        keyword_groups = extract_keyword_groups(filtered["Từ khóa"].unique())
        
        st.info(f"📊 Đã phát hiện {len(keyword_groups)} nhóm từ khóa")
        
        # Group stats
        group_stats = []
        for group_name, keywords in keyword_groups.items():
            group_data = filtered[filtered["Từ khóa"].isin(keywords)]
            
            stats = {
                "Nhóm": group_name,
                "Số từ khóa": len(keywords),
                "Top 3": (group_data["Thứ hạng"] <= 3).sum(),
                "Top 10": (group_data["Thứ hạng"] <= 10).sum(),
                "Rank TB": group_data["Thứ hạng"].mean() if group_data["Thứ hạng"].notna().any() else None,
                "Chưa rank": group_data["Thứ hạng"].isna().sum()
            }
            group_stats.append(stats)
        
        df_groups = pd.DataFrame(group_stats).sort_values("Số từ khóa", ascending=False)
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🏷️ Số nhóm", len(keyword_groups))
        with col2:
            largest_group = df_groups.iloc[0] if not df_groups.empty else None
            st.metric("📦 Nhóm lớn nhất", largest_group["Số từ khóa"] if largest_group is not None else 0)
        with col3:
            best_group = df_groups.nsmallest(1, "Rank TB") if not df_groups.empty else None
            if best_group is not None and not best_group.empty:
                st.metric("⭐ Nhóm tốt nhất", f"{best_group.iloc[0]['Nhóm'][:20]}...")
        
        # Chart
        st.markdown("#### 📊 Hiệu suất theo nhóm")
        
        fig_group = go.Figure()
        
        fig_group.add_trace(go.Bar(name='Top 3', x=df_groups['Nhóm'], y=df_groups['Top 3'], marker_color='#10b981'))
        fig_group.add_trace(go.Bar(name='Top 10', x=df_groups['Nhóm'], y=df_groups['Top 10'], marker_color='#3b82f6'))
        fig_group.add_trace(go.Bar(name='Chưa rank', x=df_groups['Nhóm'], y=df_groups['Chưa rank'], marker_color='#ef4444'))
        
        fig_group.update_layout(barmode='group', height=400, margin=dict(l=20, r=20, t=20, b=20),
                               legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_group, width='stretch')
        
        # Group selector
        st.markdown("#### 🔍 Xem chi tiết nhóm")
        
        selected_group = st.selectbox("Chọn nhóm", list(keyword_groups.keys()))
        
        if selected_group:
            group_kws = keyword_groups[selected_group]
            group_detail = filtered[filtered["Từ khóa"].isin(group_kws)].copy()
            
            st.markdown(f"**Nhóm '{selected_group}'** có {len(group_kws)} từ khóa:")
            
            # Performance by date
            if len(selected_days) > 1:
                group_trend = group_detail.groupby("Ngày").agg({
                    "Từ khóa": "count",
                    "Thứ hạng": "mean"
                }).reset_index()
                group_trend.columns = ["Ngày", "Số từ khóa", "Rank TB"]
                
                fig_group_trend = go.Figure()
                fig_group_trend.add_trace(go.Scatter(
                    x=group_trend["Ngày"], y=group_trend["Rank TB"],
                    mode='lines+markers', name='Rank trung bình',
                    line=dict(color='#667eea', width=3), marker=dict(size=10)
                ))
                fig_group_trend.update_yaxes(autorange="reversed", title="Rank trung bình")
                fig_group_trend.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_group_trend, width='stretch')
            
            # Keywords in group
            st.dataframe(group_detail[["Từ khóa", "Thứ hạng", "URL", "Ngày"]], width='stretch', height=400)

    # ===================== MODE: GOAL TRACKING =====================
    elif analysis_mode == "Mục tiêu":
        st.markdown('<p class="section-header">🎯 Goal Tracking & Milestones</p>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### Quản lý mục tiêu")
            
            # Add new goal
            with st.expander("➕ Thêm mục tiêu mới", expanded=False):
                all_keywords = filtered["Từ khóa"].unique().tolist()
                goal_keyword = st.selectbox("Chọn từ khóa", all_keywords, key="goal_kw")
                goal_target = st.number_input("Mục tiêu thứ hạng", min_value=1, max_value=100, value=3)
                goal_deadline = st.date_input("Thời hạn", value=datetime.now() + timedelta(days=30))
                
                if st.button("💾 Lưu mục tiêu"):
                    goal_id = f"{goal_keyword}_{datetime.now().timestamp()}"
                    st.session_state.goals[goal_id] = {
                        "keyword": goal_keyword,
                        "target": goal_target,
                        "deadline": goal_deadline,
                        "created": datetime.now()
                    }
                    save_session_state()  # Save goals to file
                    st.success("✅ Đã thêm mục tiêu!")
            
            # Display goals
            if st.session_state.goals:
                st.markdown("### 📋 Danh sách mục tiêu")
                
                for goal_id, goal in st.session_state.goals.items():
                    kw_data = filtered[filtered["Từ khóa"] == goal["keyword"]]
                    
                    if not kw_data.empty:
                        latest_data = kw_data.sort_values("Ngày_Sort").iloc[-1]
                        current_rank = latest_data["Thứ hạng"] if pd.notna(latest_data["Thứ hạng"]) else 100
                        
                        # Calculate progress
                        if current_rank <= goal["target"]:
                            progress = 100
                            status = "✅ Đạt mục tiêu!"
                            status_color = "#10b981"
                        else:
                            # Progress based on distance to goal
                            max_rank = 100
                            progress = max(0, (max_rank - current_rank) / (max_rank - goal["target"]) * 100)
                            
                            days_left = (goal["deadline"] - datetime.now().date()).days
                            if days_left < 0:
                                status = "⏰ Quá hạn"
                                status_color = "#ef4444"
                            elif days_left < 7:
                                status = f"⚠️ Còn {days_left} ngày"
                                status_color = "#f59e0b"
                            else:
                                status = f"⏳ Còn {days_left} ngày"
                                status_color = "#3b82f6"
                        
                        # Display goal card
                        st.markdown(f"""
                        <div class="snapshot-card">
                            <h4>{goal['keyword']}</h4>
                            <p>🎯 Mục tiêu: Top {goal['target']} | 📍 Hiện tại: {current_rank:.0f}</p>
                            <p style="color: {status_color};">{status}</p>
                            <div class="goal-progress">
                                <div class="goal-progress-bar" style="width: {progress}%"></div>
                            </div>
                            <small>Deadline: {goal['deadline']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Delete button
                        if st.button(f"🗑️ Xóa", key=f"del_{goal_id}"):
                            del st.session_state.goals[goal_id]
                            save_session_state()  # Save after deletion
                            st.rerun()
            else:
                st.info("📝 Chưa có mục tiêu nào. Hãy thêm mục tiêu đầu tiên!")
        
        with col2:
            st.markdown("### 📊 Thống kê")
            
            if st.session_state.goals:
                total_goals = len(st.session_state.goals)
                achieved = 0
                in_progress = 0
                overdue = 0
                
                for goal in st.session_state.goals.values():
                    kw_data = filtered[filtered["Từ khóa"] == goal["keyword"]]
                    if not kw_data.empty:
                        latest_rank = kw_data.sort_values("Ngày_Sort").iloc[-1]["Thứ hạng"]
                        if pd.notna(latest_rank) and latest_rank <= goal["target"]:
                            achieved += 1
                        elif (goal["deadline"] - datetime.now().date()).days < 0:
                            overdue += 1
                        else:
                            in_progress += 1
                
                st.metric("🎯 Tổng mục tiêu", total_goals)
                st.metric("✅ Đã đạt", achieved)
                st.metric("⏳ Đang theo dõi", in_progress)
                st.metric("⏰ Quá hạn", overdue)
                
                # Progress chart
                if total_goals > 0:
                    fig_goals = go.Figure(data=[go.Pie(
                        labels=['Đạt', 'Đang theo dõi', 'Quá hạn'],
                        values=[achieved, in_progress, overdue],
                        marker_colors=['#10b981', '#3b82f6', '#ef4444'],
                        hole=.4
                    )])
                    fig_goals.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
                    st.plotly_chart(fig_goals, width='stretch')

    # ===================== MODE: FORECASTING =====================
    elif analysis_mode == "Dự báo":
        st.markdown('<p class="section-header">📅 Dự báo xu hướng</p>', unsafe_allow_html=True)
        
        all_keywords = df["Từ khóa"].unique().tolist()
        forecast_keyword = st.selectbox("Chọn từ khóa để dự báo", all_keywords)
        
        forecast_days = st.slider("Dự báo bao nhiêu ngày?", min_value=7, max_value=90, value=30)
        
        if forecast_keyword:
            kw_data = df[df["Từ khóa"] == forecast_keyword].sort_values("Ngày_Sort")
            
            if len(kw_data) >= 3:
                predictions, trend = forecast_rank(kw_data, forecast_days)
                
                if predictions is not None:
                    # Display forecast info
                    col1, col2, col3 = st.columns(3)
                    
                    current_rank = kw_data.iloc[-1]["Thứ hạng"]
                    predicted_rank = predictions[-1]
                    
                    with col1:
                        st.metric("📍 Hạng hiện tại", f"{current_rank:.0f}" if pd.notna(current_rank) else "N/A")
                    with col2:
                        st.metric("🔮 Dự báo ({} ngày)".format(forecast_days), 
                                 f"{predicted_rank:.0f}", 
                                 delta=f"{current_rank - predicted_rank:+.0f}" if pd.notna(current_rank) else None,
                                 delta_color="inverse")
                    with col3:
                        trend_emoji = "📈" if trend == "up" else "📉" if trend == "down" else "➡️"
                        trend_text = "Tăng" if trend == "up" else "Giảm" if trend == "down" else "Ổn định"
                        st.metric("📊 Xu hướng", f"{trend_emoji} {trend_text}")
                    
                    # Forecast chart
                    st.markdown("#### 📈 Biểu đồ dự báo")
                    
                    # Historical data
                    historical_dates = kw_data["Ngày"].tolist()
                    historical_ranks = kw_data["Thứ hạng"].tolist()
                    
                    # Future dates
                    last_date = kw_data["Ngày_Sort"].max()
                    future_dates = [(last_date + timedelta(days=i+1)).strftime("%d-%m-%Y") for i in range(forecast_days)]
                    
                    fig_forecast = go.Figure()
                    
                    # Historical
                    fig_forecast.add_trace(go.Scatter(
                        x=historical_dates, y=historical_ranks,
                        mode='lines+markers', name='Lịch sử',
                        line=dict(color='#667eea', width=3),
                        marker=dict(size=8)
                    ))
                    
                    # Forecast
                    fig_forecast.add_trace(go.Scatter(
                        x=future_dates, y=predictions,
                        mode='lines+markers', name='Dự báo',
                        line=dict(color='#f59e0b', width=3, dash='dash'),
                        marker=dict(size=8, symbol='diamond')
                    ))
                    
                    fig_forecast.update_yaxes(autorange="reversed", title="Thứ hạng")
                    fig_forecast.update_xaxes(title="Ngày")
                    fig_forecast.update_layout(height=500, hovermode='x unified',
                                             margin=dict(l=20, r=20, t=20, b=20))
                    st.plotly_chart(fig_forecast, width='stretch')
                    
                    # Recommendations
                    st.markdown("### 💡 Đề xuất")
                    
                    if trend == "down" and predicted_rank > current_rank + 5:
                        st.markdown("""
                        <div class="alert-box alert-warning">
                            <strong>⚠️ Cảnh báo xu hướng giảm</strong><br/>
                            • Review và cập nhật nội dung<br/>
                            • Kiểm tra backlinks<br/>
                            • Tối ưu on-page SEO<br/>
                            • Phân tích đối thủ cạnh tranh
                        </div>
                        """, unsafe_allow_html=True)
                    elif trend == "up" and predicted_rank < current_rank - 3:
                        st.markdown("""
                        <div class="alert-box alert-success">
                            <strong>🎉 Xu hướng tích cực!</strong><br/>
                            • Tiếp tục strategy hiện tại<br/>
                            • Mở rộng nội dung liên quan<br/>
                            • Tăng cường internal linking<br/>
                            • Build thêm backlinks
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="alert-box alert-info">
                            <strong>ℹ️ Xu hướng ổn định</strong><br/>
                            • Duy trì chất lượng nội dung<br/>
                            • Monitor thường xuyên<br/>
                            • Chuẩn bị cho optimization tiếp theo
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Cần ít nhất 3 điểm dữ liệu để dự báo")

    # ===================== MODE: SNAPSHOTS =====================
    elif analysis_mode == "📸 Snapshots":
        st.markdown('<p class="section-header">📸 Quản lý Snapshots</p>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 💾 Danh sách Snapshots")
            
            if st.session_state.snapshots:
                for snap_name, snap_data in st.session_state.snapshots.items():
                    snap_date = snap_data["date"].strftime("%d/%m/%Y %H:%M")
                    snap_score = snap_data["score"]
                    snap_note = snap_data.get("note", "")
                    
                    st.markdown(f"""
                    <div class="snapshot-card">
                        <h4>📸 {snap_name}</h4>
                        <p>📅 {snap_date} | 📊 Score: {snap_score}/100</p>
                        <p><small>{snap_note if snap_note else 'Chưa có ghi chú'}</small></p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        if st.button("👁️ Xem", key=f"view_{snap_name}"):
                            st.session_state.selected_snapshot = snap_name
                    with col_b:
                        note = st.text_input("Ghi chú", value=snap_note, key=f"note_{snap_name}")
                        if st.button("💾", key=f"save_note_{snap_name}"):
                            st.session_state.snapshots[snap_name]["note"] = note
                            st.success("Đã lưu ghi chú!")
                    with col_c:
                        if st.button("🗑️ Xóa", key=f"del_snap_{snap_name}"):
                            del st.session_state.snapshots[snap_name]
                            st.rerun()
            else:
                st.info("📝 Chưa có snapshot nào. Tạo snapshot ở trang Tổng quan!")

            # Display selected snapshot
            if 'selected_snapshot' in st.session_state and st.session_state.selected_snapshot in st.session_state.snapshots:
                selected_snap = st.session_state.selected_snapshot
                snap_data = st.session_state.snapshots[selected_snap]

                st.markdown("---")
                st.markdown(f"### 👁️ Xem Snapshot: {selected_snap}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📅 Ngày tạo", snap_data["date"].strftime("%d/%m/%Y %H:%M"))
                with col2:
                    st.metric("📊 Score", f"{snap_data['score']}/100")
                with col3:
                    st.metric("📋 Số từ khóa", len(snap_data["data"]))

                # Display snapshot data
                st.markdown("#### 📄 Dữ liệu Snapshot")
                st.dataframe(
                    snap_data["data"].drop(columns=["Ngày_Sort"], errors="ignore"),
                    width='stretch',
                    height=400,
                    column_config={
                        "Thứ hạng": st.column_config.NumberColumn("Thứ hạng", format="%d"),
                        "URL": st.column_config.LinkColumn("URL")
                    }
                )

                # Close view button
                if st.button("❌ Đóng xem", key="close_view"):
                    del st.session_state.selected_snapshot
                    st.rerun()

        with col2:
            st.markdown("### 🔄 So sánh Snapshots")

            if len(st.session_state.snapshots) >= 2:
                snap_names = list(st.session_state.snapshots.keys())

                snap1 = st.selectbox("Snapshot 1", snap_names, index=0)
                snap2 = st.selectbox("Snapshot 2", snap_names, index=len(snap_names)-1)

                if st.button("📊 So sánh"):
                    data1 = st.session_state.snapshots[snap1]["data"]
                    data2 = st.session_state.snapshots[snap2]["data"]

                    score1 = st.session_state.snapshots[snap1]["score"]
                    score2 = st.session_state.snapshots[snap2]["score"]

                    st.metric("Thay đổi Score", f"{score2 - score1:+.1f}")

                    # Compare keywords
                    kw1 = set(data1["Từ khóa"].unique())
                    kw2 = set(data2["Từ khóa"].unique())

                    new_kw = len(kw2 - kw1)
                    lost_kw = len(kw1 - kw2)

                    st.metric("Từ khóa mới", new_kw)
                    st.metric("Từ khóa mất", lost_kw)

    # ===================== MODE: HEATMAP =====================
    elif analysis_mode == "Lịch nhiệt":
        st.markdown('<p class="section-header">📊 Performance Heatmap Calendar</p>', unsafe_allow_html=True)
        
        # Select month
        col1, col2 = st.columns(2)
        
        with col1:
            year = st.selectbox("Năm", range(2020, 2030), index=6)
        with col2:
            month = st.selectbox("Tháng", range(1, 13), index=0)
        
        # Calculate daily scores
        daily_scores = {}
        daily_keywords = {}
        for _, row in df.iterrows():
            date = row["Ngày_Sort"]
            if pd.notna(date) and date.year == year and date.month == month:
                day = date.day
                day_data = df[df["Ngày_Sort"] == date]
                score = calculate_seo_score(day_data)
                daily_scores[day] = score
                daily_keywords[day] = len(day_data)
        
        st.markdown("#### 📅 Lịch hiệu suất tháng {}/{}".format(month, year))
        
        # Get calendar
        cal = calendar.monthcalendar(year, month)
        
        # Prepare data for heatmap
        weekdays = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật']
        
        # Create matrix for heatmap
        heatmap_data = []
        text_data = []
        hover_data = []
        
        for week in cal:
            week_scores = []
            week_text = []
            week_hover = []
            for day in week:
                if day == 0:
                    week_scores.append(None)
                    week_text.append("")
                    week_hover.append("")
                else:
                    score = daily_scores.get(day, 0)
                    kw_count = daily_keywords.get(day, 0)
                    week_scores.append(score)
                    week_text.append(str(day))
                    
                    if score > 0:
                        if score >= 81:
                            label = "Xuất sắc"
                        elif score >= 61:
                            label = "Tốt"
                        elif score >= 41:
                            label = "Trung bình"
                        else:
                            label = "Yếu"
                        week_hover.append(f"Ngày {day}<br>Score: {score:.1f}/100<br>{label}<br>{kw_count} từ khóa")
                    else:
                        week_hover.append(f"Ngày {day}<br>Không có dữ liệu")
            
            heatmap_data.append(week_scores)
            text_data.append(week_text)
            hover_data.append(week_hover)
        
        # Create heatmap using Plotly
        fig_heatmap = go.Figure(data=go.Heatmap(
            z=heatmap_data,
            x=weekdays,
            y=[f"Tuần {i+1}" for i in range(len(cal))],
            text=text_data,
            hovertext=hover_data,
            hoverinfo='text',
            texttemplate='%{text}',
            textfont={"size": 16, "color": "black"},
            colorscale=[
                [0, "#F1F1F1"],      # No data
                [0.01, '#ef4444'],   # 0-40: Red
                [0.4, '#ef4444'],
                [0.41, '#f59e0b'],   # 41-60: Orange
                [0.6, '#f59e0b'],
                [0.61, '#3b82f6'],   # 61-80: Blue
                [0.8, '#3b82f6'],
                [0.81, '#10b981'],   # 81-100: Green
                [1, '#10b981']
            ],
            showscale=True,
            colorbar=dict(
                title=dict(text="Score", side="right"),
                tickmode="linear",
                tick0=0,
                dtick=20
            )
        ))
        
        fig_heatmap.update_layout(
            height=400,
            margin=dict(l=20, r=100, t=20, b=20),
            xaxis=dict(side='top'),
            yaxis=dict(autorange='reversed')
        )
        
        st.plotly_chart(fig_heatmap, width='stretch')
        
        # Legend
        st.markdown("""
        <div style="display: flex; gap: 1.5rem; margin: 1.5rem 0; flex-wrap: wrap; justify-content: center;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div style="width: 40px; height: 25px; background: #ef4444; border-radius: 4px;"></div>
                <span><strong>0-40</strong> Yếu</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div style="width: 40px; height: 25px; background: #f59e0b; border-radius: 4px;"></div>
                <span><strong>41-60</strong> Trung bình</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div style="width: 40px; height: 25px; background: #3b82f6; border-radius: 4px;"></div>
                <span><strong>61-80</strong> Tốt</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div style="width: 40px; height: 25px; background: #10b981; border-radius: 4px;"></div>
                <span><strong>81-100</strong> Xuất sắc</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Summary stats
        st.markdown("---")
        if daily_scores:
            avg_score = np.mean(list(daily_scores.values()))
            max_score = max(daily_scores.values())
            min_score = min(daily_scores.values())
            best_day = max(daily_scores, key=daily_scores.get)
            worst_day = min(daily_scores, key=daily_scores.get)
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("📊 Score TB", f"{avg_score:.1f}/100")
            with col2:
                st.metric("🏆 Cao nhất", f"{max_score:.1f}/100")
            with col3:
                st.metric("📉 Thấp nhất", f"{min_score:.1f}/100")
            with col4:
                st.metric("⭐ Ngày tốt nhất", f"{best_day}/{month}")
            with col5:
                st.metric("⚠️ Ngày cần cải thiện", f"{worst_day}/{month}")
            
            # Daily trend
            st.markdown("#### 📈 Xu hướng theo ngày trong tháng")
            
            days_sorted = sorted(daily_scores.keys())
            scores_sorted = [daily_scores[d] for d in days_sorted]
            
            fig_daily_trend = go.Figure()
            fig_daily_trend.add_trace(go.Scatter(
                x=days_sorted,
                y=scores_sorted,
                mode='lines+markers',
                name='Daily Score',
                line=dict(color='#667eea', width=3),
                marker=dict(size=10, color='#764ba2'),
                fill='tozeroy',
                fillcolor='rgba(102, 126, 234, 0.1)'
            ))
            
            fig_daily_trend.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="Ngày",
                yaxis_title="Score",
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_daily_trend, width='stretch')
        else:
            st.info("ℹ️ Không có dữ liệu cho tháng này")

    # ===================== Google Analytics Mode =====================
    elif analysis_mode == "Google Analytics":
        st.markdown('<p class="section-header">📊 Google Analytics</p>', unsafe_allow_html=True)

        # Google Analytics config - Multiple websites
        # Try to load GA credentials from Streamlit secrets first (for Streamlit Cloud)
        # Otherwise fall back to local credentials.json file
        try:
            if "gcp_service_account" in st.secrets:
                ga_creds_dict = st.secrets["gcp_service_account"]
                credentials = service_account.Credentials.from_service_account_info(
                    ga_creds_dict,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                )
            else:
                credentials = service_account.Credentials.from_service_account_file(
                    "credentials.json",
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                )
        except Exception as e:
            st.error(f"❌ Không thể tải Google Analytics credentials: {e}")
            st.info("💡 Để sử dụng Streamlit Cloud, thêm [gcp_service_account] vào Secrets")
            st.stop()
        
        WEBSITES = {
            "Website 1 - huyenhocviet.com": "464855282",
            "Website 2 - drtuananh.com": "517078868",
            "Website 3 - sdtc.com": "517020245",
        }

        # Website selector with multi-comparison option
        st.markdown("**🌐 Chọn website để phân tích**")
        col1, col2 = st.columns([2, 1])

        with col1:
            selected_website = st.selectbox("Website chính", list(WEBSITES.keys()), key="ga_website_select", label_visibility="collapsed")
        with col2:
            enable_comparison = st.checkbox("So sánh nhiều")

        selected_websites = [selected_website]
        if enable_comparison:
            other_websites = [w for w in WEBSITES.keys() if w != selected_website]
            if other_websites:
                st.markdown("**🔀 Website so sánh (tối đa 2 website)**")
                compare_websites = st.multiselect(
                    "Chọn website",
                    other_websites,
                    max_selections=2,
                    key="ga_compare_select",
                    label_visibility="collapsed"
                )
                selected_websites.extend(compare_websites)

        PROPERTY_ID = WEBSITES[selected_website]

        # Helper to get credentials for GA API
        def get_ga_credentials():
            try:
                if "gcp_service_account" in st.secrets:
                    ga_creds_dict = st.secrets["gcp_service_account"]
                    return service_account.Credentials.from_service_account_info(
                        ga_creds_dict,
                        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                    )
                else:
                    return service_account.Credentials.from_service_account_file(
                        "credentials.json",
                        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                    )
            except Exception as e:
                st.error(f"❌ Lỗi tải credentials: {e}")
                return None

        @st.cache_data(ttl=600)
        def get_analytics_data_ga(property_id, start_date, end_date, creds_str="default"):
                try:
                    # Get credentials from secrets or file
                    if "gcp_service_account" in st.secrets:
                        ga_creds_dict = st.secrets["gcp_service_account"]
                        credentials = service_account.Credentials.from_service_account_info(
                            ga_creds_dict,
                            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                        )
                    else:
                        credentials = service_account.Credentials.from_service_account_file(
                            "credentials.json",
                            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                        )
                    client = BetaAnalyticsDataClient(credentials=credentials)
                    request = RunReportRequest(
                        property=f"properties/{property_id}",
                        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                        dimensions=[
                            Dimension(name="date"),
                            Dimension(name="country"),
                            Dimension(name="city"),
                            Dimension(name="deviceCategory"),
                            Dimension(name="sessionSource"),
                        ],
                        metrics=[
                            Metric(name="activeUsers"),
                            Metric(name="sessions"),
                            Metric(name="screenPageViews"),
                            Metric(name="averageSessionDuration"),
                            Metric(name="bounceRate"),
                        ],
                    )
                    response = client.run_report(request)
                    data = []
                    for row in response.rows:
                        data.append({
                            'Ngày': row.dimension_values[0].value,
                            'Quốc gia': row.dimension_values[1].value,
                            'Thành phố': row.dimension_values[2].value,
                            'Thiết bị': row.dimension_values[3].value,
                            'Nguồn': row.dimension_values[4].value,
                            'Người dùng': int(row.metric_values[0].value),
                            'Phiên': int(row.metric_values[1].value),
                            'Lượt xem': int(row.metric_values[2].value),
                            'Thời lượng TB': float(row.metric_values[3].value),
                            'Tỷ lệ thoát': float(row.metric_values[4].value),
                        })
                    return pd.DataFrame(data)
                except Exception as e:
                    st.error(f"❌ Lỗi kết nối Google Analytics: {str(e)}")
                    return None

        @st.cache_data(ttl=600)
        def get_popular_pages_ga(property_id, start_date, end_date, creds_str="default"):
            try:
                # Get credentials from secrets or file
                if "gcp_service_account" in st.secrets:
                    ga_creds_dict = st.secrets["gcp_service_account"]
                    creds = service_account.Credentials.from_service_account_info(
                        ga_creds_dict,
                        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                    )
                else:
                    creds = service_account.Credentials.from_service_account_file(
                        "credentials.json",
                        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                    )
                client = BetaAnalyticsDataClient(credentials=creds)
                request = RunReportRequest(
                    property=f"properties/{property_id}",
                    date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                    dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
                    metrics=[
                        Metric(name="screenPageViews"),
                        Metric(name="activeUsers"),
                        Metric(name="averageSessionDuration"),
                    ],
                    limit=10,
                )
                response = client.run_report(request)
                data = []
                for row in response.rows:
                    data.append({
                        'Đường dẫn': row.dimension_values[0].value,
                        'Tiêu đề': row.dimension_values[1].value,
                        'Lượt xem': int(row.metric_values[0].value),
                        'Người dùng': int(row.metric_values[1].value),
                        'Thời lượng TB': float(row.metric_values[2].value),
                    })
                return pd.DataFrame(data)
            except Exception as e:
                st.error(f"❌ Lỗi khi lấy trang phổ biến: {str(e)}")
                return None

        # Date inputs
        col1, col2 = st.columns(2)
        with col1:
            ga_start = st.date_input("Google Analytics - Từ ngày", datetime.now() - timedelta(days=30), key="ga_start_date")
        with col2:
            ga_end = st.date_input("Google Analytics - Đến ngày", datetime.now(), key="ga_end_date")

        # Button below
        load_ga = st.button("🔄 Tải dữ liệu Google Analytics", key="load_ga")

        # Store current date range and website in session_state to track changes
        current_date_range = f"{selected_website}_{ga_start.strftime('%Y-%m-%d')}_{ga_end.strftime('%Y-%m-%d')}"
        if 'ga_current_range' not in st.session_state:
            st.session_state['ga_current_range'] = None

        # Load data if button pressed OR if date range changed OR if data doesn't exist
        should_load = load_ga or (st.session_state.get('ga_current_range') != current_date_range) or ('ga_data' not in st.session_state)

        if should_load:
            with st.spinner("⏳ Đang tải dữ liệu từ Google Analytics..."):
                # Clear cache for these functions to force fresh API call
                get_analytics_data_ga.clear()
                get_popular_pages_ga.clear()
                
                df_ga = get_analytics_data_ga(PROPERTY_ID, ga_start.strftime("%Y-%m-%d"), ga_end.strftime("%Y-%m-%d"))
                pages_ga = get_popular_pages_ga(PROPERTY_ID, ga_start.strftime("%Y-%m-%d"), ga_end.strftime("%Y-%m-%d"))

                if df_ga is not None and not df_ga.empty:
                    st.session_state['ga_data'] = df_ga
                    st.session_state['ga_pages'] = pages_ga
                    st.session_state['ga_current_range'] = current_date_range
                    st.success("✅ Tải dữ liệu Google Analytics thành công!")
                else:
                    st.error("❌ Không thể tải dữ liệu Google Analytics. Vui lòng kiểm tra Property ID và quyền truy cập.")

        if 'ga_data' in st.session_state:
            ga_df = st.session_state['ga_data']

            # Overview metrics
            st.markdown('<p class="section-header">📈 Tổng quan Google Analytics</p>', unsafe_allow_html=True)
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("👥 Người dùng", f"{ga_df['Người dùng'].sum():,}")
            with col2:
                st.metric("🔄 Phiên", f"{ga_df['Phiên'].sum():,}")
            with col3:
                st.metric("📄 Lượt xem", f"{ga_df['Lượt xem'].sum():,}")
            with col4:
                avg_duration = ga_df['Thời lượng TB'].mean()
                st.metric("⏱️ Thời lượng TB (s)", f"{avg_duration:.1f}")
            with col5:
                avg_bounce = ga_df['Tỷ lệ thoát'].mean()
                st.metric("⚡ Tỷ lệ thoát TB", f"{avg_bounce:.1%}")

            st.markdown("---")

            if enable_comparison and len(selected_websites) > 1:
                tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊 Biểu đồ", "🌍 Quốc gia", "🏙️ Thành phố", "📱 Thiết bị", "🔥 Top trang", "📋 Dữ liệu", "⚖️ So sánh Website"])
            else:
                tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Biểu đồ", "🌍 Quốc gia", "🏙️ Thành phố", "📱 Thiết bị", "🔥 Top trang", "📋 Dữ liệu"])
                tab7 = None

            with tab1:
                # Người dùng theo ngày
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.subheader("📈 Người dùng theo ngày")
                    daily_users = ga_df.groupby('Ngày')['Người dùng'].sum().reset_index()
                    daily_users['Ngày'] = pd.to_datetime(daily_users['Ngày'], format='%Y%m%d')
                    daily_users = daily_users.sort_values('Ngày')
                    fig1 = px.line(daily_users, x='Ngày', y='Người dùng', markers=True, color_discrete_sequence=['#667eea'])
                    fig1.update_layout(height=350, hovermode='x unified', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig1, width='stretch')
                
                with col_b:
                    st.subheader("📊 Phiên theo ngày")
                    daily_sessions = ga_df.groupby('Ngày')['Phiên'].sum().reset_index()
                    daily_sessions['Ngày'] = pd.to_datetime(daily_sessions['Ngày'], format='%Y%m%d')
                    daily_sessions = daily_sessions.sort_values('Ngày')
                    fig2 = px.bar(daily_sessions, x='Ngày', y='Phiên', color='Phiên', color_continuous_scale='Viridis')
                    fig2.update_layout(height=350, hovermode='x unified', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                    st.plotly_chart(fig2, use_container_width=True)

                # Source breakdown
                col_c, col_d = st.columns(2)
                
                with col_c:
                    st.subheader("🔗 Top Nguồn truy cập")
                    source_data = ga_df.groupby('Nguồn')['Phiên'].sum().nlargest(8).reset_index()
                    fig3 = px.bar(source_data, x='Phiên', y='Nguồn', orientation='h', color='Phiên', color_continuous_scale='Blues')
                    fig3.update_layout(height=350, showlegend=False, plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig3, use_container_width=True)
                
                with col_d:
                    st.subheader("📋 Top Quốc gia")
                    country_data = ga_df.groupby('Quốc gia')['Người dùng'].sum().nlargest(10).reset_index()
                    fig4 = px.bar(country_data, x='Người dùng', y='Quốc gia', orientation='h', color='Người dùng', color_continuous_scale='Greens')
                    fig4.update_layout(height=350, showlegend=False, plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig4, use_container_width=True)

            with tab2:
                st.subheader("🌍 Phân tích theo Quốc gia")
                country_detail = ga_df.groupby('Quốc gia').agg({
                    'Người dùng': 'sum',
                    'Phiên': 'sum',
                    'Lượt xem': 'sum',
                    'Thời lượng TB': 'mean',
                    'Tỷ lệ thoát': 'mean'
                }).reset_index().sort_values('Người dùng', ascending=False)
                
                col_x, col_y = st.columns(2)
                with col_x:
                    fig_country = px.pie(country_detail.head(10), values='Người dùng', names='Quốc gia', hole=0.4)
                    fig_country.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
                    st.plotly_chart(fig_country, use_container_width=True)
                
                with col_y:
                    st.dataframe(country_detail[['Quốc gia', 'Người dùng', 'Phiên', 'Lượt xem']].head(15), use_container_width=True)

                with tab4:
                    st.subheader("📱 Phân tích theo Thiết bị")
                    device_detail = ga_df.groupby('Thiết bị').agg({
                        'Người dùng': 'sum',
                        'Phiên': 'sum',
                        'Lượt xem': 'sum',
                        'Thời lượng TB': 'mean',
                        'Tỷ lệ thoát': 'mean'
                    }).reset_index().sort_values('Người dùng', ascending=False)
                    
                    col_m, col_n = st.columns(2)
                    with col_m:
                        fig_device = px.pie(device_detail, values='Người dùng', names='Thiết bị', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
                        fig_device.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
                        st.plotly_chart(fig_device, use_container_width=True)
                    
                    with col_n:
                        st.dataframe(device_detail[['Thiết bị', 'Người dùng', 'Phiên', 'Tỷ lệ thoát']], use_container_width=True)

                with tab3:
                    st.subheader("🏙️ Phân tích theo Thành phố")
                    city_detail = ga_df.groupby(['Quốc gia', 'Thành phố']).agg({
                        'Người dùng': 'sum',
                        'Phiên': 'sum',
                        'Lượt xem': 'sum',
                        'Thời lượng TB': 'mean',
                        'Tỷ lệ thoát': 'mean'
                    }).reset_index().sort_values('Người dùng', ascending=False)
                    
                    # Remove (not set) or empty cities
                    city_detail = city_detail[city_detail['Thành phố'] != '(not set)'].copy()
                    
                    col_city1, col_city2 = st.columns(2)
                    
                    with col_city1:
                        st.markdown("#### 🏙️ Top 10 Thành phố")
                        top_cities = city_detail.head(10)
                        if not top_cities.empty:
                            fig_city = px.bar(top_cities, x='Người dùng', y='Thành phố', orientation='h', 
                                             color='Người dùng', color_continuous_scale='Reds', text='Người dùng')
                            fig_city.update_traces(textposition='outside')
                            fig_city.update_layout(height=400, showlegend=False, plot_bgcolor='rgba(0,0,0,0)', 
                                                 yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_city, use_container_width=True)
                    
                    with col_city2:
                        st.markdown("#### 📊 Chi tiết Top thành phố")
                        if not city_detail.empty:
                            display_cities = city_detail.head(15)[['Quốc gia', 'Thành phố', 'Người dùng', 'Phiên', 'Lượt xem']].copy()
                            display_cities.columns = ['Quốc gia', 'Thành phố', 'Người dùng', 'Phiên', 'Lượt xem']
                            st.dataframe(display_cities, use_container_width=True, hide_index=True)
                    
                    # Vị trí chi tiết theo quốc gia
                    st.markdown("---")
                    st.markdown("#### 🗺️ Chi tiết vị trí theo quốc gia")
                    
                    countries_list = sorted(ga_df['Quốc gia'].unique())
                    selected_country_detail = st.selectbox("Chọn quốc gia để xem thành phố", countries_list)
                    
                    if selected_country_detail:
                        country_cities = ga_df[ga_df['Quốc gia'] == selected_country_detail].groupby('Thành phố').agg({
                            'Người dùng': 'sum',
                            'Phiên': 'sum',
                            'Lượt xem': 'sum'
                        }).reset_index().sort_values('Người dùng', ascending=False)
                        
                        country_cities = country_cities[country_cities['Thành phố'] != '(not set)'].copy()
                        
                        if not country_cities.empty:
                            st.markdown(f"**{selected_country_detail}** - Tổng {len(country_cities)} thành phố")
                            st.dataframe(country_cities, use_container_width=True, hide_index=True)
                        else:
                            st.info(f"Không có dữ liệu chi tiết thành phố cho {selected_country_detail}")
                    
                    # Multi-series time series - So sánh xu hướng thành phố theo ngày
                    st.markdown("---")
                    st.markdown("#### 📈 Xu hướng người dùng theo ngày (Top 5 thành phố)")
                    
                    # Get top 5 cities
                    top_5_cities = city_detail.head(5)['Thành phố'].tolist()
                    
                    if top_5_cities and len(ga_df) > 0:
                        # Prepare data for time series
                        fig_city_trend = go.Figure()
                        
                        colors_palette = ['#667eea', '#ef4444', '#10b981', '#f59e0b', '#3b82f6']
                        
                        for idx, city_name in enumerate(top_5_cities):
                            city_data = ga_df[ga_df['Thành phố'] == city_name].groupby('Ngày')['Người dùng'].sum().reset_index()
                            city_data['Ngày'] = pd.to_datetime(city_data['Ngày'], format='%Y%m%d')
                            city_data = city_data.sort_values('Ngày')
                            
                            if not city_data.empty:
                                fig_city_trend.add_trace(go.Scatter(
                                    x=city_data['Ngày'],
                                    y=city_data['Người dùng'],
                                    mode='lines+markers',
                                    name=city_name,
                                    line=dict(color=colors_palette[idx % len(colors_palette)], width=3),
                                    marker=dict(size=8)
                                ))
                        
                        fig_city_trend.update_layout(
                            height=450,
                            hovermode='x unified',
                            plot_bgcolor='rgba(0,0,0,0)',
                            xaxis_title='Ngày',
                            yaxis_title='Số người dùng',
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            margin=dict(l=20, r=20, t=20, b=20)
                        )
                        
                        st.plotly_chart(fig_city_trend, use_container_width=True)

                with tab5:
                    st.subheader("🔥 Top trang phổ biến")
                    if 'ga_pages' in st.session_state and st.session_state['ga_pages'] is not None:
                        pages_data = st.session_state['ga_pages']
                        
                        # Summary metrics
                        col_p1, col_p2, col_p3 = st.columns(3)
                        with col_p1:
                            st.metric("📄 Số trang", len(pages_data))
                        with col_p2:
                            st.metric("👁️ Tổng lượt xem", f"{pages_data['Lượt xem'].sum():,}")
                        with col_p3:
                            st.metric("👥 Tổng người dùng", f"{pages_data['Người dùng'].sum():,}")
                        
                        st.markdown("---")
                        
                        for idx, row in pages_data.iterrows():
                            with st.container():
                                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                                c1.markdown(f"**{idx+1}. {row['Tiêu đề'][:60]}**")
                                c1.caption(row['Đường dẫn'][:80])
                                c2.metric("👁️ Lượt xem", f"{int(row['Lượt xem']):,}")
                                c3.metric("👥 Người dùng", f"{int(row['Người dùng']):,}")
                                c4.metric("⏱️ Thời lượng", f"{row['Thời lượng TB']:.0f}s")
                                st.markdown("---")
                    else:
                        st.info("Không có dữ liệu trang từ Google Analytics")

                with tab6:
                    st.subheader("📋 Dữ liệu Google Analytics chi tiết đầy đủ")
                    
                    # Filters
                    col_f1, col_f2, col_f3 = st.columns(3)
                    with col_f1:
                        countries_filter = st.multiselect('Lọc theo quốc gia', ga_df['Quốc gia'].unique(), default=None)
                    with col_f2:
                        devices_filter = st.multiselect('Lọc theo thiết bị', ga_df['Thiết bị'].unique(), default=None)
                    with col_f3:
                        sources_filter = st.multiselect('Lọc theo nguồn', ga_df['Nguồn'].unique(), default=None)
                    
                    # Apply filters
                    filtered_ga = ga_df.copy()
                    if countries_filter:
                        filtered_ga = filtered_ga[filtered_ga['Quốc gia'].isin(countries_filter)]
                    if devices_filter:
                        filtered_ga = filtered_ga[filtered_ga['Thiết bị'].isin(devices_filter)]
                    if sources_filter:
                        filtered_ga = filtered_ga[filtered_ga['Nguồn'].isin(sources_filter)]
                    
                    # Export to CSV
                    csv_data = filtered_ga.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 Tải CSV",
                        data=csv_data,
                        file_name=f"ga_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                    st.dataframe(filtered_ga.sort_values('Ngày', ascending=False), use_container_width=True, height=500)

                # Comparison Tab
                if tab7 is not None:
                    with tab7:
                        st.subheader("⚖️ So sánh Website")
                        
                        # Load data for all comparison websites
                        compare_data_dict = {}
                        for comp_website in selected_websites[1:]:
                            comp_property_id = WEBSITES[comp_website]
                            with st.spinner(f"⏳ Đang tải dữ liệu từ {comp_website}..."):
                                get_analytics_data_ga.clear()
                                comp_df = get_analytics_data_ga(comp_property_id, ga_start.strftime("%Y-%m-%d"), ga_end.strftime("%Y-%m-%d"))
                            if comp_df is not None and not comp_df.empty:
                                compare_data_dict[comp_website] = comp_df
                        
                        if compare_data_dict:
                            # Overview comparison - all websites
                            st.markdown("#### 📊 So sánh Tổng quan")
                            
                            comparison_metrics = []
                            for website in selected_websites:
                                if website == selected_website:
                                    df_temp = ga_df
                                else:
                                    df_temp = compare_data_dict.get(website)
                                
                                if df_temp is not None and not df_temp.empty:
                                    comparison_metrics.append({
                                        'Website': website,
                                        'Người dùng': f"{df_temp['Người dùng'].sum():,}",
                                        'Phiên': f"{df_temp['Phiên'].sum():,}",
                                        'Lượt xem': f"{df_temp['Lượt xem'].sum():,}",
                                        'Thời lượng TB': f"{df_temp['Thời lượng TB'].mean():.1f}s",
                                        'Tỷ lệ thoát': f"{df_temp['Tỷ lệ thoát'].mean():.1%}"
                                    })
                            
                            if comparison_metrics:
                                comparison_df = pd.DataFrame(comparison_metrics)
                                st.dataframe(comparison_df, use_container_width=True, hide_index=True)
                            
                            st.divider()
                            
                            # Comparison charts
                            colors_list = ['#667eea', '#f59e0b', '#10b981']
                            
                            col_chart1, col_chart2 = st.columns(2)
                            
                            # Comparison charts - Người dùng theo ngày
                            with col_chart1:
                                st.markdown("#### 📈 Người dùng theo ngày")
                                
                                daily_users_combined = []
                                
                                for idx, website in enumerate(selected_websites):
                                    if website == selected_website:
                                        df_temp = ga_df.copy()
                                    else:
                                        df_temp = compare_data_dict.get(website)
                                        if df_temp is not None:
                                            df_temp = df_temp.copy()
                                    
                                    if df_temp is not None and not df_temp.empty:
                                        # Convert Ngày to datetime if it's a string
                                        if df_temp['Ngày'].dtype == 'object':
                                            df_temp['Ngày'] = pd.to_datetime(df_temp['Ngày'], format='%Y%m%d')
                                        
                                        daily = df_temp.groupby('Ngày')['Người dùng'].sum().reset_index()
                                        daily['Website'] = website
                                        daily_users_combined.append(daily)
                                
                                if daily_users_combined:
                                    combined_data = pd.concat(daily_users_combined, ignore_index=True)
                                    # Ensure Ngày is datetime
                                    combined_data['Ngày'] = pd.to_datetime(combined_data['Ngày'])
                                    combined_data = combined_data.sort_values('Ngày')
                                    
                                    fig_users = px.line(
                                        combined_data,
                                        x='Ngày',
                                        y='Người dùng',
                                        color='Website',
                                        markers=True,
                                        color_discrete_sequence=colors_list[:len(selected_websites)]
                                    )
                                    fig_users.update_layout(
                                        height=500, 
                                        hovermode='x unified', 
                                        plot_bgcolor='rgba(0,0,0,0)',
                                        margin=dict(l=50, r=20, t=40, b=50),
                                        legend=dict(x=0.5, y=-0.2, xanchor='center', yanchor='top', orientation='h')
                                    )
                                    st.plotly_chart(fig_users, use_container_width=True)
                            
                            # Comparison charts - Phiên theo ngày
                            with col_chart2:
                                st.markdown("#### 📊 Phiên theo ngày")
                                
                                daily_sessions_combined = []
                                
                                for website in selected_websites:
                                    if website == selected_website:
                                        df_temp = ga_df.copy()
                                    else:
                                        df_temp = compare_data_dict.get(website)
                                        if df_temp is not None:
                                            df_temp = df_temp.copy()
                                    
                                    if df_temp is not None and not df_temp.empty:
                                        # Convert Ngày to datetime if it's a string
                                        if df_temp['Ngày'].dtype == 'object':
                                            df_temp['Ngày'] = pd.to_datetime(df_temp['Ngày'], format='%Y%m%d')
                                        
                                        daily = df_temp.groupby('Ngày')['Phiên'].sum().reset_index()
                                        daily['Website'] = website
                                        daily_sessions_combined.append(daily)
                                
                                if daily_sessions_combined:
                                    combined_sessions = pd.concat(daily_sessions_combined, ignore_index=True)
                                    # Ensure Ngày is datetime
                                    combined_sessions['Ngày'] = pd.to_datetime(combined_sessions['Ngày'])
                                    combined_sessions = combined_sessions.sort_values('Ngày')
                                    
                                    fig_sessions = px.bar(
                                        combined_sessions,
                                        x='Ngày',
                                        y='Phiên',
                                        color='Website',
                                        barmode='group',
                                        color_discrete_sequence=colors_list[:len(selected_websites)]
                                    )
                                    fig_sessions.update_layout(
                                        height=500, 
                                        hovermode='x unified', 
                                        plot_bgcolor='rgba(0,0,0,0)',
                                        margin=dict(l=50, r=20, t=40, b=50),
                                        legend=dict(x=0.5, y=-0.2, xanchor='center', yanchor='top', orientation='h')
                                    )
                                    st.plotly_chart(fig_sessions, use_container_width=True)
                            
                            st.divider()
                            
                            # Top sources comparison for each website
                            st.markdown("#### 🔗 Top Nguồn truy cập - So sánh website")
                            
                            cols = st.columns(len(selected_websites))
                            
                            for idx, website in enumerate(selected_websites):
                                if website == selected_website:
                                    df_temp = ga_df
                                else:
                                    df_temp = compare_data_dict.get(website)
                                
                                if df_temp is not None and not df_temp.empty:
                                    with cols[idx]:
                                        st.markdown(f"**{website}**")
                                        source_data = df_temp.groupby('Nguồn')['Phiên'].sum().nlargest(5).reset_index()
                                        fig_src = px.bar(
                                            source_data,
                                            x='Phiên',
                                            y='Nguồn',
                                            orientation='h',
                                            color='Phiên',
                                            color_continuous_scale='Blues'
                                        )
                                        fig_src.update_layout(height=300, showlegend=False, plot_bgcolor='rgba(0,0,0,0)')
                                        st.plotly_chart(fig_src, use_container_width=True)
                        else:
                            st.error(f"❌ Không thể tải dữ liệu từ các website so sánh")


        # ===================== OTHER MODES (Keep existing code) =====================
    # So sánh ngày, Phân tích từ khóa, Phân tích URL, Nhóm từ khóa
    # ... (giữ nguyên code của các mode này từ version trước)

    # ===================== DATA TABLE =====================
    st.markdown('<p class="section-header">📄 Bảng dữ liệu chi tiết</p>', unsafe_allow_html=True)
    
    st.markdown(f"**Hiển thị {len(filtered):,} từ khóa**")
    
    # Sắp xếp lại thứ tự cột theo yêu cầu
    column_order = [
        "Từ khóa", "Trang", "Vị trí", "Thứ hạng", "URL",
        "Tiêu đề", "Domain mục tiêu", "Ngày tìm kiếm", "Ngày"
    ]
    
    # Chỉ giữ lại các cột tồn tại và theo thứ tự mong muốn
    display_columns = [col for col in column_order if col in filtered.columns]
    filtered_display = filtered[display_columns].copy()
    filtered_display.index = range(1, len(filtered_display) + 1)  # Bắt đầu từ 1
    
    st.dataframe(
        filtered_display.drop(columns=["Ngày_Sort"], errors="ignore"),
        width='stretch',
        height=600,
        column_config={
            "Thứ hạng": st.column_config.NumberColumn("Thứ hạng", format="%d"),
            "URL": st.column_config.LinkColumn("URL")
        }
    )

    # Download
    csv = filtered.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="⬇️ Tải xuống dữ liệu (CSV)",
        data=csv,
        file_name=f"seo_data_{selected_domain}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

except Exception as e:
    st.error(f"❌ Đã xảy ra lỗi: {e}")
    st.exception(e)
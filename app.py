import datetime
from datetime import date, datetime, time, timedelta
import time as time_module
import gspread
from google.oauth2.service_account import Credentials
import jdatetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==========================================
# ۱. تنظیمات صفحه و ظاهر برنامه
# ==========================================
st.set_page_config(
    page_title="مدیریت، اهداف و عارضه‌یابی زمان (ابری)",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",  # نوار کناری از ابتدا باز باشد تا تقویم دیده شود
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;600;700&display=swap');

    html, body, [class*="css"], .stMarkdown, .stText, p, h1, h2, h3, span, div, label {
        font-family: 'Vazirmatn', sans-serif !important;
        direction: rtl;
        text-align: right;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        justify-content: flex-start;
    }

    .stTabs [data-baseweb="tab"] {
        height: 48px;
        padding-left: 20px;
        padding-right: 20px;
        border-radius: 8px 8px 0px 0px;
        font-weight: 600;
        font-size: 1rem;
    }

    .metric-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .metric-card h3 {
        font-size: 1.8rem;
        margin: 0;
        font-weight: 700;
    }
    .metric-card p {
        margin: 6px 0 0 0;
        font-size: 0.85rem;
        color: #94A3B8;
        text-align: center;
    }

    .badge-productive { background-color: rgba(16, 185, 129, 0.15); color: #34D399; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-waste { background-color: rgba(239, 68, 68, 0.15); color: #F87171; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    .badge-routine { background-color: rgba(148, 163, 184, 0.15); color: #CBD5E1; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
    
    /* استایل دکمه‌های تقویم سایدبار */
    section[data-testid="stSidebar"] div.stButton > button {
        padding: 4px 2px !important;
        font-size: 0.82rem !important;
        min-height: 34px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ROUTINE_TASKS = [
    "--- انتخاب روتین ---",
    "🛌 خواب شبانه",
    "🍳 صبحانه و آماده‌سازی",
    "💇‍♂️ رسیدگی به استایل و ظاهر",
    "🙏 شکرگزاری",
    "⭐ تمرین ستاره قطبی",
    "❤️ روابط و خانواده",
    "🚗 رفت‌وآمد به محل کار/دانشگاه",
    "☕ استراحت / میان‌وعده",
    "🍽️ ناهار و استراحت",
    "🏋️ ورزش و تمرین",
    "📱 شبکه‌های اجتماعی (وب‌گردی)",
    "🍽️ شام و استراحت",
    "📖 مطالعه روزانه",
]

# تابع کمکی برای انتخاب تاریخ شمسی و بازگرداندن خروجی میلادی استاندارد
def jalali_date_picker(label: str, default_date: date = None, key: str = "j_date"):
    if default_date is None:
        default_date = date.today()
    j_def = jdatetime.date.fromgregorian(date=default_date)
    
    st.markdown(f"<p style='font-size: 0.88rem; margin-bottom: 4px; font-weight: 600;'>{label}</p>", unsafe_allow_html=True)
    c_y, c_m, c_d = st.columns([1.2, 1, 1])
    
    years = list(range(j_def.year - 2, j_def.year + 4))
    months = list(range(1, 13))
    
    with c_y:
        sel_y = st.selectbox("سال", years, index=years.index(j_def.year) if j_def.year in years else 0, key=f"{key}_y", label_visibility="collapsed")
    with c_m:
        sel_m = st.selectbox("ماه", months, index=j_def.month - 1, key=f"{key}_m", label_visibility="collapsed")
    
    max_days = 29 if sel_m == 12 else (30 if sel_m > 6 else 31)
    days = list(range(1, max_days + 1))
    init_day = min(j_def.day, max_days)
    
    with c_d:
        sel_d = st.selectbox("روز", days, index=init_day - 1, key=f"{key}_d", label_visibility="collapsed")
        
    try:
        j_obj = jdatetime.date(sel_y, sel_m, sel_d)
        return j_obj.togregorian()
    except Exception:
        return default_date

# ==========================================
# ۲. ارتباط مستقیم با Google Sheets
# ==========================================
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials_dict = dict(st.secrets["connections"]["gsheets"])
    if "private_key" in credentials_dict:
        credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    return gspread.authorize(creds)


def get_worksheet(sheet_name):
    gc = get_gspread_client()
    target = st.secrets["connections"]["gsheets"]["spreadsheet"].strip()
    sh = gc.open_by_url(target) if target.startswith("http") else gc.open_by_key(target)
    try:
        return sh.worksheet(sheet_name)
    except Exception:
        return sh.add_worksheet(title=sheet_name, rows=100, cols=20)


@st.cache_data(ttl=300)
def load_sheet_df(sheet_name):
    for attempt in range(3):
        try:
            ws = get_worksheet(sheet_name)
            vals = ws.get_all_values()
            if not vals or len(vals) < 2:
                return pd.DataFrame()
            headers = [str(c).strip() for c in vals[0]]
            df = pd.DataFrame(vals[1:], columns=headers)
            df = df[df.apply(lambda row: "".join(row.values.astype(str)).strip() != "", axis=1)]
            return df
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                time_module.sleep(2)
                continue
            return pd.DataFrame()
    return pd.DataFrame()


def save_sheet_df(sheet_name, df):
    try:
        ws = get_worksheet(sheet_name)
        df_clean = df.fillna("").astype(str)
        all_data = [df_clean.columns.tolist()] + df_clean.values.tolist()
        ws.clear()
        ws.update(range_name="A1", values=all_data)
        load_sheet_df.clear()
    except Exception as e:
        st.error(f"خطا در همگام‌سازی ابری: {e}")


# --- توابع اهداف (Goals) ---
def get_all_goals():
    df = load_sheet_df("goals")
    if not df.empty and "id" in df.columns:
        df["progress"] = pd.to_numeric(df.get("progress", 0), errors="coerce").fillna(0).astype(int)
        df["id"] = df["id"].astype(str)
        return df
    return pd.DataFrame(columns=["id", "title", "category", "goal_type", "target_date", "progress", "status"])


def add_goal(title, category, goal_type, target_date, progress):
    df = get_all_goals()
    new_id = f"G-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_row = pd.DataFrame(
        [
            {
                "id": new_id,
                "title": title,
                "category": category,
                "goal_type": goal_type,
                "target_date": str(target_date),
                "progress": int(progress),
                "status": "completed" if progress >= 100 else "active",
            }
        ]
    )
    df = pd.concat([new_row, df], ignore_index=True)
    save_sheet_df("goals", df)


def update_goal_progress(goal_id, progress):
    df = get_all_goals()
    if not df.empty:
        idx = df[df["id"] == str(goal_id)].index
        if not idx.empty:
            df.loc[idx, "progress"] = int(progress)
            df.loc[idx, "status"] = "completed" if int(progress) >= 100 else "active"
            save_sheet_df("goals", df)


def update_goal_full(goal_id, title, category, goal_type, target_date, progress):
    df = get_all_goals()
    if not df.empty:
        idx = df[df["id"] == str(goal_id)].index
        if not idx.empty:
            df.loc[idx, "title"] = title
            df.loc[idx, "category"] = category
            df.loc[idx, "goal_type"] = goal_type
            df.loc[idx, "target_date"] = str(target_date)
            df.loc[idx, "progress"] = int(progress)
            df.loc[idx, "status"] = "completed" if int(progress) >= 100 else "active"
            save_sheet_df("goals", df)


def delete_goal(goal_id):
    df = get_all_goals()
    if not df.empty:
        df = df[df["id"] != str(goal_id)]
        save_sheet_df("goals", df)


# --- توابع برنامه‌ریزی (Planned Tasks) ---
def get_planned_tasks(target_date):
    df = load_sheet_df("planned_tasks")
    if not df.empty and "task_date" in df.columns:
        filtered = df[df["task_date"] == str(target_date)].copy()
        if not filtered.empty:
            filtered["est_minutes"] = pd.to_numeric(filtered.get("est_minutes", 0), errors="coerce").fillna(0).astype(int)
            return filtered
    return pd.DataFrame(columns=["id", "title", "category", "priority", "task_date", "est_minutes", "start_time", "end_time", "status"])


def add_planned_task(title, category, priority, task_date, est_minutes, start_time, end_time):
    df = load_sheet_df("planned_tasks")
    new_id = f"P-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_row = pd.DataFrame(
        [
            {
                "id": new_id,
                "title": title,
                "category": category,
                "priority": priority,
                "task_date": str(task_date),
                "est_minutes": int(est_minutes),
                "start_time": str(start_time),
                "end_time": str(end_time),
                "status": "pending",
            }
        ]
    )
    df = pd.concat([new_row, df], ignore_index=True)
    save_sheet_df("planned_tasks", df)


def update_task_status(task_id, new_status):
    df = load_sheet_df("planned_tasks")
    if not df.empty:
        idx = df[df["id"] == str(task_id)].index
        if not idx.empty:
            df.loc[idx, "status"] = new_status
            save_sheet_df("planned_tasks", df)


def update_planned_task_full(task_id, title, category, priority, est_minutes, start_time, end_time):
    df = load_sheet_df("planned_tasks")
    if not df.empty:
        idx = df[df["id"] == str(task_id)].index
        if not idx.empty:
            df.loc[idx, "title"] = title
            df.loc[idx, "category"] = category
            df.loc[idx, "priority"] = priority
            df.loc[idx, "est_minutes"] = int(est_minutes)
            df.loc[idx, "start_time"] = str(start_time)
            df.loc[idx, "end_time"] = str(end_time)
            save_sheet_df("planned_tasks", df)


def delete_planned_task(task_id):
    df = load_sheet_df("planned_tasks")
    if not df.empty:
        df = df[df["id"] != str(task_id)]
        save_sheet_df("planned_tasks", df)


# --- توابع لاگ واقعی (Actual Logs) ---
def get_actual_logs(target_date):
    df = load_sheet_df("actual_logs")
    if not df.empty and "log_date" in df.columns:
        filtered = df[df["log_date"] == str(target_date)].copy()
        if not filtered.empty:
            filtered["duration_minutes"] = pd.to_numeric(filtered.get("duration_minutes", 0), errors="coerce").fillna(0).astype(int)
            return filtered
    return pd.DataFrame(columns=["id", "title", "category", "activity_type", "log_date", "duration_minutes", "start_time", "end_time", "notes"])


def add_actual_log(title, category, activity_type, log_date, duration_minutes, start_time, end_time, notes):
    df = load_sheet_df("actual_logs")
    new_id = f"A-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    new_row = pd.DataFrame(
        [
            {
                "id": new_id,
                "title": title,
                "category": category,
                "activity_type": activity_type,
                "log_date": str(log_date),
                "duration_minutes": int(duration_minutes),
                "start_time": str(start_time),
                "end_time": str(end_time),
                "notes": str(notes),
            }
        ]
    )
    df = pd.concat([new_row, df], ignore_index=True)
    save_sheet_df("actual_logs", df)


def delete_actual_log(log_id):
    df = load_sheet_df("actual_logs")
    if not df.empty:
        df = df[df["id"] != str(log_id)]
        save_sheet_df("actual_logs", df)


def get_logs_range(start_date, end_date):
    df = load_sheet_df("actual_logs")
    if not df.empty and "log_date" in df.columns:
        df["duration_minutes"] = pd.to_numeric(df.get("duration_minutes", 0), errors="coerce").fillna(0).astype(int)
        mask = (df["log_date"] >= str(start_date)) & (df["log_date"] <= str(end_date))
        return df[mask].sort_values("log_date", ascending=True)
    return pd.DataFrame(columns=["id", "title", "category", "activity_type", "log_date", "duration_minutes", "start_time", "end_time", "notes"])


def calc_duration_minutes(s_time: time, e_time: time):
    t_start = datetime.combine(date.today(), s_time)
    t_end = datetime.combine(date.today(), e_time)
    if t_end < t_start:
        t_end += timedelta(days=1)
    return int((t_end - t_start).total_seconds() / 60)


# ==========================================
# ۳. کامپوننت تقویم ماهانه شمسی در سایدبار
# ==========================================
def render_sidebar_calendar():
    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = date.today()
        
    cur_sel_g = st.session_state["selected_date"]
    cur_sel_j = jdatetime.date.fromgregorian(date=cur_sel_g)

    if "cal_view_year" not in st.session_state:
        st.session_state["cal_view_year"] = cur_sel_j.year
        st.session_state["cal_view_month"] = cur_sel_j.month

    v_year = st.session_state["cal_view_year"]
    v_month = st.session_state["cal_view_month"]

    month_names = [
        "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
        "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
    ]

    with st.sidebar:
        st.markdown("### 📅 تقویم شمسی")
        
        c_prev, c_title, c_next = st.columns([1, 2.5, 1])
        with c_prev:
            if st.button("◀", key="cal_prev_m", help="ماه قبل", use_container_width=True):
                if v_month == 1:
                    st.session_state["cal_view_month"] = 12
                    st.session_state["cal_view_year"] -= 1
                else:
                    st.session_state["cal_view_month"] -= 1
                st.rerun()

        with c_title:
            st.markdown(
                f"<div style='text-align: center; font-weight: bold; font-size: 0.95rem; margin-top: 4px;'>"
                f"{month_names[v_month - 1]} {v_year}"
                f"</div>",
                unsafe_allow_html=True,
            )

        with c_next:
            if st.button("▶", key="cal_next_m", help="ماه بعد", use_container_width=True):
                if v_month == 12:
                    st.session_state["cal_view_month"] = 1
                    st.session_state["cal_view_year"] += 1
                else:
                    st.session_state["cal_view_month"] += 1
                st.rerun()

        # سربرگ روزهای هفته
        weekdays = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
        h_cols = st.columns(7)
        for idx, w in enumerate(weekdays):
            h_cols[idx].markdown(
                f"<div style='text-align:center; font-size:0.75rem; font-weight:700; color:#94A3B8;'>{w}</div>",
                unsafe_allow_html=True,
            )

        first_day_of_month = jdatetime.date(v_year, v_month, 1)
        start_weekday = first_day_of_month.weekday()
        days_in_month = 29 if v_month == 12 else (30 if v_month > 6 else 31)

        day_counter = 1
        current_col = 0
        r_cols = st.columns(7)

        for _ in range(start_weekday):
            r_cols[current_col].empty()
            current_col += 1

        today_j = jdatetime.date.today()

        while day_counter <= days_in_month:
            j_this_day = jdatetime.date(v_year, v_month, day_counter)
            g_this_day = j_this_day.togregorian()

            is_selected = (g_this_day == cur_sel_g)
            btn_type = "primary" if is_selected else "secondary"

            if r_cols[current_col].button(
                str(day_counter),
                key=f"sb_day_{v_year}_{v_month}_{day_counter}",
                type=btn_type,
                use_container_width=True,
            ):
                st.session_state["selected_date"] = g_this_day
                st.rerun()

            current_col += 1
            day_counter += 1
            if current_col == 7 and day_counter <= days_in_month:
                current_col = 0
                r_cols = st.columns(7)

        st.markdown(
            f"<div style='text-align:center; font-size:0.85rem; margin-top:12px; color:#38BDF8;'>"
            f"روز انتخابی: <b>{cur_sel_j.strftime('%Y/%m/%d')}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if st.button("📍 رفتن به تاریخ امروز", use_container_width=True, key="btn_go_today"):
            st.session_state["selected_date"] = date.today()
            t_j = jdatetime.date.today()
            st.session_state["cal_view_year"] = t_j.year
            st.session_state["cal_view_month"] = t_j.month
            st.rerun()

        st.markdown("---")


# فراخوانی تقویم شمسی در سایدبار
render_sidebar_calendar()
active_date = st.session_state.get("selected_date", date.today())
active_jdate_str = str(jdatetime.date.fromgregorian(date=active_date))


# ==========================================
# ۴. رابط کاربری و تب‌های برنامه
# ==========================================
tab_goals, tab_plan, tab_log, tab_analytics = st.tabs(
    [
        "🎯 ۱. اهداف و تایم‌لاین (Goals)",
        "🌅 ۲. برنامه‌ریزی روزها (Plan)",
        "⏱️ ۳. ثبت واقعی عملکرد (Time Audit)",
        "📈 ۴. آنالیز و عارضه‌یابی زمان (Analytics)",
    ]
)

# ----------------------------------------------------
# تب اول: اهداف
# ----------------------------------------------------
with tab_goals:
    st.subheader("🎯 مدیریت اهداف، پروژه‌ها و تایم‌لاین")
    st.caption("اهداف بلندمدت و کوتاه‌مدت خود را تعریف کنید تا روزمرگی‌های خود را مستقیماً بر مبنای آن‌ها بچینید.")

    col_gform, col_glist = st.columns([1.1, 1.9], gap="large")

    with col_gform:
        st.markdown("##### ➕ تعریف هدف یا پروژه جدید")
        # پیش‌فرض ددلاین بر اساس تاریخ انتخاب شده در تقویم کنار دست شما تنظیم می‌شود
        g_target_date = jalali_date_picker(
            "ددلاین / تاریخ هدف (هماهنگ با تقویم):",
            default_date=active_date,
            key="goal_date_pick",
        )
        with st.form("new_goal_form", clear_on_submit=True):
            g_title = st.text_input("عنوان هدف / پروژه:", placeholder="مثال: استخدام دستیار، تسلط بر ستاپ‌های معاملاتی")
            g_type = st.selectbox("نوع هدف:", ["کوتاه‌مدت (هفتگی/ماهانه)", "بلندمدت (فصلی/سالانه)"])
            g_cat = st.selectbox(
                "دسته‌بندی هدف:",
                [
                    "💼 کسب‌وکار و مالی",
                    "🎯 ترید و سرمایه‌گذاری",
                    "📚 مهارت و یادگیری",
                    "❤️ روابط و خانواده",
                    "🏋️ سلامت و ورزش",
                    "👤 شخصی",
                ],
            )
            g_prog = st.slider("درصد پیشرفت اولیه:", min_value=0, max_value=100, value=0, step=5)

            g_submit = st.form_submit_button("ثبت هدف در فضای ابری", use_container_width=True)
            if g_submit:
                if g_title.strip():
                    add_goal(g_title.strip(), g_cat, g_type, str(g_target_date), g_prog)
                    st.success("هدف با موفقیت ثبت شد.")
                    st.rerun()
                else:
                    st.error("لطفاً عنوان هدف را وارد کنید.")

    with col_glist:
        st.markdown("##### 📋 لیست و مدیریت اهداف")
        goals_df = get_all_goals()

        if goals_df.empty:
            st.info("هنوز هدفی ثبت نشده است. از فرم سمت راست اولین هدف خود را ایجاد کنید.")
        else:
            for _, row in goals_df.iterrows():
                col_ginfo, col_gprog, col_gedit, col_gdel = st.columns([0.44, 0.32, 0.12, 0.12])
                with col_ginfo:
                    try:
                        g_dt = datetime.strptime(str(row['target_date']), "%Y-%m-%d").date()
                        j_target_str = str(jdatetime.date.fromgregorian(date=g_dt))
                    except Exception:
                        j_target_str = str(row['target_date'])
                        
                    st.markdown(
                        f"""
                        <div style="font-weight: 700; color: var(--text-color, inherit);">{row['title']}</div>
                        <div style="font-size: 0.82rem; color: #64748B;">{row['category']} • {row['goal_type']} • 📅 ددلاین: {j_target_str}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_gprog:
                    st.markdown(f"<div style='font-size: 0.88rem; font-weight: 600;'>پیشرفت: {row['progress']}٪</div>", unsafe_allow_html=True)
                    st.progress(int(row["progress"]) / 100)
                with col_gedit:
                    if st.button("✏️ ویرایش", key=f"edit_btn_goal_{row['id']}", use_container_width=True):
                        st.session_state[f"editing_goal_{row['id']}"] = not st.session_state.get(f"editing_goal_{row['id']}", False)
                        st.rerun()
                with col_gdel:
                    if st.button("🗑️ حذف", key=f"del_goal_{row['id']}", use_container_width=True):
                        delete_goal(row["id"])
                        st.rerun()

                # بخش ویرایش در صورت کلیک روی دکمه ویرایش
                if st.session_state.get(f"editing_goal_{row['id']}", False):
                    with st.container():
                        st.info("ویرایش اطلاعات هدف:")
                        try:
                            cur_dt = datetime.strptime(str(row['target_date']), "%Y-%m-%d").date()
                        except Exception:
                            cur_dt = date.today()
                        edit_target_date = jalali_date_picker("ویرایش ددلاین / تاریخ هدف:", default_date=cur_dt, key=f"edit_gdate_{row['id']}")

                        with st.form(f"form_edit_goal_{row['id']}"):
                            eg_title = st.text_input("عنوان:", value=row['title'])
                            goal_types = ["کوتاه‌مدت (هفتگی/ماهانه)", "بلندمدت (فصلی/سالانه)"]
                            eg_type = st.selectbox("نوع هدف:", goal_types, index=goal_types.index(row['goal_type']) if row['goal_type'] in goal_types else 0)
                            
                            goal_cats = [
                                "💼 کسب‌وکار و مالی",
                                "🎯 ترید و سرمایه‌گذاری",
                                "📚 مهارت و یادگیری",
                                "❤️ روابط و خانواده",
                                "🏋️ سلامت و ورزش",
                                "👤 شخصی",
                            ]
                            eg_cat = st.selectbox("دسته‌بندی:", goal_cats, index=goal_cats.index(row['category']) if row['category'] in goal_cats else 0)
                            eg_prog = st.slider("درصد پیشرفت:", 0, 100, int(row['progress']), step=5)

                            col_esave, col_ecancel = st.columns(2)
                            with col_esave:
                                if st.form_submit_button("💾 ذخیره تغییرات", use_container_width=True):
                                    if eg_title.strip():
                                        update_goal_full(row['id'], eg_title.strip(), eg_cat, eg_type, str(edit_target_date), eg_prog)
                                        st.session_state[f"editing_goal_{row['id']}"] = False
                                        st.success("تغییرات ذخیره شد.")
                                        st.rerun()
                                    else:
                                        st.error("عنوان نمی‌تواند خالی باشد.")
                            with col_ecancel:
                                if st.form_submit_button("انصراف", use_container_width=True):
                                    st.session_state[f"editing_goal_{row['id']}"] = False
                                    st.rerun()

                st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid rgba(148, 163, 184, 0.2);' />", unsafe_allow_html=True)

    if not goals_df.empty:
        st.write("")
        st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid rgba(148, 163, 184, 0.2);' />", unsafe_allow_html=True)
        col_c_left, col_c_mid, col_c_right = st.columns([1, 6, 1])
        with col_c_mid:
            st.markdown("<h5 style='text-align: center;'>📊 وضعیت و پیشرفت اهداف</h5>", unsafe_allow_html=True)
            calc_height = max(350, len(goals_df) * 38)
            
            fig_goals = px.bar(
                goals_df,
                x="progress",
                y="title",
                orientation="h",
                color="category",
                range_x=[0, 100],
                labels={"progress": "درصد پیشرفت (%)", "title": ""},
            )
            fig_goals.update_layout(
                font=dict(family="Vazirmatn", size=13),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=calc_height,
                xaxis=dict(showgrid=True, gridcolor="rgba(148, 163, 184, 0.2)"),
                yaxis=dict(showgrid=False, automargin=True),
                margin=dict(t=20, b=20, l=220, r=20),
            )
            st.plotly_chart(fig_goals, use_container_width=True)

# ----------------------------------------------------
# تب دوم: برنامه‌ریزی روزانه
# ----------------------------------------------------
with tab_plan:
    st.subheader("🌅 برنامه‌ریزی اهداف، روتین‌ها و تسک‌های روز")

    col_view, _ = st.columns([1.5, 2.5])
    with col_view:
        # انتخاب تاریخ مستقیم از تقویم سایدبار است اما در صورت تمایل با ویجت زیر هم قابل تنظیم است
        plan_date = jalali_date_picker("تاریخ در حال برنامه‌ریزی (هماهنگ با تقویم کناری):", default_date=active_date, key="plan_date_pick")

    p_df = get_planned_tasks(plan_date)
    plan_total_min = p_df["est_minutes"].sum() if not p_df.empty else 0
    plan_remaining_min = max(0, 1440 - plan_total_min)

    col_form, col_list, col_chart_plan = st.columns([1.1, 1.3, 1.2], gap="medium")

    with col_form:
        st.markdown("##### ➕ تعریف کار در برنامه روز")

        current_goals = get_all_goals()
        goals_options = ["--- بدون اتصال به هدف (مستقل) ---"] + (
            [f"🎯 {row['title']}" for _, row in current_goals.iterrows()] if not current_goals.empty else []
        )

        with st.form("plan_task_form", clear_on_submit=True):
            p_goal_selected = st.selectbox("انتخاب از بین اهداف و تایم‌لاین:", goals_options)
            p_preset = st.selectbox("یا انتخاب سریع کارهای روتین:", ROUTINE_TASKS, key="p_preset_sel")
            p_custom_title = st.text_input("یا عنوان کار را دستی بنویسید:", placeholder="مثال: بررسی ستاپ معاملاتی", key="p_title_input")

            p_cat = st.selectbox(
                "دسته‌بندی:",
                [
                    "💼 کاری و تجاری",
                    "🎯 ترید و بازارهای مالی",
                    "📚 مطالعه و یادگیری",
                    "❤️ روابط و خانواده",
                    "💇‍♂️ استایل و رسیدگی فردی",
                    "🎯 اهداف بلندمدت",
                    "👤 شخصی",
                    "🏋️ ورزش و سلامت",
                    "🛌 استراحت و خواب",
                ],
                key="plan_cat",
            )
            p_prio = st.selectbox("سطح اولویت:", ["🔴 فوری / حیاتی", "🟡 بااهمیت", "🟢 عادی"], key="plan_prio")

            col_ps1, col_pe1 = st.columns(2)
            with col_ps1:
                p_s_time = st.time_input("از ساعت:", value=time(9, 0), key="p_s_time")
            with col_pe1:
                p_e_time = st.time_input("تا ساعت:", value=time(10, 0), key="p_e_time")

            calculated_plan_duration = calc_duration_minutes(p_s_time, p_e_time)

            p_submit = st.form_submit_button("افزودن به برنامه", use_container_width=True)
            if p_submit:
                if p_custom_title.strip():
                    final_plan_title = p_custom_title.strip()
                elif p_preset != "--- انتخاب روتین ---":
                    final_plan_title = p_preset
                elif p_goal_selected != "--- بدون اتصال به هدف (مستقل) ---":
                    final_plan_title = p_goal_selected
                else:
                    final_plan_title = ""

                if final_plan_title and calculated_plan_duration > 0:
                    add_planned_task(
                        final_plan_title,
                        p_cat,
                        p_prio,
                        str(plan_date),
                        int(calculated_plan_duration),
                        p_s_time.strftime("%H:%M"),
                        p_e_time.strftime("%H:%M"),
                    )
                    st.success("تسک با موفقیت ثبت شد.")
                    st.rerun()
                elif calculated_plan_duration <= 0:
                    st.error("ساعت پایان باید بعد از ساعت شروع باشد.")
                else:
                    st.error("لطفاً عنوانی را برای تسک مشخص کنید.")

    with col_list:
        j_plan_date_str = str(jdatetime.date.fromgregorian(date=plan_date))
        st.markdown(f"##### 📋 برنامه‌ریزی روز {j_plan_date_str}")

        if p_df.empty:
            st.info("برای این روز هنوز برنامه‌ای تعریف نشده است.")
        else:
            done_cnt = len(p_df[p_df["status"] == "done"])
            st.caption(
                f"تعداد تسک‌ها: {len(p_df)} | انجام شده: {done_cnt} | زمان برنامه‌ریزی‌شده: {round(plan_total_min/60, 1)} ساعت"
            )

            for _, row in p_df.iterrows():
                done = str(row.get("status", "")) == "done"
                c_chk, c_txt, c_edit, c_del = st.columns([0.08, 0.62, 0.15, 0.15])
                with c_chk:
                    checked = st.checkbox("", value=done, key=f"p_chk_{row['id']}")
                    if checked != done:
                        update_task_status(row["id"], "done" if checked else "pending")
                        st.rerun()
                with c_txt:
                    style = "text-decoration: line-through; color: #94A3B8;" if done else "font-weight: 600; color: var(--text-color, inherit);"
                    time_range_str = f"⏰ {row['start_time']} تا {row['end_time']} • " if row.get("start_time") else ""
                    st.markdown(
                        f"""
                        <div style="{style} font-size: 1rem;">{row['title']}</div>
                        <div style="font-size: 0.82rem; color: #64748B;">
                            {time_range_str}{row['category']} • {row['priority']} • ⏳ {row['est_minutes']} دقیقه
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c_edit:
                    if st.button("✏️ ویرایش", key=f"p_edit_btn_{row['id']}", use_container_width=True):
                        st.session_state[f"editing_task_{row['id']}"] = not st.session_state.get(f"editing_task_{row['id']}", False)
                        st.rerun()
                with c_del:
                    if st.button("🗑️ حذف", key=f"p_del_{row['id']}", use_container_width=True):
                        delete_planned_task(row["id"])
                        st.rerun()

                # ویرایش تسک برنامه‌ریزی
                if st.session_state.get(f"editing_task_{row['id']}", False):
                    with st.container():
                        st.info("ویرایش تسک برنامه‌ریزی:")
                        with st.form(f"form_edit_task_{row['id']}"):
                            ep_title = st.text_input("عنوان تسک:", value=row['title'])
                            cats_plan = [
                                "💼 کاری و تجاری",
                                "🎯 ترید و بازارهای مالی",
                                "📚 مطالعه و یادگیری",
                                "❤️ روابط و خانواده",
                                "💇‍♂️ استایل و رسیدگی فردی",
                                "🎯 اهداف بلندمدت",
                                "👤 شخصی",
                                "🏋️ ورزش و سلامت",
                                "🛌 استراحت و خواب",
                            ]
                            ep_cat = st.selectbox("دسته‌بندی:", cats_plan, index=cats_plan.index(row['category']) if row['category'] in cats_plan else 0)
                            prios_plan = ["🔴 فوری / حیاتی", "🟡 بااهمیت", "🟢 عادی"]
                            ep_prio = st.selectbox("اولویت:", prios_plan, index=prios_plan.index(row['priority']) if row['priority'] in prios_plan else 0)

                            try:
                                def_s = datetime.strptime(row['start_time'], "%H:%M").time()
                                def_e = datetime.strptime(row['end_time'], "%H:%M").time()
                            except Exception:
                                def_s, def_e = time(9, 0), time(10, 0)

                            col_es, col_ee = st.columns(2)
                            with col_es:
                                ep_s_time = st.time_input("از ساعت:", value=def_s, key=f"ep_s_{row['id']}")
                            with col_ee:
                                ep_e_time = st.time_input("تا ساعت:", value=def_e, key=f"ep_e_{row['id']}")

                            new_dur = calc_duration_minutes(ep_s_time, ep_e_time)

                            col_tsave, col_tcancel = st.columns(2)
                            with col_tsave:
                                if st.form_submit_button("💾 ذخیره تغییرات", use_container_width=True):
                                    if ep_title.strip() and new_dur > 0:
                                        update_planned_task_full(
                                            row['id'],
                                            ep_title.strip(),
                                            ep_cat,
                                            ep_prio,
                                            new_dur,
                                            ep_s_time.strftime("%H:%M"),
                                            ep_e_time.strftime("%H:%M"),
                                        )
                                        st.session_state[f"editing_task_{row['id']}"] = False
                                        st.success("تسک به‌روزرسانی شد.")
                                        st.rerun()
                                    elif new_dur <= 0:
                                        st.error("ساعت پایان باید بعد از ساعت شروع باشد.")
                                    else:
                                        st.error("عنوان تسک نمی‌تواند خالی باشد.")
                            with col_tcancel:
                                if st.form_submit_button("انصراف", use_container_width=True):
                                    st.session_state[f"editing_task_{row['id']}"] = False
                                    st.rerun()

                st.markdown("<hr style='margin: 6px 0; border: none; border-top: 1px solid rgba(148, 163, 184, 0.2);' />", unsafe_allow_html=True)

    with col_chart_plan:
        st.markdown("##### ⏱️ چرخه ۲۴ ساعته برنامه‌ریزی")
        if not p_df.empty:
            cat_agg_plan = p_df.groupby("category")["est_minutes"].sum().reset_index()
            cat_agg_plan.loc[len(cat_agg_plan)] = ["برنامه‌ریزی نشده (خالی)", plan_remaining_min]

            fig_plan_24 = px.pie(
                cat_agg_plan,
                values="est_minutes",
                names="category",
                hole=0.65,
                color="category",
                color_discrete_map={"برنامه‌ریزی نشده (خالی)": "#64748B"},
            )
            total_plan_hours = round(plan_total_min / 60, 1)
            fig_plan_24.update_layout(
                font=dict(family="Vazirmatn"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
                annotations=[
                    dict(
                        text=f"{total_plan_hours} / 24<br>برنامه‌ریزی",
                        x=0.5,
                        y=0.5,
                        font_size=15,
                        showarrow=False,
                    )
                ],
            )
            st.plotly_chart(fig_plan_24, use_container_width=True)
            st.markdown(
                f"<div style='text-align:center; color:#64748B;'>زمان برنامه‌ریزی‌نشده: <b>{round(plan_remaining_min/60, 1)} ساعت</b></div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("با ثبت اولین تسک، نمودار ۲۴ ساعته تشکیل خواهد شد.")

# ----------------------------------------------------
# تب سوم: ثبت واقعی وقایع
# ----------------------------------------------------
with tab_log:
    st.subheader("⏱️ ثبت کارهای انجام‌شده و چرخه ۲۴ ساعته عملکرد")
    st.caption("در این بخش رویدادهای رخ‌داده در طول روز را با ساعت دقیق ثبت کنید.")

    col_audit_date, _ = st.columns([1.5, 2.5])
    with col_audit_date:
        audit_date = jalali_date_picker("تاریخ ثبت وقایع (هماهنگ با تقویم کناری):", default_date=active_date, key="audit_date_pick")

    a_df = get_actual_logs(audit_date)
    total_act_min = a_df["duration_minutes"].sum() if not a_df.empty else 0
    remaining_min = max(0, 1440 - total_act_min)

    # دریافت تسک‌های انجام‌شده (تیک‌خورده) مربوط به همین تاریخ
    done_planned_df = get_planned_tasks(audit_date)
    if not done_planned_df.empty:
        done_planned_df = done_planned_df[done_planned_df["status"] == "done"]

    done_tasks_dict = {}
    done_task_options = ["--- انتخاب از کارهای انجام‌شده برنامه ---"]
    if not done_planned_df.empty:
        for _, row_d in done_planned_df.iterrows():
            time_part = f" ({row_d['start_time']} تا {row_d['end_time']})" if row_d.get("start_time") else ""
            opt_label = f"✅ {row_d['title']}{time_part} - [{row_d['category']}]"
            done_task_options.append(opt_label)
            done_tasks_dict[opt_label] = row_d

    col_lform, col_llist, col_chart24 = st.columns([1.1, 1.3, 1.2], gap="medium")

    with col_lform:
        st.markdown("##### 📝 فرم ثبت رویداد")
        with st.form("actual_log_form", clear_on_submit=True):
            l_done_plan = st.selectbox(
                "انتخاب کار انجام‌شده از برنامه روز:",
                done_task_options,
                key="l_done_plan_sel"
            )
            l_preset = st.selectbox("یا انتخاب سریع کارهای روتین:", ROUTINE_TASKS, key="l_preset_sel")
            l_custom_title = st.text_input("یا عنوان کار را دستی تایپ کنید:", placeholder="مثلاً: جلسه کاری، تحلیل چارت", key="l_custom_title_input")

            l_type = st.selectbox(
                "نوع اثرگذاری فعالیت:",
                [
                    "🟢 کار عمیق و کاملاً مفید (Productive)",
                    "⚪ کار روتین / روزمره ضروری (Routine)",
                    "🔴 اتلاف وقت و حواس‌پرتی (Time Waste)",
                ],
            )
            l_cat = st.selectbox(
                "حوزه فعالیت:",
                [
                    "💼 کاری و مالی",
                    "🎯 ترید و سرمایه‌گذاری",
                    "📚 توسعه فردی و یادگیری",
                    "❤️ روابط و خانواده",
                    "💇‍♂️ رسیدگی به استایل و ظاهر",
                    "📱 شبکه‌های اجتماعی و سرگرمی",
                    "👥 جلسات و تماس‌ها",
                    "🚗 رفت‌وآمد و امور اداری",
                    "🏠 کارهای منزل و استراحت",
                ],
            )

            col_s1, col_e1 = st.columns(2)
            with col_s1:
                l_s_time = st.time_input("از ساعت:", value=time(8, 0), key="l_s_time")
            with col_e1:
                l_e_time = st.time_input("تا ساعت:", value=time(9, 0), key="l_e_time")

            l_duration = calc_duration_minutes(l_s_time, l_e_time)
            l_notes = st.text_input("توضیح کوتاه یا علت اتلاف وقت (اختیاری):")

            l_submit = st.form_submit_button("ثبت در وقایع روز", use_container_width=True)

            if l_submit:
                if l_custom_title.strip():
                    final_title = l_custom_title.strip()
                    chosen_cat = l_cat
                    final_duration = l_duration
                    final_s_time = l_s_time.strftime("%H:%M")
                    final_e_time = l_e_time.strftime("%H:%M")
                elif l_done_plan != "--- انتخاب از کارهای انجام‌شده برنامه ---":
                    selected_task = done_tasks_dict[l_done_plan]
                    final_title = selected_task["title"]
                    chosen_cat = selected_task.get("category", l_cat)
                    task_est = int(selected_task.get("est_minutes", 0))
                    final_duration = task_est if task_est > 0 else l_duration
                    final_s_time = selected_task.get("start_time") if selected_task.get("start_time") else l_s_time.strftime("%H:%M")
                    final_e_time = selected_task.get("end_time") if selected_task.get("end_time") else l_e_time.strftime("%H:%M")
                elif l_preset != "--- انتخاب روتین ---":
                    final_title = l_preset
                    chosen_cat = l_cat
                    final_duration = l_duration
                    final_s_time = l_s_time.strftime("%H:%M")
                    final_e_time = l_e_time.strftime("%H:%M")
                else:
                    final_title = ""
                    chosen_cat = l_cat
                    final_duration = l_duration
                    final_s_time = l_s_time.strftime("%H:%M")
                    final_e_time = l_e_time.strftime("%H:%M")

                if final_title and final_duration > 0:
                    clean_type = (
                        "کار مفید"
                        if "مفید" in l_type
                        else ("اتلاف وقت" if "اتلاف" in l_type else "روتین و ضروری")
                    )
                    add_actual_log(
                        final_title,
                        chosen_cat,
                        clean_type,
                        str(audit_date),
                        int(final_duration),
                        final_s_time,
                        final_e_time,
                        l_notes.strip(),
                    )
                    st.success("فعالیت ثبت شد.")
                    st.rerun()
                elif final_duration <= 0:
                    st.error("ساعت پایان باید بعد از ساعت شروع باشد.")
                else:
                    st.error("لطفاً عنوان فعالیت را وارد کنید.")

    with col_llist:
        j_audit_date_str = str(jdatetime.date.fromgregorian(date=audit_date))
        st.markdown(f"##### 📜 وقایع ثبت‌شده در {j_audit_date_str}")

        if a_df.empty:
            st.info("هنوز فعالیتی ثبت نشده است.")
        else:
            for _, row in a_df.iterrows():
                badge_class = (
                    "badge-productive"
                    if row["activity_type"] == "کار مفید"
                    else ("badge-waste" if row["activity_type"] == "اتلاف وقت" else "badge-routine")
                )
                c_info, c_del = st.columns([0.85, 0.15])
                with c_info:
                    notes_txt = f" - <span style='color: #F87171;'>{row['notes']}</span>" if row.get("notes") else ""
                    h, m = divmod(row["duration_minutes"], 60)
                    time_str = f"{h} ساعت و {m} دقیقه" if h > 0 else f"{m} دقیقه"
                    exact_range = f"⏰ {row['start_time']} تا {row['end_time']} • " if row.get("start_time") else ""

                    st.markdown(
                        f"""
                        <div style="font-weight: 600; color: var(--text-color, inherit);">{row['title']}{notes_txt}</div>
                        <div style="font-size: 0.85rem; color: #64748B; margin-top: 2px;">
                            <span class="{badge_class}">{row['activity_type']}</span> • 
                            <span>{exact_range}{row['category']}</span> • 
                            <span>⏱️ {time_str}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c_del:
                    if st.button("🗑️ حذف", key=f"a_del_{row['id']}", use_container_width=True):
                        delete_actual_log(row["id"])
                        st.rerun()
                st.markdown("<hr style='margin: 6px 0; border: none; border-top: 1px solid rgba(148, 163, 184, 0.2);' />", unsafe_allow_html=True)

    with col_chart24:
        st.markdown("##### ⏱️ چرخه ۲۴ ساعته روز")
        if not a_df.empty:
            type_agg_24 = a_df.groupby("activity_type")["duration_minutes"].sum().reset_index()
            type_agg_24.loc[len(type_agg_24)] = ["ثبت نشده (خالی)", remaining_min]

            fig_24 = px.pie(
                type_agg_24,
                values="duration_minutes",
                names="activity_type",
                hole=0.65,
                color="activity_type",
                color_discrete_map={
                    "کار مفید": "#10B981",
                    "اتلاف وقت": "#EF4444",
                    "روتین و ضروری": "#64748B",
                    "ثبت نشده (خالی)": "#475569",
                },
            )
            total_logged_hours = round(total_act_min / 60, 1)
            fig_24.update_layout(
                font=dict(family="Vazirmatn"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                annotations=[dict(text=f"{total_logged_hours} / 24<br>ساعت", x=0.5, y=0.5, font_size=16, showarrow=False)],
            )
            st.plotly_chart(fig_24, use_container_width=True)
            st.markdown(f"<div style='text-align:center; color:#64748B;'>زمان ثبت نشده: <b>{round(remaining_min/60, 1)} ساعت</b></div>", unsafe_allow_html=True)
        else:
            st.info("پس از ثبت اولین فعالیت، نمودار ۲۴ ساعته تشکیل می‌شود.")

# ----------------------------------------------------
# تب چهارم: تحلیل و عارضه‌یابی
# ----------------------------------------------------
with tab_analytics:
    st.subheader("📈 داشبورد عارضه‌یابی و آنالیز بهره‌وری")

    col_filter1, col_filter2, _ = st.columns([1, 1.5, 1.5])
    with col_filter1:
        date_range_preset = st.selectbox(
            "بازه تحلیل:",
            [
                "۷ روز اخیر",
                "۳۰ روز اخیر (ماهانه)",
                "امروز",
                "انتخاب بازه دلخواه",
            ],
        )

    today = date.today()
    if date_range_preset == "امروز":
        s_date, e_date = today, today
    elif date_range_preset == "۷ روز اخیر":
        s_date, e_date = today - timedelta(days=7), today
    elif date_range_preset == "۳۰ روز اخیر (ماهانه)":
        s_date, e_date = today - timedelta(days=30), today
    else:
        with col_filter2:
            s_date = jalali_date_picker("از تاریخ:", default_date=today - timedelta(days=14), key="an_s_pick")
            e_date = jalali_date_picker("تا تاریخ:", default_date=today, key="an_e_pick")

    analytics_df = get_logs_range(s_date, e_date)

    if analytics_df.empty:
        j_s = str(jdatetime.date.fromgregorian(date=s_date))
        j_e = str(jdatetime.date.fromgregorian(date=e_date))
        st.warning(f"برای بازه زمانی {j_s} تا {j_e} فعالیتی ثبت نشده است.")
    else:
        total_tracked = analytics_df["duration_minutes"].sum()
        prod_hours = round(
            analytics_df[analytics_df["activity_type"] == "کار مفید"]["duration_minutes"].sum() / 60,
            1,
        )
        waste_hours = round(
            analytics_df[analytics_df["activity_type"] == "اتلاف وقت"]["duration_minutes"].sum() / 60,
            1,
        )
        routine_hours = round(
            analytics_df[analytics_df["activity_type"] == "روتین و ضروری"]["duration_minutes"].sum() / 60,
            1,
        )

        prod_ratio = round((prod_hours * 60 / total_tracked) * 100, 1) if total_tracked > 0 else 0
        waste_ratio = round((waste_hours * 60 / total_tracked) * 100, 1) if total_tracked > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                f"""<div class="metric-card"><h3 style="color:#34D399;">{prod_hours} ساعت</h3><p>کار خالص و مفید ({prod_ratio}٪)</p></div>""",
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f"""<div class="metric-card"><h3 style="color:#F87171;">{waste_hours} ساعت</h3><p>اتلاف وقت و پرتی ({waste_ratio}٪)</p></div>""",
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f"""<div class="metric-card"><h3 style="color:#CBD5E1;">{routine_hours} ساعت</h3><p>امور روتین و اداری</p></div>""",
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                f"""<div class="metric-card"><h3 style="color:#60A5FA;">{round(total_tracked/60, 1)} ساعت</h3><p>کل زمان پایش‌شده</p></div>""",
                unsafe_allow_html=True,
            )

        st.write("")

        g1, g2 = st.columns([1, 1], gap="large")

        with g1:
            st.markdown("##### 🍩 نسبت اثربخشی زمان (مفید در برابر اتلاف)")
            type_agg = analytics_df.groupby("activity_type")["duration_minutes"].sum().reset_index()
            type_agg["ساعت"] = (type_agg["duration_minutes"] / 60).round(1)

            fig_type = px.pie(
                type_agg,
                values="duration_minutes",
                names="activity_type",
                hole=0.55,
                color="activity_type",
                color_discrete_map={
                    "کار مفید": "#10B981",
                    "اتلاف وقت": "#EF4444",
                    "روتین و ضروری": "#64748B",
                },
            )
            fig_type.update_layout(
                font=dict(family="Vazirmatn"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=20, l=10, r=10),
            )
            st.plotly_chart(fig_type, use_container_width=True)

        with g2:
            st.markdown("##### 🔍 بیشترین حوزه‌های اتلاف وقت و پرتی انرژی")
            waste_df = analytics_df[analytics_df["activity_type"] == "اتلاف وقت"]
            if waste_df.empty:
                st.success("در این بازه هیچ اتلاف وقتی ثبت نشده است! عالیه.")
            else:
                waste_cat = waste_df.groupby("category")["duration_minutes"].sum().reset_index()
                waste_cat["ساعت"] = (waste_cat["duration_minutes"] / 60).round(1)
                fig_waste = px.bar(
                    waste_cat,
                    x="ساعت",
                    y="category",
                    orientation="h",
                    color_discrete_sequence=["#EF4444"],
                )
                fig_waste.update_layout(
                    font=dict(family="Vazirmatn"),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(title="ساعت هدر رفته", showgrid=False),
                    yaxis=dict(title="", showgrid=False),
                    margin=dict(t=20, b=20, l=10, r=10),
                )
                st.plotly_chart(fig_waste, use_container_width=True)

        st.markdown("##### 📅 روند تفکیک روزانه (ساعت)")
        
        analytics_df_plot = analytics_df.copy()
        def to_jalali_str(g_str):
            try:
                g_d = datetime.strptime(str(g_str), "%Y-%m-%d").date()
                return str(jdatetime.date.fromgregorian(date=g_d))
            except Exception:
                return str(g_str)
                
        analytics_df_plot["jalali_date"] = analytics_df_plot["log_date"].apply(to_jalali_str)

        pivot_daily = (
            analytics_df_plot.pivot_table(
                index="jalali_date",
                columns="activity_type",
                values="duration_minutes",
                aggfunc="sum",
                fill_value=0,
            )
            / 60
        ).round(1)

        pivot_daily = pivot_daily.reset_index()
        fig_trend = go.Figure()

        if "کار مفید" in pivot_daily.columns:
            fig_trend.add_trace(
                go.Bar(
                    x=pivot_daily["jalali_date"],
                    y=pivot_daily["کار مفید"],
                    name="کار مفید",
                    marker_color="#10B981",
                )
            )
        if "روتین و ضروری" in pivot_daily.columns:
            fig_trend.add_trace(
                go.Bar(
                    x=pivot_daily["jalali_date"],
                    y=pivot_daily["روتین و ضروری"],
                    name="روتین و ضروری",
                    marker_color="#64748B",
                )
            )
        if "اتلاف وقت" in pivot_daily.columns:
            fig_trend.add_trace(
                go.Bar(
                    x=pivot_daily["jalali_date"],
                    y=pivot_daily["اتلاف وقت"],
                    name="اتلاف وقت",
                    marker_color="#EF4444",
                )
            )

        fig_trend.update_layout(
            barmode="stack",
            font=dict(family="Vazirmatn"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="تاریخ", showgrid=False),
            yaxis=dict(title="ساعت", showgrid=True, gridcolor="rgba(148, 163, 184, 0.2)"),
            margin=dict(t=20, b=20, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_trend, use_container_width=True)

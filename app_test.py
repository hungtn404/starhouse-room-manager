# app.py

from datetime import datetime
import os
import json
import gspread
import streamlit as st
import pandas as pd
import base64


# DANH SÁCH TÀI KHOẢN NHÂN VIÊN
# ============================
ACCOUNTS = {
    "ST001": "123456aA@",
    "SM002": "123456aA@",
    "SM004": "123456aA@",
    "SE005": "123456aA@"
}

# Google libs
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from gspread_dataframe import set_with_dataframe, get_as_dataframe
    GS_AVAILABLE = True
except Exception:
    GS_AVAILABLE = False

# -------- CONFIG --------
DATA_FILE = "data.xlsx"  # fallback local excel
# Default admin password if not set in Streamlit secrets
ADMIN_PASSWORD = "Admin@123*"
DATE_COL = "Ngày trống"
LIST_COLS = ["Loại phòng", "Nội Thất", "Tiện ích", "Hình ảnh"]
# Name of worksheet inside spreadsheet
SHEET_NAME = "data"  # will create/use a worksheet named 'data' by default
# ------------------------

st.set_page_config(page_title="Quản lý nguồn phòng trọ - STARHOUSE", layout="centered")

# -----------------------
# Helpers: IO + Normalization
# -----------------------

def reset_add_form():
    if "so_nha" in st.session_state: st.session_state["Số nhà"] = ""
    if "Đường" in st.session_state: st.session_state["Đường"] = "" # Hoặc giá trị mặc định đầu tiên
    if "Phường" in st.session_state: st.session_state["Phường"] = ""
    if "Loại phòng" in st.session_state: st.session_state["Loại phòng"] = []
    # Giữ nguyên ngày nếu bạn không muốn reset nó về ngày hiện tại
    # if "ngay_trong_key" in st.session_state: st.session_state["ngay_trong_key"] = datetime.now().date() 
    if "Nội Thất" in st.session_state: st.session_state["Nội Thất"] = []
    if "Tiện ích" in st.session_state: st.session_state["Tiện ích"] = []
    if "Ghi chú" in st.session_state: st.session_state["Ghi chú"] = ""
    if "Hoa hồng" in st.session_state: st.session_state["Hoa hồng"] = ""

def _encode_list_field(x):
    if isinstance(x, list):
        return json.dumps(x, ensure_ascii=False)
    if pd.isna(x):
        return json.dumps([])
    if isinstance(x, str) and x.strip().startswith("["):
        return x
    return json.dumps([str(x)], ensure_ascii=False)

def _decode_list_field(x):
    if isinstance(x, list):
        return x
    if pd.isna(x):
        return []
    if isinstance(x, str):
        s = x.strip()
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
            else:
                return [str(parsed)]
        except Exception:
            parts = [p.strip() for p in s.split(",") if p.strip()]
            return parts
    return [str(x)]

def generate_id(df):
    if df is None or df.empty or "ID" not in df.columns:
        return 1
    try:
        return int(pd.to_numeric(df["ID"], errors="coerce").max()) + 1
    except Exception:
        return len(df) + 1

# -----------------------
# Helpers: Convert list/array to safe display text
# -----------------------
def list_to_text(x):
    """
    Chuyển list, numpy array, pandas Series thành chuỗi,
    trả về '' nếu rỗng hoặc None.
    """
    import numpy as np
    import pandas as pd

    if isinstance(x, list):
        return ", ".join(x) if len(x) > 0 else ""
    if isinstance(x, (np.ndarray, pd.Series)):
        return ", ".join(x.tolist()) if x.size > 0 else ""
    if x is None:
        return ""
    # pd.notna chỉ dùng với giá trị scalar
    try:
        return str(x) if pd.notna(x) else ""
    except Exception:
        return ""


# -----------------------
# Google Sheets helpers
# -----------------------
def gsheet_enabled():
    """Return True if gspread available and secrets exist."""
    if not GS_AVAILABLE:
        return False
    try:
        _ = st.secrets["gcp_service_account"]
        _ = st.secrets["gsheet"]["sheet_id"] or st.secrets["gsheet"].get("sheet_url", None)
        return True
    except Exception:
        return False

def connect_gsheet():
    """Return gspread.Spreadsheet and Worksheet objects (worksheet named SHEET_NAME)."""
    if not GS_AVAILABLE:
        raise RuntimeError("gspread or google libs not installed.")

    creds_dict = st.secrets["gcp_service_account"]
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)

    client = gspread.authorize(creds)

    # prefer sheet_id, else sheet_url
    sheet_id = st.secrets["gsheet"].get("sheet_id", None) if "gsheet" in st.secrets else None
    sheet_url = st.secrets["gsheet"].get("sheet_url", None) if "gsheet" in st.secrets else None

    if sheet_id:
        sh = client.open_by_key(sheet_id)
    elif sheet_url:
        sh = client.open_by_url(sheet_url)
    else:
        raise RuntimeError("gsheet.sheet_id or sheet_url not found in secrets.")

    # get or create worksheet
    try:
        ws = sh.worksheet(SHEET_NAME)
    except Exception:
        ws = sh.add_worksheet(title=SHEET_NAME, rows="1000", cols="50")
    return sh, ws
    
def load_data_from_gsheet():
    """Load worksheet into DataFrame, decode JSON list columns and parse date"""
    sh, ws = connect_gsheet()
    # use get_as_dataframe to preserve headers and empty rows trimmed
    df = get_as_dataframe(ws, evaluate_formulas=True, header=0, usecols=None).fillna(pd.NA)
    # If returned empty DataFrame, ensure columns exist
    if df is None or df.empty:
        # create an empty df with expected columns
        cols = ["ID", "Số nhà", "Đường", "Phường", "Quận", "Giá"] + LIST_COLS + [DATE_COL,
                "Cửa sổ", "Điện", "Nước", "Dịch vụ", "Xe", "Giặt chung", "Ghi chú", "Hoa hồng", "Ngày tạo"]
        return pd.DataFrame(columns=cols)

    # strip column names
    df.columns = df.columns.str.strip()

    # decode list columns
    for col in LIST_COLS:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: _decode_list_field(x))
        else:
            df[col] = [[] for _ in range(len(df))]

    # parse date column to python date (or NaT)
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce").dt.date

    # ensure expected columns exist
    expected_cols = ["ID", "Số nhà", "Đường", "Phường", "Quận", "Giá", "Cửa sổ",
                     "Điện", "Nước", "Dịch vụ", "Xe", "Giặt chung", "Ghi chú", "Hoa hồng", "Ngày tạo"]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = pd.NA

    return df

def save_data_to_gsheet(df):
    """Write DataFrame to Google Sheet worksheet. Encode list cols to JSON strings."""
    sh, ws = connect_gsheet()
    df2 = df.copy()
    for col in LIST_COLS:
        if col in df2.columns:
            df2[col] = df2[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else (json.dumps([]) if pd.isna(x) else json.dumps([str(x)], ensure_ascii=False)))
    # ensure datetime columns are string/ISO to avoid weird formatting
    if DATE_COL in df2.columns:
        try:
            df2[DATE_COL] = pd.to_datetime(df2[DATE_COL], errors="coerce")
        except Exception:
            pass
    # set_with_dataframe will overwrite worksheet content
    ws.clear()
    set_with_dataframe(ws, df2, include_index=False, include_column_header=True, resize=True)

# -----------------------
# Local Excel fallback helpers
# -----------------------
def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=[
            "ID",
            "Số nhà",
            "Đường",
            "Phường",
            "Quận",
            "Giá",
            "Loại phòng",
            DATE_COL,
            "Cửa sổ",
            "Nội Thất",
            "Tiện ích",
            "Điện",
            "Nước",
            "Dịch vụ",
            "Xe",
            "Giặt chung",
            "Ghi chú",
            "Hoa hồng",
            "Ngày tạo"
        ])
        save_data_to_excel(df)

def load_data_from_excel():
    ensure_data_file()
    try:
        df = pd.read_excel(DATA_FILE, engine="openpyxl")
    except Exception as e:
        st.error(f"Lỗi đọc file {DATA_FILE}: {e}")
        return pd.DataFrame()
    df.columns = df.columns.str.strip()
    # decode list cols
    for col in LIST_COLS:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: _decode_list_field(x))
        else:
            df[col] = [[] for _ in range(len(df))]
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce").dt.date
    expected_cols = ["ID", "Số nhà", "Đường", "Phường", "Quận", "Giá", "Cửa sổ",
                     "Điện", "Nước", "Dịch vụ", "Xe", "Giặt chung", "Ghi chú", "Hoa hồng", "Ngày tạo"] # Thêm Hoa hồng
    for c in expected_cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df

def save_data_to_excel(df):
    df2 = df.copy()
    for col in LIST_COLS:
        if col in df2.columns:
            df2[col] = df2[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else (json.dumps([]) if pd.isna(x) else json.dumps([str(x)], ensure_ascii=False)))
    if "Ngày tạo" in df2.columns:
        try:
            df2["Ngày tạo"] = pd.to_datetime(df2["Ngày tạo"])
        except Exception:
            pass
    df2.to_excel(DATA_FILE, index=False)

# -----------------------
# Unified load/save: prefer Google Sheets if configured
# -----------------------
@st.cache_data(ttl=600)
def load_data():
    if gsheet_enabled():
        try:
            return load_data_from_gsheet()
        except Exception as e:
            st.warning(f"Không thể kết nối Google Sheets — fallback sang Excel. Lỗi: {e}")
            return load_data_from_excel()
    else:
        return load_data_from_excel()

def save_data(df):
    if gsheet_enabled():
        try:
            save_data_to_gsheet(df)
            load_data.clear()
            return
        except Exception as e:
            st.warning(f"Lưu lên Google Sheets thất bại ({e}). Lưu sang Excel thay thế.")
            save_data_to_excel(df)
            load_data.clear()
            return
    else:
        save_data_to_excel(df)
        load_data.clear()
# -----------------------
# UI Main
# -----------------------

st.title("🏠 Quản lý nguồn phòng trọ - STARHOUSE (GSheets)")

if gsheet_enabled():
    st.success("🔗 Google Sheets: Đã bật cấu hình (gspread + secrets)")
else:
    st.warning("⛔ Google Sheets chưa sẵn sàng — dùng Excel fallback")

if st.button("Test kết nối Google Sheets"):
    try:
        sh, ws = connect_gsheet()
        st.success(f"✔ Kết nối thành công!\nTên sheet: {sh.title}, Worksheet: {ws.title}")
    except Exception as e:
        st.error(f"❌ Không kết nối được: {e}")


menu = st.sidebar.radio("Chế độ", ["Admin", "Nhân viên", "CTV"])

# Admin password from secrets if available
try:
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", ADMIN_PASSWORD)
except Exception:
    ADMIN_PASSWORD = ADMIN_PASSWORD

# -----------------------
# Admin mode
# -----------------------
if menu == "Admin":
    st.subheader("Admin — Thêm / Import / Export dữ liệu")
    pwd = st.text_input("Nhập mật khẩu admin", type="password")
    if pwd != ADMIN_PASSWORD:
        st.warning("Bạn đang ở chế độ view (nhập mật khẩu để vào admin).")
        st.info("Để lọc phòng vào chế độ 'Nhân viên'.")
        if st.checkbox("Xem trước dữ liệu (chỉ xem)"):
            st.dataframe(load_data().head(50))
    else:
        st.success("Đăng nhập thành công — Admin.")

        # --- THÊM NÚT TẢI LẠI DỮ LIỆU ---
        st.markdown("---")
        if st.button("🔄 Tải lại dữ liệu từ Google Sheets (Nếu vừa chỉnh sửa thủ công)", key="reload_data_gsheet"):
            # 1. Xóa cache của hàm load_data
            load_data.clear() 
            # 2. Buộc ứng dụng chạy lại để tải dữ liệu mới
            st.rerun() 
        
        st.markdown("---")

        tab1, tab2, tab3, tab4 = st.tabs(["Thêm phòng", "Danh sách & chỉnh sửa", "Import / Export", "Lọc phòng"])

        with tab1:
            st.markdown("### ➕ Thêm phòng mới")

            if 'phong_con_list' not in st.session_state:
                st.session_state['phong_con_list'] = [
                    # Khởi tạo một phòng con mặc định
                    {'ma_phong': 'P1', 'gia': 2000000, 'loai': [], 'cua_so': 'BAN CÔNG', 'ngay_trong': datetime.now().date()}
                ]

            # Đặt ngay sau phần khởi tạo Session State

            st.markdown("---")
            # Nút này PHẢI là st.button() và PHẢI nằm NGOÀI st.form()
            if st.button("➕ Thêm phòng khác", key="add_another_room_btn"): 
                # Thêm một dictionary mới vào danh sách
                new_room_index = len(st.session_state['phong_con_list']) + 1
                st.session_state['phong_con_list'].append({
                    'ma_phong': f'P{new_room_index}', 
                    'gia': 2000000, 
                    'loai': [], 
                    'cua_so': 'BAN CÔNG', 
                    'ngay_trong': datetime.now().date()
                })
                # Tùy chọn: Rerun để cập nhật giao diện ngay lập tức
                st.rerun()
            st.markdown("---")

            st.markdown("#### 🚪 Thông tin chi tiết TỪNG PHÒNG")

            # Lặp qua danh sách các phòng con để tạo widget
            for i in range(len(st.session_state['phong_con_list'])):
                st.markdown(f"##### Phòng {i+1}")
    
                # --- NÚT XÓA (NGOÀI FORM) ---
                col_ma, col_del = st.columns([0.85, 0.15])
    
                with col_del:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True) # Tạo khoảng trống
                    # Nút Xóa cũng là st.button() và nằm NGOÀI form
                    if st.button("🗑️ Xóa", key=f"del_phong_{i}"):
                        del st.session_state['phong_con_list'][i]
                        st.rerun()

                # --- WIDGET NHẬP LIỆU PHÒNG CON (Cũng nằm ngoài form) ---
                with col_ma:
                    # Cần một key duy nhất (ví dụ: f"ma_phong_{i}")
                    ma_phong_current = st.text_input(
                        "Mã phòng (vd: A101, 102,...) **Cần UNIQUE**", 
                        value=st.session_state['phong_con_list'][i].get('ma_phong', ''),
                        key=f"ma_phong_{i}" 
                    )
    
                col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    
                with col_p1:
                    st.session_state['phong_con_list'][i]['gia'] = st.number_input(
                        "Giá (VNĐ)", 
                        step=500000, min_value=1000000, 
                        value=st.session_state['phong_con_list'][i].get('gia', 2000000),
                        key=f"gia_{i}" # Key duy nhất
                    )

                with col_p2:
                    st.session_state['phong_con_list'][i]['loai'] = st.multiselect(
                        "Loại phòng", 
                        ["Studio", "Duplex", "1PN", "2PN", "Tách bếp", "Khác"], 
                        default=st.session_state['phong_con_list'][i].get('loai', []),
                        key=f"loai_{i}" # Key duy nhất
                    )
    
                with col_p3:
                    options_cua_so = ["BAN CÔNG", "BAN CÔNG CHUNG", "Cửa sổ TRỜI", "Cửa sổ HL", "Cửa sổ GT", "Không"]
                    default_index = options_cua_so.index(st.session_state['phong_con_list'][i].get('cua_so', 'BAN CÔNG'))
                    st.session_state['phong_con_list'][i]['cua_so'] = st.selectbox(
                        "Cửa sổ", 
                        options_cua_so, 
                        index=default_index,
                        key=f"cua_so_{i}" # Key duy nhất
                    )

                with col_p4:
                    st.session_state['phong_con_list'][i]['ngay_trong'] = st.date_input(
                        "Ngày trống", 
                        value=st.session_state['phong_con_list'][i].get('ngay_trong', datetime.now().date()),
                        key=f"ngay_trong_{i}" # Key duy nhất
                    )
    
                # Cập nhật Mã phòng (vì text_input không được gán trực tiếp vào list)
                st.session_state['phong_con_list'][i]['ma_phong'] = ma_phong_current

                st.markdown("---")

            with st.form("add_form"):
                so_nha = st.text_input("Số nhà", placeholder="Ví dụ: 745/10/5", key="so_nha_key")
                # normalize số nhà 
                df_tmp = load_data()
                street_options = sorted([s for s in df_tmp['Đường'].dropna().unique().tolist()]) if (not df_tmp.empty and 'Đường' in df_tmp.columns) else []
                default_streets = [
                    "An Hội",
"An Nhơn",
"Bùi Quang Là",
"Bạch Đằng",
"Cây Trâm",
"Đỗ Thúc Tịnh",
"Đường 26 Tháng 3",
"Dương Quảng Hàm",
"Đường số 1",
"Đường số 2",
"Đường số 3",
"Đường số 4",
"Đường số 5",
"Đường số 6",
"Đường số 7",
"Đường số 8",
"Đường số 9",
"Đường số 10",
"Đường số 11",
"Đường số 12",
"Đường số 13",
"Đường số 14",
"Đường số 15",
"Đường số 17",
"Đường số 18",
"Đường số 19",
"Đường số 20",
"Đường số 21",
"Đường số 22",
"Đường số 23",
"Đường số 24",
"Đường số 25",
"Đường số 27",
"Đường số 28",
"Đường số 29",
"Đường số 30",
"Đường số 31",
"Đường số 32",
"Đường số 35",
"Đường số 38",
"Đường số 43",
"Đường số 45",
"Đường số 46",
"Đường số 47",
"Đường số 50",
"Đường số 51",
"Đường số 53",
"Đường số 55",
"Đường số 56",
"Đường số 57",
"Đường số 58",
"Đường số 59",
"Hạnh Thông",
"Hạnh Thông Tây",
"Hoàng Hoa Thám",
"Hoàng Minh Giám",
"Huỳnh Khương An",
"Huỳnh Văn Nghệ",
"Lê Đức Thọ",
"Lê Hoàng Phái",
"Lê Lai",
"Lê Lợi",
"Lê Quang Định",
"Lê Thị Hồng",
"Lê Văn Thọ",
"Lê Văn Trị",
"Lương Ngọc Quyến",
"Lý Thường Kiệt",
"Nguyễn Bỉnh Khiêm",
"Nguyễn Du",
"Nguyễn Duy Cung",
"Nguyễn Hữu Thọ",
"Nguyễn Huy Điển",
"Nguyễn Kiệm",
"Nguyễn Oanh",
"Nguyễn Thái Sơn",
"Nguyễn Thị Nhỏ",
"Nguyễn Thượng Hiền",
"Nguyễn Tư Giản",
"Nguyễn Tuân",
"Nguyễn Văn Bảo",
"Nguyễn Văn Công",
"Nguyễn Văn Dung",
"Nguyễn Văn Lượng",
"Nguyễn Văn Nghi",
"Nguyễn Văn Nghi (lặp — nếu trùng nguồn sẽ có thể xuất 1 lần)",
"Nguyễn Văn Bảo (đã nêu)",
"Nguyên Hồng",
"Nguyên Hồng (nếu trùng một vài tên nhỏ)",
"Phạm Huy Thông",
"Phạm Ngũ Lão",
"Phạm Văn Bạch",
"Phạm Văn Chiêu",
"Phạm Văn Đồng",
"Phan Huy Ích",
"Phan Văn Trị",
"Phùng Văn Cung",
"Quang Trung",
"Tân Sơn",
"Tân Thọ",
"Thích Bửu Đăng",
"Thiên Hộ Dương",
"Thống Nhất",
"Thông Tây Hội",
"Tô Ngọc Vân",
"Trần Bá Giao",
"Trần Bình Trọng",
"Trần Phú Cương",
"Trần Quốc Tuấn",
"Trần Thị Nghĩ",
"Trưng Nữ Vương",
"Trương Đăng Quế",
"Trương Minh Giảng",
"Trương Minh Ký",
"Tú Mỡ",
"Tân Sơn (đã nêu)",
"Nguyễn Văn Khối"
                ]
                # merge while keeping unique order
                seen = set()
                combined_streets = []
                for s in default_streets + street_options:
                    if s not in seen:
                        seen.add(s); combined_streets.append(s)

                duong = st.selectbox("Tên Đường", combined_streets, key="duong_key")
                phuong = st.selectbox("Phường", [
                    "Phường 1", "Phường 3", "Phường 4", "Phường 5", "Phường 6", "Phường 7",
                    "Phường 8", "Phường 9", "Phường 10", "Phường 11", "Phường 12",
                    "Phường 13", "Phường 14", "Phường 15", "Phường 16", "Phường 17"
                ], key="phuong_key")
                quan = st.selectbox("Quận", ["Gò Vấp", "Tân Bình", "Bình Thạnh", "12"], key="quan_key")
  
                noi_that = st.multiselect("Nội thất", ["Máy lạnh", "Kệ bếp", "Tủ đồ", "Tủ lạnh", "Giường", "Pallet", "Nệm", "Bàn Ghế", "Nước nóng NLMT", "Nước nóng Điện", "Tivi", "Máy giặt"], key="noi_that_key")
                tien_ich = st.multiselect("Tiện ích", ["Cổng vân tay", "Camera 24/7", "Vệ sinh chung", "Giờ giấc tự do", "Không chung chủ", "Máy giặt chung", "Thang máy"], key="tien_ich_key")
                dien = st.selectbox("Giá điện", ["3.5K", "3.7K", "3.8K", "3.9K", "4.0K", "Cập nhật"], key="dien_key")
                nuoc = st.selectbox("Giá nước", ["100K/người", "150K/người", "60K/người", "70K/người", "80K/người", "20K/khối", "23K/khối", "Cập nhật"], key="nuoc_key")
                dich_vu = st.selectbox("Dịch vụ", ["100K/phòng", "50K/phòng", "120K/phòng", "150K/phòng", "180K/phòng", "200K/phòng", "300K/phòng", "70K/người", "150K/người", "100K/người", "Cập nhật"], key="dich_vu_key")
                xe = st.selectbox("Xe", ["100K/xe", "50K/xe", "80K/chiếc", "90K/chiếc", "120K/xe", "130K/xe", "150K/xe", "200K/xe", "FREE", "Cập nhật"], key="xe_key")
                giat_chung = st.selectbox("Giặt chung", ["10K/lần", "15K/lần", "20K/lần", "50K/người", "80K/người", "Không"], key="giat_chung_key")
                ghi_chu = st.text_area("Ghi chú (tùy chọn)", key="ghi_chu_key")
                hoa_hong = st.text_input("Hoa hồng", key="hoa_hong_key") 
                
                # Upload hình ảnh
                uploaded_files = st.file_uploader(
                    "Upload ảnh phòng (jpg, png, jpeg)", 
                    type=["jpg", "png", "jpeg"], 
                    accept_multiple_files=True
                )
                image_urls = []

                if uploaded_files:
                    folder = "images"
                    os.makedirs(folder, exist_ok=True)
                    for f in uploaded_files:
                        # Dùng datetime để đảm bảo tên file là duy nhất
                        file_path = os.path.join(folder, f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.name}")
                        with open(file_path, "wb") as out:
                            out.write(f.read())
                        image_urls.append(file_path)

                submitted = st.form_submit_button("Lưu phòng", on_click=reset_add_form)
            if submitted:
                # 1. Kiểm tra dữ liệu chung
                # Lấy giá trị từ Session State (Các widget trong form tự động cập nhật Session State)
                so_nha_val = st.session_state.get("so_nha_key") 
                duong_val = st.session_state.get("duong_key")
    
                if not so_nha_val or not duong_val:
                    st.error("Vui lòng nhập đầy đủ Số nhà và Tên Đường chung.")
                elif not st.session_state['phong_con_list'] or not any(p.get('ma_phong') for p in st.session_state['phong_con_list']):
                    st.error("Vui lòng thêm ít nhất một phòng con với Mã phòng.")
                else:
                    df = load_data()
                    rows_to_add = []
        
                    # 2. Lặp qua danh sách phòng con để tạo từng bản ghi
                    for item in st.session_state['phong_con_list']:
                        if not item.get('ma_phong'):
                            st.warning(f"Bỏ qua phòng thiếu Mã phòng: {item}")
                            continue
            
                        new_id = generate_id(df)
                        loai_phong_final = ["DUPLEX" if p == "Gác lửng" else p for p in item.get('loai', [])]
            
                        # Tạo new_row từ thông tin chung (lấy từ form) + thông tin phòng con (lấy từ item)
                        new_row = {
                            "ID": new_id,
                            # Thêm Mã phòng vào Số nhà để phân biệt (RẤT QUAN TRỌNG)
                            "Số nhà": so_nha_val,
                            "Đường": duong_val,
                            # ... (Lấy các trường chung khác từ Session State hoặc biến cục bộ của form)
                            "Phường": st.session_state.get("phuong_key"),
                            "Quận": st.session_state.get("quan_key"),
                
                            # Thông tin phòng con
                            "Mã phòng": (f"{item['ma_phong']}" if item['ma_phong'] else ""), 
                            "Giá": item['gia'],
                            "Loại phòng": loai_phong_final,
                            DATE_COL: item['ngay_trong'],
                            "Cửa sổ": item['cua_so'],
                
                            # Thông tin chung còn lại
                            "Nội Thất": st.session_state.get("noi_that_key"),
                            "Tiện ích": st.session_state.get("tien_ich_key"),
                            "Điện": st.session_state.get("dien_key"),
                            "Nước": st.session_state.get("nuoc_key"),
                            "Dịch vụ": st.session_state.get("dich_vu_key"),
                            "Xe": st.session_state.get("xe_key"),
                            "Giặt": st.session_state.get("giat_chung_key"),
                            "Ghi chú": st.session_state.get("ghi_chu_key"),
                            "Hoa hồng": st.session_state.get("hoa_hong_key"),
                            "Hình ảnh": image_urls, # image_urls cần được xác định từ file_uploader trong form
                            "Ngày tạo": datetime.now()
                        }
                        rows_to_add.append(new_row)
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                    if rows_to_add:
                        save_data(df)
                        st.success(f"Đã lưu thành công **{len(rows_to_add)} phòng** mới.")
            
                        # CẬP NHẬT: Reset form và Session State cho list phòng con
                        reset_add_form() 
                        st.session_state['phong_con_list'] = [{'ma_phong': 'P1', 'gia': 2000000, 'loai': [], 'cua_so': 'BAN CÔNG', 'ngay_trong': datetime.now().date()}]
                        st.rerun()
                    else:
                        st.error("Không có phòng nào được lưu.")

        with tab2:
            st.markdown("### 📋 Danh sách hiện tại")

            df = load_data().sort_values(by="Ngày tạo", ascending=False).reset_index(drop=True)
            st.write(f"Tổng bản ghi: {len(df)}")

            # Thêm cột button upload (hiển thị trong bảng thôi)
            df["Hình ảnh"] = ""

            edited_df = st.data_editor(
                df,
                width='stretch',
                hide_index=True,
                key="room_table",
                column_config={
                    "Hình ảnh": st.column_config.TextColumn(
                        "Hình ảnh",
                        help="Bấm vào mục bên dưới để upload ảnh"
                    )
                },
                disabled=["Hình ảnh"] 
            )

            so_nha_filter = st.text_input("🔍 Lọc theo số nhà:")
            filtered_df = df[df["Số nhà"].astype(str).str.contains(so_nha_filter, case=False, na=False)] \
                    if so_nha_filter else df.head(0)
            if so_nha_filter and filtered_df.empty:
                st.warning("❌ Không tìm thấy phòng nào phù hợp!")

            st.markdown("### 📤 Kết quả")

            # Hiện bảng kết quả
            if not filtered_df.empty:
                st.markdown("### 📋 Kết quả lọc:")
                st.dataframe(filtered_df, width='stretch')

                # Chọn ID để upload ảnh
                list_ids = filtered_df["ID"].tolist()
                chon_id = st.selectbox("📌 Chọn ID cần upload ảnh", [None] + list_ids)

                if chon_id:
                    st.markdown(f"### 📤 Upload ảnh cho ID **{chon_id}**")

                    # Hiện uploader (không lưu ngay)
                    uploaded_files = st.file_uploader(
                        "Tải ảnh lên:",
                        accept_multiple_files=True,
                        key=f"upload_{chon_id}"
                    )

                    # Nếu có file → show danh sách đang chờ lưu
                    if uploaded_files:
                        st.info("📌 Ảnh đã chọn (chưa lưu):")
                        for file in uploaded_files:
                            st.write(f"• {file.name}")

                        # Nút LƯU ảnh
                        if st.button("💾 Lưu ảnh", key=f"save_{chon_id}"):
                            urls = []
                            import os
                            if not os.path.exists("uploads"):
                                os.makedirs("uploads")

                            # Lưu file vào thư mục
                            for file in uploaded_files:
                                save_path = f"uploads/{chon_id}_{file.name}"
                                with open(save_path, "wb") as f:
                                    f.write(file.getbuffer())
                                urls.append(save_path)

                            # Load DF thật
                            df_real = load_data()
                            matches = df_real.index[df_real["ID"] == chon_id].tolist()
                            row_index = matches[0]

                            # Lấy ảnh cũ
                            old_imgs = df_real.at[row_index, "Hình ảnh"]
                            if isinstance(old_imgs, list):
                                base = old_imgs
                            elif pd.isna(old_imgs) or old_imgs in ("", None):
                                base = []
                            else:
                                base = [old_imgs]

                            # Ghép ảnh mới
                            new_imgs = base + urls
                            df_real.at[row_index, "Hình ảnh"] = new_imgs

                            # Lưu dữ liệu
                            save_data(df_real)

                            st.success("✅ Đã lưu ảnh vào Google Sheet!")

                            # Reset uploader sau lần rerun tiếp theo
                            st.session_state["reset_uploader"] = f"upload_{chon_id}"

                            st.rerun()
            

        with tab3:
            st.markdown("### 🔁 Import / Export Excel / CSV")
            # Export current data (download CSV)
            df_current = load_data()
            csv_bytes = df_current.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Tải xuống CSV hiện tại", csv_bytes, file_name="data_export.csv", mime="text/csv")

            st.markdown("---")
            st.markdown("**Upload file Excel (.xlsx)** (ghi đè hoặc merge)")
            uploaded = st.file_uploader("Chọn file .xlsx để import", type=["xlsx"])
            if uploaded is not None:
                try:
                    df_new = pd.read_excel(uploaded, engine="openpyxl")
                    # decode list cols from uploaded file
                    for col in LIST_COLS:
                        if col in df_new.columns:
                            df_new[col] = df_new[col].apply(lambda x: _decode_list_field(x))
                        else:
                            df_new[col] = [[] for _ in range(len(df_new))]
                    action = st.radio("Hành động khi import", ["Merge (ghép dữ liệu)", "Overwrite (ghi đè)"])
                    if st.button("Thực hiện import"):
                        df_old = load_data()
                        if action == "Overwrite (ghi đè)":
                            save_data(df_new)
                            st.success("Đã ghi đè dữ liệu lên nguồn lưu (Sheet/Excel).")
                        else:
                            if "ID" not in df_new.columns:
                                df_new["ID"] = range(generate_id(df_old), generate_id(df_old) + len(df_new))
                            df_merged = pd.concat([df_old, df_new], ignore_index=True)
                            save_data(df_merged)
                            st.success("Đã ghép dữ liệu vào nguồn lưu.")
                except Exception as e:
                    st.error(f"Lỗi khi đọc file: {e}")
        with tab4:
            st.subheader("Nhân viên — Lọc & Xem")
            st.info("Nhân viên chỉ có thể **lọc** và **xem ĐỊA CHỈ** của phòng. Không có quyền chỉnh sửa.")
            df = load_data()

            st.markdown("### 🔎 Tìm kiếm & Lọc phòng")

            quans = sorted([q for q in df['Quận'].dropna().unique().tolist()]) if 'Quận' in df.columns else []
            phuongs = sorted([p for p in df['Phường'].dropna().unique().tolist()]) if 'Phường' in df.columns else []
            duongs = sorted([d for d in df['Đường'].dropna().unique().tolist()]) if 'Đường' in df.columns else []

            col1, col2 = st.columns(2)
            with col1:
                loc_quan = st.multiselect("Quận", options=quans)
                loc_phuong = st.multiselect("Phường", options=phuongs)
                loc_duong = st.multiselect("Đường", options=duongs)
            with col2:
                loc_loai = st.multiselect("Loại phòng", options=["Studio", "Duplex", "1PN", "2PN", "Tách bếp", "Khác"])
                loc_cuaso = st.multiselect("Cửa sổ", options=["BAN CÔNG", "BAN CÔNG CHUNG", "Cửa sổ TRỜI", "Cửa sổ HL", "Cửa sổ GT", "Không"])
                loc_nt = st.multiselect("Nội thất", options=["Máy lạnh", "Tủ lạnh", "Giường", "Nệm", "Bàn Ghế", "Nước nóng NLMT", "Nước nóng Điện"])
                loc_tienich = st.multiselect("Tiện ích", options=["Cổng vân tay", "Camera 24/7", "Vệ sinh chung", "Giờ giấc tự do", "Không chung chủ", "Máy giặt chung", "Thang máy"])

            gia_min, gia_max = st.slider("Khoảng giá (VNĐ)", 2_000_000, 50_000_000, (2_000_000, 20_000_000), step=100_000)

            # Make date filter optional (Streamlit date_input always returns a date)
            use_date_filter = st.checkbox("Bật lọc theo ngày trống (trước ngày)")
            loc_ngay = None
            if use_date_filter:
                loc_ngay = st.date_input("Ngày trống trước ngày (tuỳ chọn)")

            keyword = st.text_input("Từ khoá địa chỉ (nhập quận, đường, số nhà...)")

            # apply filters safely
            df_filtered = df.copy()

            if loc_quan:
                df_filtered = df_filtered[df_filtered['Quận'].isin(loc_quan)]
            if loc_phuong:
                df_filtered = df_filtered[df_filtered['Phường'].isin(loc_phuong)]
            if loc_duong:
                df_filtered = df_filtered[df_filtered['Đường'].isin(loc_duong)]

            if loc_loai:
                df_filtered = df_filtered[df_filtered['Loại phòng'].apply(lambda x: any(item in x for item in loc_loai) if isinstance(x, list) else any(item in str(x) for item in loc_loai))]

            if loc_cuaso:
                df_filtered = df_filtered[df_filtered['Cửa sổ'].apply(lambda x: any(item in x for item in loc_cuaso) if isinstance(x, list) else any(item in str(x) for item in loc_cuaso))]

            if loc_nt:
                df_filtered = df_filtered[df_filtered['Nội Thất'].apply(lambda x: any(item in x for item in loc_nt) if isinstance(x, list) else any(item in str(x) for item in loc_nt))]

            if loc_tienich:
                df_filtered = df_filtered[df_filtered['Tiện ích'].apply(lambda x: any(item in x for item in loc_tienich) if isinstance(x, list) else any(item in str(x) for item in loc_tienich))]

            # price filter
            try:
                df_filtered = df_filtered[(df_filtered['Giá'] >= gia_min) & (df_filtered['Giá'] <= gia_max)]
            except Exception:
                pass

            # SAFE date filter: compare python date with python date
            if loc_ngay:
                if DATE_COL in df_filtered.columns:
                    loc_date = pd.to_datetime(loc_ngay).date()  # ensure it's a date object
                    # robust per-row check: convert row value to date if possible and compare
                    def date_ok(x):
                        if pd.isna(x):
                            return False
                        # if it's already a date
                        if isinstance(x, datetime):
                            return x.date() <= loc_date
                        try:
                            # x might be pandas Timestamp or date-like
                            xr = pd.to_datetime(x, errors="coerce")
                            if pd.isna(xr):
                                return False
                            return xr.date() <= loc_date
                        except Exception:
                            return False
                    df_filtered = df_filtered[df_filtered[DATE_COL].apply(date_ok)]

            # keyword filter over address fields
            if keyword:
                kw = keyword.strip().lower()
                df_filtered = df_filtered[df_filtered.apply(lambda r: kw in str(r.get('Số nhà','')).lower() or kw in str(r.get('Đường','')).lower() or kw in str(r.get('Phường','')).lower() or kw in str(r.get('Quận','')).lower(), axis=1)]

            st.markdown(f"### 📋 Kết quả: **{len(df_filtered)} phòng** tìm thấy")

            if not df_filtered.empty:
                for idx, row in df_filtered.sort_values(by=DATE_COL, na_position='last').iterrows():
                    dia_chi = f"{row.get('Số nhà','')} {row.get('Đường','')}, {row.get('Phường','')}, {row.get('Quận','')}"
                    ma_phong = row.get('Mã phòng')
                    # FORMATTING FOR DISPLAY AND SHARE BUTTON
                    gia_text = f"{int(row['Giá']):,} VNĐ" if pd.notna(row.get('Giá')) else ""
                    nothat_text = list_to_text(row.get('Nội Thất'))
                    tienich_text = list_to_text(row.get('Tiện ích'))
                    loai_text = list_to_text(row.get('Loại phòng'))
                    ngay_text = row[DATE_COL].strftime("%d/%m/%Y") if pd.notna(row.get(DATE_COL)) else ''
            
                    # Create shareable text - ĐÃ THÊM HOA HỒNG
                    share_text = f"""{row.get('Số nhà','')} {row.get('Đường','')}, {row.get('Phường','')}, {row.get('Quận','')}
---------------
💥Giá + Mã phòng:
{ma_phong}: {gia_text.replace(" VNĐ", "")} ({loai_text}, {row.get('Cửa sổ','')}, {ngay_text} TRỐNG)

💸Các Chi phí:
+ Điện: {row.get('Điện','')}
+ Nước: {row.get('Nước','')}
+ Dịch vụ: {row.get('Dịch vụ','')}
+ Giữ xe máy: {row.get('Xe','')}
+ Giặt: {row.get('Giặt','' )}

🛏️ Nội thất: {nothat_text}
🧹Tiện ích: {tienich_text}
✨Ghi chú: {row.get('Ghi chú','')}
---------------
Hoa hồng: {row.get('Hoa hồng', 'Không')}
        """.strip()

                    st.markdown(f"#### 🏠 {dia_chi} ({ma_phong})")
                    st.write(f"**Giá:** {gia_text}  |  **Loại:** {loai_text}")
                    st.write(f"**Cửa sổ:** {row.get('Cửa sổ','')}  |  **Ngày trống:** {ngay_text}")
                    st.write(f"**Nội thất:** {nothat_text}    |    **Tiện ích:** {tienich_text}")
                    st.write(f"**Điện/Nước:** {row.get('Điện','')} / {row.get('Nước','')}    |    **Dịch vụ/Xe/Giặt:** {row.get('Dịch vụ','')} / {row.get('Xe','')} / {row.get('Giặt','')}")
                    st.write(f"**Hoa hồng:** {row.get('Hoa hồng','')}") # 👉 HIỂN THỊ HOA HỒNG RIÊNG
                    st.write(f"**Ghi chú:** {row.get('Ghi chú','')}")
            
                    # 👉 BƯỚC CẬP NHẬT: HIỂN THỊ HÌNH ẢNH (Từ câu trả lời trước)
                    image_urls = row.get('Hình ảnh')
                    if image_urls and isinstance(image_urls, list) and len(image_urls) > 0:
                        st.markdown("##### 📸 Hình ảnh phòng")
                        # Hiển thị tối đa 3 ảnh trên 1 dòng
                        cols = st.columns(min(len(image_urls), 3)) 
                        for i, url in enumerate(image_urls):
                            if os.path.exists(url):
                                # Sử dụng st.image để hiển thị ảnh từ đường dẫn cục bộ
                                cols[i % 3].image(url, caption=os.path.basename(url), use_column_width="auto")
                            else:
                                cols[i % 3].warning(f"File ảnh không tồn tại: {os.path.basename(url)}")

                    # Thêm nút Chia sẻ
                    st.code(share_text, language="text") # Hiển thị text để tiện copy
            
                    st.markdown("---")

                @st.cache_data
                def convert_df(df_in):
                    return df_in.to_csv(index=False).encode('utf-8-sig')

                csv = convert_df(df_filtered)
                st.download_button("Tải xuống kết quả (CSV)", csv, file_name="phong_tro_loc.csv", mime='text/csv')
            else:
                st.write("Không có bản ghi nào khớp.")


# -----------------------
# Nhân viên (xem & lọc) - đúng scope
# -----------------------

    

elif menu == "Nhân viên":
    def check_login():
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        if st.session_state.logged_in:
            return True
    
        st.warning("🔒 Vui lòng đăng nhập để truy cập mục NHÂN VIÊN")

        username = st.text_input("Tên đăng nhập")
        password = st.text_input("Mật khẩu", type="password")

        if st.button("Đăng nhập"):
            if username in ACCOUNTS and ACCOUNTS[username] == password:
                st.session_state.logged_in = True
                st.success("Đăng nhập thành công! 🎉")
                st.rerun()
            else:
                st.error("Sai tài khoản hoặc mật khẩu!")

        return False
    if not check_login():
        st.stop()
    st.subheader("Nhân viên — Lọc & Xem")
    st.info("Nhân viên chỉ có thể **lọc** và **xem ĐỊA CHỈ** của phòng. Không có quyền chỉnh sửa.")
    df = load_data()

    st.markdown("### 🔎 Tìm kiếm & Lọc phòng")

    quans = sorted([q for q in df['Quận'].dropna().unique().tolist()]) if 'Quận' in df.columns else []
    phuongs = sorted([p for p in df['Phường'].dropna().unique().tolist()]) if 'Phường' in df.columns else []
    duongs = sorted([d for d in df['Đường'].dropna().unique().tolist()]) if 'Đường' in df.columns else []

    col1, col2 = st.columns(2)
    with col1:
        loc_quan = st.multiselect("Quận", options=quans)
        loc_phuong = st.multiselect("Phường", options=phuongs)
        loc_duong = st.multiselect("Đường", options=duongs)
    with col2:
        loc_loai = st.multiselect("Loại phòng", options=["Studio", "Duplex", "1PN", "2PN", "Tách bếp", "Khác"])
        loc_cuaso = st.multiselect("Cửa sổ", options=["BAN CÔNG", "BAN CÔNG CHUNG", "Cửa sổ TRỜI", "Cửa sổ HL", "Cửa sổ GT", "Không"])
        loc_nt = st.multiselect("Nội thất", options=["Máy lạnh", "Tủ lạnh", "Giường", "Nệm", "Bàn Ghế", "Nước nóng NLMT", "Nước nóng Điện"])
        loc_tienich = st.multiselect("Tiện ích", options=["Cổng vân tay", "Camera 24/7", "Vệ sinh chung", "Giờ giấc tự do", "Không chung chủ", "Máy giặt chung", "Thang máy"])

    gia_min, gia_max = st.slider("Khoảng giá (VNĐ)", 2_000_000, 50_000_000, (2_000_000, 20_000_000), step=100_000)

    # Make date filter optional (Streamlit date_input always returns a date)
    use_date_filter = st.checkbox("Bật lọc theo ngày trống (trước ngày)")
    loc_ngay = None
    if use_date_filter:
        loc_ngay = st.date_input("Ngày trống trước ngày (tuỳ chọn)")

    keyword = st.text_input("Từ khoá địa chỉ (nhập quận, đường, số nhà...)")

    # apply filters safely
    df_filtered = df.copy()

    if loc_quan:
        df_filtered = df_filtered[df_filtered['Quận'].isin(loc_quan)]
    if loc_phuong:
        df_filtered = df_filtered[df_filtered['Phường'].isin(loc_phuong)]
    if loc_duong:
        df_filtered = df_filtered[df_filtered['Đường'].isin(loc_duong)]

    if loc_loai:
        df_filtered = df_filtered[df_filtered['Loại phòng'].apply(lambda x: any(item in x for item in loc_loai) if isinstance(x, list) else any(item in str(x) for item in loc_loai))]

    if loc_cuaso:
        df_filtered = df_filtered[df_filtered['Cửa sổ'].apply(lambda x: any(item in x for item in loc_cuaso) if isinstance(x, list) else any(item in str(x) for item in loc_cuaso))]

    if loc_nt:
        df_filtered = df_filtered[df_filtered['Nội Thất'].apply(lambda x: any(item in x for item in loc_nt) if isinstance(x, list) else any(item in str(x) for item in loc_nt))]

    if loc_tienich:
        df_filtered = df_filtered[df_filtered['Tiện ích'].apply(lambda x: any(item in x for item in loc_tienich) if isinstance(x, list) else any(item in str(x) for item in loc_tienich))]

    # price filter
    try:
        df_filtered = df_filtered[(df_filtered['Giá'] >= gia_min) & (df_filtered['Giá'] <= gia_max)]
    except Exception:
        pass

    # SAFE date filter: compare python date with python date
    if loc_ngay:
        if DATE_COL in df_filtered.columns:
            loc_date = pd.to_datetime(loc_ngay).date()  # ensure it's a date object
            # robust per-row check: convert row value to date if possible and compare
            def date_ok(x):
                if pd.isna(x):
                    return False
                # if it's already a date
                if isinstance(x, datetime):
                    return x.date() <= loc_date
                try:
                    # x might be pandas Timestamp or date-like
                    xr = pd.to_datetime(x, errors="coerce")
                    if pd.isna(xr):
                        return False
                    return xr.date() <= loc_date
                except Exception:
                    return False
            df_filtered = df_filtered[df_filtered[DATE_COL].apply(date_ok)]

    # keyword filter over address fields
    if keyword:
        kw = keyword.strip().lower()
        df_filtered = df_filtered[df_filtered.apply(lambda r: kw in str(r.get('Số nhà','')).lower() or kw in str(r.get('Đường','')).lower() or kw in str(r.get('Phường','')).lower() or kw in str(r.get('Quận','')).lower(), axis=1)]

    st.markdown(f"### 📋 Kết quả: **{len(df_filtered)} phòng** tìm thấy")

    if not df_filtered.empty:
        for idx, row in df_filtered.sort_values(by=DATE_COL, na_position='last').iterrows():
            dia_chi = f"{row.get('Số nhà','')} {row.get('Đường','')}, {row.get('Phường','')}, {row.get('Quận','')}"
            ma_phong = row.get('Mã phòng')
            # FORMATTING FOR DISPLAY AND SHARE BUTTON
            gia_text = f"{int(row['Giá']):,} VNĐ" if pd.notna(row.get('Giá')) else ""
            nothat_text = list_to_text(row.get('Nội Thất'))
            tienich_text = list_to_text(row.get('Tiện ích'))
            loai_text = list_to_text(row.get('Loại phòng'))
            ngay_text = row[DATE_COL].strftime("%d/%m/%Y") if pd.notna(row.get(DATE_COL)) else "Không có"
            
            # Create shareable text - ĐÃ THÊM HOA HỒNG
            

            st.markdown(f"#### 🏠 {dia_chi} ({ma_phong})")
            st.write(f"**Giá:** {gia_text}  |  **Loại:** {loai_text}")
            st.write(f"**Cửa sổ:** {row.get('Cửa sổ','')}  |  **Ngày trống:** {ngay_text}")
            st.write(f"**Nội thất:** {nothat_text}    |    **Tiện ích:** {tienich_text}")
            st.write(f"**Điện/Nước:** {row.get('Điện','')} / {row.get('Nước','')}    |    **Dịch vụ/Xe/Giặt:** {row.get('Dịch vụ','')} / {row.get('Xe','')} / {row.get('Giặt','')}")
            st.write(f"**Hoa hồng:** {row.get('Hoa hồng','')}") # 👉 HIỂN THỊ HOA HỒNG RIÊNG
            st.write(f"**Ghi chú:** {row.get('Ghi chú','')}")
            
            # 👉 BƯỚC CẬP NHẬT: HIỂN THỊ HÌNH ẢNH (Từ câu trả lời trước)
            # Hiển thị hình ảnh + chọn download
            image_urls = row.get('Hình ảnh')
            if image_urls and isinstance(image_urls, list) and len(image_urls) > 0:
                st.markdown("##### 📸 Hình ảnh phòng")
    
                # --- NÚT CHỌN TẤT CẢ ---
                select_all = st.checkbox("✅ Chọn tất cả ảnh", key=f"{ma_phong}_select_all")
    
                # Hiển thị tối đa 3 ảnh trên 1 dòng
                cols = st.columns(min(len(image_urls), 3)) 
                selected_files = []  # Danh sách ảnh được chọn download
    
                for i, url in enumerate(image_urls):
                    if os.path.exists(url):
                        with cols[i % 3]:
                            # Hiển thị ảnh
                            st.image(url, caption=os.path.basename(url), width=True)
                
                            # Checkbox chọn ảnh riêng lẻ
                            selected = select_all or st.checkbox("Chọn ảnh", key=f"{ma_phong}_{i}")
                            if selected:
                                selected_files.append(url)
                    else:
                        cols[i % 3].warning(f"File ảnh không tồn tại: {os.path.basename(url)}")
    
                # Nút download nếu có ảnh được chọn
                if selected_files:
                    from io import BytesIO
                    from zipfile import ZipFile
                    zip_buffer = BytesIO()
                    with ZipFile(zip_buffer, "w") as zip_file:
                        for fpath in selected_files:
                            zip_file.write(fpath, arcname=os.path.basename(fpath))
                    zip_buffer.seek(0)

                    st.download_button(
                        label="💾 Tải về ảnh đã chọn",
                        data=zip_buffer,
                        file_name=f"phong_{ma_phong}_images.zip",
                        mime="application/zip"
                    )

elif menu == 'CTV':
    st.subheader("Nhân viên — Lọc & Xem")
    st.info("Nhân viên chỉ có thể **lọc** và **xem ĐỊA CHỈ** của phòng. Không có quyền chỉnh sửa.")
    df = load_data()

    st.markdown("### 🔎 Tìm kiếm & Lọc phòng")

    quans = sorted([q for q in df['Quận'].dropna().unique().tolist()]) if 'Quận' in df.columns else []
    phuongs = sorted([p for p in df['Phường'].dropna().unique().tolist()]) if 'Phường' in df.columns else []
    duongs = sorted([d for d in df['Đường'].dropna().unique().tolist()]) if 'Đường' in df.columns else []

    col1, col2 = st.columns(2)
    with col1:
        loc_quan = st.multiselect("Quận", options=quans)
        loc_phuong = st.multiselect("Phường", options=phuongs)
        loc_duong = st.multiselect("Đường", options=duongs)
    with col2:
        loc_loai = st.multiselect("Loại phòng", options=["Studio", "Duplex", "1PN", "2PN", "Tách bếp", "Khác"])
        loc_cuaso = st.multiselect("Cửa sổ", options=["BAN CÔNG", "BAN CÔNG CHUNG", "Cửa sổ TRỜI", "Cửa sổ HL", "Cửa sổ GT", "Không"])
        loc_nt = st.multiselect("Nội thất", options=["Máy lạnh", "Tủ lạnh", "Giường", "Nệm", "Bàn Ghế", "Nước nóng NLMT", "Nước nóng Điện"])
        loc_tienich = st.multiselect("Tiện ích", options=["Cổng vân tay", "Camera 24/7", "Vệ sinh chung", "Giờ giấc tự do", "Không chung chủ", "Máy giặt chung", "Thang máy"])

    gia_min, gia_max = st.slider("Khoảng giá (VNĐ)", 2_000_000, 50_000_000, (2_000_000, 20_000_000), step=100_000)

    # Make date filter optional (Streamlit date_input always returns a date)
    use_date_filter = st.checkbox("Bật lọc theo ngày trống (trước ngày)")
    loc_ngay = None
    if use_date_filter:
        loc_ngay = st.date_input("Ngày trống trước ngày (tuỳ chọn)")

    keyword = st.text_input("Từ khoá địa chỉ (nhập quận, đường, số nhà...)")

    # apply filters safely
    df_filtered = df.copy()

    if loc_quan:
        df_filtered = df_filtered[df_filtered['Quận'].isin(loc_quan)]
    if loc_phuong:
        df_filtered = df_filtered[df_filtered['Phường'].isin(loc_phuong)]
    if loc_duong:
        df_filtered = df_filtered[df_filtered['Đường'].isin(loc_duong)]

    if loc_loai:
        df_filtered = df_filtered[df_filtered['Loại phòng'].apply(lambda x: any(item in x for item in loc_loai) if isinstance(x, list) else any(item in str(x) for item in loc_loai))]

    if loc_cuaso:
        df_filtered = df_filtered[df_filtered['Cửa sổ'].apply(lambda x: any(item in x for item in loc_cuaso) if isinstance(x, list) else any(item in str(x) for item in loc_cuaso))]

    if loc_nt:
        df_filtered = df_filtered[df_filtered['Nội Thất'].apply(lambda x: any(item in x for item in loc_nt) if isinstance(x, list) else any(item in str(x) for item in loc_nt))]

    if loc_tienich:
        df_filtered = df_filtered[df_filtered['Tiện ích'].apply(lambda x: any(item in x for item in loc_tienich) if isinstance(x, list) else any(item in str(x) for item in loc_tienich))]

    # price filter
    try:
        df_filtered = df_filtered[(df_filtered['Giá'] >= gia_min) & (df_filtered['Giá'] <= gia_max)]
    except Exception:
        pass

    # SAFE date filter: compare python date with python date
    if loc_ngay:
        if DATE_COL in df_filtered.columns:
            loc_date = pd.to_datetime(loc_ngay).date()  # ensure it's a date object
            # robust per-row check: convert row value to date if possible and compare
            def date_ok(x):
                if pd.isna(x):
                    return False
                # if it's already a date
                if isinstance(x, datetime):
                    return x.date() <= loc_date
                try:
                    # x might be pandas Timestamp or date-like
                    xr = pd.to_datetime(x, errors="coerce")
                    if pd.isna(xr):
                        return False
                    return xr.date() <= loc_date
                except Exception:
                    return False
            df_filtered = df_filtered[df_filtered[DATE_COL].apply(date_ok)]

    # keyword filter over address fields
    if keyword:
        kw = keyword.strip().lower()
        df_filtered = df_filtered[df_filtered.apply(lambda r: kw in str(r.get('Số nhà','')).lower() or kw in str(r.get('Đường','')).lower() or kw in str(r.get('Phường','')).lower() or kw in str(r.get('Quận','')).lower(), axis=1)]

    st.markdown(f"### 📋 Kết quả: **{len(df_filtered)} phòng** tìm thấy")

    if not df_filtered.empty:
    # --- BỔ SUNG: Hàm che số nhà ---
        def mask_so_nha(so_nha):
            """
            Chuyển số nhà thành dạng xxx
            Ví dụ:
                1897 -> 18xx
                187 -> 1xx
                12 -> xx
                5 -> x
                127/12/12 -> 127
            """
            try:
                s = str(so_nha).strip()
                if '/' in s:  # nếu có dấu '/', chỉ lấy phần đầu
                    s = s.split('/')[0]
                if len(s) == 0:
                    return "xx"
                elif len(s) == 1:
                    return "x"
                elif len(s) == 2:
                    return "xx"
                else:
                    return s[:-2] + "xx"
            except Exception:
                return "xx"

        for idx, row in df_filtered.sort_values(by=DATE_COL, na_position='last').iterrows():
            masked_so_nha = mask_so_nha(row.get('Số nhà',''))
            dia_chi = f"{masked_so_nha} {row.get('Đường','')}, {row.get('Phường','')}, {row.get('Quận','')}"

            ma_phong = row.get('Mã phòng')
            # FORMATTING FOR DISPLAY AND SHARE BUTTON
            gia_text = f"{int(row['Giá']):,} VNĐ" if pd.notna(row.get('Giá')) else ""
            nothat_text = list_to_text(row.get('Nội Thất'))
            tienich_text = list_to_text(row.get('Tiện ích'))
            loai_text = list_to_text(row.get('Loại phòng'))
            ngay_text = row[DATE_COL].strftime("%d/%m/%Y") if pd.notna(row.get(DATE_COL)) else "Không có"
            
            # Create shareable text - ĐÃ THÊM HOA HỒNG
            

            st.markdown(f"#### 🏠 {dia_chi} ({ma_phong})")
            st.write(f"**Giá:** {gia_text}  |  **Loại:** {loai_text}")
            st.write(f"**Cửa sổ:** {row.get('Cửa sổ','')}  |  **Ngày trống:** {ngay_text}")
            st.write(f"**Nội thất:** {nothat_text}    |    **Tiện ích:** {tienich_text}")
            st.write(f"**Điện/Nước:** {row.get('Điện','')} / {row.get('Nước','')}    |    **Dịch vụ/Xe/Giặt:** {row.get('Dịch vụ','')} / {row.get('Xe','')} / {row.get('Giặt','')}")
            st.write(f"**Hoa hồng:** {row.get('Hoa hồng','')}") # 👉 HIỂN THỊ HOA HỒNG RIÊNG
            st.write(f"**Ghi chú:** {row.get('Ghi chú','')}")
            
            # 👉 BƯỚC CẬP NHẬT: HIỂN THỊ HÌNH ẢNH (Từ câu trả lời trước)
            # Hiển thị hình ảnh + chọn download
            image_urls = row.get('Hình ảnh')
            if image_urls and isinstance(image_urls, list) and len(image_urls) > 0:
                st.markdown("##### 📸 Hình ảnh phòng")
    
                # --- NÚT CHỌN TẤT CẢ ---
                select_all = st.checkbox("✅ Chọn tất cả ảnh", key=f"{ma_phong}_select_all")
    
                # Hiển thị tối đa 3 ảnh trên 1 dòng
                cols = st.columns(min(len(image_urls), 3)) 
                selected_files = []  # Danh sách ảnh được chọn download
    
                for i, url in enumerate(image_urls):
                    if os.path.exists(url):
                        with cols[i % 3]:
                            # Hiển thị ảnh
                            st.image(url, caption=os.path.basename(url), width='stretch')
                
                            # Checkbox chọn ảnh riêng lẻ
                            selected = select_all or st.checkbox("Chọn ảnh", key=f"{ma_phong}_{i}")
                            if selected:
                                selected_files.append(url)
                    else:
                        cols[i % 3].warning(f"File ảnh không tồn tại: {os.path.basename(url)}")
    
                # Nút download nếu có ảnh được chọn
                if selected_files:
                    from io import BytesIO
                    from zipfile import ZipFile
                    zip_buffer = BytesIO()
                    with ZipFile(zip_buffer, "w") as zip_file:
                        for fpath in selected_files:
                            zip_file.write(fpath, arcname=os.path.basename(fpath))
                    zip_buffer.seek(0)

                    st.download_button(
                        label="💾 Tải về ảnh đã chọn",
                        data=zip_buffer,
                        file_name=f"phong_{ma_phong}_images.zip",
                        mime="application/zip"
                    )
            
            st.markdown("---")

        @st.cache_data
        def convert_df(df_in):
            return df_in.to_csv(index=False).encode('utf-8-sig')

        csv = convert_df(df_filtered)
        st.download_button("Tải xuống kết quả (CSV)", csv, file_name="phong_tro_loc.csv", mime='text/csv')
    else:
        st.write("Không có bản ghi nào khớp.")

# footer
st.markdown("---")

st.caption("App xây dựng bời hungtn AKA TRAN NGOC HUNG")
























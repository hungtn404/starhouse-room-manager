# app.py
from datetime import datetime
import os
import json
import pandas as pd
import streamlit as st

# -------- CONFIG --------
DATA_FILE = "data.xlsx"
# Default admin password if not set in Streamlit secrets
ADMIN_PASSWORD = "Admin@123*"
DATE_COL = "Ngày trống"
LIST_COLS = ["Loại phòng", "Nội Thất", "Tiện ích"]
# ------------------------

st.set_page_config(page_title="Quản lý nguồn phòng trọ - STARHOUSE", layout="centered")

# -----------------------
# Helpers: IO + Normalization
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
            "Ngày tạo"
        ])
        save_data(df)

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

def load_data():
    ensure_data_file()
    try:
        df = pd.read_excel(DATA_FILE, engine="openpyxl")
    except Exception as e:
        st.error(f"Lỗi đọc file {DATA_FILE}: {e}")
        return pd.DataFrame()

    df.columns = df.columns.str.strip()

    # parse date -> keep as python date (or NaT -> NaN)
    if DATE_COL in df.columns:
        try:
            df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce").dt.date
        except Exception:
            pass

    # decode json fields to list
    for col in LIST_COLS:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: _decode_list_field(x))
        else:
            df[col] = [[] for _ in range(len(df))]

    # fill missing columns with defaults
    expected_cols = [
        "ID", "Số nhà", "Đường", "Phường", "Quận", "Giá", "Cửa sổ",
        "Điện", "Nước", "Dịch vụ", "Xe", "Giặt chung", "Ghi chú", "Ngày tạo"
    ]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = pd.NA

    return df

def save_data(df):
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

def generate_id(df):
    if "ID" not in df.columns or df.empty:
        return 1
    else:
        try:
            return int(df["ID"].max()) + 1
        except Exception:
            return len(df) + 1

# -----------------------
# UI
# -----------------------

st.title("🏠 Quản lý nguồn phòng trọ - STARHOUSE")

menu = st.sidebar.radio("Chế độ", ["Admin", "Nhân viên (xem lọc)"])

# Use secrets safely (works both local and cloud)
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
        st.info("Để lọc phòng vào chế độ 'Nhân viên (xem lọc)'.")
        if st.checkbox("Xem trước dữ liệu (chỉ xem)"):
            st.dataframe(load_data().head(50))
    else:
        st.success("Đăng nhập thành công — Admin.")
        tab1, tab2, tab3 = st.tabs(["Thêm phòng", "Danh sách & chỉnh sửa", "Import / Export"])

        with tab1:
            st.markdown("### ➕ Thêm phòng mới")
            with st.form("add_form"):
                so_nha = st.text_input("Số nhà", placeholder="Ví dụ: 745/10/5")
                # replace '/' with '.' as requested
                df_tmp = load_data()
                street_options = sorted([s for s in df_tmp['Đường'].dropna().unique().tolist()]) if not df_tmp.empty else []
                default_streets = [
                    "An Hội", "Nguyễn Văn Khối", "Lê Văn Thọ", "Quang Trung", "Tân Sơn"
                ]
                # merge while keeping unique order
                seen = set()
                combined_streets = []
                for s in default_streets + street_options:
                    if s not in seen:
                        seen.add(s); combined_streets.append(s)

                duong = st.selectbox("Tên Đường", combined_streets)
                phuong = st.selectbox("Phường", [
                    "Phường 1", "Phường 3", "Phường 4", "Phường 5", "Phường 6", "Phường 7",
                    "Phường 8", "Phường 9", "Phường 10", "Phường 11", "Phường 12",
                    "Phường 13", "Phường 14", "Phường 15", "Phường 16", "Phường 17"
                ])
                quan = st.selectbox("Quận", ["Gò Vấp", "Tân Bình", "Bình Thạnh", "12"])
                gia = st.number_input("Giá (VNĐ)", step=500000, min_value=2000000)
                loai = st.multiselect("Loại phòng", ["Studio", "Duplex", "1PN", "2PN", "Tách bếp", "Khác"])
                ngay_trong = st.date_input("Ngày trống (chọn nếu có)")
                cua_so = st.selectbox("Cửa sổ", ["BAN CÔNG", "BAN CÔNG CHUNG", "Cửa sổ TRỜI", "Cửa sổ HL", "Cửa sổ GT", "Không"])
                noi_that = st.multiselect("Nội thất", ["Máy lạnh", "Tủ lạnh", "Giường", "Nệm", "Bàn Ghế", "Nước nóng NLMT", "Nước nóng Điện"])
                tien_ich = st.multiselect("Tiện ích", ["Cổng vân tay", "Camera 24/7", "Vệ sinh chung", "Giờ giấc tự do", "Không chung chủ", "Máy giặt chung", "Thang máy"])
                dien = st.selectbox("Giá điện", ["3.5K", "3.7K", "3.8K", "4.0K"])
                nuoc = st.selectbox("Giá nước", ["100K/người", "20K/khối"])
                dich_vu = st.selectbox("Dịch vụ", ["100K/phòng", "150K/phòng", "200K/phòng"])
                xe = st.selectbox("Xe", ["100K/xe", "150K/xe", "200K/xe", "FREE"])
                giat_chung = st.selectbox("Giặt chung", ["15K/lần", "20K/lần", "50K/người", "Không"])
                ghi_chu = st.text_area("Ghi chú (tùy chọn)")
                submitted = st.form_submit_button("Lưu phòng")
            if submitted:
                df = load_data()
                new_id = generate_id(df)
                new_row = {
                    "ID": new_id,
                    "Số nhà": so_nha,
                    "Đường": duong,
                    "Phường": phuong,
                    "Quận": quan,
                    "Giá": gia,
                    "Loại phòng": loai,
                    DATE_COL: ngay_trong,
                    "Cửa sổ": cua_so,
                    "Nội Thất": noi_that,
                    "Tiện ích": tien_ich,
                    "Điện": dien,
                    "Nước": nuoc,
                    "Dịch vụ": dich_vu,
                    "Xe": xe,
                    "Giặt chung": giat_chung,
                    "Ghi chú": ghi_chu,
                    "Ngày tạo": datetime.now()
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df)
                st.success(f"Đã lưu phòng ID={new_id}")

        with tab2:
            st.markdown("### 📋 Danh sách hiện tại (Admin có thể xóa 1 dòng)")
            df = load_data()
            st.write(f"Tổng bản ghi: {len(df)}")
            st.dataframe(df.sort_values(by="Ngày tạo", ascending=False).reset_index(drop=True))
            st.markdown("---")
            st.markdown("**Xóa bản ghi** — nhập ID để xóa")
            del_id = st.number_input("ID cần xóa", min_value=1, step=1)
            if st.button("Xóa"):
                df = load_data()
                if del_id in df["ID"].values:
                    df = df[df["ID"] != del_id]
                    save_data(df)
                    st.success(f"Đã xóa ID={del_id}")
                else:
                    st.error("ID không tồn tại")

        with tab3:
            st.markdown("### 🔁 Import / Export Excel")
            st.markdown("- Tải xuống file Excel hiện tại:")
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "rb") as f:
                    st.download_button("Tải file data.xlsx", f, file_name="data.xlsx")
            else:
                st.info("Chưa có file data.xlsx trên server (app sẽ tự tạo khi lưu bản ghi).")

            st.markdown("---")
            st.markdown("**Upload file Excel** (ghi đè hoặc merge)")
            uploaded = st.file_uploader("Chọn file .xlsx để import", type=["xlsx"])
            if uploaded is not None:
                try:
                    df_new = pd.read_excel(uploaded, engine="openpyxl")
                    # decode list cols from uploaded file
                    for col in LIST_COLS:
                        if col in df_new.columns:
                            df_new[col] = df_new[col].apply(lambda x: _decode_list_field(x))
                    action = st.radio("Hành động khi import", ["Merge (ghép dữ liệu)", "Overwrite (ghi đè)"])
                    if st.button("Thực hiện import"):
                        df_old = load_data()
                        if action == "Overwrite (ghi đè)":
                            save_data(df_new)
                            st.success("Đã ghi đè file với dữ liệu upload.")
                        else:
                            if "ID" not in df_new.columns:
                                df_new["ID"] = range(generate_id(df_old), generate_id(df_old) + len(df_new))
                            df_merged = pd.concat([df_old, df_new], ignore_index=True)
                            save_data(df_merged)
                            st.success("Đã ghép dữ liệu vào file hiện tại.")
                except Exception as e:
                    st.error(f"Lỗi khi đọc file: {e}")

# -----------------------
# Nhân viên (xem & lọc) - đúng scope
# -----------------------
elif menu == "Nhân viên (xem lọc)":
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
            df_filtered = df_filtered[df_filtered[DATE_COL].apply(lambda x: (pd.notna(x) and isinstance(x, (datetime,)) and x.date() <= loc_date) or (pd.notna(x) and isinstance(x, pd._libs.tslibs.timestamps.Timestamp) and x.date() <= loc_date) or (pd.notna(x) and not isinstance(x, (datetime, pd._libs.tslibs.timestamps.Timestamp)) and x <= loc_date) if pd.notna(x) else False)]

            # Simpler robust alternative:
            # df_filtered = df_filtered[df_filtered[DATE_COL].apply(lambda x: pd.notna(x) and x <= loc_date)]

    # keyword filter over address fields
    if keyword:
        kw = keyword.strip().lower()
        df_filtered = df_filtered[df_filtered.apply(lambda r: kw in str(r.get('Số nhà','')).lower() or kw in str(r.get('Đường','')).lower() or kw in str(r.get('Phường','')).lower() or kw in str(r.get('Quận','')).lower(), axis=1)]

    st.markdown(f"### 📋 Kết quả: **{len(df_filtered)} phòng** tìm thấy")

    if not df_filtered.empty:
        for idx, row in df_filtered.sort_values(by=DATE_COL, na_position='last').iterrows():
            dia_chi = f"{row.get('Số nhà','')} {row.get('Đường','')}, {row.get('Phường','')}, {row.get('Quận','')}"
            gia_text = f"{int(row['Giá']):,} VNĐ" if pd.notna(row.get('Giá')) else ""
            loai_text = ", ".join(row['Loại phòng']) if isinstance(row['Loại phòng'], list) and row['Loại phòng'] else (str(row['Loại phòng']) if pd.notna(row.get('Loại phòng')) else '')
            nothat_text = ", ".join(row['Nội Thất']) if isinstance(row['Nội Thất'], list) and row['Nội Thất'] else (str(row['Nội Thất']) if pd.notna(row.get('Nội Thất')) else '')
            tienich_text = ", ".join(row['Tiện ích']) if isinstance(row['Tiện ích'], list) and row['Tiện ích'] else (str(row['Tiện ích']) if pd.notna(row.get('Tiện ích')) else '')
            ngay_text = row[DATE_COL].strftime("%d/%m/%Y") if pd.notna(row.get(DATE_COL)) else "Không có"

            st.markdown(f"#### 🏠 {dia_chi}")
            st.write(f"**Giá:** {gia_text}  |  **Loại:** {loai_text}")
            st.write(f"**Cửa sổ:** {row.get('Cửa sổ','')}  |  **Ngày trống:** {ngay_text}")
            st.write(f"**Nội thất:** {nothat_text}   |   **Tiện ích:** {tienich_text}")
            st.write(f"**Điện/Nước:** {row.get('Điện','')} / {row.get('Nước','')}   |   **Dịch vụ/Xe/Giặt:** {row.get('Dịch vụ','')} / {row.get('Xe','')} / {row.get('Giặt chung','')}")
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
st.caption("App xây dựng bằng Streamlit — lưu file Excel (data.xlsx). Đề xuất: chuyển sang Google Sheets hoặc database nếu cần multi-user/độ bền dữ liệu cao hơn.")

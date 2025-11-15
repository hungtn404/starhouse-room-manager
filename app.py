# app.py
from datetime import datetime
import io
import os
import pandas as pd
import streamlit as st
import json

# -------- CONFIG --------
DATA_FILE = "data.xlsx"
ADMIN_PASSWORD = "Admin@123*"  # đổi password này trước khi production
DATE_COL = "Ngày trống"
# ------------------------

st.set_page_config(page_title="Quản lý nguồn phòng trọ - STARHOUSE", layout="centered")

# --- helper: create sample file if not exist
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
        df.to_excel(DATA_FILE, index=False)

def load_data():
    ensure_data_file()
    df = pd.read_excel(DATA_FILE, engine="openpyxl")

    # parse JSON → list
    list_cols = ["Loại phòng", "Nội Thất", "Tiện ích"]
    for col in list_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) and x.startswith("[") else [])

    # handle ngày trống
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce").dt.date

    return df

def save_data(df):
    df2 = df.copy()
    list_cols = ["Loại phòng", "Nội Thất", "Tiện ích"]
    for col in list_cols:
        df2[col] = df2[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else x)
    df2.to_excel(DATA_FILE, index=False)

def generate_id(df):
    if "ID" not in df.columns or df.empty:
        return 1
    else:
        return int(df["ID"].max()) + 1

# --- UI ---
st.title("🏠 Quản lý nguồn phòng trọ - STARHOUSE")

menu = st.sidebar.radio("Chế độ", ["Admin", "Nhân viên (xem lọc)"])

if menu == "Admin":
    st.subheader("Admin — Thêm / Import / Export dữ liệu")
    pwd = st.text_input("Nhập mật khẩu admin", type="password")
    if pwd != ADMIN_PASSWORD:
        st.warning("Bạn đang ở chế độ view (nhập mật khẩu để vào admin).")
        st.info("Để lọc phòng vào chế độ 'Nhân viên (xem lọc)'.")
        # show a small preview when wrong password
        if st.checkbox("Xem trước dữ liệu (chỉ xem)"):
            df_preview = load_data()
            st.dataframe(df_preview.head(50))
    else:
        st.success("Đăng nhập thành công — Admin.")
        tab1, tab2, tab3 = st.tabs(["Thêm phòng", "Danh sách & chỉnh sửa", "Import / Export"])

        with tab1:
            st.markdown("### ➕ Thêm phòng mới")
            with st.form("add_form"):
                so_nha = st.text_input("Số nhà", placeholder="Ví dụ: 745/10/5")
                duong = st.selectbox("Tên Đường", ["An Hội",
"An Nhơn",
"Bùi Quang Là",
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
"Nguyễn Văn Khối"])
                phuong = st.selectbox("Phường", ["Phường 1",
"Phường 3",
"Phường 4",
"Phường 5",
"Phường 6",
"Phường 7",
"Phường 8",
"Phường 9",
"Phường 10",
"Phường 11",
"Phường 12",
"Phường 13",
"Phường 14",
"Phường 15",
"Phường 16",
"Phường 17"])
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
            with open(DATA_FILE, "rb") as f:
                st.download_button("Tải file data.xlsx", f, file_name="data.xlsx")
            st.markdown("---")
            st.markdown("**Upload file Excel** (ghi đè hoặc merge)")
            uploaded = st.file_uploader("Chọn file .xlsx để import", type=["xlsx"])
            if uploaded is not None:
                try:
                    df_new = pd.read_excel(uploaded, engine="openpyxl")
                    action = st.radio("Hành động khi import", ["Merge (ghép dữ liệu)", "Overwrite (ghi đè)"])
                    if st.button("Thực hiện import"):
                        df_old = load_data()
                        if action == "Overwrite (ghi đè)":
                            save_data(df_new)
                            st.success("Đã ghi đè file với dữ liệu upload.")
                        else:
                            # simple merge: append and reassign IDs if missing
                            if "ID" not in df_new.columns:
                                df_new["ID"] = range(generate_id(df_old), generate_id(df_old) + len(df_new))
                            df_merged = pd.concat([df_old, df_new], ignore_index=True)
                            save_data(df_merged)
                            st.success("Đã ghép dữ liệu vào file hiện tại.")
                except Exception as e:
                    st.error(f"Lỗi khi đọc file: {e}")

elif menu == "Nhân viên (xem lọc)":
    st.subheader("Nhân viên — Lọc & Xem")
    st.info("Nhân viên chỉ có thể **lọc** và **xem ĐỊA CHỈ** của phòng. Không có quyền chỉnh sửa.")
    df = load_data()

# -------------------------------
#        NHÂN VIÊN XEM PHÒNG
# -------------------------------
st.markdown("### 🔎 Tìm kiếm & Lọc phòng")

df = load_data()

# 🔍 Thanh lọc
col1, col2 = st.columns(2)
with col1:
    loc_quan = st.multiselect("Quận", sorted(df["Quận"].dropna().unique().tolist()))
    loc_phuong = st.multiselect("Phường", sorted(df["Phường"].dropna().unique().tolist()))
    loc_duong = st.multiselect("Đường", sorted(df["Đường"].dropna().unique().tolist()))
with col2:
    loc_loai = st.multiselect("Loại phòng", ["Studio", "Duplex", "1PN", "2PN", "Tách bếp", "Khác"])
    loc_nt = st.multiselect("Nội thất", ["Máy lạnh", "Tủ lạnh", "Giường", "Nệm", "Bàn Ghế", "Nước nóng NLMT", "Nước nóng Điện"])
    loc_tienich = st.multiselect("Tiện ích", ["Cổng vân tay", "Camera 24/7", "Vệ sinh chung", "Giờ giấc tự do", "Không chung chủ", "Máy giặt chung", "Thang máy"])

# Lọc theo giá
gia_min, gia_max = st.slider("Khoảng giá", 2_000_000, 20_000_000, (2_000_000, 20_000_000), step=500_000)

# Lọc theo ngày trống
loc_ngay = st.date_input("Ngày trống trước ngày (tuỳ chọn)")

# --------------------------------------
#        ÁP DỤNG CÁC BỘ LỌC
# --------------------------------------
df_filtered = df.copy()

# Lọc quận / phường / đường
if loc_quan:
    df_filtered = df_filtered[df_filtered["Quận"].isin(loc_quan)]

if loc_phuong:
    df_filtered = df_filtered[df_filtered["Phường"].isin(loc_phuong)]

if loc_duong:
    df_filtered = df_filtered[df_filtered["Đường"].isin(loc_duong)]

# Lọc loại phòng (list → check chứa)
if loc_loai:
    df_filtered = df_filtered[df_filtered["Loại phòng"].apply(lambda x: any(item in x for item in loc_loai))]

# Lọc nội thất
if loc_nt:
    df_filtered = df_filtered[df_filtered["Nội Thất"].apply(lambda x: any(item in x for item in loc_nt))]

# Lọc tiện ích
if loc_tienich:
    df_filtered = df_filtered[df_filtered["Tiện ích"].apply(lambda x: any(item in x for item in loc_tienich))]

# Lọc giá
df_filtered = df_filtered[(df_filtered["Giá"] >= gia_min) & (df_filtered["Giá"] <= gia_max)]

# Lọc theo ngày trống
if loc_ngay:
    df_filtered = df_filtered[
        (df_filtered[DATE_COL].notna()) &
        (df_filtered[DATE_COL] <= pd.to_datetime(loc_ngay))
    ]

# --------------------------------------
#        HIỂN THỊ DANH SÁCH
# --------------------------------------
st.markdown(f"### 📋 Kết quả: **{len(df_filtered)} phòng** tìm thấy")

for idx, row in df_filtered.iterrows():
    st.markdown(f"""
    #### 🏠 {row['Số nhà']} {row['Đường']}, {row['Phường']}, {row['Quận']}
    **Giá:** {int(row['Giá']):,} VNĐ  
    **Loại phòng:** {", ".join(row['Loại phòng']) if isinstance(row['Loại phòng'], list) else "Không"
}  
    **Cửa sổ:** {row['Cửa sổ']}  
    **Nội thất:** {", ".join(row['Nội Thất']) if row['Nội Thất'] else 'Không'}  
    **Tiện ích:** {", ".join(row['Tiện ích']) if row['Tiện ích'] else 'Không'}  
    **Điện/Nước:** {row['Điện']}, {row['Nước']}  
    **Dịch vụ:** {row['Dịch vụ']} — **Xe:** {row['Xe']}  
    **Giặt chung:** {row['Giặt chung']}  
    **Ngày trống:** {row[DATE_COL].strftime("%d/%m/%Y") if pd.notnull(row[DATE_COL]) else "Không có"}
    ---
    """)


# --- footer
st.markdown("---")
st.caption("App xây dựng nhanh bằng Streamlit — dùng file Excel (data.xlsx). Nếu cần mình có thể nâng cấp sang Google Sheets hoặc database để multi-user an toàn hơn.")

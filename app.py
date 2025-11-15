# app.py
from datetime import datetime
import io
import os
import pandas as pd
import streamlit as st

# -------- CONFIG --------
DATA_FILE = "data.xlsx"
ADMIN_PASSWORD = "hungadmin2025"  # đổi password này trước khi production
DATE_COL = "Ngày trống"
# ------------------------

st.set_page_config(page_title="Quản lý nguồn phòng trọ", layout="centered")

# --- helper: create sample file if not exist
def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=[
            "ID",
            "Địa chỉ",
            "Giá",
            "Loại phòng",
            DATE_COL,
            "Cửa sổ",
            "Ghi chú",
            "Ngày tạo"
        ])
        df.to_excel(DATA_FILE, index=False)

def load_data():
    ensure_data_file()
    try:
        df = pd.read_excel(DATA_FILE, parse_dates=[DATE_COL], engine="openpyxl")
    except Exception:
        df = pd.read_excel(DATA_FILE, engine="openpyxl")
    # normalize
    if DATE_COL in df.columns:
        try:
            df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce").dt.date
        except Exception:
            pass
    return df

def save_data(df):
    df.to_excel(DATA_FILE, index=False)

def generate_id(df):
    if "ID" not in df.columns or df.empty:
        return 1
    else:
        return int(df["ID"].max()) + 1

# --- UI ---
st.title("🏠 Quản lý nguồn phòng trọ (Streamlit)")

menu = st.sidebar.radio("Chế độ", ["Đăng nhập Admin", "Nhân viên (xem lọc)"])

if menu == "Đăng nhập Admin":
    st.subheader("Admin — Thêm / Import / Export dữ liệu")
    pwd = st.text_input("Nhập mật khẩu admin", type="password")
    if pwd != ADMIN_PASSWORD:
        st.warning("Bạn đang ở chế độ view (nhập đúng mật khẩu để vào admin).")
        st.info("Muốn dùng chế độ nhân viên thì qua menu 'Nhân viên (xem lọc)'.")
        # show a small preview when wrong password
        if st.checkbox("Xem preview dữ liệu (chỉ xem)"):
            df_preview = load_data()
            st.dataframe(df_preview.head(50))
    else:
        st.success("Đăng nhập thành công — quyền Admin.")
        tab1, tab2, tab3 = st.tabs(["Thêm phòng", "Danh sách & chỉnh sửa", "Import / Export"])

        with tab1:
            st.markdown("### ➕ Thêm phòng mới")
            with st.form("add_form"):
                dia_chi = st.text_input("Địa chỉ", placeholder="Ví dụ: Số 3 An Hội, P13, Q.Gò Vấp")
                gia = st.number_input("Giá (VNĐ)", step=50000, min_value=0)
                loai = st.selectbox("Loại phòng", ["Studio", "Duplex", "Gác lửng", "Phòng thường", "Khác"])
                ngay_trong = st.date_input("Ngày trống (chọn nếu có)")
                cua_so = st.selectbox("Cửa sổ", ["Có", "Không", "Không rõ"])
                ghi_chu = st.text_area("Ghi chú (tùy chọn)")
                submitted = st.form_submit_button("Lưu phòng")
            if submitted:
                df = load_data()
                new_id = generate_id(df)
                new_row = {
                    "ID": new_id,
                    "Địa chỉ": dia_chi,
                    "Giá": gia,
                    "Loại phòng": loai,
                    DATE_COL: ngay_trong,
                    "Cửa sổ": cua_so,
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
    st.subheader("Nhân viên — Lọc & Xem (Chỉ xem địa chỉ theo policy)")
    st.info("Nhân viên chỉ có thể **lọc** và **xem ĐỊA CHỈ** của phòng. Không có quyền chỉnh sửa.")
    df = load_data()

    # Filters
    st.markdown("#### Bộ lọc")
    col1, col2 = st.columns(2)
    with col1:
        gia_max = st.number_input("Giá tối đa (VNĐ)", value=int(df["Giá"].max() if "Giá" in df.columns and not df.empty else 10000000))
        loai_sel = st.selectbox("Loại phòng", options=["Tất cả"] + (df["Loại phòng"].dropna().unique().tolist() if "Loại phòng" in df.columns else []))
    with col2:
        cua_so_sel = st.selectbox("Cửa sổ", options=["Tất cả", "Có", "Không", "Không rõ"])
        ngay_tu = st.date_input("Từ ngày trống (tùy chọn)", value=None)

    keyword = st.text_input("Từ khoá địa chỉ (nhập quận, đường,...)")

    # filtering logic
    df_filtered = df.copy()
    if "Giá" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["Giá"] <= gia_max]
    if loai_sel and loai_sel != "Tất cả":
        df_filtered = df_filtered[df_filtered["Loại phòng"] == loai_sel]
    if cua_so_sel and cua_so_sel != "Tất cả" and "Cửa sổ" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["Cửa sổ"] == cua_so_sel]
    if keyword:
        df_filtered = df_filtered[df_filtered["Địa chỉ"].astype(str).str.contains(keyword, case=False, na=False)]
    if ngay_tu:
        if DATE_COL in df_filtered.columns:
            df_filtered = df_filtered[pd.to_datetime(df_filtered[DATE_COL], errors="coerce").dt.date >= ngay_tu]

    st.write(f"Kết quả: {len(df_filtered)} bản ghi")
    # show only address and minimal info
    if not df_filtered.empty:
        show_df = df_filtered[["ID", "Địa chỉ", "Giá", "Loại phòng", DATE_COL]].copy()
        show_df = show_df.sort_values(by=DATE_COL, ascending=True).reset_index(drop=True)
        st.dataframe(show_df)
        with st.expander("Xem Địa chỉ dạng danh sách (dễ copy)"):
            for i, row in show_df.iterrows():
                st.write(f"- ID {row['ID']} | {row['Địa chỉ']} | {row.get('Giá',''):,} VNĐ | {row.get('Loại phòng','')}")
    else:
        st.write("Không có bản ghi nào khớp.")

# --- footer
st.markdown("---")
st.caption("App xây dựng nhanh bằng Streamlit — dùng file Excel (data.xlsx). Nếu cần mình có thể nâng cấp sang Google Sheets hoặc database để multi-user an toàn hơn.")

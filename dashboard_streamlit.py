import streamlit as st
import pandas as pd
import numpy as np # ### REVISI: Menambahkan numpy untuk menangani NaN
import re
import os
import glob
import altair as alt

# Konfigurasi halaman Streamlit agar lebih lebar
st.set_page_config(layout="wide")

# Fungsi untuk mengekstrak WMO ID dari nama file
def get_wmo_id_from_filename(filename):
    """Mengekstrak angka dari nama file, diasumsikan sebagai WMO ID."""
    match = re.search(r'(\d+)', filename)
    if match:
        return match.group(1)
    return os.path.basename(filename)

# Fungsi yang dimodifikasi untuk mem-parsing satu file dari path-nya
def parse_log_file(file_path):
    """Membaca satu file log dari path, mem-parsingnya, dan menambahkan WMO ID."""
    wmo_id = get_wmo_id_from_filename(os.path.basename(file_path))
    log_pattern = re.compile(
        r"\[(.*?)\]\s+di luar batas:\s+sebelumnya=(.*?),\s+sesudah=(.*?)\s+\(timestamp:\s+(.*?)\)"
    )
    
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = log_pattern.match(line.strip())
                if match:
                    variable, before_val, after_val, timestamp = match.groups()
                    data.append({
                        "wmo_id": wmo_id,
                        "variabel": variable.strip(),
                        "nilai_sebelumnya": before_val.strip(),
                        "nilai_sesudah": after_val.strip(),
                        "timestamp": timestamp.strip()
                    })
    except Exception as e:
        st.warning(f"Gagal membaca file {file_path}: {e}")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['nilai_sebelumnya'] = pd.to_numeric(df['nilai_sebelumnya'], errors='coerce')
    df['nilai_sesudah'] = pd.to_numeric(df['nilai_sesudah'], errors='coerce')
    df.dropna(subset=['timestamp'], inplace=True)
    return df

# Fungsi untuk memuat semua log dari sebuah folder
@st.cache_data
def load_data_from_folder(folder_path):
    """Memindai folder, mem-parsing semua file log, dan menggabungkannya."""
    search_pattern = os.path.join(folder_path, '*_log.txt')
    log_files = glob.glob(search_pattern)

    if not log_files:
        return pd.DataFrame()

    all_dfs = [parse_log_file(f) for f in log_files]
    all_dfs = [df for df in all_dfs if not df.empty]
    
    if not all_dfs:
        return pd.DataFrame()

    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df

# Fungsi baru untuk memuat dan mem-parsing data CSV dari Phase 2
@st.cache_data
def load_phase_2_data(folder_path):
    """Memindai folder, membaca semua file CSV, dan menggabungkannya."""
    search_pattern = os.path.join(folder_path, 'updated_*.csv')
    csv_files = glob.glob(search_pattern)

    if not csv_files:
        st.warning(f"Tidak ada file CSV dengan format 'updated_*.csv' ditemukan di '{folder_path}'.")
        return pd.DataFrame()

    all_dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            required_cols = ['wmo_id', 'parameter', 'before', 'after', 'timestamp', 'after_45', 'flag', 'after_alt_2']
            if all(col in df.columns for col in required_cols):
                 all_dfs.append(df)
            else:
                st.warning(f"File {f} dilewati karena tidak memiliki semua kolom yang dibutuhkan (termasuk after_alt_2).")
        except Exception as e:
            st.warning(f"Gagal membaca atau memproses file CSV {f}: {e}")

    if not all_dfs:
        return pd.DataFrame()

    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'], errors='coerce')
    combined_df['wmo_id'] = combined_df['wmo_id'].astype(str)
    
    numeric_cols = ['before', 'after', 'after_45', 'after_alt_2']
    for col in numeric_cols:
        if col in combined_df.columns:
            combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce')

    return combined_df


# --- UI STREAMLIT ---

st.title("🛰️ Dashboard Analisis Log Lengkap")
st.markdown("Analisis data dari log awal dan data perbaikan.")

tab_main, tab_dist, tab_trend_monthly, tab_trend_yearly, tab_phase2, tab_raw = st.tabs([
    "🏠 Ringkasan", 
    "📊 Distribusi", 
    "📈 Tren Bulanan", 
    "📉 Tren Tahunan", 
    "🔍 Analisis Lanjutan ",
    "📋 Data Mentah"
])

with st.sidebar:
    st.header("1. Konfigurasi Analisis")
    folder_path_phase1 = st.text_input("Path Folder Log Awal :", "pengecekan_revisi")

    if st.button("🚀 Mulai Analisis "):
        if not os.path.isdir(folder_path_phase1):
            st.error(f"Error: Folder '{folder_path_phase1}' tidak ditemukan.")
        else:
            with st.spinner(f"Menganalisis file di '{folder_path_phase1}'..."):
                df_combined = load_data_from_folder(folder_path_phase1)
                if df_combined.empty:
                    st.error(f"Tidak ada file log valid (*_log.txt) ditemukan di '{folder_path_phase1}'.")
                else:
                    st.session_state['data'] = df_combined
                    st.success(f"Analisis  selesai! Ditemukan {len(st.session_state['data'])} temuan.")
                    st.rerun()

if 'data' in st.session_state:
    df = st.session_state['data']

    with st.sidebar:
        st.header("2. Filter Tampilan Data")
        all_wmo_ids = sorted(df['wmo_id'].unique().tolist())
        selected_wmo_ids = st.multiselect("Pilih Stasiun (WMO ID):", options=all_wmo_ids, default=all_wmo_ids)
        
        all_variables = sorted(df['variabel'].unique().tolist())
        selected_variables = st.multiselect("Pilih Variabel:", options=all_variables, default=all_variables)

        if not df.empty and not df['timestamp'].isnull().all():
            min_date = df['timestamp'].min().date()
            max_date = df['timestamp'].max().date()
            date_range = st.date_input("Pilih Rentang Tanggal:", value=(min_date, max_date), min_value=min_date, max_value=max_date)
            start_date, end_date = date_range[0], date_range[-1]
        else:
            start_date, end_date = pd.Timestamp('1970-01-01').date(), pd.Timestamp.now().date()

    df_filtered = df[
        (df['wmo_id'].isin(selected_wmo_ids)) &
        (df['variabel'].isin(selected_variables)) &
        (df['timestamp'].dt.date >= start_date) &
        (df['timestamp'].dt.date <= end_date)
    ]
    st.sidebar.info(f"Menampilkan **{len(df_filtered)}** dari total **{len(df)}** temuan Phase 1.")

    with tab_main:
        st.header("Ringkasan & Statistik ")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.metric("Total Temuan", f"{len(df_filtered):,}")
            st.metric("Stasiun Dianalisis", f"{df_filtered['wmo_id'].nunique():,}")
        with col2:
            st.metric("Variabel Bermasalah", f"{df_filtered['variabel'].nunique():,}")
        with col3:
            st.subheader("Tabel Parameter Bermasalah")
            param_counts = df_filtered['variabel'].value_counts().reset_index()
            param_counts.columns = ['Parameter', 'Jumlah Temuan']
            st.dataframe(param_counts, use_container_width=True)

    with tab_dist:
        st.header("Distribusi Temuan ")
        if not df_filtered.empty:
            st.subheader("Distribusi Temuan per Variabel")
            var_counts = df_filtered['variabel'].value_counts().reset_index()
            var_counts.columns = ['variabel', 'jumlah']
            chart_bar_var = alt.Chart(var_counts).mark_bar().encode(
                x=alt.X('jumlah:Q', title='Jumlah Temuan'),
                y=alt.Y('variabel:N', title='Nama Variabel', sort='-x')
            ).interactive()
            st.altair_chart(chart_bar_var, use_container_width=True)

            st.subheader("Distribusi Temuan per Stasiun (WMO ID)")
            wmo_counts = df_filtered['wmo_id'].value_counts().reset_index()
            wmo_counts.columns = ['wmo_id', 'jumlah']
            chart_bar_wmo = alt.Chart(wmo_counts).mark_bar(color='orange').encode(
                x=alt.X('jumlah:Q', title='Jumlah Temuan'),
                y=alt.Y('wmo_id:N', title='WMO ID', sort='-x')
            ).interactive()
            st.altair_chart(chart_bar_wmo, use_container_width=True)
        else:
            st.warning("Tidak ada data untuk ditampilkan berdasarkan filter saat ini.")

    with tab_trend_monthly:
        st.header("Tren Temuan Berdasarkan Waktu (Bulanan)")
        if not df_filtered.empty:
            errors_over_time = df_filtered.set_index('timestamp').resample('M').size().reset_index(name='jumlah_temuan')
            chart_line = alt.Chart(errors_over_time).mark_line(point=True).encode(
                x=alt.X('yearmonth(timestamp):T', title='Bulan'),
                y=alt.Y('jumlah_temuan:Q', title='Jumlah Temuan'),
                tooltip=['yearmonth(timestamp)', 'jumlah_temuan']
            ).interactive()
            st.altair_chart(chart_line, use_container_width=True)
        else:
            st.warning("Tidak ada data untuk ditampilkan berdasarkan filter saat ini.")

    with tab_trend_yearly:
        st.header("Analisis Tren Tahunan untuk Parameter Spesifik")
        available_vars = sorted(df_filtered['variabel'].unique().tolist())
        
        if available_vars:
            param_to_analyze = st.selectbox("Pilih satu parameter untuk dianalisis:", options=available_vars)
            df_param_trend = df_filtered[df_filtered['variabel'] == param_to_analyze]
            trend_data = df_param_trend.groupby([df_param_trend['timestamp'].dt.year.rename('tahun'), 'wmo_id']).size().reset_index(name='jumlah_temuan')
            
            chart_trend_yearly = alt.Chart(trend_data).mark_line(point=True).encode(
                x=alt.X('tahun:O', title='Tahun', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('jumlah_temuan:Q', title=f'Jumlah Temuan ({param_to_analyze})'),
                color=alt.Color('wmo_id:N', title='WMO ID'),
                tooltip=['tahun', 'wmo_id', 'jumlah_temuan']
            ).interactive()
            st.altair_chart(chart_trend_yearly, use_container_width=True)
        else:
            st.warning("Tidak ada variabel yang tersedia untuk dianalisis berdasarkan filter Anda.")

    with tab_raw:
        st.header("Detail Data Mentah ")
        st.dataframe(df_filtered)

with tab_phase2:
    st.header("🔍 Analisis lanjutan untuk tindak lanjut perbaikan data")
    st.markdown("Tab ini menganalisis file CSV dari proses tindak lanjut perbaikan data untuk melihat status setiap data yang bermasalah.")
    
    with st.expander("ℹ️ Klik di sini untuk melihat penjelasan nilai 'flag'"):
        st.markdown("""
        Kolom `flag` di dalam file CSV menandakan status perubahan nilai setelah proses pengecekan alternatif:
        - **`flag = 0`**: Tidak ada perubahan nilai. Nilai tetap sama setelah pengecekan alternatif.
        - **`flag = 1`**: Nilai berubah. Nilai baru diambil dari pengecekan alternatif 1 (**RAW_ME45**).
        - **`flag = 2`**: Nilai berubah. Nilai baru diambil dari pengecekan alternatif 2.
        """)

    folder_path_phase2 = st.text_input("Masukkan path ke folder  (CSV):", "phase_2_logs")

    if st.button("📊 Jalankan Analisis "):
        if not os.path.isdir(folder_path_phase2):
            st.error(f"Error: Folder '{folder_path_phase2}' tidak ditemukan.")
        else:
            with st.spinner(f"Menganalisis file CSV di '{folder_path_phase2}'..."):
                df_phase2 = load_phase_2_data(folder_path_phase2)
                if df_phase2.empty:
                    st.error(f"Tidak ada data valid yang dapat dimuat dari folder '{folder_path_phase2}'.")
                else:
                    st.session_state['data_phase2'] = df_phase2
                    st.success(f"Analisis  selesai! {len(df_phase2)} baris data dimuat.")
    
    if 'data_phase2' in st.session_state:
        df_p2 = st.session_state['data_phase2']
        
        st.markdown("---")
        st.subheader("Filter Analisis ")
        
        col1, col2,col3= st.columns(3)
        with col1:
            all_wmo_ids_p2 = sorted(df_p2['wmo_id'].unique().tolist())
            selected_wmo_ids_p2 = st.multiselect("Pilih Stasiun (WMO ID) :", options=all_wmo_ids_p2, default=all_wmo_ids_p2, key="p2_wmo_filter")
        with col2:
            all_params_p2 = sorted(df_p2['parameter'].unique().tolist())
            selected_params_p2 = st.multiselect("Pilih Parameter :", options=all_params_p2, default=all_params_p2, key="p2_param_filter")
        with col3:
            selected_flags = st.multiselect(
                "Filter Berdasarkan Flag:",
                options=[0, 1, 2],
                default=[0, 1, 2],
                key="p2_flag_filter"
            )

        df_p2_filtered = df_p2[
            (df_p2['wmo_id'].isin(selected_wmo_ids_p2)) &
            (df_p2['parameter'].isin(selected_params_p2)) &
            (df_p2['flag'].isin(selected_flags)) # <-- Tambahkan baris ini
        ]
        
        df_problem = df_p2_filtered[df_p2_filtered['after'] == 9999].copy()
        total_problem = len(df_problem)

        if total_problem == 0:
            st.info("Berdasarkan filter Anda, tidak ditemukan data dengan nilai `after = 9999`.")
        else:
            total_salvageable = df_problem['after_45'].notna().sum()
            total_unsalvageable = total_problem - total_salvageable
            percentage = (total_salvageable / total_problem * 100) if total_problem > 0 else 0

            st.markdown("---")
            st.subheader("Hasil Rekapitulasi Perbaikan Data (Berdasarkan Filter)")
            col1_recap, col2_recap, col3_recap = st.columns(3)
            col1_recap.metric("Total Data Problem (`after=9999`)", f"{total_problem:,}")
            col2_recap.metric("Data Diselamatkan (via `after_45`)", f"{total_salvageable:,}", f"{percentage:.2f}% dari total problem")
            col3_recap.metric("Data Belum Terselamatkan", f"{total_unsalvageable:,}")

            ### REVISI: Blok ini diubah total untuk menampilkan tabel sesuai permintaan baru ###
            st.markdown("---")
            st.subheader("Detail Data Problem dan Aksi Perbaikan")
            st.markdown("Tabel ini menampilkan semua data yang bermasalah (`after = 9999`) dan hasil dari pengecekan nilai alternatif.")

            # Buat salinan untuk menghindari SettingWithCopyWarning
            df_display = df_problem.copy()

            # 1. Tambahkan kolom 'Nilai Setelah Aksi Alternatif 1'
            # Jika flag=1, isi dengan nilai after_45, selain itu isi dengan "-"
            df_display['Nilai Setelah Aksi Alternatif 1'] = np.where(
                df_display['flag'] == 1, 
                df_display['after_45'], 
                '-'
            )

            # 2. Tambahkan kolom 'Nilai Setelah Aksi Alternatif 2'
            # Jika flag=2, isi dengan nilai after_alt_2, selain itu isi dengan "-"
            df_display['Nilai Setelah Aksi Alternatif 2'] = np.where(
                df_display['flag'] == 2, 
                df_display['after_alt_2'], 
                '-'
            )

            # 3. Pilih dan ganti nama kolom untuk ditampilkan
            df_display_final = df_display[[
                'wmo_id', 'parameter', 'timestamp', 'before', 'after_45',
                'Nilai Setelah Aksi Alternatif 1', 'Nilai Setelah Aksi Alternatif 2', 'flag'
            ]].rename(columns={
                'before': 'RAW_ME48',
                'after_45': 'RAW_ME45'
            })
            
            # Tampilkan dataframe yang sudah rapi
            st.dataframe(df_display_final, use_container_width=True)

if 'data' not in st.session_state and 'data_phase2' not in st.session_state:
    st.info("Selamat datang! Silakan pilih folder log dan klik tombol analisis di sidebar untuk memulai.")
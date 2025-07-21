import streamlit as st
import pandas as pd
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

# --- UI STREAMLIT ---

st.title("🛰️ Dashboard Analisis Log")
st.markdown("Analisis semua file log dari dalam satu folder secara otomatis.")

# 1. Input Folder Path
st.header("1. Konfigurasi Folder Analisis")
folder_path = st.text_input("Masukkan path ke folder log Anda:", "pengecekan")

if st.button("🚀 Mulai Analisis Semua File"):
    if not os.path.isdir(folder_path):
        st.error(f"Error: Folder '{folder_path}' tidak ditemukan.")
    else:
        with st.spinner(f"Mencari dan menganalisis file di '{folder_path}'..."):
            df_combined = load_data_from_folder(folder_path)
            if df_combined.empty:
                st.error(f"Tidak ada file log yang valid (*_log.txt) ditemukan di folder '{folder_path}'.")
            else:
                st.session_state['data'] = df_combined
                st.success(f"Analisis selesai! Menemukan {len(st.session_state['data'])} temuan dari {st.session_state['data']['wmo_id'].nunique()} stasiun.")

# Tampilkan sisa dashboard jika data ada
if 'data' in st.session_state:
    df = st.session_state['data']

    # --- SIDEBAR UNTUK FILTER ---
    st.sidebar.header("Filter Tampilan")
    all_wmo_ids = sorted(df['wmo_id'].unique().tolist())
    selected_wmo_ids = st.sidebar.multiselect("Pilih Stasiun (WMO ID):", options=all_wmo_ids, default=all_wmo_ids)
    
    all_variables = sorted(df['variabel'].unique().tolist())
    selected_variables = st.sidebar.multiselect("Pilih Variabel:", options=all_variables, default=all_variables)

    min_date = df['timestamp'].min().date()
    max_date = df['timestamp'].max().date()
    date_range = st.sidebar.date_input("Pilih Rentang Tanggal:", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    start_date, end_date = date_range[0], date_range[-1]

    # Terapkan filter
    df_filtered = df[
        (df['wmo_id'].isin(selected_wmo_ids)) &
        (df['variabel'].isin(selected_variables)) &
        (df['timestamp'].dt.date >= start_date) &
        (df['timestamp'].dt.date <= end_date)
    ]
    st.info(f"Menampilkan **{len(df_filtered)}** dari total **{len(df)}** temuan berdasarkan filter Anda.")
    st.markdown("---")

    # --- TAMPILAN UTAMA ---

    st.header("2. Ringkasan & Statistik")
    col1, col2, col3 = st.columns([1,1,2])
    with col1:
        st.metric("Total Temuan", f"{len(df_filtered):,}")
        st.metric("Stasiun Dianalisis", f"{df_filtered['wmo_id'].nunique():,}")
        
    with col2:
        st.metric("Variabel Bermasalah", f"{df_filtered['variabel'].nunique():,}")
    
    with col3:
        st.subheader("Tabel Parameter Bermasalah")
        param_counts = df_filtered['variabel'].value_counts().reset_index()
        param_counts.columns = ['Parameter', 'Jumlah Temuan']
        st.dataframe(param_counts, height=180) # Tambahkan tinggi agar tabel lebih rapi
    
    st.markdown("---")

    st.header("3. Visualisasi Analitis")

    tab1, tab2, tab3 = st.tabs(["📊 Distribusi Umum", "📈 Tren Waktu (Bulanan)", "📉 Tren Tahunan per Parameter"])

    with tab1:
        st.subheader("Distribusi Temuan per Variabel")
        # Kondisi untuk menampilkan pesan jika tidak ada data
        if not df_filtered.empty:
            var_counts = df_filtered['variabel'].value_counts().reset_index()
            var_counts.columns = ['variabel', 'jumlah']
            chart_bar_var = alt.Chart(var_counts).mark_bar().encode(
                x=alt.X('jumlah:Q', title='Jumlah Temuan'),
                y=alt.Y('variabel:N', title='Nama Variabel', sort='-x')
            ).interactive()
            st.altair_chart(chart_bar_var, use_container_width=True)
        else:
            st.warning("Tidak ada data untuk ditampilkan berdasarkan filter saat ini.")

        st.subheader("Distribusi Temuan per Stasiun (WMO ID)")
        if not df_filtered.empty:
            wmo_counts = df_filtered['wmo_id'].value_counts().reset_index()
            wmo_counts.columns = ['wmo_id', 'jumlah']
            chart_bar_wmo = alt.Chart(wmo_counts).mark_bar(color='orange').encode(
                x=alt.X('jumlah:Q', title='Jumlah Temuan'),
                y=alt.Y('wmo_id:N', title='WMO ID', sort='-x')
            ).interactive()
            st.altair_chart(chart_bar_wmo, use_container_width=True)
        else:
            st.warning("Tidak ada data untuk ditampilkan berdasarkan filter saat ini.")

    with tab2:
        st.subheader("Tren Temuan Berdasarkan Waktu (Bulanan)")
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

    with tab3:
        st.subheader("Analisis Tren Tahunan untuk Parameter Spesifik")
        st.markdown("Gunakan ini untuk menyelidiki kapan sebuah parameter mulai banyak bermasalah.")
        
        # Filter unik yang tersedia di data yang sudah terfilter
        available_vars = sorted(df_filtered['variabel'].unique().tolist())
        
        if available_vars:
            # Dropdown untuk memilih satu parameter
            param_to_analyze = st.selectbox(
                "Pilih satu parameter untuk dianalisis:",
                options=available_vars
            )

            # Filter data lebih lanjut untuk parameter yang dipilih
            df_param_trend = df_filtered[df_filtered['variabel'] == param_to_analyze]

            # Agregasi data per tahun dan per wmo_id
            trend_data = df_param_trend.groupby([df_param_trend['timestamp'].dt.year.rename('tahun'), 'wmo_id']).size().reset_index(name='jumlah_temuan')
            
            # Buat grafik tren tahunan
            chart_trend_yearly = alt.Chart(trend_data).mark_line(point=True).encode(
                x=alt.X('tahun:O', title='Tahun', axis=alt.Axis(labelAngle=0)), # 'O' untuk Ordinal/kategorikal
                y=alt.Y('jumlah_temuan:Q', title=f'Jumlah Temuan ({param_to_analyze})'),
                color=alt.Color('wmo_id:N', title='WMO ID'),
                tooltip=['tahun', 'wmo_id', 'jumlah_temuan']
            ).interactive()
            st.altair_chart(chart_trend_yearly, use_container_width=True)
        else:
            st.warning("Tidak ada variabel yang tersedia untuk dianalisis berdasarkan filter Anda.")

    st.markdown("---")

    st.header("4. Detail Data Mentah")
    st.dataframe(df_filtered)
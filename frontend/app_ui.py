import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="HR Talent Analytics - Lion Parcel", layout="wide")
st.title("🦁 HR Intelligent CV Dashboard - Lion Parcel")

# URL Backend API (Hardcoded)
API_BASE_URL = "http://localhost:8000/api"

# 1. Inisialisasi Session State
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'df' not in st.session_state:
    st.session_state.df = None
if 'raw_responses' not in st.session_state:
    st.session_state.raw_responses = {}

with st.sidebar:
    st.header("⚙️ Kriteria Penilaian HR")
    
    job_role = st.text_input("Posisi Pekerjaan:", placeholder="Masukkan posisi pekerjaan")
    

    job_description = st.text_area(
        "Job Requirement & Description:",
        height=200, 
        placeholder="Masukkan kualifikasi, skill wajib, dan deskripsi pekerjaan"
    )
    
    st.divider()
    uploaded_files = st.file_uploader(
        "Upload CV Pelamar (PDF/DOCX)", 
        type=["pdf", "docx"], 
        accept_multiple_files=True
    )

# 2. Proses Analisis
if st.button("Jalankan Analisis Massal 🚀") and uploaded_files:
    if not job_description.strip():
        st.error("⚠️ Mohon isi Job Requirement & Description terlebih dahulu untuk acuan penilaian HR!")
    else:
        results = []
        raw_responses = {}
        
        with st.status("Menganalisis dokumen terhadap Job Requirement...", expanded=True) as status:
            for file in uploaded_files:
                st.write(f"Menganalisis {file.name}...")
                
                files = {"file": (file.name, file.getvalue(), file.type)}
                data = {
                    "job_role": job_role,
                    "job_description": job_description
                }
                
                try:
                    response = requests.post(f"{API_BASE_URL}/analyze", files=files, data=data)
                    
                    if response.status_code == 200:
                        res_data = response.json()
                        raw_responses[file.name] = res_data
                        
                        candidate = res_data.get("candidate", {})
                        breakdown = res_data.get("score_breakdown", {})
                        domain = res_data.get("domain", {})
                        
                        name = candidate.get("name") or file.name
                        phone = candidate.get("phone") or "N/A"
                        email = candidate.get("email") or "N/A"
                        
                        if phone != "N/A":
                            clean_phone = ''.join(filter(str.isdigit, phone))
                            wa_link = f"https://wa.me/{clean_phone}"
                        else:
                            wa_link = None
                            
                        # MENGHITUNG BOBOT PERSENTASE AKTUAL DARI MASING-MASING PARAMETER
                        w_keyword = round(breakdown.get("keyword_relevance", 0) * 0.30)
                        w_skills = round(breakdown.get("skill_relevance", 0) * 0.25)
                        w_section = round(breakdown.get("section_completeness", 0) * 0.15)
                        w_experience = round(breakdown.get("experience_clarity", 0) * 0.15)
                        w_format = round(breakdown.get("formatting_score", 0) * 0.10)
                        w_project = round(breakdown.get("project_impact", 0) * 0.05)
                        
                        results.append({
                            "Nama Pelamar": name,
                            "Skor Match (%)": int(res_data.get("ats_score", 0)),
                            "Domain": domain.get("primary", "Unknown"),
                            "Keyword (30%)": w_keyword,
                            "Skills (25%)": w_skills,
                            "Experience (15%)": w_experience,
                            "Section (15%)": w_section,
                            "Format (10%)": w_format,
                            "Project (5%)": w_project,
                            "WhatsApp": wa_link if wa_link else phone,
                            "Email": email
                        })
                    else:
                        st.error(f"Gagal menganalisis {file.name}. Error: {response.text}")
                        
                except Exception as e:
                    st.error(f"Error saat menghubungi backend untuk {file.name}: {str(e)}")
                    
            status.update(label="Analisis Selesai!", state="complete", expanded=False)

        # 3. Simpan hasil ke Session State
        if results:
            st.session_state.df = pd.DataFrame(results).sort_values(by="Skor Match (%)", ascending=False)
            st.session_state.raw_responses = raw_responses
            st.session_state.analysis_done = True

# 4. Tampilkan Dashboard jika analisis sudah selesai
if st.session_state.analysis_done and st.session_state.df is not None:
    df = st.session_state.df
    raw_responses = st.session_state.raw_responses
    
    # --- SECTION 1: ANALYTICS DASHBOARD ---
    st.divider()
    st.subheader("📊 Analytics Dashboard")
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Total Pelamar", len(df))
    col_m2.metric("Rata-rata Skor Match", f"{df['Skor Match (%)'].mean():.1f}%")
    col_m3.metric("Lolos Kualifikasi (>70%)", len(df[df['Skor Match (%)'] >= 70]))

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.write("**Top Ranking Kandidat (Berdasarkan JD)**")
        st.bar_chart(df.head(10).set_index("Nama Pelamar")["Skor Match (%)"])
    with col_c2:
        st.write("**Rata-rata Kontribusi Parameter**")
        avg_params = df[["Keyword (30%)", "Skills (25%)", "Experience (15%)", "Section (15%)", "Format (10%)", "Project (5%)"]].mean()
        st.bar_chart(avg_params)

    # --- SECTION 2: TABEL RANKING LENGKAP ---
    st.divider()
    st.subheader("📝 Daftar Ranking & Rincian Penilaian Kandidat")
    
    st.data_editor(
        df,
        column_config={
            "Skor Match (%)": st.column_config.ProgressColumn(
                "Skor Total", 
                help="Total Skor Kecocokan (Maksimal 100%)",
                min_value=0, max_value=100, format="%d%%"
            ),
            "Keyword (30%)": st.column_config.NumberColumn("Keyword (30%)", format="%d%%"),
            "Skills (25%)": st.column_config.NumberColumn("Skills (25%)", format="%d%%"),
            "Experience (15%)": st.column_config.NumberColumn("Experience (15%)", format="%d%%"),
            "Section (15%)": st.column_config.NumberColumn("Section (15%)", format="%d%%"),
            "Format (10%)": st.column_config.NumberColumn("Format (10%)", format="%d%%"),
            "Project (5%)": st.column_config.NumberColumn("Project (5%)", format="%d%%"),
            "Domain": st.column_config.TextColumn("Domain Klasifikasi"),
            "WhatsApp": st.column_config.LinkColumn("Hubungi", display_text="Chat 📲"),
            "Email": st.column_config.TextColumn("Email Pelamar")
        },
        use_container_width=True, 
        hide_index=True, 
        disabled=True
    )

    # --- SECTION 3: EXPORT & REPORT ---
    st.divider()
    st.subheader("📥 Export & Generate Report")
    
    col_e1, col_e2 = st.columns(2)
    
    with col_e1:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button(
            "Download Laporan Rekap (Excel) 📥", 
            data=buffer.getvalue(), 
            file_name="Laporan_HR_LionParcel.xlsx"
        )
        
    with col_e2:
        st.write("**Download Report Detail (PDF) per Kandidat:**")
        for file_name, res_data in raw_responses.items():
            try:
                pdf_resp = requests.post(f"{API_BASE_URL}/download-report", json=res_data)
                if pdf_resp.status_code == 200:
                    st.download_button(
                        label=f"📄 PDF Report - {file_name}",
                        data=pdf_resp.content,
                        file_name=f"ATS_Report_{file_name}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{file_name}"
                    )
            except Exception as e:
                st.error(f"Gagal generate PDF untuk {file_name}")
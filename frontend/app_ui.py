import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="ATS Resume Analyzer - Lion Parcel", layout="wide")
st.title("🦁 ATS Resume Analyzer - Lion Parcel")

API_BASE_URL = "http://localhost:8000/api"

if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'df' not in st.session_state:
    st.session_state.df = None
if 'raw_responses' not in st.session_state:
    st.session_state.raw_responses = {}

with st.sidebar:
    st.header("⚙️ Kriteria Penilaian HR")
    
    job_role = st.text_input("Posisi Pekerjaan:", placeholder="Masukkan posisi pekerjaan")
    job_description = st.text_area("Job Requirement & Description:", height=150, placeholder="Masukkan kualifikasi dan deskripsi pekerjaan")
    
    st.subheader("🎯 Personalisasi Penilaian")
    target_domain = st.selectbox("Target Domain (Opsional):", ["Auto-Detect", "Software / IT", "Data / AI", "Marketing", "Finance", "General"])
    
    COMMON_KEYWORDS = ["B2B", "B2C", "Leadership", "Agile", "Scrum", "Problem Solving", "Analytics"]
    COMMON_SKILLS = ["Python", "SQL", "Excel", "Java", "Tableau", "Machine Learning", "Digital Marketing"]
    
    custom_keywords = st.multiselect(
        "Keyword Khusus:",
        options=COMMON_KEYWORDS,
        default=["Agile", "B2B"],
        max_selections=20,
        accept_new_options=True,
        help="Pilih dari daftar atau ketik keyword baru lalu tekan Enter"
    )
    
    custom_skills = st.multiselect(
        "Skill Wajib:",
        options=COMMON_SKILLS,
        default=["Python", "SQL"],
        max_selections=20,
        accept_new_options=True,
        help="Pilih dari daftar atau ketik skill baru lalu tekan Enter"
    )
    
    st.divider()
    
    # --- KONFIGURASI AI (Tanpa API Key Input) ---
    st.header("🤖 Konfigurasi AI Review")
    ai_temperature = st.slider("Temperature (Objektif ↔ Kreatif):", min_value=0.0, max_value=1.0, value=0.7, step=0.1)
    ai_max_tokens = st.slider("Max Tokens (Panjang Ulasan):", min_value=200, max_value=1500, value=800, step=100)
    # --------------------------------------------
    
    st.divider()
    uploaded_files = st.file_uploader("Upload CV Pelamar (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

if st.button("Jalankan Analisis Massal 🚀") and uploaded_files:
    if not job_description.strip() and not custom_keywords:
        st.error("⚠️ Mohon isi minimal Job Description atau Keyword Khusus!")
    else:
        results = []
        raw_responses = {}
        
        with st.status("Menganalisis dokumen...", expanded=True) as status:
            for idx, file in enumerate(uploaded_files):
                st.write(f"Menganalisis {file.name}...")
                
                unique_file_id = f"{idx}_{file.name}"
                
                files = {"file": (file.name, file.getvalue(), file.type)}
                data = {
                    "job_role": job_role,
                    "job_description": job_description,
                    "target_domain": target_domain,
                    "custom_keywords": ",".join(custom_keywords),
                    "custom_skills": ",".join(custom_skills)
                }
                
                try:
                    response = requests.post(f"{API_BASE_URL}/analyze", files=files, data=data)
                    if response.status_code == 200:
                        res_data = response.json()
                        raw_responses[unique_file_id] = res_data
                        
                        candidate = res_data.get("candidate", {}) or {}
                        breakdown = res_data.get("score_breakdown", {}) or {}
                        domain = res_data.get("domain", {}) or {}
                        
                        name = candidate.get("name") or f"Kandidat {idx+1} ({file.name})"
                        phone = candidate.get("phone") or "N/A"
                        email = candidate.get("email") or "N/A"
                        
                        # --- LOGIKA WHATSAPP LINK ---
                        if phone != "N/A":
                            clean_phone = ''.join(filter(str.isdigit, phone))
                            if clean_phone.startswith('0'):
                                clean_phone = '62' + clean_phone[1:]
                            wa_link = f"https://wa.me/{clean_phone}" if clean_phone else "N/A"
                        else:
                            wa_link = "N/A"
                        # ----------------------------
                            
                        results.append({
                            "Nama Pelamar": name,
                            "Skor Match (%)": int(res_data.get("ats_score", 0)),
                            "Domain": domain.get("primary", "Unknown"),
                            "Keyword (30%)": round(breakdown.get("keyword_relevance", 0) * 0.30),
                            "Skills (25%)": round(breakdown.get("skill_relevance", 0) * 0.25),
                            "Experience (15%)": round(breakdown.get("experience_clarity", 0) * 0.15),
                            "Section (15%)": round(breakdown.get("section_completeness", 0) * 0.15),
                            "Format (10%)": round(breakdown.get("formatting_score", 0) * 0.10),
                            "Project (5%)": round(breakdown.get("project_impact", 0) * 0.05),
                            "WhatsApp": wa_link,
                            "Email": email
                        })
                    else:
                        st.error(f"Gagal menganalisis {file.name}. Error: {response.text}")
                except Exception as e:
                    st.error(f"Error untuk {file.name}: {str(e)}")
                    
            status.update(label="Analisis Selesai!", state="complete", expanded=False)

        if results:
            st.session_state.df = pd.DataFrame(results).sort_values(by="Skor Match (%)", ascending=False)
            st.session_state.raw_responses = raw_responses
            st.session_state.analysis_done = True

if st.session_state.analysis_done and st.session_state.df is not None:
    df = st.session_state.df
    
    st.divider()
    st.subheader("📊 Analytics Dashboard")
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Total Pelamar", len(df))
    col_m2.metric("Rata-rata Skor Match", f"{df['Skor Match (%)'].mean():.1f}%")
    col_m3.metric("Lolos Kualifikasi (>70%)", len(df[df['Skor Match (%)'] >= 70]))

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.write("**Top Ranking Kandidat**")
        st.bar_chart(df.head(10).set_index("Nama Pelamar")["Skor Match (%)"])
    with col_c2:
        st.write("**Rata-rata Kontribusi Parameter**")
        avg_params = df[["Keyword (30%)", "Skills (25%)", "Experience (15%)", "Section (15%)", "Format (10%)", "Project (5%)"]].mean()
        st.bar_chart(avg_params)

    st.divider()
    st.subheader("📝 Daftar Ranking & Rincian Penilaian")
    
    st.data_editor(
        df,
        column_config={
            "Skor Match (%)": st.column_config.ProgressColumn("Skor Total", min_value=0, max_value=100, format="%d%%"),
            "Keyword (30%)": st.column_config.NumberColumn("Keyword (30%)", format="%d%%"),
            "Skills (25%)": st.column_config.NumberColumn("Skills (25%)", format="%d%%"),
            "Experience (15%)": st.column_config.NumberColumn("Experience (15%)", format="%d%%"),
            "Section (15%)": st.column_config.NumberColumn("Section (15%)", format="%d%%"),
            "Format (10%)": st.column_config.NumberColumn("Format (10%)", format="%d%%"),
            "Project (5%)": st.column_config.NumberColumn("Project (5%)", format="%d%%"),
            "WhatsApp": st.column_config.LinkColumn("Hubungi", display_text="Chat 📲"),
        },
        use_container_width=True, 
        hide_index=True, 
        disabled=True
    )

    st.divider()
    st.subheader("📥 Tindakan Lanjutan: Gen-AI & Report Export")
    col_e1, col_e2 = st.columns([1, 2])
    
    with col_e1:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("Download Laporan Rekap (Excel) 📥", data=buffer.getvalue(), file_name="Laporan_HR_LionParcel.xlsx")
        
    with col_e2:
        st.write("**Detail Analisis Individual:**")
        for unique_file_id, res_data in st.session_state.raw_responses.items():
            display_name = unique_file_id.split("_", 1)[1]
            candidate_name = res_data.get("candidate", {}).get("name") or display_name
            
            with st.expander(f"👤 {candidate_name} - Skor: {res_data.get('ats_score')}%"):
                col_btn, col_dl, col_ai = st.columns([1, 1, 1])
                pdf_state_key = f"pdf_bytes_{unique_file_id}"
                ai_review_key = f"ai_review_{unique_file_id}"
                
                with col_btn:
                    if st.button(f"⚙️ Generate PDF", key=f"btn_{unique_file_id}"):
                        with st.spinner("Membuat PDF..."):
                            try:
                                pdf_resp = requests.post(f"{API_BASE_URL}/download-report", json=res_data)
                                if pdf_resp.status_code == 200:
                                    st.session_state[pdf_state_key] = pdf_resp.content
                                else:
                                    st.error("Gagal men-generate PDF")
                            except Exception as e:
                                st.error("Gagal menghubungi server")
                
                with col_dl:
                    if pdf_state_key in st.session_state:
                        st.download_button(
                            label=f"📥 Download PDF",
                            data=st.session_state[pdf_state_key],
                            file_name=f"ATS_Report_{candidate_name}.pdf",
                            mime="application/pdf",
                            key=f"dl_{unique_file_id}"
                        )
                
                # --- TOMBOL GENERATIVE AI ---
                with col_ai:
                    if st.button(f"✨ Minta Ulasan AI", key=f"ai_btn_{unique_file_id}"):
                        with st.spinner("AI sedang membaca CV..."):
                            ai_payload = {
                                "cv_text": res_data.get("raw_text", ""), 
                                "job_description": job_description,
                                "temperature": ai_temperature,
                                "max_tokens": ai_max_tokens
                            }
                            try:
                                ai_resp = requests.post(f"{API_BASE_URL}/ai-review", json=ai_payload)
                                if ai_resp.status_code == 200:
                                    result = ai_resp.json()
                                    if result.get("success"):
                                        st.session_state[ai_review_key] = result.get("review")
                                    else:
                                        st.error(result.get("error"))
                                else:
                                    st.error("Gagal menghubungi server AI")
                            except Exception as e:
                                st.error(f"Error AI: {str(e)}")
                                    
                # Menampilkan ulasan jika sudah dibuat
                if ai_review_key in st.session_state:
                    st.markdown("---")
                    st.markdown("### ✨ Kesimpulan Generative AI")
                    st.info(st.session_state[ai_review_key])
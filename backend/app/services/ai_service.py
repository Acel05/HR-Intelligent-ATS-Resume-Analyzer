"""
Generative AI Service - Provides qualitative contextual analysis of resumes
"""
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Muat variabel environment dari file .env
load_dotenv()

class AIService:
    def generate_review(
        self, 
        cv_text: str, 
        job_description: str, 
        temperature: float = 0.7, 
        max_tokens: int = 800
    ) -> str:
        try:
            # Mengambil API Key dari file .env
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise Exception("GEMINI_API_KEY belum di-set di file .env backend.")

            # Konfigurasi API
            genai.configure(api_key=api_key)
            
            # Setup parameter AI
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Menggunakan model Gemini 1.5 Flash (Sangat cepat dan andal untuk teks)
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                generation_config=generation_config
            )
            
            # Prompt Engineering
            prompt = f"""
            Anda adalah seorang Senior HR / Talent Acquisition Expert profesional.
            Tugas Anda adalah melakukan ulasan kualitatif terhadap CV pelamar berdasarkan Job Description (JD) yang diberikan.
            
            Job Description:
            {job_description if job_description.strip() else "Tidak ada JD spesifik, evaluasi sebagai profil profesional umum."}
            
            Teks CV Pelamar:
            {cv_text}
            
            Berikan analisis Anda dalam format Markdown dengan struktur berikut:
            1. **Kelebihan Utama:** (Sebutkan 2-3 kekuatan terbesar kandidat terkait posisi)
            2. **Gap / Kekurangan:** (Sebutkan apa yang kurang atau tidak sesuai dengan ekspektasi JD)
            3. **Kesimpulan & Rekomendasi:** (Apakah kandidat ini direkomendasikan untuk lanjut ke tahap interview? Mengapa?)
            
            Gunakan Bahasa Indonesia yang profesional, ringkas, dan objektif.
            """
            
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            raise Exception(f"Gagal menghasilkan ulasan AI: {str(e)}")

ai_service = AIService()
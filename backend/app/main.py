"""
ATS Resume Analyzer - FastAPI Backend
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import os
import tempfile
from typing import Optional

from app.services.resume_parser import ResumeParser
from app.services.ats_scorer import ATSScorer
from app.services.skill_extractor import SkillExtractor
from app.services.domain_classifier import DomainClassifier
from app.services.report_generator import ReportGenerator
from app.models.schemas import AnalysisResponse

app = FastAPI(
    title="ATS Resume Analyzer",
    description="AI-powered resume analysis and ATS scoring",
    version="1.0.0"
)

# CORS configuration - allow all origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
resume_parser = ResumeParser()
ats_scorer = ATSScorer()
skill_extractor = SkillExtractor()
domain_classifier = DomainClassifier()
report_generator = ReportGenerator()

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@app.get("/")
async def root():
    return {"message": "ATS Resume Analyzer API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_resume(
    file: UploadFile = File(...),
    job_role: Optional[str] = Form(None),
    job_description: Optional[str] = Form(None)
):
    """
    Analyze uploaded resume and return comprehensive ATS analysis
    """
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds 5MB limit"
        )
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Parse resume
        parsed_data = resume_parser.parse(tmp_path, file_ext)
        
        # Get OCR metadata
        parsing_method = parsed_data.get("parsing_method", "standard")
        ocr_confidence = parsed_data.get("ocr_confidence")
        
        # Extract skills
        skills_data = skill_extractor.extract(parsed_data["raw_text"])
        
        # Classify domain (DIBIARKAN ASLI DARI CV, TIDAK DI-OVERRIDE)
        domain_data = domain_classifier.classify(parsed_data["raw_text"], skills_data)
        
        # Calculate ATS Score (Penilaian tetap menggunakan JD dan Role HR)
        ats_analysis = ats_scorer.calculate_score(
            parsed_data=parsed_data, 
            skills=skills_data, 
            domain=domain_data,
            job_role=job_role,
            job_description=job_description,
            parsing_method=parsing_method,
            ocr_confidence=ocr_confidence
        )
        
        os.unlink(tmp_path)
        
        response = AnalysisResponse(
            success=True,
            candidate=parsed_data["candidate"],
            ats_score=ats_analysis["score"],
            score_breakdown=ats_analysis["breakdown"],
            score_category=ats_analysis["category"],
            domain=domain_data,
            skills=skills_data,
            projects=parsed_data["projects"],
            experience=parsed_data["experience"],
            education=parsed_data["education"],
            issues=ats_analysis["issues"],
            suggestions=ats_analysis["suggestions"],
            keywords_analysis=ats_analysis["keywords_analysis"],
            parsing_method=parsing_method,
            ocr_confidence=ocr_confidence
        )
        
        return response
        
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/download-report")
async def download_report(request: Request):
    """
    Generate and download PDF report from analysis data
    """
    try:
        analysis_data = await request.json()
        pdf_bytes = report_generator.generate_pdf(analysis_data)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=ats-resume-report.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    job_description: Optional[str] = Form(None),
    custom_keywords: Optional[str] = Form(None),
    custom_skills: Optional[str] = Form(None),
    target_domain: Optional[str] = Form(None)
):
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
    
    content = await file.read()
    await file.seek(0)
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        parsed_data = resume_parser.parse(tmp_path, file_ext)
        parsing_method = parsed_data.get("parsing_method", "standard")
        ocr_confidence = parsed_data.get("ocr_confidence")
        
        skills_data = skill_extractor.extract(parsed_data["raw_text"])
        
        domain_data = domain_classifier.classify(parsed_data["raw_text"], skills_data)
        if target_domain and target_domain != "Auto-Detect":
            domain_data.primary = target_domain
            
        ats_analysis = ats_scorer.calculate_score(
            parsed_data=parsed_data, 
            skills=skills_data, 
            domain=domain_data,
            job_role=job_role,
            job_description=job_description,
            custom_keywords=custom_keywords,
            custom_skills=custom_skills,
            parsing_method=parsing_method,
            ocr_confidence=ocr_confidence
        )
        
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

@app.post("/api/download-report")
async def download_report(request: Request):
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
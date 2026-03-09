"""
Resume Parser Service - Extracts text and structured data from PDF/DOCX
"""
import re
from pypdf import PdfReader
from docx import Document
from typing import Dict, List, Any, Optional
from app.models.schemas import CandidateInfo, Project, Experience, ExperienceSummary, Education
from app.services.ocr_service import ocr_service

class ResumeParser:
    PARSING_STANDARD = "standard"
    PARSING_OCR = "ocr"
    PARSING_OCR_UNAVAILABLE = "ocr_unavailable"
    
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    PHONE_PATTERN = r'(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}|\+\d{1,3}[-.\s]?\d{6,14}'
    LINKEDIN_PATTERN = r'(?:linkedin\.com/in/|linkedin:?\s*)([a-zA-Z0-9-]+)'
    GITHUB_PATTERN = r'(?:github\.com/|github:?\s*)([a-zA-Z0-9-]+)'
    
    SECTION_HEADERS = {
        'experience': ['experience', 'work experience', 'employment', 'pengalaman', 'riwayat pekerjaan', 'internship'],
        'education': ['education', 'academic', 'pendidikan', 'riwayat pendidikan', 'academic background'],
        'skills': ['skills', 'technical skills', 'keahlian', 'keterampilan', 'kemampuan', 'hard skill', 'soft skill'],
        'projects': ['projects', 'personal projects', 'proyek', 'portofolio', 'project', 'karya'],
        'certifications': ['certifications', 'certificates', 'sertifikasi', 'lisensi', 'penghargaan', 'sertifikat'],
        'summary': ['summary', 'profile', 'objective', 'profil', 'tentang saya', 'ringkasan']
    }
    
    ACTION_VERBS = [
        'achieved', 'built', 'created', 'developed', 'led', 'managed', 'optimized',
        'mencapai', 'membangun', 'membuat', 'mengembangkan', 'memimpin', 'mengelola', 'mengoptimalkan'
    ]
    
    MONTHS_PATTERN = r'(?:Jan(?:uari)?|Feb(?:ruari)?|Mar(?:et)?|Apr(?:il)?|Mei|May|Jun(?:i)?|Jul(?:i)?|Agt|Agu(?:stus)?|Aug(?:ust)?|Sep(?:tember)?|Okt(?:ober)?|Oct(?:ober)?|Nov(?:ember)?|Des(?:ember)?|Dec(?:ember)?)'
    SEPARATOR_PATTERN = r'\s*(?:[-–—to]+|s/?d\.?|sampai(?: dengan)?|hingga)\s*'
    PRESENT_PATTERN = r'(?:Present|Current|Saat ini|Sekarang|Kini|Hingga kini)'
    
    def parse(self, file_path: str, file_ext: str) -> Dict[str, Any]:
        parsing_method = self.PARSING_STANDARD
        ocr_confidence = None
        has_tables = False
        has_images = False
        
        if file_ext == '.pdf':
            raw_text = self._extract_pdf_text(file_path)
            has_tables = self._check_pdf_tables(file_path)
            has_images = self._check_pdf_images(file_path)
            raw_text, parsing_method, ocr_confidence = self._apply_ocr_if_needed(file_path, raw_text)
        else:
            raw_text = self._extract_docx_text(file_path)
            has_tables = self._check_docx_tables(file_path)
            has_images = self._check_docx_images(file_path)
        
        sections = self._identify_sections(raw_text)
        
        candidate = self._extract_candidate_info(raw_text)
        experience = self._extract_experience(raw_text, sections.get('experience', ''))
        projects = self._extract_projects(raw_text, sections.get('projects', ''))
        education = self._extract_education(raw_text, sections.get('education', ''))
        
        return {
            "raw_text": raw_text,
            "candidate": candidate,
            "experience": experience,
            "projects": projects,
            "education": education,
            "sections": sections,
            "formatting": {
                "has_tables": has_tables,
                "has_images": has_images,
                "word_count": len(raw_text.split()),
                "line_count": len(raw_text.split('\n'))
            },
            "parsing_method": parsing_method,
            "ocr_confidence": ocr_confidence
        }
    
    def _apply_ocr_if_needed(self, file_path: str, standard_text: str) -> tuple:
        if not ocr_service.is_available(): return standard_text, self.PARSING_STANDARD, None
        email_match = re.search(self.EMAIL_PATTERN, standard_text)
        phone_match = re.search(self.PHONE_PATTERN, standard_text)
        if not ocr_service.needs_ocr(standard_text, email=email_match.group() if email_match else None, phone=phone_match.group() if phone_match else None):
            return standard_text, self.PARSING_STANDARD, None
        if ocr_service.should_skip_ocr(file_path): return standard_text, self.PARSING_OCR_UNAVAILABLE, None
        
        ocr_text, parsing_method, confidence = ocr_service.extract_text_with_ocr(file_path)
        if ocr_text and parsing_method == self.PARSING_OCR: return ocr_text, parsing_method, confidence
        return standard_text, parsing_method, confidence
    
    def _extract_pdf_text(self, file_path: str) -> str:
        text = ""
        try:
            for page in PdfReader(file_path).pages: text += (page.extract_text() or "") + "\n"
        except: pass
        return text
    
    def _extract_docx_text(self, file_path: str) -> str:
        text = ""
        try:
            for para in Document(file_path).paragraphs: text += para.text + "\n"
        except: pass
        return text

    def _check_pdf_tables(self, file_path: str) -> bool:
        try:
            for page in PdfReader(file_path).pages:
                text = page.extract_text() or ""
                lines = text.split('\n')
                if sum(1 for line in lines if line.count('\t') >= 2 or line.count('|') >= 2) > 3: return True
        except: pass
        return False
    
    def _check_pdf_images(self, file_path: str) -> bool:
        try:
            for page in PdfReader(file_path).pages:
                if '/XObject' in page.get('/Resources', {}):
                    xobject = page['/Resources']['/XObject']
                    if xobject:
                        for obj in xobject:
                            if xobject[obj]['/Subtype'] == '/Image': return True
        except: pass
        return False
    
    def _check_docx_tables(self, file_path: str) -> bool:
        try: return len(Document(file_path).tables) > 0
        except: return False
    
    def _check_docx_images(self, file_path: str) -> bool:
        try:
            for rel in Document(file_path).part.rels.values():
                if "image" in rel.reltype: return True
        except: pass
        return False
    
    def _identify_sections(self, text: str) -> Dict[str, str]:
        sections = {}
        lines = text.split('\n')
        current_section = None
        current_content = []
        for line in lines:
            line_lower = line.lower().strip()
            section_found = None
            for section_type, headers in self.SECTION_HEADERS.items():
                if any(line_lower == h or line_lower.startswith(h + ':') or line_lower.startswith(h + ' ') for h in headers):
                    section_found = section_type
                    break
            
            if section_found:
                if current_section: sections[current_section] = '\n'.join(current_content)
                current_section = section_found
                current_content = []
            elif current_section:
                current_content.append(line)
        if current_section: sections[current_section] = '\n'.join(current_content)
        return sections
    
    def _extract_candidate_info(self, text: str) -> CandidateInfo:
        lines = text.split('\n')[:15]
        name = None
        for line in lines:
            line = line.strip()
            if 2 < len(line) < 50 and '@' not in line and not re.search(self.PHONE_PATTERN, line):
                if not any(word in line.lower() for word in ['resume', 'cv', 'curriculum', 'profil']):
                    words = line.split()
                    if 1 <= len(words) <= 4 and all(w.replace('.', '').replace('-', '').isalpha() for w in words):
                        name = line
                        break
        
        email_match = re.search(self.EMAIL_PATTERN, text)
        phone_match = re.search(self.PHONE_PATTERN, text)
        linkedin_match = re.search(self.LINKEDIN_PATTERN, text, re.IGNORECASE)
        github_match = re.search(self.GITHUB_PATTERN, text, re.IGNORECASE)
        
        return CandidateInfo(
            name=name, 
            email=email_match.group() if email_match else None,
            phone=phone_match.group() if phone_match else None, 
            location=self._extract_location(text),
            linkedin=f"linkedin.com/in/{linkedin_match.group(1)}" if linkedin_match else None, 
            github=f"github.com/{github_match.group(1)}" if github_match else None
        )
    
    def _extract_location(self, text: str) -> Optional[str]:
        for pattern in [r'(?:Location|Address|Alamat|Domisili|Kota)[:\s]*([A-Za-z0-9\s,\.]+)', r'([A-Za-z]+,\s*[A-Z]{2})\s*\d{5}', r'([A-Za-z\s]+,\s*[A-Za-z\s]+,\s*(?:Indonesia))']:
            match = re.search(pattern, text[:600], re.IGNORECASE)
            if match and 3 < len(match.group(1).strip()) < 80: return match.group(1).strip()
        return None
    
    def _extract_experience(self, full_text: str, experience_section: str) -> ExperienceSummary:
        positions = []
        text_to_analyze = experience_section if experience_section else full_text
        entries = self._split_experience_entries(text_to_analyze)
        
        total_months = 0
        for entry in entries[:5]: 
            exp = self._parse_experience_entry(entry)
            if exp.company or exp.role:
                positions.append(exp)
                if exp.duration: total_months += self._estimate_duration_months(exp.duration)
        
        overall_quality = sum(p.bullet_quality for p in positions) // len(positions) if positions else 0
        return ExperienceSummary(total_years=round(total_months / 12, 1), total_months=total_months, positions=positions, overall_quality=overall_quality)
    
    def _split_experience_entries(self, text: str) -> List[str]:
        date_pattern = r'(' + self.MONTHS_PATTERN + r'\.?\s*\d{4}|\b\d{4}\b)'
        lines = text.split('\n')
        entries, current_entry = [], []
        for line in lines:
            if re.search(date_pattern, line, re.IGNORECASE) and current_entry:
                entries.append('\n'.join(current_entry))
                current_entry = []
            current_entry.append(line)
        if current_entry: entries.append('\n'.join(current_entry))
        return entries if entries else [text]
    
    def _parse_experience_entry(self, entry: str) -> Experience:
        lines = entry.strip().split('\n')
        company, role, duration = None, None, None
        
        for line in lines[:4]:
            line = line.strip()
            if not line: continue
            
            date_match = re.search(r'(' + self.MONTHS_PATTERN + r'\.?\s*\d{4}|\b\d{4}\b)' + self.SEPARATOR_PATTERN + r'(' + self.PRESENT_PATTERN + r'|' + self.MONTHS_PATTERN + r'\.?\s*\d{4}|\b\d{4}\b)', line, re.IGNORECASE)
            if date_match:
                duration = line
                continue
            
            role_keywords = ['engineer', 'developer', 'manager', 'analyst', 'staf', 'staff', 'magang', 'intern']
            if any(kw in line.lower() for kw in role_keywords) and not role: role = line
            elif not company and len(line) > 2: company = line
        
        bullets = [l for l in lines if l.strip().startswith(('•', '-', '*', '●'))]
        action_count = sum(1 for b in bullets if any(v in b.lower() for v in self.ACTION_VERBS))
        has_metrics = any(re.search(r'\d+%|\$\d+|Rp\d+', b.lower()) for b in bullets)
        
        bullet_quality = min(100, int((action_count / len(bullets)) * 70) + (30 if has_metrics else 0)) if bullets else 0
        
        return Experience(company=company, role=role, duration=duration, description='\n'.join(bullets[:5]) if bullets else None, bullet_quality=bullet_quality, has_metrics=has_metrics, action_verbs_count=action_count)
    
    def _estimate_duration_months(self, duration_str: str) -> int:
        if re.search(self.PRESENT_PATTERN, duration_str, re.IGNORECASE): return 12
        dates = re.findall(r'\b(\d{4})\b', duration_str)
        if len(dates) >= 2:
            try: return max(1, (int(dates[-1]) - int(dates[0])) * 12)
            except: pass
        return 6 
    
    def _extract_projects(self, full_text: str, projects_section: str) -> List[Project]:
        projects = []
        entries = self._split_project_entries(projects_section if projects_section else full_text)
        for entry in entries[:5]:
            project = self._parse_project_entry(entry)
            if project.title: projects.append(project)
        return projects
    
    def _split_project_entries(self, text: str) -> List[str]:
        lines = text.split('\n')
        entries, current_entry = [], []
        for line in lines:
            if line.strip() and not line.strip().startswith(('•', '-', '*')):
                if current_entry and len(current_entry) > 1:
                    entries.append('\n'.join(current_entry))
                    current_entry = []
            current_entry.append(line)
        if current_entry: entries.append('\n'.join(current_entry))
        return entries
    
    def _parse_project_entry(self, entry: str) -> Project:
        lines = entry.strip().split('\n')
        title, technologies, description = None, [], []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line: continue
            if i == 0 or not title: title = line.replace('•', '').replace('-', '').strip()
            else:
                tech_match = re.search(r'(?:Tech|Technologies|Stack|Tools)[:\s]+(.+)', line, re.IGNORECASE)
                if tech_match: technologies.extend([t.strip() for t in tech_match.group(1).split(',')])
                else: description.append(line)
        
        score = 50 + (20 if technologies else 0) + (15 if description else 0)
        return Project(title=title, technologies=technologies, description='\n'.join(description) if description else None, impact=None, score=min(100, score))
    
    def _extract_education(self, full_text: str, education_section: str) -> List[Education]:
        education, current_edu = [], {}
        lines = (education_section if education_section else full_text).split('\n')
        
        degree_keywords = ['bachelor', 'master', 'sarjana', 'magister', 's1', 's2', 's3', 'd3', 'diploma']
        institution_keywords = ['universitas', 'institut', 'politeknik', 'university', 'college']
        
        for line in lines:
            line_lower = line.lower().strip()
            if not line_lower: continue
            
            is_degree_line = False
            for kw in degree_keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', line_lower):
                    is_degree_line = True
                    if current_edu and ('degree' in current_edu or 'institution' in current_edu):
                        education.append(Education(**current_edu))
                        current_edu = {}
                    current_edu['degree'] = line.strip()
                    break
            
            if not is_degree_line:
                year_match = re.search(r'\b(19|20)\d{2}\b', line)
                if year_match and current_edu: current_edu['year'] = year_match.group()
                
                gpa_match = re.search(r'(?:GPA|CGPA|IPK)[\s:]*(\d+[.,]\d+)', line, re.IGNORECASE)
                if gpa_match and current_edu: current_edu['gpa'] = gpa_match.group(1).replace(',', '.')
                
                if current_edu and 'institution' not in current_edu and len(line.strip()) > 3:
                    current_edu['institution'] = line.strip()
                elif not current_edu and any(inst in line_lower for inst in institution_keywords):
                    current_edu['institution'] = line.strip()
                    
        if current_edu: education.append(Education(**current_edu))
        return education[:3]
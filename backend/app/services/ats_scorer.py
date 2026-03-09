"""
ATS Scorer Service - Calculates ATS compatibility score and provides insights
"""
import re
from typing import Dict, List, Any
from app.models.schemas import (
    SkillsData, DomainInfo, ScoreBreakdown, 
    ATSIssue, Suggestion, KeywordsAnalysis
)

class ATSScorer:
    DOMAIN_KEYWORDS = {
        'Software / IT': ['developed', 'built', 'implemented', 'designed', 'optimized', 'api', 'database', 'cloud'],
        'Data / AI': ['analyzed', 'modeled', 'predicted', 'visualized', 'accuracy', 'training', 'dataset', 'pipeline'],
        'Marketing': ['campaign', 'engagement', 'conversion', 'roi', 'brand', 'strategy', 'optimization', 'analytics'],
        'Finance': ['analyzed', 'forecasted', 'modeled', 'valued', 'budgeted', 'compliance', 'revenue', 'profit'],
        'General': ['managed', 'led', 'achieved', 'improved', 'increased', 'reduced', 'delivered', 'collaborated']
    }
    
    REQUIRED_SECTIONS = ['experience', 'education', 'skills']
    RECOMMENDED_SECTIONS = ['summary', 'projects', 'certifications']
    
    def calculate_score(
        self, 
        parsed_data: Dict, 
        skills: SkillsData, 
        domain: DomainInfo,
        job_role: str = None,
        job_description: str = None,
        custom_keywords: str = None,
        custom_skills: str = None,
        parsing_method: str = "standard",
        ocr_confidence: str = None
    ) -> Dict[str, Any]:
        
        is_ocr = parsing_method == "ocr"
        ocr_penalty_reduction = 0.7 if is_ocr else 1.0  
        ocr_min_score_floor = 25 if is_ocr else 0  
        
        raw_text = parsed_data.get('raw_text', '')
        sections = parsed_data.get('sections', {})
        formatting = parsed_data.get('formatting', {})
        candidate = parsed_data.get('candidate', {})
        experience = parsed_data.get('experience', {})
        projects = parsed_data.get('projects', [])
        
        hr_keywords = []
        if custom_keywords:
            hr_keywords = [k.strip().lower() for k in custom_keywords.split(',') if k.strip()]
        elif job_description:
            hr_keywords = self._extract_keywords_from_jd(job_description)
            
        hr_skills = []
        if custom_skills:
            hr_skills = [s.strip().lower() for s in custom_skills.split(',') if s.strip()]

        if hr_keywords or hr_skills:
            keyword_score = self._calculate_dynamic_keyword_score(raw_text, hr_keywords) if hr_keywords else self._calculate_keyword_score(raw_text, domain.primary)
            skill_score = self._calculate_dynamic_skill_score(skills, hr_skills) if hr_skills else self._calculate_skill_score(skills, hr_keywords)
        else:
            keyword_score = self._calculate_keyword_score(raw_text, domain.primary)
            skill_score = self._calculate_skill_score(skills)
            
        section_score = self._calculate_section_score(sections, candidate)
        formatting_score = self._calculate_formatting_score(formatting, raw_text, is_ocr, ocr_penalty_reduction)
        experience_score = self._calculate_experience_score(experience)
        project_score = self._calculate_project_score(projects)
        
        breakdown = ScoreBreakdown(
            keyword_relevance=keyword_score, section_completeness=section_score, formatting_score=formatting_score,
            skill_relevance=skill_score, experience_clarity=experience_score, project_impact=project_score
        )
        
        weights = {
            'keyword_relevance': 0.30 if (job_description or custom_keywords) else 0.20,
            'skill_relevance': 0.25 if (job_description or custom_skills) else 0.20,
            'section_completeness': 0.15,
            'formatting_score': 0.10,
            'experience_clarity': 0.15,
            'project_impact': 0.05
        }
        
        final_score = int(
            keyword_score * weights['keyword_relevance'] + section_score * weights['section_completeness'] +
            formatting_score * weights['formatting_score'] + skill_score * weights['skill_relevance'] +
            experience_score * weights['experience_clarity'] + project_score * weights['project_impact']
        )
        
        if is_ocr and final_score < ocr_min_score_floor: final_score = ocr_min_score_floor
            
        category = self._get_score_category(final_score)
        issues = self._identify_issues(raw_text, sections, formatting, skills, candidate, experience)
        
        if is_ocr:
            issues.insert(0, ATSIssue(type='parsing', severity='Low', description='Resume diproses menggunakan OCR.', suggestion='Unggah format PDF text-based atau DOCX untuk akurasi maksimal.'))
            
        suggestions = self._generate_suggestions(raw_text, domain.primary, skills, sections, experience, projects)
        keywords_analysis = self._analyze_keywords(raw_text, domain.primary, hr_keywords)
        
        return {
            'score': final_score, 'breakdown': breakdown, 'category': category, 'issues': issues,
            'suggestions': suggestions, 'keywords_analysis': keywords_analysis
        }

    def _extract_keywords_from_jd(self, jd: str) -> List[str]:
        if not jd: return []
        stopwords = {'dan', 'atau', 'dengan', 'untuk', 'yang', 'di', 'ke', 'dari', 'memiliki', 'mampu', 'menguasai', 'minimal', 'tahun', 'pengalaman'}
        words = re.findall(r'\b[a-zA-Z]{3,}\b', jd.lower())
        return list(set([w for w in words if w not in stopwords]))[:20]

    def _calculate_dynamic_keyword_score(self, text: str, hr_keywords: List[str]) -> int:
        if not hr_keywords: return 50
        text_lower = text.lower()
        found = sum(1 for kw in hr_keywords if kw in text_lower)
        return min(100, int((found / len(hr_keywords)) * 100))

    def _calculate_keyword_score(self, text: str, domain: str) -> int:
        text_lower = text.lower()
        keywords = self.DOMAIN_KEYWORDS.get(domain, self.DOMAIN_KEYWORDS['General'])
        found = sum(1 for kw in keywords if kw in text_lower)
        return min(100, int((found / len(keywords)) * 60) + 40)

    def _calculate_section_score(self, sections: Dict, candidate: Any) -> int:
        score = sum(20 for s in self.REQUIRED_SECTIONS if s in sections and len(sections[s].strip()) > 50)
        candidate_dict = candidate.dict() if hasattr(candidate, 'dict') else candidate
        if candidate_dict.get('email'): score += 10
        if candidate_dict.get('phone'): score += 10
        score += sum(7 for s in self.RECOMMENDED_SECTIONS if s in sections and len(sections[s].strip()) > 20)
        return min(100, score)

    def _calculate_formatting_score(self, formatting: Dict, text: str, is_ocr: bool, penalty_factor: float) -> int:
        score = 100
        if formatting.get('has_tables'): score -= int(15 * penalty_factor)
        if formatting.get('has_images'): score -= int(10 * penalty_factor)
        word_count = formatting.get('word_count', len(text.split()))
        if word_count < (150 if is_ocr else 200): score -= int(20 * penalty_factor)
        bullet_count = text.count('•') + text.count('-')
        if bullet_count < (3 if is_ocr else 5): score -= int(10 * penalty_factor)
        return max(0, min(100, score))

    def _calculate_dynamic_skill_score(self, skills: SkillsData, hr_skills: List[str]) -> int:
        all_skills = [s.lower() for s in skills.programming_languages + skills.frameworks + skills.tools + skills.databases + skills.soft_skills]
        matched = sum(1 for target in hr_skills if any(target in sk for sk in all_skills) or any(sk in target for sk in all_skills))
        return min(100, int((matched / len(hr_skills)) * 100))

    def _calculate_skill_score(self, skills: SkillsData, hr_keywords: List[str] = None) -> int:
        score = min(40, skills.total_count * 3)
        if skills.programming_languages: score += 15
        if skills.frameworks: score += 15
        if skills.tools: score += 10
        if skills.soft_skills: score += 10
        return min(100, score)

    def _calculate_experience_score(self, experience: Any) -> int:
        if not experience: return 30
        exp_dict = experience.dict() if hasattr(experience, 'dict') else experience
        positions = exp_dict.get('positions', [])
        score = 30 + min(20, len(positions) * 10)
        score += int(exp_dict.get('overall_quality', 0) * 0.5)
        return min(100, score)

    def _calculate_project_score(self, projects: List) -> int:
        if not projects: return 40
        score = 50 + sum(p.get('score', 0) * 0.1 for p in (p.dict() if hasattr(p, 'dict') else p for p in projects[:5]))
        return min(100, int(score))

    def _get_score_category(self, score: int) -> str:
        if score >= 80: return 'Excellent'
        elif score >= 60: return 'Good'
        elif score >= 40: return 'Needs Improvement'
        return 'Poor'

    def _identify_issues(self, text, sections, formatting, skills, candidate, experience) -> List[ATSIssue]:
        issues = []
        if formatting.get('has_tables'): issues.append(ATSIssue(type='formatting', severity='High', description='Tables detected', suggestion='Use text formatting.'))
        c_dict = candidate.dict() if hasattr(candidate, 'dict') else candidate
        if not c_dict.get('email'): issues.append(ATSIssue(type='contact', severity='High', description='No email detected', suggestion='Add email.'))
        if 'experience' not in sections: issues.append(ATSIssue(type='section', severity='High', description='No Experience section', suggestion='Add Experience section.'))
        return issues

    def _generate_suggestions(self, text, domain, skills, sections, experience, projects) -> List[Suggestion]:
        return []

    def _analyze_keywords(self, text: str, domain: str, hr_keywords: List[str] = None) -> KeywordsAnalysis:
        text_lower = text.lower()
        if hr_keywords:
            return KeywordsAnalysis(
                found=[kw for kw in hr_keywords if kw in text_lower],
                missing=[kw for kw in hr_keywords if kw not in text_lower][:10],
                recommended=[]
            )
        return KeywordsAnalysis(found=[], missing=[], recommended=[])
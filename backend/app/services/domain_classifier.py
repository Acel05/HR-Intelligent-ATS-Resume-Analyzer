"""
Domain Classifier Service - Classifies resume into job domain categories
Supports 20+ industries for comprehensive resume analysis (Bilingual: EN & ID)
"""
import re
from typing import Dict, List, Tuple
from app.models.schemas import DomainInfo, SkillsData

class DomainClassifier:
    """Classify resume into job domain categories across all major industries"""
    
    # Comprehensive domain keywords covering 20+ industries (Added Indonesian Keywords)
    DOMAIN_KEYWORDS = {
        # ==================== TECHNOLOGY ====================
        'Software / IT': {
            'keywords': [
                'software', 'developer', 'engineer', 'programming', 'coding',
                'web', 'frontend', 'backend', 'fullstack', 'full-stack',
                'api', 'devops', 'cloud', 'microservices', 'architecture',
                'agile', 'scrum', 'sprint', 'deployment', 'ci/cd',
                'testing', 'debugging', 'algorithm', 'data structure',
                'mobile', 'ios', 'android', 'app development', 'saas',
                'pengembang', 'pemrograman', 'rekayasa perangkat lunak', 'sistem informasi'
            ],
            'skills': [
                'python', 'java', 'javascript', 'react', 'angular', 'vue',
                'node.js', 'docker', 'kubernetes', 'aws', 'git', 'linux',
                'typescript', 'golang', 'rust', 'c++', 'c#'
            ],
            'titles': [
                'software engineer', 'developer', 'programmer', 'sde',
                'tech lead', 'engineering manager', 'devops engineer',
                'solutions architect', 'cto', 'full stack developer',
                'it support', 'programmer staf'
            ]
        },
        'Data Science / AI': {
            'keywords': [
                'data', 'machine learning', 'ml', 'artificial intelligence', 'ai',
                'deep learning', 'neural network', 'nlp', 'computer vision',
                'analytics', 'statistics', 'modeling', 'prediction',
                'big data', 'etl', 'pipeline', 'warehouse', 'visualization',
                'kecerdasan buatan', 'statistik', 'analisis data', 'visualisasi data'
            ],
            'skills': [
                'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas',
                'numpy', 'sql', 'spark', 'hadoop', 'tableau', 'power bi',
                'r', 'sas', 'databricks', 'snowflake', 'airflow', 'dbt'
            ],
            'titles': [
                'data scientist', 'data analyst', 'ml engineer', 'data engineer',
                'ai engineer', 'research scientist', 'analytics manager',
                'business analyst', 'analis data'
            ]
        },

        # ==================== BUSINESS ====================
        'Marketing': {
            'keywords': [
                'marketing', 'campaign', 'brand', 'branding', 'digital marketing',
                'social media', 'content', 'seo', 'sem', 'ppc', 'advertising',
                'email marketing', 'automation', 'lead generation', 'funnel',
                'pemasaran', 'periklanan', 'kampanye', 'media sosial', 'promosi'
            ],
            'skills': [
                'google analytics', 'hubspot', 'mailchimp', 'facebook ads', 
                'google ads', 'hootsuite', 'canva', 'wordpress', 'seo'
            ],
            'titles': [
                'marketing manager', 'digital marketer', 'content strategist',
                'seo specialist', 'growth marketer', 'brand manager',
                'cmo', 'marketing director', 'manajer pemasaran', 'staf pemasaran'
            ]
        },
        'Finance / Banking': {
            'keywords': [
                'finance', 'financial', 'accounting', 'investment', 'banking',
                'trading', 'portfolio', 'risk', 'compliance', 'audit',
                'budgeting', 'forecasting', 'valuation', 'equity', 'tax',
                'keuangan', 'akuntansi', 'perbankan', 'pajak', 'investasi',
                'anggaran', 'pembukuan', 'auditor'
            ],
            'skills': [
                'excel', 'financial modeling', 'bloomberg', 'vba',
                'sql', 'sap', 'oracle financials', 'quickbooks', 'cpa'
            ],
            'titles': [
                'financial analyst', 'accountant', 'investment banker',
                'portfolio manager', 'risk analyst', 'controller', 'cfo',
                'akuntan', 'staf keuangan', 'manajer keuangan', 'teller'
            ]
        },
        'Sales': {
            'keywords': [
                'sales', 'selling', 'revenue', 'quota', 'pipeline',
                'prospecting', 'closing', 'negotiation', 'account',
                'client', 'customer', 'relationship', 'b2b', 'b2c',
                'penjualan', 'klien', 'pelanggan', 'negosiasi', 'target penjualan'
            ],
            'skills': [
                'salesforce', 'hubspot', 'linkedin sales navigator', 'pipedrive'
            ],
            'titles': [
                'sales representative', 'account executive', 'sales manager',
                'business development', 'sales director', 'account manager',
                'staf penjualan', 'sales marketing', 'pramuniaga'
            ]
        },
        'Human Resources': {
            'keywords': [
                'human resources', 'hr', 'recruiting', 'talent acquisition',
                'onboarding', 'employee relations', 'compensation', 'benefits',
                'payroll', 'training', 'development', 'performance management',
                'sumber daya manusia', 'sdm', 'personalia', 'rekrutmen',
                'pelatihan', 'karyawan', 'penggajian'
            ],
            'skills': [
                'workday', 'bamboohr', 'linkedin recruiter', 'hris', 'adp'
            ],
            'titles': [
                'hr manager', 'recruiter', 'talent acquisition', 'hr business partner',
                'hr generalist', 'hr director', 'manajer hrd', 'staf personalia', 'hrd'
            ]
        },
        'Operations / Supply Chain': {
            'keywords': [
                'operations', 'supply chain', 'logistics', 'procurement',
                'inventory', 'warehouse', 'distribution', 'fulfillment',
                'manufacturing', 'production', 'quality control',
                'operasional', 'logistik', 'pergudangan', 'rantai pasok',
                'pengadaan', 'produksi', 'distribusi', 'inventaris'
            ],
            'skills': [
                'sap', 'oracle', 'netsuite', 'lean six sigma', 'excel'
            ],
            'titles': [
                'operations manager', 'supply chain manager', 'logistics coordinator',
                'warehouse manager', 'plant manager', 'manajer operasional',
                'staf logistik', 'admin gudang'
            ]
        },
        'Project Management': {
            'keywords': [
                'project management', 'program management', 'pmo',
                'agile', 'scrum', 'waterfall', 'kanban', 'sprint',
                'milestone', 'timeline', 'budget', 'resource allocation',
                'manajemen proyek', 'pengelolaan proyek', 'jadwal'
            ],
            'skills': [
                'jira', 'asana', 'trello', 'monday', 'ms project', 'pmp'
            ],
            'titles': [
                'project manager', 'program manager', 'scrum master',
                'product owner', 'manajer proyek'
            ]
        },

        # ==================== ENTRY LEVEL & GENERAL ====================
        'Student / Fresher': {
            'keywords': [
                'student', 'fresher', 'graduate', 'university', 'college',
                'intern', 'internship', 'campus', 'academic', 'thesis',
                'mahasiswa', 'lulusan', 'magang', 'kampus', 'akademik',
                'skripsi', 'sarjana', 'fresh graduate'
            ],
            'skills': [],
            'titles': [
                'intern', 'trainee', 'fresher', 'graduate', 'entry level',
                'junior', 'associate', 'apprentice', 'peserta magang'
            ]
        },
        'General Administration': {
            'keywords': [
                'administration', 'admin', 'clerical', 'data entry',
                'document', 'filing', 'office', 'receptionist', 'secretary',
                'administrasi', 'sekretaris', 'resepsionis', 'entri data',
                'dokumen', 'kantor', 'tata usaha'
            ],
            'skills': ['microsoft word', 'microsoft excel', 'data entry'],
            'titles': [
                'admin', 'administrator', 'administrative assistant',
                'secretary', 'receptionist', 'staf administrasi', 'admin support'
            ]
        }
    }
    
    def classify(self, text: str, skills: SkillsData) -> DomainInfo:
        """Classify resume into a domain category"""
        text_lower = text.lower()
        
        domain_scores: Dict[str, float] = {}
        keywords_matched: Dict[str, List[str]] = {}
        
        for domain, data in self.DOMAIN_KEYWORDS.items():
            score, matched = self._calculate_domain_score(text_lower, data, skills)
            domain_scores[domain] = score
            keywords_matched[domain] = matched
        
        total_score = sum(domain_scores.values())
        
        # PERBAIKAN 1: Fallback jika dokumen kosong atau tidak ada keyword yang cocok sama sekali
        if total_score == 0:
            return DomainInfo(
                primary="Unknown / General",
                confidence=0.5,
                secondary=None,
                keywords_matched=[]
            )
            
        sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_domain = sorted_domains[0][0]
        primary_score = sorted_domains[0][1]
        secondary_domain = sorted_domains[1][0] if len(sorted_domains) > 1 else None
        secondary_score = sorted_domains[1][1] if len(sorted_domains) > 1 else 0
        
        confidence = (primary_score / total_score) if total_score > 0 else 0.5
        
        if secondary_score > 0 and (primary_score - secondary_score) < primary_score * 0.2:
            confidence *= 0.8
        
        return DomainInfo(
            primary=primary_domain,
            confidence=round(confidence, 2),
            secondary=secondary_domain if secondary_score > primary_score * 0.5 else None,
            keywords_matched=keywords_matched.get(primary_domain, [])[:10]
        )
    
    def _calculate_domain_score(
        self, 
        text: str, 
        domain_data: Dict, 
        skills: SkillsData
    ) -> Tuple[float, List[str]]:
        """Calculate score for a domain"""
        score = 0.0
        matched = []
        
        for keyword in domain_data['keywords']:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text):
                score += 1
                matched.append(keyword)
        
        for title in domain_data['titles']:
            pattern = r'\b' + re.escape(title) + r'\b'
            if re.search(pattern, text):
                score += 3
                matched.append(title)
        
        # PERBAIKAN 2: Proteksi `NoneType` menggunakan operator `or []`
        all_user_skills = set(
            s.lower() for s in 
            (skills.programming_languages or []) + 
            (skills.frameworks or []) + 
            (skills.tools or []) + 
            (skills.databases or []) +
            (skills.soft_skills or [])
        )
        
        for skill in domain_data['skills']:
            if skill.lower() in all_user_skills:
                score += 2
                matched.append(skill)
        
        return score, matched
    
    def get_domain_description(self, domain: str) -> str:
        """Get description for a domain"""
        descriptions = {
            'Software / IT': 'Software development, web/mobile applications, and IT infrastructure',
            'Data Science / AI': 'Data science, machine learning, analytics, and artificial intelligence',
            'Marketing': 'Digital marketing, brand management, and growth strategies',
            'Finance / Banking': 'Financial analysis, accounting, investment, and risk management',
            'Sales': 'Sales, business development, and account management',
            'Human Resources': 'Talent acquisition, employee relations, and people operations',
            'Operations / Supply Chain': 'Logistics, procurement, manufacturing, and process optimization',
            'Project Management': 'Project/program management, agile methodologies, and delivery',
            'Student / Fresher': 'Entry-level position with academic focus',
            'General Administration': 'General office administration, data entry, and secretarial duties',
            'Unknown / General': 'General professional role or uncategorized domain'
        }
        return descriptions.get(domain, 'General professional role')
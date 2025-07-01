from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import json
import asyncio
import logging
from datetime import datetime
import google.generativeai as genai
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import torch
import PyPDF2
import docx
from werkzeug.utils import secure_filename
import re
from typing import Dict, List, Any
import sqlite3
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app, origins=["http://localhost:5173"])

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY', 'AIzaSyAXuhgIgjJzHsvwUZx3FG8GddReQhRuCxc'))

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(model.name)

class EnhancedInsuranceAnalyzer:
    def __init__(self):
        self.db_path = 'insurance_agent.db'
        self.init_database()
        self.load_models()
        self.strategy_database = self.load_strategy_database()

    def init_database(self):
        """Initialize SQLite database for case tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Cases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                case_type TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                policy_data TEXT,
                claim_data TEXT,
                strategy_used TEXT,
                outcome TEXT,
                success_score REAL
            )
        ''')
        
        # Negotiations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS negotiations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                round_number INTEGER,
                strategy TEXT,
                letter_content TEXT,
                response_received TEXT,
                success_probability REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases (id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def load_models(self):
        """Load the language models"""
        try:
            # Load a smaller model for analysis (you can replace with Llama/Mistral)
            self.tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
            self.model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")
            
            # Initialize text classification pipeline
            self.classifier = pipeline("text-classification", 
                                     model="distilbert-base-uncased-finetuned-sst-2-english")
            
            logger.info("Models loaded successfully")
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            # Fallback to basic functionality
            self.tokenizer = None
            self.model = None
            self.classifier = None    
        
    def load_strategy_database(self):
        """Load predefined negotiation strategies"""
        return {
            "policy_interpretation_challenge": {
                "description": "Challenge insurer's interpretation of policy terms",
                "templates": [
                    "Based on my review of Section {section} of my policy, I believe your denial is incorrect...",
                    "The policy clearly states in {clause} that coverage applies when...",
                ],
                "success_rate": 0.73,
                "aggression_level": "medium"
            },
            "precedent_citation": {
                "description": "Cite legal precedents and similar cases",
                "templates": [
                    "Similar cases such as {case_name} have established that...",
                    "According to state insurance regulations {regulation}, insurers must...",
                ],
                "success_rate": 0.81,
                "aggression_level": "high"
            },
            "collaborative_approach": {
                "description": "Seek mutual resolution through cooperation",
                "templates": [
                    "I understand your position, however, I believe we can find a mutually beneficial solution...",
                    "I'm confident we can resolve this matter amicably by considering...",
                ],
                "success_rate": 0.65,
                "aggression_level": "low"
            },
            "documentation_emphasis": {
                "description": "Emphasize thorough documentation and evidence",
                "templates": [
                    "The attached documentation clearly demonstrates...",
                    "As evidenced by the enclosed {document_type}, the facts show...",
                ],
                "success_rate": 0.79,
                "aggression_level": "medium"
            },
            "pre_existing_challenge": {
                "description": "Challenge pre-existing condition determinations",
                "templates": [
                    "The determination of a pre-existing condition appears to be incorrect based on...",
                    "Medical evidence supports that this condition was not pre-existing because...",
                ],
                "success_rate": 0.68,
                "aggression_level": "medium"
            },
            "procedural_violation": {
                "description": "Challenge procedural violations in claim handling",
                "templates": [
                    "The insurer failed to follow proper claim investigation procedures...",
                    "Required documentation was not adequately requested or reviewed...",
                ],
                "success_rate": 0.77,
                "aggression_level": "medium"
            }
        }
    
    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
    def extract_text_from_file(self, filepath):
        """Extract text from uploaded files"""
        try:
            file_extension = filepath.rsplit('.', 1)[1].lower()
            
            if file_extension == 'pdf':
                with open(filepath, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text()
                return text
                
            elif file_extension == 'docx':
                doc = docx.Document(filepath)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text
                
            elif file_extension == 'txt':
                with open(filepath, 'r', encoding='utf-8') as file:
                    return file.read()
                    
            else:
                return "Unsupported file type for text extraction"
                
        except Exception as e:
            logger.error(f"Error extracting text from file: {e}")
            return "Error extracting text from file"

    def extract_comprehensive_info(self, text: str) -> Dict[str, Any]:
        """Extract comprehensive information from insurance documents"""
        if not text or not text.strip():
            return self._empty_comprehensive_analysis()
        
        # Clean text for better processing
        cleaned_text = self._clean_text(text)
        
        info = {
            "document_type": self._identify_document_type(cleaned_text),
            "policy_numbers": self._extract_policy_numbers(cleaned_text),
            "claim_numbers": self._extract_claim_numbers(cleaned_text),
            "dates": self._extract_dates(cleaned_text),
            "parties": self._extract_parties(cleaned_text),
            "amounts": self._extract_amounts(cleaned_text),
            "coverage_types": self._extract_coverage_types(cleaned_text),
            "exclusions": self._extract_exclusions(cleaned_text),
            "denial_reasons": self._extract_denial_reasons(cleaned_text),
            "policy_clauses": self._extract_policy_clauses(cleaned_text),
            "deadlines": self._extract_deadlines(cleaned_text),
            "required_documents": self._extract_required_documents(cleaned_text),
            "contact_info": self._extract_contact_info(cleaned_text),
            "key_phrases": self._extract_key_phrases(cleaned_text)
        }
        
        return info
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for better processing"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters that might interfere
        text = re.sub(r'[^\w\s\-.,;:()\[\]/@#$%]', ' ', text)
        return text.strip()
    
    def _identify_document_type(self, text: str) -> str:
        """Identify the type of insurance document"""
        text_lower = text.lower()
        
        if any(phrase in text_lower for phrase in ['rejection', 'denial', 'denied', 'reject']):
            return "claim_denial"
        elif any(phrase in text_lower for phrase in ['policy', 'coverage', 'terms', 'conditions']):
            return "policy"
        elif any(phrase in text_lower for phrase in ['claim', 'incident', 'loss']):
            return "claim"
        else:
            return "general"
    
    def _extract_policy_numbers(self, text: str) -> List[str]:
        """Extract policy numbers with multiple patterns"""
        patterns = [
            r"(?i)policy\s*(?:number|no\.?|#)\s*:?\s*([A-Z0-9\-]{6,20})",
            r"(?i)policy\s*:?\s*([A-Z0-9\-]{6,20})",
            r"(?i)ref(?:erence)?\s*(?:no\.?|#)?\s*:?\s*([A-Z0-9\-]{6,20})",
            r"\b([A-Z]\d{8,15})\b",  # Pattern like H567891234, T345678912
            r"\b([A-Z]{1,3}\d{6,12})\b",  # Variations
            r"(?i)policy\s+([A-Z0-9]{6,20})",
        ]
        
        policy_numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 6 and match not in policy_numbers:
                    policy_numbers.append(match.strip())
        
        return policy_numbers[:3]  # Return top 3 matches
    
    def _extract_claim_numbers(self, text: str) -> List[str]:
        """Extract claim numbers"""
        patterns = [
            r"(?i)claim\s*(?:number|no\.?|#)\s*:?\s*([A-Z0-9\-]{6,20})",
            r"(?i)claim\s*:?\s*([A-Z0-9\-]{6,20})",
            r"(?i)file\s*(?:number|no\.?|#)\s*:?\s*([A-Z0-9\-]{6,20})",
        ]
        
        claim_numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 6 and match not in claim_numbers:
                    claim_numbers.append(match.strip())
        
        return claim_numbers
    
    def select_strategy(self, leverage_points, claim_type, user_profile=None):
        """Enhanced strategy selection"""
        strategy_scores = {}
        
        # Start with base success rates
        for strategy_name, strategy_data in self.strategy_database.items():
            strategy_scores[strategy_name] = strategy_data["success_rate"]
        
        # Adjust scores based on leverage points
        for point in leverage_points:
            point_type = point.get("type", "")
            strength = point.get("strength", 0.5)
            
            if point_type == "pre_existing_challenge":
                strategy_scores["pre_existing_challenge"] += 0.15
                strategy_scores["documentation_emphasis"] += 0.10
            elif point_type == "exclusion_interpretation":
                strategy_scores["policy_interpretation_challenge"] += 0.15
            elif point_type == "coverage_mismatch":
                strategy_scores["policy_interpretation_challenge"] += 0.12
                strategy_scores["precedent_citation"] += 0.08
            elif point_type == "medical_documentation":
                strategy_scores["documentation_emphasis"] += 0.12
        
        # Adjust for claim type
        if claim_type == "travel":
            strategy_scores["documentation_emphasis"] += 0.05
            strategy_scores["policy_interpretation_challenge"] += 0.05
        
        # Select highest scoring strategy
        best_strategy = max(strategy_scores, key=strategy_scores.get)
        return best_strategy, round(strategy_scores[best_strategy], 3)
    
    def calculate_success_probability(self, strategy, leverage_points, claim_amount):
        """Enhanced success probability calculation"""
        # Base probability from strategy
        base_probability = self.strategy_database.get(strategy, {}).get("success_rate", 0.5)
        
        # Calculate leverage bonus
        total_strength = sum(point.get("strength", 0.5) for point in leverage_points)
        leverage_bonus = min(0.25, total_strength * 0.15)  # Cap at 25% bonus
        
        # Adjust for specific leverage types
        for point in leverage_points:
            point_type = point.get("type", "")
            if point_type == "pre_existing_challenge":
                leverage_bonus += 0.05  # Pre-existing challenges often successful
            elif point_type == "coverage_mismatch":
                leverage_bonus += 0.08  # Strong argument
        
        # Calculate final probability
        final_probability = min(0.95, base_probability + leverage_bonus)
        return round(final_probability, 2)
    
    async def generate_negotiation_letter(self, strategy, policy_analysis, claim_analysis, leverage_points):
        """Enhanced letter generation"""
        try:
            # Try Gemini API first
            model = genai.GenerativeModel('gemini-2.0-flash')  # Updated model name
            
            prompt = f"""
            Generate a professional insurance claim negotiation letter based on this information:

            STRATEGY: {strategy}
            
            CLAIM DETAILS:
            - Policy Number: {policy_analysis.get('policy_number', 'Not specified')}
            - Claim Number: {claim_analysis.get('claim_number', 'Not specified')}
            - Claim Type: {claim_analysis.get('claim_type', 'general')}
            - Claim Status: {claim_analysis.get('claim_status', 'denied')}
            - Incident Date: {claim_analysis.get('incident_date', 'Not specified')}
            - Denial Reasons: {'; '.join(claim_analysis.get('denial_reasons', ['Not specified']))}

            LEVERAGE POINTS:
            {chr(10).join([f"- {point['description']} (Strength: {point['strength']:.0%})" for point in leverage_points])}

            Write a professional letter that:
            1. References specific policy and claim numbers
            2. Addresses the denial reasons directly
            3. Uses leverage points to build strong arguments
            4. Requests specific actions
            5. Sets a 30-day deadline
            6. Maintains professional but firm tone

            Format as a complete business letter.
            """
            
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
                
        except Exception as e:
            logger.error(f"Gemini API failed: {e}")
        
        # Fallback to template
        return self.generate_enhanced_template_letter(strategy, policy_analysis, claim_analysis, leverage_points)
    
    def generate_enhanced_template_letter(self, strategy, policy_analysis, claim_analysis, leverage_points):
        """Enhanced template letter with real data"""
        
        # Extract information
        policy_number = policy_analysis.get('policy_number', '[POLICY_NUMBER]')
        claim_number = claim_analysis.get('claim_number', policy_number)  # Use policy number if claim number not found
        incident_date = claim_analysis.get('incident_date', '[DATE]')
        denial_reasons = claim_analysis.get('denial_reasons', [])
        claim_type = claim_analysis.get('claim_type', 'insurance')
        
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Build specific arguments based on denial reasons
        denial_text = ""
        if denial_reasons:
            denial_text = f"specifically citing: {'; '.join(denial_reasons[:2])}"
        else:
            denial_text = "without adequate justification"
        
        # Build leverage arguments
        leverage_text = ""
        for i, point in enumerate(leverage_points[:3], 1):
            leverage_text += f"\n{i}. {point['description']}\n"
        
        letter = f"""[Your Name]
[Your Address]
[City, State ZIP Code]
[Phone Number]
[Email Address]

{current_date}

XYZ Travel Insurance
Claims Department
[Insurance Company Address]

RE: Policy Number: {policy_number}
    Claim Number: {claim_number}
    Date of Incident: {incident_date}

Dear Claims Review Manager,

I am writing to formally request immediate reconsideration of my {claim_type} insurance claim denial dated {incident_date}.

Your denial letter stated that my claim was rejected {denial_text}. After careful review of my policy terms and the circumstances surrounding this claim, I believe this denial was issued in error and request immediate reinvestigation.

The following points support my position for reconsideration:
{leverage_text}

Based on this analysis, I believe your denial decision was incorrect and respectfully request that you:

1. Immediately reopen my claim file for comprehensive review
2. Provide detailed written explanation of specific policy provisions supporting the denial
3. Allow me to submit additional documentation if required
4. Process payment for this valid claim within 30 days

I have been a faithful policyholder and have always paid my premiums promptly. I trust you will give this matter immediate attention and provide a substantive written response within 30 days of receipt of this letter.

Please contact me at [YOUR PHONE] or [YOUR EMAIL] if you require any additional information.

I look forward to your prompt response and favorable resolution of this matter.

Sincerely,

[Your Signature]
[Your Printed Name]
Policy Holder

Enclosures: [Supporting Documentation]
cc: [State Insurance Commissioner if applicable]
"""
        
        return letter
    
    def _extract_dates(self, text: str) -> Dict[str, List[str]]:
        """Extract various dates from the document"""
        date_patterns = [
            r"\d{1,2}[-/]\w{3}[-/]\d{2,4}",  # 10-May-2024, 22-Apr-2024
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",  # 10/5/2024, 22/04/2024
            r"(?i)(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}",
            r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",  # 2024-05-10
        ]
        
        dates = {
            "incident_dates": [],
            "claim_dates": [],
            "denial_dates": [],
            "deadline_dates": [],
            "all_dates": []
        }
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                date_str = match.strip() if isinstance(match, str) else ' '.join(match).strip()
                if date_str and date_str not in dates["all_dates"]:
                    dates["all_dates"].append(date_str)
        
        # Categorize dates based on context
        text_lower = text.lower()
        for date in dates["all_dates"]:
            date_context = self._get_date_context(text_lower, date.lower())
            if any(word in date_context for word in ['incident', 'accident', 'occurred']):
                dates["incident_dates"].append(date)
            elif any(word in date_context for word in ['claim', 'filed', 'submitted']):
                dates["claim_dates"].append(date)
            elif any(word in date_context for word in ['denial', 'denied', 'rejection']):
                dates["denial_dates"].append(date)
            elif any(word in date_context for word in ['deadline', 'within', 'days']):
                dates["deadline_dates"].append(date)
        
        return dates
    
    def _get_date_context(self, text: str, date: str) -> str:
        """Get context around a date for categorization"""
        try:
            date_index = text.find(date)
            if date_index != -1:
                start = max(0, date_index - 50)
                end = min(len(text), date_index + len(date) + 50)
                return text[start:end]
        except:
            pass
        return ""
    
    def _extract_parties(self, text: str) -> Dict[str, List[str]]:
        """Extract parties involved (policyholder, insurer)"""
        parties = {
            "policyholders": [],
            "insurers": [],
            "contacts": []
        }
        
        # Extract policyholders
        policyholder_patterns = [
            r"(?i)(?:dear|to)\s+(?:mr\.?|ms\.?|mrs\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"(?i)insured:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"(?i)policyholder:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]
        
        for pattern in policyholder_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match and len(match.split()) <= 4:  # Reasonable name length
                    parties["policyholders"].append(match.strip())
        
        # Extract insurers
        insurer_patterns = [
            r"(?i)([A-Z][a-zA-Z\s]+(?:Insurance|Travel|Health)(?:\s+(?:Company|Corp|Inc))?)",
            r"(?i)(XYZ\s+(?:Health|Travel)\s+Insurance)",
            r"(?i)sincerely,?\s*([A-Z][a-zA-Z\s]+Insurance[^.\n]*)",
        ]
        
        for pattern in insurer_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean_match = match.strip()
                if len(clean_match) > 5 and clean_match not in parties["insurers"]:
                    parties["insurers"].append(clean_match)
        
        return parties
    
    def _extract_amounts(self, text: str) -> List[str]:
        """Extract monetary amounts"""
        amount_patterns = [
            r"\$[\d,]+\.?\d*",
            r"(?i)amount[:\s]*\$?[\d,]+\.?\d*",
            r"(?i)claim[:\s]*\$?[\d,]+\.?\d*",
            r"(?i)damages[:\s]*\$?[\d,]+\.?\d*",
        ]
        
        amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match and match not in amounts:
                    amounts.append(match.strip())
        
        return amounts
    
    def _extract_coverage_types(self, text: str) -> List[str]:
        """Extract coverage types with improved patterns"""
        coverage_patterns = [
            # Direct coverage mentions
            r"(?i)(travel\s+insurance|trip\s+cancellation|flight\s+cancellation)",
            r"(?i)(medical\s+coverage|health\s+insurance|emergency\s+medical)",
            r"(?i)(baggage\s+coverage|trip\s+interruption|travel\s+delay)",
            r"(?i)(auto\s+insurance|vehicle\s+coverage|collision\s+coverage)",
            r"(?i)(property\s+insurance|home\s+insurance|dwelling\s+coverage)",
            
            # Coverage context
            r"(?i)coverage\s+(?:for|includes?)\s+([^.\n]{5,50})",
            r"(?i)insured\s+for\s+([^.\n]{5,50})",
            r"(?i)policy\s+covers\s+([^.\n]{5,50})",
            r"(?i)benefits\s+include\s+([^.\n]{5,50})",
            
            # Subject line coverage
            r"(?i)subject:\s*([^.\n]*(?:insurance|coverage|claim)[^.\n]*)",
        ]
        
        coverage_types = []
        for pattern in coverage_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean_match = match.strip().lower()
                if len(clean_match) > 3 and clean_match not in [c.lower() for c in coverage_types]:
                    coverage_types.append(match.strip())
        
        return coverage_types[:10]  # Limit to avoid noise
    
    def _extract_exclusions(self, text: str) -> List[str]:
        """Extract exclusions with improved patterns"""
        exclusion_patterns = [
            # Direct exclusion mentions
            r"(?i)exclusion\s+clause\s+([0-9.]+)[^.\n]*([^.\n]{10,100})",
            r"(?i)excluded[:\s]*([^.\n]{10,100})",
            r"(?i)(?:not\s+covered|does\s+not\s+cover)[:\s]*([^.\n]{10,100})",
            r"(?i)pre-existing\s+(?:medical\s+)?condition[s]?[^.\n]*",
            r"(?i)we\s+do\s+not\s+(?:cover|pay\s+for)[:\s]*([^.\n]{10,100})",
            
            # Contextual exclusions
            r"(?i)(?:due\s+to|because\s+of|resulting\s+from)\s+([^.\n]*exclusion[^.\n]*)",
            r"(?i)listed\s+under\s+exclusion[^.\n]*([^.\n]{10,100})",
        ]
        
        exclusions = []
        for pattern in exclusion_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle tuple results from capturing groups
                    exclusion_text = ' '.join([m for m in match if m and len(m) > 3])
                else:
                    exclusion_text = match
                
                clean_exclusion = exclusion_text.strip().rstrip('.,;')
                if len(clean_exclusion) > 5 and clean_exclusion not in exclusions:
                    exclusions.append(clean_exclusion)
        
        return exclusions[:8]  # Limit to avoid noise
    
    def _extract_denial_reasons(self, text: str) -> List[str]:
        """Extract denial reasons with comprehensive patterns"""
        denial_patterns = [
            # Direct denial reasons
            r"(?i)(?:rejection|denial|denied|decline[d]?)\s+(?:of|reason[s]?)[:\s]*([^.\n]{15,200})",
            r"(?i)reason\s+for\s+(?:rejection|denial)[:\s]*([^.\n]{15,200})",
            r"(?i)(?:because|due\s+to|as)[:\s]*([^.\n]{15,200})",
            r"(?i)not\s+(?:covered|eligible)[:\s]*([^.\n]{15,200})",
            
            # Specific denial contexts
            r"(?i)your\s+(?:claim|cancellation)\s+was\s+(?:due\s+to|because\s+of)\s+([^.\n]{15,200})",
            r"(?i)investigation\s+reveals\s+(?:that\s+)?([^.\n]{15,200})",
            r"(?i)our\s+review\s+(?:shows|indicates|reveals)\s+(?:that\s+)?([^.\n]{15,200})",
            
            # Policy violation reasons
            r"(?i)as\s+per\s+policy\s+clause\s+([0-9.]+)[^.\n]*([^.\n]{10,150})",
            r"(?i)under\s+(?:exclusion\s+)?clause\s+([0-9.]+)[^.\n]*([^.\n]{10,150})",
        ]
        
        denial_reasons = []
        for pattern in denial_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    reason_text = ' '.join([m for m in match if m and len(m) > 5])
                else:
                    reason_text = match
                
                clean_reason = reason_text.strip().rstrip('.,;')
                if len(clean_reason) > 10 and clean_reason not in denial_reasons:
                    denial_reasons.append(clean_reason)
        
        return denial_reasons[:6]  # Limit to most relevant
    
    def _extract_policy_clauses(self, text: str) -> List[str]:
        """Extract policy clauses and sections referenced"""
        clause_patterns = [
            r"(?i)(?:policy\s+)?clause\s+([0-9.]+)",
            r"(?i)section\s+([A-Z0-9.]+)",
            r"(?i)article\s+([A-Z0-9.]+)",
            r"(?i)paragraph\s+([0-9.]+)",
            r"(?i)exclusion\s+clause\s+([0-9.]+)",
        ]
        
        clauses = []
        for pattern in clause_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match and match not in clauses:
                    clauses.append(match.strip())
        
        return clauses
    
    def _extract_deadlines(self, text: str) -> List[str]:
        """Extract deadlines and time limits"""
        deadline_patterns = [
            r"(?i)within\s+(\d+)\s+days",
            r"(?i)(\d+)\s+days?\s+of\s+(?:this\s+letter|receipt)",
            r"(?i)deadline[:\s]*([^.\n]{5,50})",
            r"(?i)must\s+be\s+submitted\s+(?:within\s+)?([^.\n]{5,50})",
        ]
        
        deadlines = []
        for pattern in deadline_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean_deadline = match.strip()
                if len(clean_deadline) > 1 and clean_deadline not in deadlines:
                    deadlines.append(clean_deadline)
        
        return deadlines
    
    def _extract_required_documents(self, text: str) -> List[str]:
        """Extract required or missing documents"""
        doc_patterns = [
            r"(?i)(?:missing|required|essential|supporting)\s+documents?\s*(?:such\s+as\s+)?([^.\n]{10,100})",
            r"(?i)(?:diagnostic\s+reports?|medical\s+records?|hospital\s+discharge\s+summar(?:y|ies))",
            r"(?i)(?:receipts?|invoices?|bills?|statements?)",
            r"(?i)(?:police\s+report|incident\s+report|accident\s+report)",
            r"(?i)additional\s+documentation[^.\n]*([^.\n]{10,100})",
        ]
        
        documents = []
        for pattern in doc_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean_doc = match.strip().rstrip('.,;')
                if len(clean_doc) > 3 and clean_doc not in documents:
                    documents.append(clean_doc)
        
        return documents
    
    def _extract_contact_info(self, text: str) -> Dict[str, List[str]]:
        """Extract contact information"""
        contact_info = {
            "phone_numbers": [],
            "emails": [],
            "addresses": []
        }
        
        # Phone numbers
        phone_patterns = [
            r"1800-[A-Z]+",
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            r"\(\d{3}\)\s*\d{3}[-.]?\d{4}",
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            contact_info["phone_numbers"].extend(matches)
        
        # Email addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        contact_info["emails"] = re.findall(email_pattern, text)
        
        return contact_info
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases that might be useful for analysis"""
        key_phrase_patterns = [
            r"(?i)((?:as\s+per|according\s+to|based\s+on)\s+[^.\n]{10,50})",
            r"(?i)((?:claims\s+must\s+be|policy\s+requires|coverage\s+applies)\s+[^.\n]{10,50})",
            r"(?i)((?:we\s+regret|unfortunately|disappointed)\s+[^.\n]{10,50})",
        ]
        
        key_phrases = []
        for pattern in key_phrase_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean_phrase = match.strip()
                if len(clean_phrase) > 10 and clean_phrase not in key_phrases:
                    key_phrases.append(clean_phrase)
        
        return key_phrases[:5]
    
    async def analyze_policy_document(self, text: str) -> Dict[str, Any]:
        """Enhanced policy document analysis"""
        if not text or not text.strip():
            return self._empty_policy_analysis()
        
        # Get comprehensive info
        comprehensive_info = self.extract_comprehensive_info(text)
        
        analysis = {
            "coverage_types": comprehensive_info["coverage_types"],
            "exclusions": comprehensive_info["exclusions"],
            "limits": {},
            "deductibles": {},
            "key_clauses": comprehensive_info["policy_clauses"],
            "policy_number": comprehensive_info["policy_numbers"][0] if comprehensive_info["policy_numbers"] else "",
            "coverage_period": "",
            "insurer_name": comprehensive_info["parties"]["insurers"][0] if comprehensive_info["parties"]["insurers"] else "",
            "contact_info": comprehensive_info["contact_info"],
            "comprehensive_data": comprehensive_info
        }
        
        return analysis
    
    async def analyze_claim_document(self, text: str) -> Dict[str, Any]:
        """Enhanced claim document analysis"""
        if not text or not text.strip():
            return self._empty_claim_analysis()
        
        # Get comprehensive info
        comprehensive_info = self.extract_comprehensive_info(text)
        
        # Determine claim type from document analysis
        claim_type = self._determine_claim_type(text, comprehensive_info)
        
        # Determine claim status
        claim_status = "denied" if comprehensive_info["document_type"] == "claim_denial" else "unknown"
        
        analysis = {
            "claim_number": (comprehensive_info["claim_numbers"][0] if comprehensive_info["claim_numbers"] 
                           else comprehensive_info["policy_numbers"][0] if comprehensive_info["policy_numbers"] else ""),
            "claim_type": claim_type,
            "denial_reasons": comprehensive_info["denial_reasons"],
            "damages_claimed": comprehensive_info["amounts"][0] if comprehensive_info["amounts"] else "Not specified",
            "incident_date": self._get_best_date(comprehensive_info["dates"]),
            "claim_status": claim_status,
            "key_facts": comprehensive_info["key_phrases"],
            "insurer_position": comprehensive_info["denial_reasons"][0] if comprehensive_info["denial_reasons"] else "",
            "policy_sections_cited": comprehensive_info["policy_clauses"],
            "documentation_requested": comprehensive_info["required_documents"],
            "deadlines": comprehensive_info["deadlines"],
            "comprehensive_data": comprehensive_info
        }
        
        return analysis
    
    def _determine_claim_type(self, text: str, comprehensive_info: Dict) -> str:
        """Determine claim type from text and extracted info"""
        text_lower = text.lower()
        coverage_types = [c.lower() for c in comprehensive_info["coverage_types"]]
        
        # Check coverage types first
        if any("travel" in c or "trip" in c or "flight" in c for c in coverage_types):
            return "travel"
        elif any("health" in c or "medical" in c for c in coverage_types):
            return "health"
        elif any("auto" in c or "vehicle" in c for c in coverage_types):
            return "auto"
        
        # Check text content
        if any(word in text_lower for word in ['travel', 'trip', 'flight', 'cancellation']):
            return "travel"
        elif any(word in text_lower for word in ['health', 'medical', 'hospital', 'diagnostic']):
            return "health"
        elif any(word in text_lower for word in ['auto', 'vehicle', 'car', 'accident']):
            return "auto"
        else:
            return "general"
    
    def _get_best_date(self, dates_dict: Dict[str, List[str]]) -> str:
        """Get the most relevant date from extracted dates"""
        # Priority order: incident > claim > denial > any
        for date_type in ["incident_dates", "claim_dates", "denial_dates", "all_dates"]:
            if dates_dict.get(date_type):
                return dates_dict[date_type][0]
        return "Not specified"
    
    async def find_leverage_points(self, policy_analysis: Dict, claim_analysis: Dict, full_text: str = None) -> List[Dict]:
        """Enhanced leverage point identification"""
        leverage_points = []
        
        comprehensive_data = claim_analysis.get("comprehensive_data", {})
        denial_reasons = claim_analysis.get("denial_reasons", [])
        coverage_types = policy_analysis.get("coverage_types", [])
        exclusions = policy_analysis.get("exclusions", [])
        required_docs = claim_analysis.get("documentation_requested", [])
        
        # Pre-existing condition challenges
        for reason in denial_reasons:
            reason_lower = reason.lower()
            if "pre-existing" in reason_lower and "medical" in reason_lower:
                leverage_points.append({
                    "type": "pre_existing_challenge",
                    "description": "Challenge pre-existing medical condition determination",
                    "strength": 0.75,
                    "evidence": f"Pre-existing condition claim requires proper medical timeline documentation: '{reason[:100]}...'"
                })
        
        # Coverage vs denial mismatch
        claim_type = claim_analysis.get("claim_type", "")
        if coverage_types and claim_analysis.get("claim_status") == "denied":
            relevant_coverage = [c for c in coverage_types if claim_type.lower() in c.lower()]
            if relevant_coverage:
                leverage_points.append({
                    "type": "coverage_mismatch",
                    "description": "Policy provides relevant coverage but claim was denied",
                    "strength": 0.80,
                    "evidence": f"Policy explicitly covers {claim_type} claims: {', '.join(relevant_coverage[:2])}"
                })
        
        # Procedural violations - insufficient investigation
        if not required_docs and claim_analysis.get("claim_status") == "denied":
            leverage_points.append({
                "type": "insufficient_investigation",
                "description": "Insurer may not have conducted adequate investigation",
                "strength": 0.65,
                "evidence": "No additional documentation was requested before denial, suggesting inadequate investigation"
            })
        
        # Missing documentation issues
        if required_docs:
            leverage_points.append({
                "type": "documentation_procedural",
                "description": "Challenge documentation requirements and procedures",
                "strength": 0.70,
                "evidence": f"Required documents: {', '.join(required_docs[:3])} - insurer must provide clear guidance on requirements"
            })
        
        # Policy interpretation issues
        policy_clauses = claim_analysis.get("policy_sections_cited", [])
        if policy_clauses:
            leverage_points.append({
                "type": "policy_interpretation",
                "description": f"Challenge interpretation of policy clauses {', '.join(policy_clauses[:2])}",
                "strength": 0.72,
                "evidence": f"Policy clauses {', '.join(policy_clauses[:2])} may be misinterpreted or misapplied to this specific case"
            })
        
        # Medical documentation specific
        if claim_type == "health" or any("medical" in reason.lower() for reason in denial_reasons):
            leverage_points.append({
                "type": "medical_documentation",
                "description": "Request detailed medical documentation review",
                "strength": 0.60,
                "evidence": "Medical determinations require comprehensive review of all medical records and professional opinions"
            })
        
        # If no specific leverage points found, add general review
        if not leverage_points:
            leverage_points.append({
                "type": "comprehensive_review",
                "description": "Request comprehensive policy and claim review",
                "strength": 0.55,
                "evidence": "All claim denials warrant thorough review of policy terms, claim procedures, and applicable regulations"
            })
        
        return sorted(leverage_points, key=lambda x: x['strength'], reverse=True)
    
    async def generate_negotiation_strategy(self, policy_analysis: Dict, claim_analysis: Dict, leverage_points: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive negotiation strategy"""
        
        # Determine primary strategy based on strongest leverage points
        if not leverage_points:
            primary_strategy = "collaborative_approach"
        else:
            top_leverage = leverage_points[0]["type"]
            strategy_mapping = {
                "pre_existing_challenge": "pre_existing_challenge",
                "coverage_mismatch": "policy_interpretation_challenge",
                "insufficient_investigation": "procedural_violation",
                "documentation_procedural": "documentation_emphasis",
                "policy_interpretation": "policy_interpretation_challenge",
                "medical_documentation": "documentation_emphasis"
            }
            primary_strategy = strategy_mapping.get(top_leverage, "collaborative_approach")
        
        strategy_data = self.strategy_database[primary_strategy]
        
        # Calculate success probability based on leverage points and strategy
        base_success_rate = strategy_data["success_rate"]
        leverage_bonus = sum(point["strength"] for point in leverage_points[:3]) * 0.1
        success_probability = min(0.95, base_success_rate + leverage_bonus)
        
        # Determine potential outcomes
        claimed_amount = self._extract_claimed_amount(claim_analysis)
        potential_outcomes = self._calculate_potential_outcomes(claimed_amount, success_probability)
        
        # Generate strategy phases
        negotiation_phases = self._generate_negotiation_phases(primary_strategy, leverage_points)
        
        return {
            "primary_strategy": primary_strategy,
            "strategy_description": strategy_data["description"],
            "aggression_level": strategy_data["aggression_level"],
            "success_probability": round(success_probability, 2),
            "potential_outcomes": potential_outcomes,
            "key_leverage_points": leverage_points[:3],
            "negotiation_phases": negotiation_phases,
            "recommended_timeline": self._generate_timeline(negotiation_phases),
            "fallback_strategies": self._get_fallback_strategies(primary_strategy)
        }
    
    def _extract_claimed_amount(self, claim_analysis: Dict) -> float:
        """Extract claimed amount from analysis"""
        damages = claim_analysis.get("damages_claimed", "")
        if isinstance(damages, str):
            # Extract numeric value from string like "$5,000" or "5000"
            import re
            numbers = re.findall(r'[\d,]+\.?\d*', damages.replace(',', ''))
            if numbers:
                try:
                    return float(numbers[0])
                except:
                    pass
        return 10000.0  # Default estimate
    
    def _calculate_potential_outcomes(self, claimed_amount: float, success_probability: float) -> Dict[str, Any]:
        """Calculate potential financial outcomes"""
        return {
            "best_case": {
                "amount": claimed_amount,
                "probability": success_probability * 0.3,
                "description": "Full claim amount recovered"
            },
            "likely_case": {
                "amount": claimed_amount * 0.6,
                "probability": success_probability * 0.5,
                "description": "Partial settlement achieved"
            },
            "minimum_case": {
                "amount": claimed_amount * 0.3,
                "probability": success_probability * 0.7,
                "description": "Minimum acceptable settlement"
            }
        }
    
    def _generate_negotiation_phases(self, primary_strategy: str, leverage_points: List[Dict]) -> List[Dict]:
        """Generate sequential negotiation phases"""
        phases = []
        
        # Phase 1: Initial Appeal
        phases.append({
            "phase": 1,
            "name": "Initial Formal Appeal",
            "objective": "Present strongest arguments and evidence",
            "duration_days": "5-7",
            "key_actions": [
                "Submit comprehensive appeal letter",
                "Include all supporting documentation",
                "Reference specific policy clauses",
                "Request detailed review timeline"
            ]
        })
        
        # Phase 2: Follow-up and Clarification
        phases.append({
            "phase": 2,
            "name": "Follow-up and Pressure",
            "objective": "Maintain momentum and add pressure",
            "duration_days": "10-14",
            "key_actions": [
                "Follow up on appeal status",
                "Request explanation of delay",
                "Provide additional evidence if needed",
                "Reference regulatory compliance requirements"
            ]
        })
        
        # Phase 3: Escalation (if needed)
        if primary_strategy in ["procedural_violation", "precedent_citation"]:
            phases.append({
                "phase": 3,
                "name": "Regulatory Escalation",
                "objective": "Escalate to regulatory authorities",
                "duration_days": "15-20",
                "key_actions": [
                    "File complaint with insurance commissioner",
                    "Reference pattern of improper denials",
                    "Request regulatory investigation",
                    "Consider legal consultation"
                ]
            })
        
        return phases
    
    def _generate_timeline(self, phases: List[Dict]) -> str:
        """Generate recommended timeline for negotiation"""
        total_days = sum(int(phase["duration_days"].split("-")[1]) for phase in phases)
        return f"Expected duration: {total_days} days across {len(phases)} phases"
    
    def _get_fallback_strategies(self, primary_strategy: str) -> List[str]:
        """Get fallback strategies if primary fails"""
        fallback_map = {
            "policy_interpretation_challenge": ["documentation_emphasis", "procedural_violation"],
            "precedent_citation": ["policy_interpretation_challenge", "collaborative_approach"],
            "collaborative_approach": ["documentation_emphasis", "procedural_violation"],
            "documentation_emphasis": ["policy_interpretation_challenge", "collaborative_approach"],
            "pre_existing_challenge": ["documentation_emphasis", "precedent_citation"],
            "procedural_violation": ["precedent_citation", "policy_interpretation_challenge"]
        }
        return fallback_map.get(primary_strategy, ["collaborative_approach"])
    
    async def generate_appeal_letter(self, strategy: Dict, policy_analysis: Dict, claim_analysis: Dict) -> str:
        """Generate personalized appeal letter"""
        
        primary_strategy = strategy["primary_strategy"]
        strategy_templates = self.strategy_database[primary_strategy]["templates"]
        
        # Get key information
        policy_number = policy_analysis.get("policy_number", "")
        claim_number = claim_analysis.get("claim_number", "")
        insurer_name = policy_analysis.get("insurer_name", "Insurance Company")
        denial_reasons = claim_analysis.get("denial_reasons", [])
        leverage_points = strategy.get("key_leverage_points", [])
        
        # Build letter components
        header = self._generate_letter_header(insurer_name, policy_number, claim_number)
        opening = self._generate_opening_paragraph(claim_analysis)
        main_arguments = self._generate_main_arguments(leverage_points, strategy_templates)
        policy_references = self._generate_policy_references(policy_analysis, claim_analysis)
        conclusion = self._generate_conclusion(strategy["aggression_level"])
        
        full_letter = f"{header}\n\n{opening}\n\n{main_arguments}\n\n{policy_references}\n\n{conclusion}"
        
        return full_letter
    
    def _generate_letter_header(self, insurer_name: str, policy_number: str, claim_number: str) -> str:
        """Generate professional letter header"""
        current_date = datetime.now().strftime("%B %d, %Y")
        
        return f"""Date: {current_date}

To: Claims Review Department
{insurer_name}

RE: Formal Appeal for Claim Denial
Policy Number: {policy_number}
Claim Number: {claim_number}

Dear Claims Review Team,"""
    
    def _generate_opening_paragraph(self, claim_analysis: Dict) -> str:
        """Generate opening paragraph"""
        claim_type = claim_analysis.get("claim_type", "insurance")
        incident_date = claim_analysis.get("incident_date", "")
        
        return f"""I am writing to formally appeal the denial of my {claim_type} insurance claim submitted on {incident_date}. After careful review of the denial letter and my policy terms, I believe the decision to deny coverage is incorrect and not supported by the facts of my case or the terms of my insurance policy."""
    
    def _generate_main_arguments(self, leverage_points: List[Dict], templates: List[str]) -> str:
        """Generate main arguments section"""
        arguments = []
        
        for i, point in enumerate(leverage_points[:3], 1):
            template = templates[min(i-1, len(templates)-1)]
            evidence = point.get("evidence", "")
            
            # Customize template based on leverage point type
            if point["type"] == "pre_existing_challenge":
                argument = f"Regarding the pre-existing condition determination: {evidence} The medical timeline clearly demonstrates this condition was not pre-existing as defined in the policy terms."
            elif point["type"] == "coverage_mismatch":
                argument = f"Policy Coverage Analysis: {evidence} The denial appears to contradict the explicit coverage provided under my policy."
            elif point["type"] == "procedural_violation":
                argument = f"Claims Handling Procedures: {evidence} The investigation process did not meet the standards required under state insurance regulations."
            else:
                argument = f"Key Issue #{i}: {evidence}"
            
            arguments.append(argument)
        
        return "\n\n".join(arguments)
    
    def _generate_policy_references(self, policy_analysis: Dict, claim_analysis: Dict) -> str:
        """Generate policy references section"""
        clauses = claim_analysis.get("policy_sections_cited", [])
        coverage_types = policy_analysis.get("coverage_types", [])
        
        references = "Policy Analysis:\n"
        
        if coverage_types:
            references += f"• My policy explicitly provides coverage for: {', '.join(coverage_types[:3])}\n"
        
        if clauses:
            references += f"• The cited policy clauses ({', '.join(clauses)}) do not support the denial when properly interpreted\n"
        
        references += "• I request a detailed explanation of how the denial aligns with the specific policy language and definitions"
        
        return references
    
    def _generate_conclusion(self, aggression_level: str) -> str:
        """Generate conclusion based on aggression level"""
        if aggression_level == "high":
            return """I expect a prompt reversal of this denial decision. Should this matter not be resolved satisfactorily within 30 days, I will be compelled to file a complaint with the state insurance commissioner and explore all available legal remedies.

I look forward to your immediate attention to this matter and a favorable resolution.

Sincerely,
[Your Name]
[Your Contact Information]"""
        
        elif aggression_level == "medium":
            return """I respectfully request a comprehensive review of this claim denial and expect a prompt response addressing the concerns outlined above. I am confident that upon proper review, coverage will be extended as required under my policy terms.

Please confirm receipt of this appeal and provide a timeline for your review process.

Sincerely,
[Your Name]
[Your Contact Information]"""
        
        else:  # low/collaborative
            return """I hope we can work together to resolve this matter fairly and promptly. I am available to provide any additional information that may be helpful in reconsidering this claim.

Thank you for your time and consideration. I look forward to hearing from you soon.

Best regards,
[Your Name]
[Your Contact Information]"""
    
    async def predict_outcomes(self, strategy: Dict, case_history: List[Dict] = None) -> Dict[str, Any]:
        """Predict negotiation outcomes based on strategy and historical data"""
        
        primary_strategy = strategy["primary_strategy"]
        leverage_points = strategy.get("key_leverage_points", [])
        
        # Base predictions on strategy success rates
        base_success = self.strategy_database[primary_strategy]["success_rate"]
        
        # Adjust based on leverage strength
        leverage_adjustment = sum(point["strength"] for point in leverage_points) * 0.1
        
        # Historical case similarity (simplified - would use ML in production)
        historical_adjustment = 0.05 if case_history else 0
        
        final_success_probability = min(0.95, base_success + leverage_adjustment + historical_adjustment)
        
        return {
            "success_probability": round(final_success_probability, 2),
            "predicted_timeline": strategy.get("recommended_timeline", "30-45 days"),
            "confidence_level": "high" if final_success_probability > 0.75 else "medium" if final_success_probability > 0.6 else "low",
            "key_risk_factors": self._identify_risk_factors(strategy, leverage_points),
            "optimization_suggestions": self._generate_optimization_suggestions(strategy, leverage_points)
        }
    
    def _identify_risk_factors(self, strategy: Dict, leverage_points: List[Dict]) -> List[str]:
        """Identify potential risk factors"""
        risks = []
        
        if strategy["aggression_level"] == "high":
            risks.append("High aggression may escalate to adversarial relationship")
        
        if len(leverage_points) < 2:
            risks.append("Limited leverage points may reduce negotiation power")
        
        if not any(point["strength"] > 0.7 for point in leverage_points):
            risks.append("No strong leverage points identified")
        
        return risks
    
    def _generate_optimization_suggestions(self, strategy: Dict, leverage_points: List[Dict]) -> List[str]:
        """Generate suggestions to optimize strategy"""
        suggestions = []
        
        if len(leverage_points) < 3:
            suggestions.append("Gather additional evidence to strengthen negotiation position")
        
        if strategy["aggression_level"] == "low" and any(point["strength"] > 0.8 for point in leverage_points):
            suggestions.append("Consider more assertive approach given strong evidence")
        
        suggestions.append("Document all communications for potential regulatory complaint")
        suggestions.append("Set clear deadlines for insurer responses")
        
        return suggestions
    
    def _empty_comprehensive_analysis(self) -> Dict[str, Any]:
        """Return empty structure for comprehensive analysis"""
        return {
            "document_type": "unknown",
            "policy_numbers": [],
            "claim_numbers": [],
            "dates": {"incident_dates": [], "claim_dates": [], "denial_dates": [], "deadline_dates": [], "all_dates": []},
            "parties": {"policyholders": [], "insurers": [], "contacts": []},
            "amounts": [],
            "coverage_types": [],
            "exclusions": [],
            "denial_reasons": [],
            "policy_clauses": [],
            "deadlines": [],
            "required_documents": [],
            "contact_info": {"phone_numbers": [], "emails": [], "addresses": []},
            "key_phrases": []
        }
    
    def _empty_policy_analysis(self) -> Dict[str, Any]:
        """Return empty structure for policy analysis"""
        return {
            "coverage_types": [],
            "exclusions": [],
            "limits": {},
            "deductibles": {},
            "key_clauses": [],
            "policy_number": "",
            "coverage_period": "",
            "insurer_name": "",
            "contact_info": {"phone_numbers": [], "emails": [], "addresses": []},
            "comprehensive_data": self._empty_comprehensive_analysis()
        }
    
    def _empty_claim_analysis(self) -> Dict[str, Any]:
        """Return empty structure for claim analysis"""
        return {
            "claim_number": "",
            "claim_type": "unknown",
            "denial_reasons": [],
            "damages_claimed": "Not specified",
            "incident_date": "Not specified",
            "claim_status": "unknown",
            "key_facts": [],
            "insurer_position": "",
            "policy_sections_cited": [],
            "documentation_requested": [],
            "deadlines": [],
            "comprehensive_data": self._empty_comprehensive_analysis()
        }

# Initialize the agent
agent = EnhancedInsuranceAnalyzer()

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Handle file uploads"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        uploaded_files = []
        
        for file in files:
            if file and file.filename and agent.allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Extract text content
                text_content = agent.extract_text_from_file(filepath)
                
                uploaded_files.append({
                    'filename': filename,
                    'filepath': filepath,
                    'content': text_content[:500] + '...' if len(text_content) > 500 else text_content
                })
        
        return jsonify({
            'success': True,
            'files': uploaded_files
        })
        
    except Exception as e:
        logger.error(f"Error uploading files: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
async def analyze_case():
    """Analyze uploaded documents and generate strategy"""
    try:
        data = request.json
        filenames = data.get('filenames', [])
        
        if not filenames:
            return jsonify({'error': 'No files to analyze'}), 400
        
        # Process all uploaded files
        full_text = ""
        
        for filename in filenames:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                text = agent.extract_text_from_file(filepath)
                full_text += text + "\n"
        
        # For the travel insurance PDF, treat as both policy and claim document
        policy_analysis = await agent.analyze_policy_document(full_text)
        claim_analysis = await agent.analyze_claim_document(full_text)
        
        # Find leverage points
        leverage_points = await agent.find_leverage_points(policy_analysis, claim_analysis, full_text)
        
        # Select strategy
        strategy, strategy_score = agent.select_strategy(leverage_points, claim_analysis.get('claim_type', 'general'))
        
        # Calculate success probability
        success_probability = agent.calculate_success_probability(
            strategy, leverage_points, claim_analysis.get('damages_claimed', '')
        )
        
        return jsonify({
            'success': True,
            'analysis': {
                'policy_analysis': policy_analysis,
                'claim_analysis': claim_analysis,
                'leverage_points': leverage_points,
                'recommended_strategy': strategy,
                'strategy_score': strategy_score,
                'success_probability': success_probability
            }
        })
        
    except Exception as e:
        logger.error(f"Error analyzing case: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-letter', methods=['POST'])
def generate_letter():
    """Generate negotiation letter"""
    try:
        data = request.json
        analysis = data.get('analysis', {})
        
        # Generate letter
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        letter = loop.run_until_complete(
            agent.generate_negotiation_letter(
                analysis.get('recommended_strategy'),
                analysis.get('policy_analysis'),
                analysis.get('claim_analysis'),
                analysis.get('leverage_points')
            )
        )
        
        loop.close()
        
        return jsonify({
            'success': True,
            'letter': letter,
            'strategy': analysis.get('recommended_strategy'),
            'success_probability': analysis.get('success_probability')
        })
        
    except Exception as e:
        logger.error(f"Error generating letter: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-case', methods=['POST'])
def save_case():
    """Save case to database"""
    try:
        data = request.json
        
        conn = sqlite3.connect(agent.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO cases (user_id, case_type, status, policy_data, claim_data, strategy_used)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data.get('user_id', 'anonymous'),
            data.get('case_type', 'general'),
            'active',
            json.dumps(data.get('policy_analysis', {})),
            json.dumps(data.get('claim_analysis', {})),
            data.get('strategy', '')
        ))
        
        case_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'case_id': case_id
        })
        
    except Exception as e:
        logger.error(f"Error saving case: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cases', methods=['GET'])
def get_cases():
    """Get all cases"""
    try:
        conn = sqlite3.connect(agent.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, case_type, status, created_at, strategy_used, success_score
            FROM cases
            ORDER BY created_at DESC
        ''')
        
        cases = []
        for row in cursor.fetchall():
            cases.append({
                'id': row[0],
                'case_type': row[1],
                'status': row[2],
                'created_at': row[3],
                'strategy_used': row[4],
                'success_score': row[5]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'cases': cases
        })
        
    except Exception as e:
        logger.error(f"Error getting cases: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
import PyPDF2
import re
from typing import Dict, List, Any
import logging
from datetime import datetime
from models import ExtractedInfo, DocumentType

class DocumentProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Regex patterns for extraction
        self.patterns = {
            'policy_number': [
                r'Policy\s*Number\s*:?\s*([A-Z0-9\-]+)',
                r'Policy\s*No\.?\s*:?\s*([A-Z0-9\-]+)',
                r'Policy\s*#?\s*:?\s*([A-Z0-9\-]+)',
                r'Policy\s*ID\s*:?\s*([A-Z0-9\-]+)'
            ],
            'claim_number': [
                r'Claim\s*#?\s*:?\s*([A-Z0-9\-]+)',
                r'Claim\s*Number\s*:?\s*([A-Z0-9\-]+)'
            ],
            'monetary_amounts': [
                r'\$[\d,]+\.?\d*',
                r'USD\s*[\d,]+\.?\d*',
                r'(\d+,?\d*\.?\d*)\s*dollars?'
            ],
            'dates': [
                r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
                r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}',
                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}'
            ],
            'email_addresses': [
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            ],
            'phone_numbers': [
                r'\(\d{3}\)\s*\d{3}-\d{4}',
                r'\d{3}-\d{3}-\d{4}',
                r'\d{3}\.\d{3}\.\d{4}'
            ]
        }
        
        # Keywords for document type detection
        self.document_keywords = {
            DocumentType.DENIAL_LETTER: [
                'denial', 'denied', 'reject', 'declined', 'not covered',
                'exclusion', 'not liable', 'insufficient', 'ineligible'
            ],
            DocumentType.SETTLEMENT_OFFER: [
                'settlement', 'offer', 'propose', 'resolve', 'payment',
                'accept', 'final offer', 'compromise'
            ],
            DocumentType.POLICY_DOCUMENT: [
                'policy', 'coverage', 'terms', 'conditions', 'premium',
                'deductible', 'limits', 'endorsement'
            ],
            DocumentType.CLAIM_FORM: [
                'claim form', 'application', 'incident report',
                'loss report', 'damage report'
            ],
            DocumentType.CORRESPONDENCE: [
                'letter', 'correspondence', 'communication', 'response',
                'follow-up', 'inquiry'
            ]
        }

    async def extract_information(self, file_path: str) -> ExtractedInfo:
        """Extract information from PDF document"""
        try:
            text = self._extract_text_from_pdf(file_path)
            
            # Determine document type
            doc_type = self._classify_document_type(text)
            
            # Extract various information
            policy_details = self._extract_policy_details(text)
            claim_details = self._extract_claim_details(text)
            monetary_amounts = self._extract_monetary_amounts(text)
            key_dates = self._extract_dates(text)
            parties_involved = self._extract_parties(text)
            coverage_types = self._extract_coverage_types(text)
            denial_reasons = self._extract_denial_reasons(text) if doc_type == DocumentType.DENIAL_LETTER else []
            settlement_amounts = self._extract_settlement_amounts(text) if doc_type == DocumentType.SETTLEMENT_OFFER else []
            
            # Calculate extraction confidence
            extraction_confidence = self._calculate_extraction_confidence(
                policy_details, claim_details, monetary_amounts
            )
            
            return ExtractedInfo(
                document_type=doc_type,
                extraction_confidence=extraction_confidence,
                policy_details=policy_details,
                claim_details=claim_details,
                monetary_amounts=monetary_amounts,
                key_dates=key_dates,
                parties_involved=parties_involved,
                coverage_types=coverage_types,
                denial_reasons=denial_reasons,
                settlement_amounts=settlement_amounts
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting information: {str(e)}")
            raise

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            self.logger.error(f"Error reading PDF: {str(e)}")
            raise

    def _classify_document_type(self, text: str) -> str:
        lowered = text.lower()

        if any(phrase in lowered for phrase in ["denied", "we regret", "not covered", "unfortunately"]):
            return "denial_letter"
        elif "offer" in lowered and "settlement" in lowered:
            return "settlement_offer"
        elif "policy number" in lowered and "coverage" in lowered:
            return "policy_document"
        elif "claim form" in lowered or "fill out the form" in lowered:
            return "claim_form"
        elif "correspondence" in lowered or "communication" in lowered:
            return "correspondence"
        else:
            return "correspondence"  # fallback instead of invalid "uploaded_document"


    def _extract_policy_details(self, text: str) -> Dict[str, Any]:
        """Extract policy-related information"""
        policy_details = {}
        
        # Extract policy number
        for pattern in self.patterns['policy_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                policy_details['policy_number'] = match.group(1)
                break
        
        # Extract insurer name
        insurer_patterns = [
            r'([A-Z][a-z]+\s+Insurance)',
            r'([A-Z][a-z]+\s+Mutual)',
            r'([A-Z][a-z]+\s+Assurance)'
        ]
        for pattern in insurer_patterns:
            match = re.search(pattern, text)
            if match:
                policy_details['insurer'] = match.group(1)
                break
        
        # Extract policy effective dates
        effective_date_pattern = r'effective\s+date[:\s]+([^\n]+)'
        match = re.search(effective_date_pattern, text, re.IGNORECASE)
        if match:
            policy_details['effective_date'] = match.group(1).strip()
        
        return policy_details

    def _extract_claim_details(self, text: str) -> Dict[str, Any]:
        """Extract claim-related information"""
        claim_details = {}
        
        # Extract claim number
        for pattern in self.patterns['claim_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                claim_details['claim_number'] = match.group(1)
                break
        
        # Extract incident date
        incident_patterns = [
            r'incident\s+date[:\s]+([^\n]+)',
            r'date\s+of\s+loss[:\s]+([^\n]+)',
            r'accident\s+date[:\s]+([^\n]+)'
        ]
        for pattern in incident_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                claim_details['incident_date'] = match.group(1).strip()
                break
        
        # Extract damage description
        damage_patterns = [
            r'damage[ds]?[:\s]+([^\n\.]+)',
            r'loss[:\s]+([^\n\.]+)',
            r'incident[:\s]+([^\n\.]+)'
        ]
        for pattern in damage_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                claim_details['damage_description'] = match.group(1).strip()
                break
        
        return claim_details

    def _extract_monetary_amounts(self, text: str) -> List[str]:
        """Extract all monetary amounts from text"""
        amounts = []
        for pattern in self.patterns['monetary_amounts']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            amounts.extend(matches)
        return list(set(amounts))  # Remove duplicates

    def _extract_dates(self, text: str) -> List[str]:
        """Extract all dates from text"""
        dates = []
        for pattern in self.patterns['dates']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        return list(set(dates))

    def _extract_parties(self, text: str) -> List[str]:
        """Extract involved parties (names, companies)"""
        parties = []
        
        # Extract email addresses as potential parties
        for pattern in self.patterns['email_addresses']:
            matches = re.findall(pattern, text)
            parties.extend(matches)
        
        # Extract names after common prefixes
        name_patterns = [
            r'insured[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)',
            r'policyholder[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)',
            r'claimant[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)'
        ]
        for pattern in name_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            parties.extend(matches)
        
        return list(set(parties))

    def _extract_coverage_types(self, text: str) -> List[str]:
        """Extract types of coverage mentioned"""
        coverage_keywords = [
            'liability', 'collision', 'comprehensive', 'medical',
            'property damage', 'bodily injury', 'uninsured motorist',
            'personal injury protection', 'gap coverage'
        ]
        
        text_lower = text.lower()
        found_coverage = [coverage for coverage in coverage_keywords if coverage in text_lower]
        return found_coverage

    def _extract_denial_reasons(self, text: str) -> List[str]:
        """Extract reasons for claim denial"""
        denial_patterns = [
            r'denied\s+because[:\s]+([^\n\.]+)',
            r'reason\s+for\s+denial[:\s]+([^\n\.]+)',
            r'not\s+covered\s+due\s+to[:\s]+([^\n\.]+)',
            r'exclusion[:\s]+([^\n\.]+)'
        ]
        
        reasons = []
        for pattern in denial_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            reasons.extend(matches)
        
        return [reason.strip() for reason in reasons]

    def _extract_settlement_amounts(self, text: str) -> List[float]:
        """Extract settlement amounts as floats"""
        amounts = self._extract_monetary_amounts(text)
        settlement_amounts = []
        
        for amount_str in amounts:
            # Clean and convert to float
            cleaned = re.sub(r'[^\d.]', '', amount_str)
            try:
                amount = float(cleaned)
                settlement_amounts.append(amount)
            except ValueError:
                continue
        
        return settlement_amounts

    def _calculate_extraction_confidence(self, policy_details: Dict, claim_details: Dict, 
                                       monetary_amounts: List[str]) -> float:
        """Calculate confidence score for extraction"""
        confidence_factors = [
            0.3 if policy_details.get('policy_number') else 0,
            0.2 if claim_details.get('claim_number') else 0,
            0.2 if monetary_amounts else 0,
            0.15 if policy_details.get('insurer') else 0,
            0.15 if claim_details.get('incident_date') else 0
        ]
        
        return sum(confidence_factors)
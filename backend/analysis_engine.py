import json
import logging
from typing import Dict, List, Any, Optional
import random
from datetime import datetime, timedelta
from models import ExtractedInfo, AnalysisResult, PayoutRange, SimilarCase

class AnalysisEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Load knowledge base (in production, this would be from a database)
        self.similar_cases_db = self._load_similar_cases()
        self.success_factors_db = self._load_success_factors()
        self.industry_benchmarks = self._load_industry_benchmarks()

    async def analyze_case(self, extracted_info: ExtractedInfo, parameters: Optional[Dict[str, Any]] = None) -> AnalysisResult:
        """Analyze case and predict success probability"""
        try:
            # Find similar cases
            similar_cases = self._find_similar_cases(extracted_info)

            # Calculate success probability
            success_probability = self._calculate_success_probability(extracted_info, similar_cases)

            # Estimate payout range
            payout_range = self._estimate_payout_range(extracted_info, similar_cases)

            # Identify risk and strength factors
            risk_factors = self._identify_risk_factors(extracted_info)
            strength_factors = self._identify_strength_factors(extracted_info)

            # Get market comparisons
            market_comparisons = self._get_market_comparisons(extracted_info)

            # Estimate timeline
            timeline_estimate = self._estimate_timeline(extracted_info, success_probability)

            return AnalysisResult(
                success_probability=round(success_probability, 2),
                estimated_payout_range=payout_range,
                risk_factors=risk_factors,
                strength_factors=strength_factors,
                similar_cases=similar_cases[:3],
                market_comparisons=market_comparisons,
                timeline_estimate=timeline_estimate
            )

        except Exception as e:
            self.logger.error(f"Error analyzing case: {str(e)}")
            raise

    def _load_similar_cases(self) -> List[Dict[str, Any]]:
        """Load historical similar cases database"""
        # In production, this would load from a real database
        return [
            {
                "case_id": "HIST_001",
                "document_type": "denial_letter",
                "policy_type": "auto",
                "denial_reason": "policy exclusion",
                "original_claim": 3500,
                "final_payout": 2800,
                "success_rate": 0.8,
                "strategy_used": "Policy Interpretation Challenge",
                "key_factors": ["policy ambiguity", "precedent case", "documentation quality"]
            },
            {
                "case_id": "HIST_002", 
                "document_type": "settlement_offer",
                "policy_type": "home",
                "initial_offer": 4200,
                "final_settlement": 6800,
                "success_rate": 0.62,
                "strategy_used": "Market Value Documentation",
                "key_factors": ["comparable sales", "expert appraisal", "damage photos"]
            },
            {
                "case_id": "HIST_003",
                "document_type": "denial_letter",
                "policy_type": "auto",
                "denial_reason": "coverage limit",
                "original_claim": 1800,
                "final_payout": 1200,
                "success_rate": 0.67,
                "strategy_used": "Coverage Scope Expansion",
                "key_factors": ["policy interpretation", "industry standards"]
            }
        ]

    def _load_success_factors(self) -> Dict[str, float]:
        """Load success factors and their weights"""
        return {
            "policy_ambiguity": 0.25,
            "documentation_quality": 0.20,
            "precedent_cases": 0.18,
            "expert_testimony": 0.15,
            "timeline_compliance": 0.12,
            "damage_evidence": 0.10
        }

    def _load_industry_benchmarks(self) -> Dict[str, Any]:
        """Load industry benchmark data"""
        return {
            "auto": {
                "average_settlement_increase": 0.35,
                "success_rate_by_type": {
                    "denial_letter": 0.68,
                    "settlement_offer": 0.72,
                    "policy_document": 0.45
                }
            },
            "home": {
                "average_settlement_increase": 0.42,
                "success_rate_by_type": {
                    "denial_letter": 0.71,
                    "settlement_offer": 0.65,
                    "policy_document": 0.38
                }
            },
            "health": {
                "average_settlement_increase": 0.28,
                "success_rate_by_type": {
                    "denial_letter": 0.58,
                    "settlement_offer": 0.63,
                    "policy_document": 0.41
                }
            }
        }

    def _find_similar_cases(self, extracted_info: ExtractedInfo) -> List[SimilarCase]:
        """Find similar historical cases"""
        similar_cases = []

        try:
            # Fallback to static DB matching
            for case in self.similar_cases_db:
                similarity_score = self._calculate_similarity(extracted_info, case)
                if similarity_score > 0.3:
                    similar_cases.append(SimilarCase(
                        case_id=case["case_id"],
                        similarity_score=round(similarity_score, 2),
                        outcome=f"Increased payout by ${case.get('final_payout', 0) - case.get('original_claim', 0)}",
                        payout_achieved=case.get('final_payout', 0),
                        strategy_used=case.get('strategy_used', 'Unknown'),
                        success_factors=case.get('key_factors', [])
                    ))
            
            similar_cases.sort(key=lambda x: x.similarity_score, reverse=True)
            return similar_cases[:5]

        except Exception as e:
            self.logger.warning(f"Error finding similar cases: {str(e)}")
            return []

    def _calculate_similarity(self, extracted_info: ExtractedInfo, historical_case: Dict) -> float:
        """Calculate similarity score between current case and historical case"""
        similarity_factors = []
        
        # Document type similarity
        if extracted_info.document_type.value == historical_case.get('document_type'):
            similarity_factors.append(0.3)
        
        # Policy type similarity (inferred from coverage types)
        current_policy_type = self._infer_policy_type(extracted_info)
        if current_policy_type == historical_case.get('policy_type'):
            similarity_factors.append(0.25)
        
        # Monetary amount similarity
        current_amounts = []
        for amt in extracted_info.monetary_amounts:
            try:
                amt_cleaned = amt.replace(",", "").replace("$", "").strip()
                if amt_cleaned:
                    current_amounts.append(float(amt_cleaned))
            except (ValueError, AttributeError):
                continue  # Skip malformed amounts

        if current_amounts and historical_case.get("original_claim"):
            avg_current = sum(current_amounts) / len(current_amounts)
            historical_amount = float(historical_case["original_claim"])
            amount_ratio = min(avg_current, historical_amount) / max(avg_current, historical_amount)
            similarity_factors.append(amount_ratio * 0.2)
        
        # Denial reason similarity (for denial letters)
        if (extracted_info.document_type.value == 'denial_letter' and 
            extracted_info.denial_reasons and historical_case.get('denial_reason')):
            if any(reason.lower() in historical_case['denial_reason'].lower() 
                   for reason in extracted_info.denial_reasons):
                similarity_factors.append(0.25)
        
        return sum(similarity_factors) if similarity_factors else 0.1

    def _infer_policy_type(self, extracted_info: ExtractedInfo) -> str:
        """Infer policy type from coverage types and other indicators"""
        coverage_types = [coverage.lower() for coverage in extracted_info.coverage_types]
        
        auto_indicators = ['collision', 'comprehensive', 'liability', 'uninsured motorist']
        home_indicators = ['property damage', 'dwelling', 'personal property', 'liability']
        health_indicators = ['medical', 'prescription', 'hospital', 'physician']
        
        auto_score = sum(1 for indicator in auto_indicators if any(indicator in coverage for coverage in coverage_types))
        home_score = sum(1 for indicator in home_indicators if any(indicator in coverage for coverage in coverage_types))
        health_score = sum(1 for indicator in health_indicators if any(indicator in coverage for coverage in coverage_types))
        
        if auto_score > home_score and auto_score > health_score:
            return 'auto'
        elif home_score > health_score:
            return 'home'
        else:
            return 'health'

    def _calculate_success_probability(self, extracted_info: ExtractedInfo, 
                                     similar_cases: List[SimilarCase]) -> float:
        """Calculate success probability based on multiple factors"""
        base_probability = 0.5
        
        # Historical case success rates
        if similar_cases:
            historical_avg = sum(case.similarity_score * 0.7 for case in similar_cases) / len(similar_cases)
            base_probability = (base_probability + historical_avg) / 2
        
        # Document type factor
        policy_type = self._infer_policy_type(extracted_info)
        if policy_type in self.industry_benchmarks:
            doc_type_success = self.industry_benchmarks[policy_type]['success_rate_by_type'].get(
                extracted_info.document_type.value, 0.5
            )
            base_probability = (base_probability + doc_type_success) / 2
        
        # Extraction confidence factor
        confidence_boost = (extracted_info.extraction_confidence - 0.5) * 0.2
        base_probability += confidence_boost
        
        # Documentation quality factor
        doc_quality_score = self._assess_documentation_quality(extracted_info)
        base_probability += doc_quality_score * 0.15
        
        # Ensure probability stays within bounds
        return max(0.1, min(0.95, base_probability))

    def _assess_documentation_quality(self, extracted_info: ExtractedInfo) -> float:
        """Assess quality of documentation"""
        quality_factors = []
        
        # Policy number presence
        if extracted_info.policy_details.get('policy_number'):
            quality_factors.append(0.2)
        
        # Monetary amounts clarity
        if extracted_info.monetary_amounts:
            quality_factors.append(0.2)
        
        # Date information
        if extracted_info.key_dates:
            quality_factors.append(0.15)
        
        # Parties involved
        if extracted_info.parties_involved:
            quality_factors.append(0.15)
        
        # Coverage types identified
        if extracted_info.coverage_types:
            quality_factors.append(0.15)
        
        # Specific details for document type
        if extracted_info.document_type.value == 'denial_letter' and extracted_info.denial_reasons:
            quality_factors.append(0.15)
        elif extracted_info.document_type.value == 'settlement_offer' and extracted_info.settlement_amounts:
            quality_factors.append(0.15)
        
        return sum(quality_factors)

    def _estimate_payout_range(self, extracted_info: ExtractedInfo, 
                              similar_cases: List[SimilarCase]) -> PayoutRange:
        """Estimate potential payout range"""
        # Get base amount from extracted monetary amounts
        base_amounts = []
        for amount_str in extracted_info.monetary_amounts:
            if isinstance(amount_str, str) and any(char.isdigit() for char in amount_str):
                cleaned = amount_str.replace(",", "").replace("$", "").strip()
                try:
                    base_amounts.append(float(cleaned))
                except ValueError:
                    continue  # Skip any non-numeric strings
        
        if not base_amounts:
            base_amounts = [1000]  # Default fallback
        
        base_amount = float(max(base_amounts)) if base_amounts else 1000.0
        
        # Calculate multipliers based on similar cases
        if similar_cases:
            improvement_ratios = []
            for case in similar_cases:
                if hasattr(case, 'payout_achieved') and case.payout_achieved > 0:
                    # Estimate original claim from context
                    estimated_original = case.payout_achieved * 0.7  # Assume 30% improvement
                    ratio = case.payout_achieved / estimated_original
                    improvement_ratios.append(ratio)
            
            if improvement_ratios:
                avg_improvement = sum(improvement_ratios) / len(improvement_ratios)
            else:
                avg_improvement = 1.3  # Default 30% improvement
        else:
            avg_improvement = 1.25  # Default 25% improvement
        
        # Calculate range
        minimum = base_amount * 1.05  # 5% minimum improvement
        expected = base_amount * avg_improvement
        maximum = base_amount * (avg_improvement * 1.5)  # Optimistic scenario
        
        # Confidence based on data quality
        confidence = (extracted_info.extraction_confidence + 
                     (0.8 if similar_cases else 0.3)) / 2
        
        return PayoutRange(
            minimum=round(minimum, 2),
            expected=round(expected, 2),
            maximum=round(maximum, 2),
            confidence=min(0.95, confidence)
        )

    def _identify_risk_factors(self, extracted_info: ExtractedInfo) -> List[str]:
        """Identify potential risk factors that could hurt the case"""
        risk_factors = []
        
        # Low extraction confidence
        if extracted_info.extraction_confidence < 0.6:
            risk_factors.append("Incomplete document information may weaken position")
        
        # Missing key information
        if not extracted_info.policy_details.get('policy_number'):
            risk_factors.append("Missing policy number complicates verification")
        
        if not extracted_info.monetary_amounts:
            risk_factors.append("No clear monetary amounts identified")
        
        # Document type specific risks
        if extracted_info.document_type.value == 'denial_letter':
            if not extracted_info.denial_reasons:
                risk_factors.append("Unclear denial reasons make counter-arguments difficult")
        
        # Timeline risks
        if not extracted_info.key_dates:
            risk_factors.append("Missing timeline information may indicate missed deadlines")
        
        return risk_factors

    def _identify_strength_factors(self, extracted_info: ExtractedInfo) -> List[str]:
        """Identify factors that strengthen the case"""
        strength_factors = []
        
        # High extraction confidence
        if extracted_info.extraction_confidence > 0.8:
            strength_factors.append("Clear, well-documented case with complete information")
        
        # Complete policy information
        if extracted_info.policy_details.get('policy_number') and extracted_info.policy_details.get('insurer'):
            strength_factors.append("Complete policy identification enables thorough review")
        
        # Clear monetary amounts
        if len(extracted_info.monetary_amounts) > 1:
            strength_factors.append("Multiple monetary references provide negotiation leverage")
        
        # Good documentation
        if extracted_info.parties_involved and extracted_info.key_dates:
            strength_factors.append("Well-documented timeline and parties support credibility")
        
        # Specific coverage types
        if extracted_info.coverage_types:
            strength_factors.append("Identified coverage types enable targeted policy analysis")
        
        return strength_factors

    def _get_market_comparisons(self, extracted_info: ExtractedInfo) -> Dict[str, Any]:
        """Get market comparison data"""
        policy_type = self._infer_policy_type(extracted_info)
        
        return {
            "policy_type": policy_type,
            "industry_average_increase": self.industry_benchmarks.get(policy_type, {}).get('average_settlement_increase', 0.3),
            "success_rate_benchmark": self.industry_benchmarks.get(policy_type, {}).get('success_rate_by_type', {}).get(
                extracted_info.document_type.value, 0.5
            ),
            "comparable_case_count": len(self.similar_cases_db),
            "market_conditions": "Favorable for consumer advocacy"
        }

    def _estimate_timeline(self, extracted_info: ExtractedInfo, success_probability: float) -> Dict[str, int]:
        """Estimate negotiation timeline"""
        base_days = 30
        
        # Document type affects timeline
        if extracted_info.document_type.value == 'denial_letter':
            base_days = 45
        elif extracted_info.document_type.value == 'settlement_offer':
            base_days = 21
        
        # Success probability affects timeline
        if success_probability > 0.7:
            multiplier = 0.8  # Easier cases resolve faster
        elif success_probability < 0.5:
            multiplier = 1.3  # Harder cases take longer
        else:
            multiplier = 1.0
        
        estimated_days = int(base_days * multiplier)
        
        return {
            "initial_response_days": min(7, estimated_days // 4),
            "negotiation_rounds": max(1, estimated_days // 15),
            "total_estimated_days": estimated_days,
            "maximum_timeline_days": estimated_days * 2
        }
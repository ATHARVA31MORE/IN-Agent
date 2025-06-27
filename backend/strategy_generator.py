import logging
from typing import Dict, List, Any
from models import ExtractedInfo, AnalysisResult, Strategy, StrategyApproach, NegotiationPlan, NegotiationRound
from sentence_transformers import SentenceTransformer
import chromadb
import json
from pathlib import Path

class StrategyGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.strategy_templates = self._load_strategy_templates()
        self.legal_precedents = self._load_legal_precedents()
        self.policy_clause_library = self._load_policy_clauses()
        
        # Initialize ChromaDB for similarity search
        self.chroma_client = chromadb.Client()
        self.similar_cases_collection = self.chroma_client.create_collection("similar_cases")
        self._load_similar_cases_to_chroma()
        
        # Initialize sentence transformer model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def _load_similar_cases_to_chroma(self):
        """Load similar cases into ChromaDB for similarity search"""
        try:
            cases = json.loads(Path("data/similar_cases.json").read_text())
            for idx, case in enumerate(cases):
                self.similar_cases_collection.add(
                    documents=[case["description"]],
                    metadatas=[{"strategy": case["strategy"], "outcome": case["outcome"]}],
                    ids=[str(idx)]
                )
        except Exception as e:
            self.logger.error(f"Error loading similar cases to ChromaDB: {str(e)}")

    def _find_similar_cases(self, text: str) -> List[Dict[str, Any]]:
        """Find similar cases using ChromaDB"""
        try:
            query_embedding = self.model.encode(text)
            results = self.similar_cases_collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=5
            )
            return [
                {
                    "strategy": results["metadatas"][0][i]["strategy"],
                    "outcome": results["metadatas"][0][i]["outcome"],
                    "document": results["documents"][0][i]
                }
                for i in range(len(results["ids"][0]))
            ]
        except Exception as e:
            self.logger.error(f"Error finding similar cases: {str(e)}")
            return []

    async def generate_strategy(self, extracted_info: ExtractedInfo, 
                              analysis: AnalysisResult) -> Strategy:
        """Generate optimal negotiation strategy"""
        try:
            # Select primary strategy approach
            approach = self._select_strategy_approach(extracted_info, analysis)
            
            # Get strategy template
            strategy_template = self._get_strategy_template(approach, extracted_info.document_type)
            
            # Identify leverage points
            leverage_points = self._identify_leverage_points(extracted_info, analysis)
            
            # Generate recommended actions
            recommended_actions = self._generate_recommended_actions(
                extracted_info, analysis, approach
            )
            
            # Find relevant legal precedents
            legal_precedents = self._find_relevant_precedents(extracted_info)
            
            # Identify applicable policy clauses
            policy_clauses = self._identify_policy_clauses(extracted_info)
            
            # Create negotiation plan
            negotiation_plan = self._create_negotiation_plan(
                extracted_info, analysis, approach
            )
            
            # Calculate strategy confidence
            confidence = self._calculate_strategy_confidence(
                extracted_info, analysis, leverage_points
            )
            
            return Strategy(
                name=strategy_template['name'],
                approach=approach,
                confidence=confidence,
                key_leverage_points=leverage_points,
                recommended_actions=recommended_actions,
                legal_precedents=legal_precedents,
                policy_clauses=policy_clauses,
                negotiation_plan=negotiation_plan
            )
            
        except Exception as e:
            self.logger.error(f"Error generating strategy: {str(e)}")
            raise

    def _load_strategy_templates(self) -> Dict[str, Any]:
        """Load strategy templates for different approaches"""
        return {
            StrategyApproach.AGGRESSIVE: {
                "denial_letter": {
                    "name": "Aggressive Policy Challenge",
                    "description": "Direct confrontation of denial with strong legal backing",
                    "tactics": ["immediate_escalation", "legal_threat", "deadline_pressure"]
                },
                "settlement_offer": {
                    "name": "Aggressive Counter-Offer",
                    "description": "Strong rejection with significantly higher counter-proposal",
                    "tactics": ["market_comparisons", "expert_valuations", "precedent_citing"]
                },
                "policy_document": {
                    "name": "Coverage Expansion Demand",
                    "description": "Aggressive interpretation of policy language",
                    "tactics": ["ambiguity_exploitation", "broad_interpretation", "industry_standards"]
                }
            },
            StrategyApproach.COLLABORATIVE: {
                "denial_letter": {
                    "name": "Collaborative Resolution",
                    "description": "Partnership approach to find mutually acceptable solution",
                    "tactics": ["information_sharing", "joint_problem_solving", "compromise_seeking"]
                },
                "settlement_offer": {
                    "name": "Collaborative Negotiation",
                    "description": "Working together to reach fair settlement",
                    "tactics": ["transparent_communication", "incremental_adjustments", "mutual_benefits"]
                },
                "policy_document": {
                    "name": "Cooperative Clarification",
                    "description": "Joint review of policy terms for mutual understanding",
                    "tactics": ["clarification_requests", "expert_consultation", "precedent_review"]
                }
            },
            StrategyApproach.DATA_DRIVEN: {
                "denial_letter": {
                    "name": "Evidence-Based Challenge",
                    "description": "Using data and documentation to overturn denial",
                    "tactics": ["statistical_analysis", "expert_reports", "documentation_review"]
                },
                "settlement_offer": {
                    "name": "Market Value Documentation",
                    "description": "Comprehensive data analysis to justify higher settlement",
                    "tactics": ["market_research", "comparable_analysis", "expert_appraisals"]
                },
                "policy_document": {
                    "name": "Analytical Policy Review",
                    "description": "Systematic analysis of policy terms and applications",
                    "tactics": ["clause_analysis", "precedent_research", "industry_comparisons"]
                }
            },
            StrategyApproach.LEGAL_THREAT: {
                "denial_letter": {
                    "name": "Legal Action Threat",
                    "description": "Escalation threat with legal consequences",
                    "tactics": ["regulatory_complaints", "lawsuit_preparation", "bad_faith_claims"]
                },
                "settlement_offer": {
                    "name": "Legal Leverage Strategy",
                    "description": "Using legal pressure to increase settlement",
                    "tactics": ["legal_precedents", "regulatory_citations", "attorney_involvement"]
                },
                "policy_document": {
                    "name": "Legal Interpretation Challenge",
                    "description": "Legal challenge to policy interpretation",
                    "tactics": ["case_law_citations", "regulatory_standards", "legal_opinions"]
                }
            },
            StrategyApproach.ASSERTIVE: {
                "denial_letter": {
                    "name": "Policy Interpretation Challenge",
                    "description": "Firm but professional challenge of denial reasoning",
                    "tactics": ["policy_analysis", "precedent_citing", "documentation_emphasis"]
                },
                "settlement_offer": {
                    "name": "Value Justification Strategy",
                    "description": "Clear demonstration of higher settlement value",
                    "tactics": ["damage_documentation", "cost_analysis", "market_comparisons"]
                },
                "policy_document": {
                    "name": "Coverage Scope Expansion",
                    "description": "Assertive interpretation of coverage scope",
                    "tactics": ["clause_interpretation", "industry_practices", "reasonable_expectations"]
                }
            }
        }

    def _load_legal_precedents(self) -> List[Dict[str, str]]:
        """Load legal precedent database"""
        return [
            {
                "case_name": "State Farm v. Campbell",
                "principle": "Insurer bad faith liability",
                "application": "Denial without reasonable investigation"
            },
            {
                "case_name": "Gruenberg v. Aetna Insurance",
                "principle": "Duty to settle within policy limits",
                "application": "Settlement offer negotiations"
            },
            {
                "case_name": "Gray v. Zurich Insurance",
                "principle": "Reasonable expectations doctrine",
                "application": "Policy interpretation disputes"
            }
        ]

    def _load_policy_clauses(self) -> Dict[str, List[str]]:
        """Load common policy clause interpretations"""
        return {
            "coverage_clauses": [
                "All risks coverage includes unlisted perils",
                "Occurrence-based triggers cover manifestation events",
                "Named perils require specific policy listing"
            ],
            "exclusion_clauses": [
                "Exclusions must be clear and unambiguous",
                "Ambiguous exclusions interpreted against insurer",
                "Exclusions cannot contradict coverage grants"
            ],
            "limits_clauses": [
                "Per-occurrence limits apply to single events",
                "Aggregate limits cap total policy payments",
                "Sub-limits may apply to specific coverage types"
            ]
        }

    def _select_strategy_approach(self, extracted_info: ExtractedInfo, 
                                analysis: AnalysisResult) -> StrategyApproach:
        """Select optimal strategy approach based on case characteristics"""
        
        # Scoring system for each approach
        approach_scores = {
            StrategyApproach.AGGRESSIVE: 0,
            StrategyApproach.COLLABORATIVE: 0,
            StrategyApproach.DATA_DRIVEN: 0,
            StrategyApproach.LEGAL_THREAT: 0,
            StrategyApproach.ASSERTIVE: 0
        }
        
        # Success probability influences approach
        if analysis.success_probability > 0.8:
            approach_scores[StrategyApproach.AGGRESSIVE] += 2
            approach_scores[StrategyApproach.ASSERTIVE] += 1
        elif analysis.success_probability > 0.6:
            approach_scores[StrategyApproach.ASSERTIVE] += 2
            approach_scores[StrategyApproach.DATA_DRIVEN] += 1
        else:
            approach_scores[StrategyApproach.COLLABORATIVE] += 2
            approach_scores[StrategyApproach.DATA_DRIVEN] += 1
        
        # Document type influences approach
        if extracted_info.document_type.value == 'denial_letter':
            approach_scores[StrategyApproach.ASSERTIVE] += 2
            if extracted_info.denial_reasons:
                approach_scores[StrategyApproach.DATA_DRIVEN] += 1
        elif extracted_info.document_type.value == 'settlement_offer':
            approach_scores[StrategyApproach.DATA_DRIVEN] += 2
            approach_scores[StrategyApproach.COLLABORATIVE] += 1
        
        # Extraction confidence influences approach
        if extracted_info.extraction_confidence > 0.8:
            approach_scores[StrategyApproach.DATA_DRIVEN] += 1
            approach_scores[StrategyApproach.ASSERTIVE] += 1
        
        # Risk factors influence approach
        if len(analysis.risk_factors) > 3:
            approach_scores[StrategyApproach.COLLABORATIVE] += 1
        elif len(analysis.risk_factors) < 2:
            approach_scores[StrategyApproach.AGGRESSIVE] += 1
        
        # Select approach with highest score
        return max(approach_scores, key=approach_scores.get)

    def _get_strategy_template(self, approach: StrategyApproach, 
                             document_type) -> Dict[str, Any]:
        """Get strategy template for approach and document type"""
        return self.strategy_templates[approach][document_type.value]

    def _identify_leverage_points(self, extracted_info: ExtractedInfo, 
                                analysis: AnalysisResult) -> List[str]:
        """Identify key leverage points for negotiation"""
        leverage_points = []
        
        # High-value similar cases
        if analysis.similar_cases:
            high_value_cases = [case for case in analysis.similar_cases 
                              if case.similarity_score > 0.7]
            if high_value_cases:
                leverage_points.append(f"Similar successful cases with {len(high_value_cases)} precedents")
        
        # Policy ambiguities
        if extracted_info.document_type.value == 'denial_letter' and extracted_info.denial_reasons:
            leverage_points.append("Questionable denial reasoning requires clarification")
        
        # Documentation quality
        if extracted_info.extraction_confidence > 0.8:
            leverage_points.append("Complete documentation supports claim validity")
        
        # Coverage scope issues
        if extracted_info.coverage_types:
            leverage_points.append("Multiple coverage types may provide alternative claim paths")
        
        # Timeline compliance
        if extracted_info.key_dates:
            leverage_points.append("Documented timeline shows compliance with policy requirements")
        
        # Market value discrepancies
        if extracted_info.document_type.value == 'settlement_offer':
            leverage_points.append("Settlement offer below market value standards")
        
        return leverage_points

    def _generate_recommended_actions(self, extracted_info: ExtractedInfo, 
                                    analysis: AnalysisResult, 
                                    approach: StrategyApproach) -> List[str]:
        """Generate specific recommended actions"""
        actions = []
        
        # Document-specific actions
        if extracted_info.document_type.value == 'denial_letter':
            actions.extend([
                "Request detailed explanation of denial reasoning",
                "Gather additional supporting documentation",
                "Review policy language for coverage confirmation"
            ])
        elif extracted_info.document_type.value == 'settlement_offer':
            actions.extend([
                "Obtain independent damage assessment",
                "Research comparable settlement amounts",
                "Document all loss-related expenses"
            ])
        
        # Approach-specific actions
        if approach == StrategyApproach.AGGRESSIVE:
            actions.extend([
                "Set firm deadlines for response",
                "Escalate to senior claims management",
                "Reference potential regulatory complaints"
            ])
        elif approach == StrategyApproach.DATA_DRIVEN:
            actions.extend([
                "Compile comprehensive evidence package",
                "Obtain expert opinions or appraisals",
                "Prepare statistical comparisons"
            ])
        elif approach == StrategyApproach.COLLABORATIVE:
            actions.extend([
                "Schedule discussion meeting",
                "Propose joint fact-finding process",
                "Explore creative resolution options"
            ])
        
        # Success probability based actions
        if analysis.success_probability > 0.7:
            actions.append("Proceed with confident negotiation stance")
        else:
            actions.append("Build stronger case foundation before major negotiations")
        
        return actions

    def _find_relevant_precedents(self, extracted_info: ExtractedInfo) -> List[str]:
        """Find relevant legal precedents"""
        relevant_precedents = []
        
        for precedent in self.legal_precedents:
            # Simple keyword matching - in production would use more sophisticated NLP
            if (extracted_info.document_type.value == 'denial_letter' and 
                'denial' in precedent['application'].lower()):
                relevant_precedents.append(f"{precedent['case_name']}: {precedent['principle']}")
            elif (extracted_info.document_type.value == 'settlement_offer' and 
                  'settlement' in precedent['application'].lower()):
                relevant_precedents.append(f"{precedent['case_name']}: {precedent['principle']}")
        
        return relevant_precedents

    def _identify_policy_clauses(self, extracted_info: ExtractedInfo) -> List[str]:
        """Identify relevant policy clauses"""
        relevant_clauses = []
        
        # Coverage-related clauses
        if extracted_info.coverage_types:
            relevant_clauses.extend(self.policy_clause_library['coverage_clauses'][:2])
        
        # Exclusion-related clauses (for denial letters)
        if extracted_info.document_type.value == 'denial_letter':
            relevant_clauses.extend(self.policy_clause_library['exclusion_clauses'][:2])
        
        # Limits-related clauses
        if extracted_info.monetary_amounts:
            relevant_clauses.extend(self.policy_clause_library['limits_clauses'][:1])
        
        return relevant_clauses

    def _create_negotiation_plan(self, extracted_info: ExtractedInfo, 
                               analysis: AnalysisResult, 
                               approach: StrategyApproach) -> NegotiationPlan:
        """Create detailed negotiation plan"""
        
        # Determine number of rounds based on complexity and success probability
        if analysis.success_probability > 0.8:
            total_rounds = 2
        elif analysis.success_probability > 0.6:
            total_rounds = 3
        else:
            total_rounds = 4
        
        rounds = []
        
        # Round 1: Initial Position
        rounds.append(NegotiationRound(
            round=1,
            objective="Present initial case and establish position",
            key_actions=[
                "Submit comprehensive initial response",
                "Present key evidence and documentation",
                "State desired outcome clearly"
            ],
            expected_outcome="Acknowledgment of case merit and engagement",
            timeline_days=7
        ))
        
        # Round 2: Evidence Phase
        if total_rounds >= 2:
            rounds.append(NegotiationRound(
                round=2,
                objective="Strengthen case with additional evidence",
                key_actions=[
                    "Provide supplemental documentation",
                    "Address any insurer concerns",
                    "Reference similar cases and precedents"
                ],
                expected_outcome="Movement toward settlement discussion",
                timeline_days=14
            ))
        
        # Round 3: Negotiation Phase
        if total_rounds >= 3:
            rounds.append(NegotiationRound(
                round=3,
                objective="Engage in active settlement negotiation",
                key_actions=[
                    "Present counter-offers",
                    "Negotiate specific terms",
                    "Explore compromise solutions"
                ],
                expected_outcome="Concrete settlement proposal",
                timeline_days=10
            ))
        
        # Round 4: Final Resolution
        if total_rounds >= 4:
            rounds.append(NegotiationRound(
                round=4,
                objective="Reach final resolution or escalate",
                key_actions=[
                    "Finalize settlement terms",
                    "Document agreement details",
                    "Prepare escalation if necessary"
                ],
                expected_outcome="Final settlement or escalation decision",
                timeline_days=7
            ))
        
        total_duration = sum(round.timeline_days for round in rounds)
        
        return NegotiationPlan(
            total_rounds=total_rounds,
            estimated_duration_days=total_duration,
            rounds=rounds
        )

    def _calculate_strategy_confidence(self, extracted_info: ExtractedInfo, 
                                     analysis: AnalysisResult, 
                                     leverage_points: List[str]) -> float:
        """Calculate confidence in the strategy"""
        confidence_factors = []
        
        # Base on analysis success probability
        confidence_factors.append(analysis.success_probability * 0.4)
        
        # Extraction quality
        confidence_factors.append(extracted_info.extraction_confidence * 0.2)
        
        # Number of leverage points
        leverage_score = min(len(leverage_points) / 5, 1.0) * 0.2
        confidence_factors.append(leverage_score)
        
        # Similar cases availability
        similar_cases_score = min(len(analysis.similar_cases) / 3, 1.0) * 0.1
        confidence_factors.append(similar_cases_score)
        
        # Risk vs strength factors
        risk_strength_ratio = len(analysis.strength_factors) / max(len(analysis.risk_factors), 1)
        risk_strength_score = min(risk_strength_ratio / 2, 1.0) * 0.1
        confidence_factors.append(risk_strength_score)
        
        # Document type specific factors
        if extracted_info.document_type.value == 'denial_letter':
            if len(extracted_info.denial_reasons) > 0:
                denial_reason_score = 0.1
            else:
                denial_reason_score = 0.05
            confidence_factors.append(denial_reason_score)
        elif extracted_info.document_type.value == 'settlement_offer':
            if len(extracted_info.settlement_amounts) > 0:
                settlement_amount_score = 0.1
            else:
                settlement_amount_score = 0.05
            confidence_factors.append(settlement_amount_score)
        else:
            confidence_factors.append(0.05)  # Default for other document types
        
        # Calculate final confidence score
        return min(sum(confidence_factors), 1.0)
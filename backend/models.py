from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    DENIAL_LETTER = "denial_letter"
    SETTLEMENT_OFFER = "settlement_offer"
    POLICY_DOCUMENT = "policy_document"
    CLAIM_FORM = "claim_form"
    CORRESPONDENCE = "correspondence"

class CaseStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class StrategyApproach(str, Enum):
    AGGRESSIVE = "aggressive"
    COLLABORATIVE = "collaborative"
    DATA_DRIVEN = "data_driven"
    LEGAL_THREAT = "legal_threat"
    ASSERTIVE = "assertive"

class ExtractedInfo(BaseModel):
    document_type: DocumentType
    extraction_confidence: float = Field(ge=0, le=1)
    policy_details: Dict[str, Any] = Field(default_factory=dict)
    claim_details: Dict[str, Any] = Field(default_factory=dict)
    monetary_amounts: List[str] = Field(default_factory=list)
    key_dates: List[str] = Field(default_factory=list)
    parties_involved: List[str] = Field(default_factory=list)
    coverage_types: List[str] = Field(default_factory=list)
    denial_reasons: List[str] = Field(default_factory=list)
    settlement_amounts: List[float] = Field(default_factory=list)

class PayoutRange(BaseModel):
    minimum: float
    expected: float
    maximum: float
    confidence: float = Field(ge=0, le=1)

class NegotiationRound(BaseModel):
    round: int
    objective: str
    key_actions: List[str]
    expected_outcome: str
    timeline_days: int

class NegotiationPlan(BaseModel):
    total_rounds: int
    estimated_duration_days: int
    rounds: List[NegotiationRound]

class Strategy(BaseModel):
    name: str
    approach: StrategyApproach
    confidence: float = Field(ge=0, le=1)
    key_leverage_points: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    legal_precedents: List[str] = Field(default_factory=list)
    policy_clauses: List[str] = Field(default_factory=list)
    negotiation_plan: Optional[NegotiationPlan] = None

class SimilarCase(BaseModel):
    case_id: str
    similarity_score: float = Field(ge=0, le=1)
    outcome: str
    payout_achieved: float
    strategy_used: str
    success_factors: List[str]

class AnalysisResult(BaseModel):
    success_probability: float = Field(ge=0, le=1)
    estimated_payout_range: PayoutRange
    risk_factors: List[str] = Field(default_factory=list)
    strength_factors: List[str] = Field(default_factory=list)
    similar_cases: List[SimilarCase] = Field(default_factory=list)
    market_comparisons: Dict[str, Any] = Field(default_factory=dict)
    timeline_estimate: Dict[str, int] = Field(default_factory=dict)

class CaseData(BaseModel):
    case_id: str
    claim_type: DocumentType
    policy_number: str
    success_probability: float = Field(ge=0, le=1)
    estimated_payout: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: CaseStatus
    extracted_info: ExtractedInfo
    analysis: AnalysisResult
    strategy: Strategy
    file_path: Optional[str] = None

class CaseResponse(BaseModel):
    case_id: str
    claim_type: DocumentType
    policy_number: str
    success_probability: float
    estimated_payout: float
    created_at: str
    status: CaseStatus
    extracted_info: ExtractedInfo
    analysis: AnalysisResult
    strategy: Strategy

class AnalysisRequest(BaseModel):
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    force_reanalysis: bool = False
    strategy_preference: Optional[StrategyApproach] = None

class LetterRequest(BaseModel):
    tone: Optional[str] = "professional"
    urgency_level: Optional[str] = "medium"
    include_legal_references: bool = True
    custom_points: List[str] = Field(default_factory=list)

class NegotiationLetter(BaseModel):
    subject: str
    body: str
    recipient: str
    sender_name: str
    policy_number: str
    case_id: str
    generated_at: datetime
    letter_type: str
    key_points: List[str]
    legal_references: List[str] = Field(default_factory=list)

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    components: Dict[str, str]
    version: str = "1.0.0"

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime
    case_id: Optional[str] = None
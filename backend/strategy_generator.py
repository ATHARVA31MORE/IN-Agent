import logging
import json
import os
import time
from typing import Dict, List, Any, Optional
from enum import Enum
import asyncio
import google.generativeai as genai
from models import ExtractedInfo, AnalysisResult, Strategy, StrategyApproach, NegotiationPlan, NegotiationRound

class AIProvider(Enum):
    GEMINI = "gemini"

class ModelStatus(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    GENERATING = "generating"

class OptimizedStrategyGenerator:
    def __init__(self, provider: str = "gemini"):
        self.logger = logging.getLogger(__name__)
        self.provider = AIProvider.GEMINI  # Only support Gemini now
        self.status = ModelStatus.INITIALIZING
        self.status_message = "Starting initialization..."
        
        # Get API key from environment
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Initialize Gemini client
        self.initialization_time = None
        self.last_generation_time = None
        
        # Load insurance domain knowledge for strategies
        self.insurance_knowledge = self._load_insurance_knowledge()
        
        # Initialize Gemini
        self._initialize_gemini()

    def get_status(self) -> Dict[str, Any]:
        """Get current model status and progress"""
        return {
            "status": self.status.value,
            "message": self.status_message,
            "provider": self.provider.value,
            "model_ready": self.status == ModelStatus.READY,
            "initialization_time": self.initialization_time,
            "last_generation_time": self.last_generation_time,
            "memory_usage": {"type": "api", "local_memory": False}
        }

    def _initialize_gemini(self):
        """Initialize Gemini API client"""
        start_time = time.time()
        
        try:
            self.status = ModelStatus.INITIALIZING
            self.status_message = "Configuring Gemini API..."
            
            # Configure Gemini
            genai.configure(api_key=self.api_key)
            
            # Initialize the model
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Test the connection
            self._test_generation()
            
            self.initialization_time = time.time() - start_time
            self.status = ModelStatus.READY
            self.status_message = f"Gemini API ready! Initialized in {self.initialization_time:.1f}s"
            
            self.logger.info(f"Successfully initialized Gemini API in {self.initialization_time:.1f}s")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini API: {str(e)}")
            self.status = ModelStatus.ERROR
            self.status_message = f"Failed to initialize Gemini: {str(e)}"

    def _test_generation(self):
        """Test Gemini API to ensure it's working"""
        try:
            test_prompt = "Generate a brief test strategy response:"
            response = self.model.generate_content(test_prompt)
            if response.text:
                self.logger.info("Gemini API test generation successful")
            else:
                raise Exception("Empty response from Gemini API")
        except Exception as e:
            self.logger.error(f"Gemini API test failed: {str(e)}")
            raise

    def _load_insurance_knowledge(self) -> Dict[str, Any]:
        """Load insurance domain knowledge for AI context"""
        return {
            "legal_principles": [
                "Duty of good faith and fair dealing",
                "Reasonable expectations doctrine", 
                "Contra proferentem (ambiguity against drafter)",
                "Estoppel and waiver principles"
            ],
            "negotiation_tactics": [
                "Documentation requests",
                "Policy interpretation challenges",
                "Precedent citations",
                "Market value comparisons",
                "Timeline pressure"
            ],
            "common_denial_reasons": [
                "Policy exclusions",
                "Coverage limitations", 
                "Insufficient documentation",
                "Pre-existing conditions",
                "Late reporting"
            ]
        }

    async def generate_strategy(self, extracted_info: ExtractedInfo, 
                              analysis: AnalysisResult, 
                              timeout: int = 30) -> Strategy:
        """Generate strategy with timeout and status tracking"""
        
        # Check if API is ready
        if self.status != ModelStatus.READY:
            if self.status == ModelStatus.ERROR:
                self.logger.warning("Gemini API failed to initialize, using fallback strategy")
                return self._create_fallback_strategy(extracted_info, analysis)
            else:
                self.logger.info(f"Gemini API not ready (status: {self.status.value}), waiting...")
                # Wait for API to be ready (with timeout)
                wait_time = 0
                while self.status != ModelStatus.READY and wait_time < timeout:
                    await asyncio.sleep(1)
                    wait_time += 1
                
                if self.status != ModelStatus.READY:
                    self.logger.warning(f"Gemini API not ready after {timeout}s, using fallback")
                    return self._create_fallback_strategy(extracted_info, analysis)
        
        try:
            self.status = ModelStatus.GENERATING
            self.status_message = "Generating strategy with Gemini..."
            start_time = time.time()
            
            # Create prompt
            strategy_prompt = self._create_strategy_prompt(extracted_info, analysis)
            
            # Generate with timeout
            strategy_response = await asyncio.wait_for(
                self._generate_gemini_strategy(strategy_prompt),
                timeout=timeout
            )
            
            # Parse response
            strategy = self._parse_strategy_response(strategy_response, extracted_info, analysis)
            
            self.last_generation_time = time.time() - start_time
            self.status = ModelStatus.READY
            self.status_message = f"Strategy generated in {self.last_generation_time:.1f}s"
            
            return strategy
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Strategy generation timed out after {timeout}s")
            self.status = ModelStatus.READY
            self.status_message = "Generation timed out, using fallback"
            return self._create_fallback_strategy(extracted_info, analysis)
        except Exception as e:
            self.logger.error(f"Error generating Gemini strategy: {str(e)}")
            self.status = ModelStatus.READY
            self.status_message = f"Generation error: {str(e)}"
            return self._create_fallback_strategy(extracted_info, analysis)

    def _create_strategy_prompt(self, extracted_info: ExtractedInfo, 
                               analysis: AnalysisResult) -> str:
        """Create optimized prompt for Gemini strategy generation"""
        
        # Handle dict vs object access
        if isinstance(extracted_info, dict):
            document_type = extracted_info.get('document_type', 'UNKNOWN')
            policy_details = extracted_info.get('policy_details', {})
            coverage_types = extracted_info.get('coverage_types', [])
            monetary_amounts = extracted_info.get('monetary_amounts', [])
            denial_reasons = extracted_info.get('denial_reasons', [])
        else:
            document_type = extracted_info.document_type.value if hasattr(extracted_info.document_type, 'value') else str(extracted_info.document_type)
            policy_details = extracted_info.policy_details
            coverage_types = extracted_info.coverage_types
            monetary_amounts = extracted_info.monetary_amounts
            denial_reasons = extracted_info.denial_reasons or []

        if isinstance(analysis, dict):
            success_probability = analysis.get('success_probability', 0)
            strength_factors = analysis.get('strength_factors', [])
            risk_factors = analysis.get('risk_factors', [])
        else:
            success_probability = analysis.success_probability
            strength_factors = analysis.strength_factors
            risk_factors = analysis.risk_factors
        
        # Create comprehensive prompt for Gemini
        prompt = f"""You are an expert insurance negotiation strategist. Create a detailed negotiation strategy in JSON format based on the following case details:

CASE DETAILS:
- Document Type: {document_type}
- Policy Number: {policy_details.get('policy_number', 'Not provided')}
- Insurance Company: {policy_details.get('insurer', 'Insurance Company')}
- Success Probability: {success_probability}%
- Coverage Types: {', '.join(coverage_types[:3]) if coverage_types else 'General coverage'}
- Claim Amount: {', '.join(map(str, monetary_amounts[:2])) if monetary_amounts else 'Under review'}
- Denial Reasons (if applicable): {', '.join(denial_reasons[:2]) if denial_reasons else 'None provided'}

STRENGTHS: {', '.join(strength_factors[:3]) if strength_factors else 'None identified'}
RISKS: {', '.join(risk_factors[:2]) if risk_factors else 'None identified'}

REQUIREMENTS:
1. Generate a complete negotiation strategy in JSON format
2. Include strategy name, approach, confidence score
3. List key leverage points (3-5 items)
4. Provide recommended actions (3-5 items)
5. Include relevant legal precedents (2-3 items)
6. Reference specific policy clauses (2-3 items)
7. Create a basic negotiation plan with 2-3 rounds
8. Use professional but assertive language

LEGAL PRINCIPLES TO CONSIDER:
- Duty of good faith and fair dealing
- Reasonable expectations doctrine
- Contra proferentem principle
- State insurance regulations

OUTPUT FORMAT:
{{
    "strategy_name": "Strategic approach name",
    "approach": "ASSERTIVE|COLLABORATIVE|AGGRESSIVE",
    "confidence": 0.0-1.0,
    "key_leverage_points": ["point1", "point2", "point3"],
    "recommended_actions": ["action1", "action2", "action3"],
    "legal_precedents": ["precedent1", "precedent2"],
    "policy_clauses": ["clause1", "clause2"],
    "negotiation_plan": {{
        "total_rounds": 2,
        "estimated_duration_days": 14,
        "rounds": [
            {{
                "round": 1,
                "objective": "Initial presentation",
                "key_actions": ["action1", "action2"],
                "expected_outcome": "Response received",
                "timeline_days": 7
            }},
            {{
                "round": 2,
                "objective": "Final negotiation",
                "key_actions": ["action1", "action2"],
                "expected_outcome": "Settlement",
                "timeline_days": 7
            }}
        ]
    }}
}}

Please generate the strategy now:"""
        
        return prompt

    async def _generate_gemini_strategy(self, prompt: str) -> str:
        """Generate strategy using Gemini API with async wrapper"""
        
        def generate_sync():
            try:
                # Configure generation parameters
                generation_config = genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=1000,
                    stop_sequences=None
                )
                
                # Generate content
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                if not response.text:
                    raise Exception("Empty response from Gemini API")
                
                self.logger.info(f"Generated strategy response length: {len(response.text)}")
                return response.text
                
            except Exception as e:
                self.logger.error(f"Gemini API strategy generation error: {str(e)}")
                raise
        
        # Run in thread to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, generate_sync)
        return response

    def _parse_strategy_response(self, ai_response: str, extracted_info: ExtractedInfo, 
                                analysis: AnalysisResult) -> Strategy:
        """Parse AI response with better error handling"""
        try:
            # Clean response
            cleaned_response = ai_response.strip()
            
            # Extract JSON
            start_idx = cleaned_response.find('{')
            end_idx = cleaned_response.rfind('}')
            
            if start_idx == -1 or end_idx == -1:
                self.logger.warning("No JSON found in response")
                return self._create_fallback_strategy(extracted_info, analysis)
            
            json_str = cleaned_response[start_idx:end_idx+1]
            
            try:
                strategy_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON parse error: {str(e)}")
                return self._create_fallback_strategy(extracted_info, analysis)
            
            # Convert to Strategy object with defaults
            approach_str = strategy_data.get("approach", "ASSERTIVE")
            try:
                approach = StrategyApproach(approach_str)
            except ValueError:
                approach = StrategyApproach.ASSERTIVE
            
            # Create negotiation plan from response or use default
            if "negotiation_plan" in strategy_data:
                np_data = strategy_data["negotiation_plan"]
                rounds = [
                    NegotiationRound(
                        round=round_data["round"],
                        objective=round_data.get("objective", ""),
                        key_actions=round_data.get("key_actions", []),
                        expected_outcome=round_data.get("expected_outcome", ""),
                        timeline_days=round_data.get("timeline_days", 7)
                    )
                    for round_data in np_data.get("rounds", [])
                ]
                
                negotiation_plan = NegotiationPlan(
                    total_rounds=np_data.get("total_rounds", 2),
                    estimated_duration_days=np_data.get("estimated_duration_days", 14),
                    rounds=rounds
                )
            else:
                # Fallback plan
                negotiation_plan = NegotiationPlan(
                    total_rounds=2,
                    estimated_duration_days=14,
                    rounds=[
                        NegotiationRound(
                            round=1,
                            objective="Present case",
                            key_actions=["Submit documentation", "Present arguments"],
                            expected_outcome="Initial response",
                            timeline_days=7
                        ),
                        NegotiationRound(
                            round=2,
                            objective="Negotiate settlement",
                            key_actions=["Address concerns", "Finalize agreement"],
                            expected_outcome="Settlement",
                            timeline_days=7
                        )
                    ]
                )
            
            return Strategy(
                name=strategy_data.get("strategy_name", "AI Generated Strategy"),
                approach=approach,
                confidence=float(strategy_data.get("confidence", 0.7)),
                key_leverage_points=strategy_data.get("key_leverage_points", []),
                recommended_actions=strategy_data.get("recommended_actions", []),
                legal_precedents=strategy_data.get("legal_precedents", []),
                policy_clauses=strategy_data.get("policy_clauses", []),
                negotiation_plan=negotiation_plan
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing strategy: {str(e)}")
            return self._create_fallback_strategy(extracted_info, analysis)

    def _create_fallback_strategy(self, extracted_info: ExtractedInfo, 
                                analysis: AnalysisResult) -> Strategy:
        """Fast fallback strategy"""
        return Strategy(
            name="Standard Negotiation Strategy",
            approach=StrategyApproach.ASSERTIVE,
            confidence=0.65,
            key_leverage_points=[
                "Policy coverage interpretation",
                "Documentation evidence",
                "Legal precedent support"
            ],
            recommended_actions=[
                "Submit comprehensive documentation",
                "Request detailed policy interpretation",
                "Escalate to senior claims handler",
                "Reference applicable legal standards"
            ],
            legal_precedents=[
                "Duty of good faith",
                "Reasonable expectations doctrine"
            ],
            policy_clauses=[
                "Coverage scope interpretation",
                "Exclusion clarity requirements"
            ],
            negotiation_plan=NegotiationPlan(
                total_rounds=2,
                estimated_duration_days=14,
                rounds=[
                    NegotiationRound(
                        round=1,
                        objective="Present case",
                        key_actions=["Submit documentation", "Present arguments"],
                        expected_outcome="Initial response",
                        timeline_days=7
                    ),
                    NegotiationRound(
                        round=2,
                        objective="Negotiate settlement",
                        key_actions=["Address concerns", "Finalize agreement"],
                        expected_outcome="Settlement",
                        timeline_days=7
                    )
                ]
            )
        )

    def cleanup(self):
        """Clean up resources (minimal for API-based approach)"""
        try:
            self.status = ModelStatus.INITIALIZING
            self.status_message = "Cleaning up..."
            self.logger.info("Strategy generation API resources cleaned up")
        except Exception as e:
            self.logger.error(f"Error during strategy generator cleanup: {str(e)}")

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()

# For backward compatibility
AIStrategyGenerator = OptimizedStrategyGenerator
HuggingFaceStrategyGenerator = OptimizedStrategyGenerator
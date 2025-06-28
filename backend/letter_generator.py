import logging
import os
import time
from typing import Dict, Any
from datetime import datetime
import asyncio
import google.generativeai as genai
from enum import Enum

class AIProvider(Enum):
    GEMINI = "gemini"

class ModelStatus(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    GENERATING = "generating"

class OptimizedLetterGenerator:
    def __init__(self, provider: str = "gemini"):
        self.logger = logging.getLogger(__name__)
        self.provider = AIProvider.GEMINI
        self.status = ModelStatus.INITIALIZING
        self.status_message = "Starting initialization..."
        
        # Get API key from environment
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Initialize Gemini client
        self.initialization_time = None
        self.last_generation_time = None
        self._initialize_gemini()

    def get_status(self) -> Dict[str, Any]:
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
        start_time = time.time()
        try:
            self.status = ModelStatus.INITIALIZING
            self.status_message = "Configuring Gemini API..."
            
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
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
        try:
            test_prompt = "Write a brief professional letter opening:"
            response = self.model.generate_content(test_prompt)
            if not response.text:
                raise Exception("Empty response from Gemini API")
            self.logger.info("Gemini API test generation successful")
        except Exception as e:
            self.logger.error(f"Gemini API test failed: {str(e)}")
            raise

    async def generate_letter(self, case_data: Dict[str, Any], timeout: int = 30) -> str:
        if self.status != ModelStatus.READY:
            if self.status == ModelStatus.ERROR:
                self.logger.warning("Gemini API failed, using fallback letter")
                return self._create_fallback_letter(case_data)
            else:
                self.logger.info(f"Gemini API not ready (status: {self.status.value}), waiting...")
                wait_time = 0
                while self.status != ModelStatus.READY and wait_time < timeout:
                    await asyncio.sleep(1)
                    wait_time += 1
                
                if self.status != ModelStatus.READY:
                    self.logger.warning(f"Gemini API not ready after {timeout}s, using fallback")
                    return self._create_fallback_letter(case_data)
        
        try:
            self.status = ModelStatus.GENERATING
            self.status_message = "Generating letter with Gemini..."
            start_time = time.time()
            
            letter_prompt = self._create_letter_prompt(case_data)
            letter_response = await asyncio.wait_for(
                self._generate_gemini_letter(letter_prompt),
                timeout=timeout
            )
            
            formatted_letter = self._format_letter(letter_response, case_data)
            
            self.last_generation_time = time.time() - start_time
            self.status = ModelStatus.READY
            self.status_message = f"Letter generated in {self.last_generation_time:.1f}s"
            
            return formatted_letter
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Letter generation timed out after {timeout}s")
            self.status = ModelStatus.READY
            self.status_message = "Generation timed out, using fallback"
            return self._create_fallback_letter(case_data)
        except Exception as e:
            self.logger.error(f"Error generating Gemini letter: {str(e)}")
            self.status = ModelStatus.READY
            self.status_message = f"Generation error: {str(e)}"
            return self._create_fallback_letter(case_data)

    def _create_letter_prompt(self, case_data: Dict[str, Any]) -> str:
        extracted_info = case_data.get('extracted_info', {})
        analysis = case_data.get('analysis', {})
        strategy = case_data.get('strategy', {})
        
        # Extract key information with fallbacks
        policy_number = extracted_info.get('policy_details', {}).get('policy_number', 'H567891234')
        insurer = extracted_info.get('policy_details', {}).get('insurer', 'Insurance Company')
        claim_amount = self._get_primary_amount(extracted_info.get('monetary_amounts', ['$1,250']))
        
        # Get analysis factors
        strengths = analysis.get('strength_factors', [
            "Policy coverage clearly applies to this type of incident",
            "All documentation has been provided in accordance with policy requirements"
        ])
        
        # Get strategy points
        leverage_points = strategy.get('key_leverage_points', [
            "The settlement amount does not reflect the actual damages incurred",
            "Based on similar cases and industry standards"
        ])
        
        # Get similar cases info
        similar_cases = analysis.get('similar_cases', [])
        similar_case_ref = ""
        if similar_cases:
            similar_case_ref = (
                f"Reference Case {similar_cases[0].get('case_id', 'HIST_001')} "
                f"achieved ${similar_cases[0].get('payout_achieved', 1250)} "
                f"using {similar_cases[0].get('strategy_used', 'Policy Interpretation')}"
            )

        prompt = f"""You are an expert insurance claims negotiator. Generate a professional negotiation letter with this exact structure:

**Required Format:**
Subject: Re: Claim Review - {policy_number}

Dear Claims Adjuster,

[Opening paragraph: State purpose and policy reference]
I am writing regarding my insurance claim for Policy #{policy_number}.

[Body paragraph 1: State your position with analysis]
After careful review of the policy terms and claim details, I believe there are several important factors that warrant reconsideration:

[Bullet points of key arguments - include 3-5 of these]
- {strengths[0] if len(strengths) > 0 else "Policy coverage applies to this incident"}
- {strengths[1] if len(strengths) > 1 else "Complete documentation has been provided"}
- {leverage_points[0] if len(leverage_points) > 0 else "Settlement doesn't reflect damages"}
- {similar_case_ref if similar_case_ref else "Industry standards support higher valuation"}

[Body paragraph 2: Specific request with analysis]
Based on the evidence and comparable cases, I believe a fair settlement would be in the range of {claim_amount}.

[Closing paragraph: Call to action]
I have attached supporting documentation and would welcome the opportunity to discuss this matter further. Please respond by [date 14 days from today].

Sincerely,
[Your Name]

**Key Requirements:**
1. Use EXACTLY this structure and formatting
2. Maintain professional but firm tone
3. Keep letter concise (150-250 words)
4. Include all bullet points exactly as shown
5. Reference specific policy terms when possible
6. Incorporate analysis data naturally
7. End with clear call to action and timeline
8. Do NOT include any additional text outside the letter structure"""

        return prompt

    def _get_primary_amount(self, amounts: list) -> str:
        """Extract and format the primary monetary amount"""
        if not amounts:
            return "$1,250"
        
        # Clean and find highest amount
        cleaned_amounts = []
        for amt in amounts:
            try:
                cleaned = amt.replace(",", "").replace("$", "").strip()
                if cleaned:
                    cleaned_amounts.append(float(cleaned))
            except (ValueError, AttributeError):
                continue
        
        if not cleaned_amounts:
            return "$1,250"
        
        max_amount = max(cleaned_amounts)
        return f"${max_amount:,.2f}"

    async def _generate_gemini_letter(self, prompt: str) -> str:
        def generate_sync():
            try:
                generation_config = genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=800,
                    stop_sequences=None
                )
                
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                if not response.text:
                    raise Exception("Empty response from Gemini API")
                
                return response.text
                
            except Exception as e:
                self.logger.error(f"Gemini API letter generation error: {str(e)}")
                raise
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, generate_sync)

    def _format_letter(self, letter_content: str, case_data: Dict[str, Any]) -> str:
        try:
            cleaned = letter_content.strip()
            
            # Ensure proper subject line
            policy_number = case_data.get('extracted_info', {}).get('policy_details', {}).get('policy_number', 'H567891234')
            if not cleaned.startswith(f"Subject: Re: Claim Review - {policy_number}"):
                cleaned = f"Subject: Re: Claim Review - {policy_number}\n\n{cleaned}"
            
            # Ensure proper closing
            if not any(closing in cleaned.lower() for closing in ["sincerely", "regards"]):
                cleaned += "\n\nSincerely,\n[Your Name]"
            
            return cleaned
            
        except Exception as e:
            self.logger.error(f"Error formatting letter: {str(e)}")
            return self._create_fallback_letter(case_data)

    def _create_fallback_letter(self, case_data: Dict[str, Any]) -> str:
        policy_details = case_data.get('extracted_info', {}).get('policy_details', {})
        analysis = case_data.get('analysis', {})
        today = datetime.now().strftime('%B %d, %Y')
        policy_number = policy_details.get('policy_number', 'H567891234')
        
        return f"""Subject: Re: Claim Review - {policy_number}

Dear Claims Adjuster,

I am writing regarding my insurance claim for Policy #{policy_number}.

After careful review of the policy terms and claim details, I believe there are several important factors that warrant reconsideration:

- Policy coverage clearly applies to this type of incident
- All documentation has been provided in accordance with policy requirements
- The settlement amount does not reflect the actual damages incurred

Based on similar cases and industry standards, I believe a fair settlement would be in the range of $1,250.

I have attached supporting documentation and would welcome the opportunity to discuss this matter further. Please respond by {today}.

Sincerely,
[Your Name]"""

# For backward compatibility
AILetterGenerator = OptimizedLetterGenerator
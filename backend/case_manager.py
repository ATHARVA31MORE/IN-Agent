import logging
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from models import CaseData, ExtractedInfo, AnalysisResult, Strategy, CaseStatus

class CaseManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cases_db_path = "data/cases.json"
        self.cases = {}
        self._load_cases()

    def _load_cases(self):
        """Load cases from JSON file if it exists"""
        try:
            if os.path.exists(self.cases_db_path):
                with open(self.cases_db_path, 'r') as f:
                    cases_data = json.load(f)
                    self.cases = cases_data
                self.logger.info(f"Loaded {len(self.cases)} cases from database")
            else:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(self.cases_db_path), exist_ok=True)
                self.cases = {}
                self._save_cases()
                self.logger.info("Created new cases database")
        except Exception as e:
            self.logger.error(f"Error loading cases: {str(e)}")
            self.cases = {}

    def _save_cases(self):
        """Save cases to JSON file"""
        try:
            with open(self.cases_db_path, 'w') as f:
                json.dump(self.cases, f, default=self._json_serializer, indent=2)
            self.logger.info(f"Saved {len(self.cases)} cases to database")
        except Exception as e:
            self.logger.error(f"Error saving cases: {str(e)}")

    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
            return obj.dict()
        raise TypeError(f"Type {type(obj)} not serializable")

    async def create_case(self, case_id: str, extracted_info: ExtractedInfo, 
                        analysis: AnalysisResult, strategy: Strategy) -> Dict[str, Any]:
        """Create a new case"""
        try:
            # Extract policy number from extracted info if available
            policy_number = "Unknown"
            if extracted_info.policy_details and "policy_number" in extracted_info.policy_details:
                policy_number = extracted_info.policy_details["policy_number"]

            # Create case data
            case_data = CaseData(
                case_id=case_id,
                claim_type=extracted_info.document_type,
                policy_number=policy_number,
                success_probability=analysis.success_probability,
                estimated_payout=analysis.estimated_payout_range.expected,
                created_at=datetime.now(),
                status=CaseStatus.ACTIVE,
                extracted_info=extracted_info,
                analysis=analysis,
                strategy=strategy
            )

            # Convert to dict for storage
            case_dict = case_data.dict()
            self.cases[case_id] = case_dict
            self._save_cases()

            self.logger.info(f"Created new case: {case_id}")
            return case_dict

        except Exception as e:
            self.logger.error(f"Error creating case: {str(e)}")
            raise

    async def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get case by ID"""
        try:
            if case_id in self.cases:
                return self.cases[case_id]
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving case {case_id}: {str(e)}")
            raise

    async def get_all_cases(self) -> List[Dict[str, Any]]:
        """Get all cases"""
        try:
            return list(self.cases.values())
        except Exception as e:
            self.logger.error(f"Error retrieving all cases: {str(e)}")
            raise

    async def update_case(self, case_id: str, analysis: Optional[AnalysisResult] = None, 
                        strategy: Optional[Strategy] = None) -> Dict[str, Any]:
        """Update case with new analysis and/or strategy"""
        try:
            if case_id not in self.cases:
                raise ValueError(f"Case {case_id} not found")

            case = self.cases[case_id]
            
            # Update analysis if provided
            if analysis:
                case["analysis"] = analysis.dict()
                case["success_probability"] = analysis.success_probability
                case["estimated_payout"] = analysis.estimated_payout_range.expected
            
            # Update strategy if provided
            if strategy:
                case["strategy"] = strategy.dict()
            
            # Update timestamp
            case["updated_at"] = datetime.now().isoformat()
            
            self._save_cases()
            self.logger.info(f"Updated case: {case_id}")
            
            return case

        except Exception as e:
            self.logger.error(f"Error updating case {case_id}: {str(e)}")
            raise

    async def delete_case(self, case_id: str) -> bool:
        """Delete a case"""
        try:
            if case_id in self.cases:
                del self.cases[case_id]
                self._save_cases()
                self.logger.info(f"Deleted case: {case_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting case {case_id}: {str(e)}")
            raise

    async def update_case_status(self, case_id: str, status: CaseStatus) -> Dict[str, Any]:
        """Update case status"""
        try:
            if case_id not in self.cases:
                raise ValueError(f"Case {case_id} not found")

            case = self.cases[case_id]
            case["status"] = status.value
            case["updated_at"] = datetime.now().isoformat()
            
            self._save_cases()
            self.logger.info(f"Updated status for case {case_id} to {status.value}")
            
            return case

        except Exception as e:
            self.logger.error(f"Error updating status for case {case_id}: {str(e)}")
            raise
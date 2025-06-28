from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import uvicorn
from datetime import datetime
import os
import io
from typing import Dict, Any
import tempfile
from dotenv import load_dotenv

load_dotenv()

from document_processor import DocumentProcessor
from analysis_engine import AnalysisEngine
from strategy_generator import OptimizedStrategyGenerator
from letter_generator import OptimizedLetterGenerator
from case_manager import CaseManager
from models import (
    CaseResponse, AnalysisRequest, DocumentType, StrategyApproach, 
    CaseStatus, LetterRequest, HealthCheck, ErrorResponse
)

print("=== Environment Variables Debug ===")
print(f"GEMINI_API_KEY: {'set' if os.getenv('GEMINI_API_KEY') else 'not set'}")

# Initialize AI components with Gemini
try:
    strategy_generator = OptimizedStrategyGenerator(provider="gemini")
    letter_generator = OptimizedLetterGenerator(provider="gemini")
    print("Successfully initialized Gemini-powered AI components")
except Exception as e:
    print(f"Error initializing AI components: {str(e)}")
    raise RuntimeError(f"Failed to initialize AI components: {str(e)}")

app = FastAPI(title="AI Insurance Negotiation Agent", version="2.2.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000", 
        "http://localhost:5173", 
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories if they don't exist
os.makedirs("generated_letters", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("temp", exist_ok=True)

# Initialize components
document_processor = DocumentProcessor()
analysis_engine = AnalysisEngine()
case_manager = CaseManager()

@app.get("/")
async def root():
    return {
        "message": "AI Insurance Negotiation Agent API", 
        "status": "active",
        "version": "2.2.0 - Gemini API",
        "ai_provider": "gemini",
        "endpoints": {
            "upload": "/api/upload",
            "cases": "/api/cases",
            "health": "/api/health",
            "ai_status": "/api/ai-status"
        }
    }

@app.get("/api/ai-status")
async def get_ai_status():
    """Get AI model status and performance metrics"""
    try:
        strategy_status = strategy_generator.get_status()
        letter_status = letter_generator.get_status()
        
        return {
            "strategy_generator": strategy_status,
            "letter_generator": letter_status,
            "overall_status": "ready" if (
                strategy_status["model_ready"] and letter_status["model_ready"]
            ) else "loading"
        }
    except Exception as e:
        return {
            "error": str(e),
            "overall_status": "error"
        }

@app.post("/api/upload", response_model=CaseResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload and process insurance document"""
    temp_file_path = None
    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Create temporary file
        temp_file_path = os.path.join("temp", f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        
        # Save uploaded file
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Extract information from document
        extracted_info = await document_processor.extract_information(temp_file_path)
        
        # Analyze case
        analysis_result = await analysis_engine.analyze_case(extracted_info)
        
        # Generate strategy using Gemini API
        strategy = await strategy_generator.generate_strategy(
            extracted_info, 
            analysis_result, 
            timeout=30
        )

        # Create case
        case_id = f"CASE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        case_data = await case_manager.create_case(
            case_id=case_id,
            extracted_info=extracted_info,
            analysis=analysis_result,
            strategy=strategy
        )

        # Convert datetime to string for JSON response
        if isinstance(case_data.get("created_at"), datetime):
            case_data["created_at"] = case_data["created_at"].isoformat()
        
        # Add AI-generated insights to response with model status
        ai_status = strategy_generator.get_status()
        case_data["ai_insights"] = {
            "strategy_confidence": strategy.confidence,
            "key_leverage_points": len(strategy.key_leverage_points),
            "negotiation_rounds": strategy.negotiation_plan.total_rounds if strategy.negotiation_plan else 0,
            "estimated_timeline": strategy.negotiation_plan.estimated_duration_days if strategy.negotiation_plan else 0,
            "approach": strategy.approach.value,
            "generation_time": ai_status.get("last_generation_time"),
            "model_provider": "gemini"
        }
        
        return CaseResponse(**case_data)

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR UPLOAD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                print(f"Warning: Could not remove temp file {temp_file_path}: {str(e)}")

@app.get("/api/cases")
async def get_cases():
    """Get all cases with summary information"""
    try:
        cases = await case_manager.get_all_cases()
        
        # Add summary statistics
        summary = {
            "total_cases": len(cases),
            "active_cases": len([c for c in cases if c.get("status") == CaseStatus.ACTIVE.value]),
            "completed_cases": len([c for c in cases if c.get("status") == CaseStatus.COMPLETED.value]),
            "total_estimated_value": sum(c.get("estimated_payout", 0) for c in cases),
            "average_success_probability": sum(c.get("success_probability", 0) for c in cases) / len(cases) if cases else 0
        }
        
        return {
            "cases": cases,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cases: {str(e)}")

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """Get specific case details"""
    try:
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Add additional metadata
        case["metadata"] = {
            "case_age_days": (datetime.now() - datetime.fromisoformat(case["created_at"].replace("Z", "+00:00"))).days if case.get("created_at") else 0,
            "has_strategy": bool(case.get("strategy")),
            "has_analysis": bool(case.get("analysis")),
            "document_type": case.get("extracted_info", {}).get("document_type", "unknown")
        }
        
        return case
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve case: {str(e)}")

@app.post("/api/cases/{case_id}/letter")
async def generate_negotiation_letter(case_id: str, letter_request: LetterRequest = None):
    """Generate AI-powered negotiation letter for case"""
    try:
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Generate letter using Gemini API
        letter_content = await letter_generator.generate_letter(
            case, 
            timeout=30
        )
        
        # Get letter generation status
        letter_status = letter_generator.get_status()
        
        return {
            "case_id": case_id,
            "letter": letter_content,
            "generated_at": datetime.now().isoformat(),
            "letter_metadata": {
                "word_count": len(letter_content.split()),
                "has_policy_references": "policy" in letter_content.lower(),
                "has_legal_references": any(term in letter_content.lower() for term in ["precedent", "legal", "court", "law"]),
                "tone": getattr(letter_request, 'tone', 'professional') if letter_request else 'professional',
                "generation_time": letter_status.get("last_generation_time"),
                "model_provider": "gemini"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Letter generation failed: {str(e)}")

@app.get("/api/cases/{case_id}/letter-pdf")
async def download_letter_pdf(case_id: str):
    """Generate and download PDF letter"""
    try:
        # Get case data
        case_data = await case_manager.get_case(case_id)
        if not case_data:
            raise HTTPException(status_code=404, detail="Case not found")

        # Generate letter using Gemini API
        letter_content = await letter_generator.generate_letter(case_data, timeout=30)
        
        # Generate PDF
        pdf_content = letter_generator.generate_pdf(letter_content)

        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=negotiation_letter_{case_id}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

@app.get("/api/health", response_model=HealthCheck)
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        # Test AI providers
        ai_status = "active"
        strategy_status = "unknown"
        letter_status = "unknown"
        
        try:
            # Check strategy generator status
            strategy_info = strategy_generator.get_status()
            strategy_status = strategy_info["status"]
            
            # Check letter generator status
            letter_info = letter_generator.get_status()
            letter_status = letter_info["status"]
            
            # Overall AI status
            if strategy_status == "ready" and letter_status == "ready":
                ai_status = "ready"
            elif strategy_status == "error" or letter_status == "error":
                ai_status = "error"
            else:
                ai_status = "loading"
                
        except Exception as e:
            ai_status = f"error: {str(e)}"

        return HealthCheck(
            status="healthy",
            timestamp=datetime.now(),
            components={
                "document_processor": "active",
                "analysis_engine": "active", 
                "strategy_generator": strategy_status,
                "letter_generator": letter_status,
                "case_manager": "active",
                "ai_provider": ai_status,
                "database": "active" if os.path.exists("data/cases.json") else "initializing",
                "model_provider": "gemini"
            },
            version="2.2.0"
        )
    except Exception as e:
        return HealthCheck(
            status="degraded",
            timestamp=datetime.now(),
            components={
                "error": str(e)
            },
            version="2.2.0"
        )

@app.get("/api/stats")
async def get_system_stats():
    """Get system statistics and performance metrics"""
    try:
        cases = await case_manager.get_all_cases()
        
        # Calculate statistics
        total_cases = len(cases)
        if total_cases == 0:
            return {"message": "No cases found", "stats": {}}
        
        success_probabilities = [c.get("success_probability", 0) for c in cases]
        estimated_payouts = [c.get("estimated_payout", 0) for c in cases]
        
        # Get AI performance stats
        strategy_status = strategy_generator.get_status()
        letter_status = letter_generator.get_status()
        
        stats = {
            "total_cases": total_cases,
            "average_success_probability": sum(success_probabilities) / total_cases,
            "total_estimated_value": sum(estimated_payouts),
            "max_estimated_payout": max(estimated_payouts) if estimated_payouts else 0,
            "min_estimated_payout": min(estimated_payouts) if estimated_payouts else 0,
            "case_types": {},
            "strategy_approaches": {},
            "status_distribution": {},
            "ai_performance": {
                "strategy_initialization_time": strategy_status.get("initialization_time"),
                "letter_initialization_time": letter_status.get("initialization_time"),
                "last_strategy_generation_time": strategy_status.get("last_generation_time"),
                "last_letter_generation_time": letter_status.get("last_generation_time"),
                "memory_usage": {
                    "strategy_generator": strategy_status.get("memory_usage"),
                    "letter_generator": letter_status.get("memory_usage")
                }
            }
        }
        
        # Count case types, strategies, and statuses
        for case in cases:
            # Case types
            case_type = case.get("extracted_info", {}).get("document_type", "unknown")
            stats["case_types"][case_type] = stats["case_types"].get(case_type, 0) + 1
            
            # Strategy approaches
            strategy = case.get("strategy", {})
            approach = strategy.get("approach", "unknown")
            stats["strategy_approaches"][approach] = stats["strategy_approaches"].get(approach, 0) + 1
            
            # Status distribution
            status = case.get("status", "unknown")
            stats["status_distribution"][status] = stats["status_distribution"].get(status, 0) + 1
        
        return {"stats": stats}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate stats: {str(e)}")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc.detail),
            timestamp=datetime.now()
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc),
            timestamp=datetime.now()
        ).dict()
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
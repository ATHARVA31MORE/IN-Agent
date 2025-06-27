from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import uvicorn
from datetime import datetime
import os
import io
from typing import Dict, Any
import tempfile

from document_processor import DocumentProcessor
from analysis_engine import AnalysisEngine
from strategy_generator import StrategyGenerator
from case_manager import CaseManager
from letter_generator import LetterGenerator
from models import CaseResponse, AnalysisRequest

app = FastAPI(title="AI Insurance Negotiation Agent", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories if they don't exist
os.makedirs("generated_letters", exist_ok=True)

# Initialize components
document_processor = DocumentProcessor()
analysis_engine = AnalysisEngine()
strategy_generator = StrategyGenerator()
case_manager = CaseManager()
letter_generator = LetterGenerator()

@app.get("/")
async def root():
    return {"message": "AI Insurance Negotiation Agent API", "status": "active"}

@app.post("/api/upload", response_model=CaseResponse)
async def upload_document(file: UploadFile = File(...)):
    file_path = f"temp_{file.filename}"
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        extracted_info = await document_processor.extract_information(file_path)
        analysis_result = await analysis_engine.analyze_case(extracted_info)
        strategy = await strategy_generator.generate_strategy(extracted_info, analysis_result)

        case_id = f"CASE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        case_data = await case_manager.create_case(
            case_id=case_id,
            extracted_info=extracted_info,
            analysis=analysis_result,
            strategy=strategy
        )

        os.remove(file_path)
        case_data["created_at"] = case_data["created_at"].isoformat()
        return CaseResponse(**case_data)

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        print("ERROR UPLOAD:", str(e))  # ← Debug print
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/api/cases")
async def get_cases():
    """Get all cases"""
    try:
        cases = await case_manager.get_all_cases()
        return {"cases": cases}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cases: {str(e)}")

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """Get specific case details"""
    try:
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return case
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve case: {str(e)}")

@app.post("/api/cases/{case_id}/analyze")
async def reanalyze_case(case_id: str, request: AnalysisRequest):
    """Re-analyze case with updated parameters"""
    try:
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Re-run analysis with new parameters
        analysis_result = await analysis_engine.analyze_case(
            case['extracted_info'], 
            request.parameters
        )
        
        # Update strategy
        strategy = await strategy_generator.generate_strategy(
            case['extracted_info'], 
            analysis_result
        )
        
        # Update case
        updated_case = await case_manager.update_case(
            case_id, 
            analysis=analysis_result, 
            strategy=strategy
        )
        
        return updated_case
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-analysis failed: {str(e)}")

@app.post("/api/cases/{case_id}/letter")
async def generate_negotiation_letter(case_id: str):
    """Generate negotiation letter for case"""
    try:
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        letter = await letter_generator.generate_letter(case)
        
        return {
            "case_id": case_id,
            "letter": letter,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Letter generation failed: {str(e)}")

@app.get("/api/cases/{case_id}/letter-pdf")
async def download_letter_pdf(case_id: str):
    """Generate and download PDF letter using the existing letter generator"""
    try:
        # Get case data
        case_data = await case_manager.get_case(case_id)
        if not case_data:
            raise HTTPException(status_code=404, detail="Case not found")

        # Generate letter using the existing letter generator
        letter = await letter_generator.generate_letter(case_data)
        
        # Generate PDF using the existing PDF generation method (removed await)
        pdf_content = letter_generator.generate_pdf(letter)

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
        print(f"PDF generation error: {str(e)}")  # Debug print
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

@app.post("/api/cases/{case_id}/letter-pdf")
async def generate_negotiation_letter_pdf_stream(case_id: str):
    """Alternative endpoint for POST requests - generates PDF version of negotiation letter"""
    try:
        case = await case_manager.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        letter = await letter_generator.generate_letter(case)
        pdf_content = letter_generator.generate_pdf(letter)  # Removed await
        
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
        print(f"PDF generation error: {str(e)}")  # Debug print
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "document_processor": "active",
            "analysis_engine": "active",
            "strategy_generator": "active",
            "case_manager": "active",
            "letter_generator": "active"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
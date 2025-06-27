import logging
from datetime import datetime
from models import NegotiationLetter
from reportlab.lib.pagesizes import letter as letter_size  # Renamed to avoid conflict
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
import io
import os

class LetterGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def generate_letter(self, case_data: dict) -> NegotiationLetter:
        try:
            strategy = case_data.get("strategy", {})
            extracted_info = case_data.get("extracted_info", {})
            analysis = case_data.get("analysis", {})
            
            # Safe extraction of data with defaults
            policy_details = extracted_info.get("policy_details", {})
            policy_number = policy_details.get("policy_number", "Unknown")
            case_id = case_data.get("case_id", "Unknown")
            
            # Handle different payout formats
            payout = 0
            if analysis.get("estimated_payout_range"):
                if isinstance(analysis["estimated_payout_range"], dict):
                    payout = analysis["estimated_payout_range"].get("expected", 0)
                else:
                    payout = analysis["estimated_payout_range"]
            elif analysis.get("estimated_payout"):
                payout = analysis["estimated_payout"]
            
            # Generate dynamic content based on case details
            denial_reasons = "\n".join(
                f"• {reason}" for reason in extracted_info.get("denial_reasons", [])
            ) if extracted_info.get("denial_reasons") else "Not specified"
            
            subject = f"Re: Claim Review - Policy #{policy_number}"
            body = (
                f"Dear Claims Adjuster,\n\n"
                f"I am writing regarding my insurance claim under Policy #{policy_number} (Case ID: {case_id}).\n\n"
            )
            
            document_type = extracted_info.get("document_type", "unknown")
            if document_type == "denial_letter":
                body += (
                    f"After reviewing the denial letter citing the following reasons:\n{denial_reasons}\n\n"
                    f"I believe this denial is incorrect for the following reasons:\n"
                    f"• The policy language is ambiguous in this context\n"
                    f"• Similar claims have been approved under comparable circumstances\n"
                    f"• All required documentation was submitted timely\n\n"
                )
            else:
                body += (
                    f"After reviewing the settlement offer, I believe it does not adequately compensate "
                    f"for the damages incurred for these reasons:\n"
                    f"• The offer doesn't reflect current market rates\n"
                    f"• Not all damages were accounted for\n"
                    f"• The calculations appear to be incorrect\n\n"
                )
                
            body += (
                f"Based on my analysis and comparable cases, I believe a fair resolution would be "
                f"in the range of ${payout:,.2f}.\n\n"
                f"I request your response within 7 business days. Please contact me if you require "
                f"any additional information.\n\n"
                f"Sincerely,\n[Your Name]"
            )
            
            return NegotiationLetter(
                subject=subject,
                body=body,
                recipient="Claims Department",
                sender_name="[Your Name]",
                policy_number=policy_number,
                case_id=case_id,
                generated_at=datetime.now(),
                letter_type="claim_appeal",
                key_points=[
                    "Policy coverage applies",
                    "Documentation complete",
                    "Fair settlement requested"
                ],
                legal_references=[
                    "Reasonable Expectations Doctrine",
                    "Bad Faith Denial Principle"
                ]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to generate letter: {str(e)}")
            raise Exception(f"Letter generation failed: {str(e)}")

    def generate_pdf(self, negotiation_letter: NegotiationLetter) -> bytes:  # Removed async, renamed parameter
        """Generate PDF version of the negotiation letter using ReportLab"""
        try:
            # Create a bytes buffer to store the PDF
            buffer = io.BytesIO()
            
            # Create the PDF document - using letter_size instead of letter
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter_size,  # Fixed naming conflict
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Create custom styles
            header_style = ParagraphStyle(
                'CustomHeader',
                parent=styles['Normal'],
                fontSize=12,
                spaceAfter=6,
                alignment=TA_LEFT
            )
            
            subject_style = ParagraphStyle(
                'CustomSubject',
                parent=styles['Normal'],
                fontSize=14,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                alignment=TA_LEFT
            )
            
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=6,
                alignment=TA_LEFT,
                leading=14
            )
            
            signature_style = ParagraphStyle(
                'CustomSignature',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=6,
                alignment=TA_LEFT
            )
            
            footer_style = ParagraphStyle(
                'CustomFooter',
                parent=styles['Normal'],
                fontSize=8,
                alignment=TA_CENTER,
                textColor='gray'
            )
            
            # Build the document content
            story = []
            
            # Header information
            story.append(Paragraph(f"<b>Date:</b> {negotiation_letter.generated_at.strftime('%B %d, %Y')}", header_style))
            story.append(Paragraph(f"<b>To:</b> {negotiation_letter.recipient}", header_style))
            story.append(Paragraph(f"<b>Re:</b> Policy #{negotiation_letter.policy_number}", header_style))
            story.append(Spacer(1, 12))
            
            # Subject
            story.append(Paragraph(f"<b>Subject:</b> {negotiation_letter.subject}", subject_style))
            story.append(Spacer(1, 12))
            
            # Body - split into paragraphs for better formatting
            body_paragraphs = negotiation_letter.body.split('\n\n')
            for paragraph in body_paragraphs:
                if paragraph.strip():
                    # Replace line breaks within paragraphs and escape HTML characters
                    formatted_paragraph = paragraph.replace('\n', '<br/>').replace('<', '&lt;').replace('>', '&gt;')
                    # Handle bullet points properly
                    if '•' in formatted_paragraph:
                        formatted_paragraph = formatted_paragraph.replace('•', '&#8226;')
                    story.append(Paragraph(formatted_paragraph, body_style))
                    story.append(Spacer(1, 6))
            
            # Add extra space before signature
            story.append(Spacer(1, 24))
            
            # Signature
            story.append(Paragraph("Sincerely,", signature_style))
            story.append(Spacer(1, 24))
            story.append(Paragraph(negotiation_letter.sender_name, signature_style))
            
            # Footer
            story.append(Spacer(1, 36))
            story.append(Paragraph(
                f"Generated on {negotiation_letter.generated_at.strftime('%Y-%m-%d %H:%M:%S')} | Case ID: {negotiation_letter.case_id}",
                footer_style
            ))
            
            # Build the PDF
            doc.build(story)
            
            # Get the PDF content
            pdf_content = buffer.getvalue()
            buffer.close()
            
            return pdf_content
                
        except Exception as e:
            self.logger.error(f"Failed to generate PDF: {str(e)}")
            raise Exception(f"PDF generation failed: {str(e)}")

    def generate_html_preview(self, negotiation_letter: NegotiationLetter) -> str:  # Renamed parameter
        """Generate HTML preview of the letter (optional method)"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <meta charset="utf-8">
                <title>Negotiation Letter Preview</title>
                <style>
                    body {{ 
                        font-family: Arial, sans-serif; 
                        line-height: 1.6; 
                        margin: 40px;
                        color: #333;
                        max-width: 800px;
                    }}
                    .header {{ 
                        margin-bottom: 30px; 
                        border-bottom: 2px solid #007bff;
                        padding-bottom: 20px;
                    }}
                    .date, .recipient, .policy {{ 
                        margin-bottom: 10px; 
                    }}
                    .subject {{ 
                        font-weight: bold; 
                        margin-bottom: 20px; 
                        font-size: 16px;
                    }}
                    .body {{ 
                        white-space: pre-line; 
                        margin-bottom: 40px; 
                        text-align: justify;
                    }}
                    .signature {{ 
                        margin-top: 40px; 
                    }}
                    .footer {{
                        margin-top: 50px;
                        font-size: 10px;
                        color: #666;
                        text-align: center;
                        border-top: 1px solid #eee;
                        padding-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <div class="date"><strong>Date:</strong> {negotiation_letter.generated_at.strftime('%B %d, %Y')}</div>
                    <div class="recipient"><strong>To:</strong> {negotiation_letter.recipient}</div>
                    <div class="policy"><strong>Re:</strong> Policy #{negotiation_letter.policy_number}</div>
                    <div class="subject"><strong>Subject:</strong> {negotiation_letter.subject}</div>
                </div>
                
                <div class="body">{negotiation_letter.body}</div>
                
                <div class="signature">
                    <div>Sincerely,</div>
                    <br>
                    <div>{negotiation_letter.sender_name}</div>
                </div>
                
                <div class="footer">
                    Generated on {negotiation_letter.generated_at.strftime('%Y-%m-%d %H:%M:%S')} | Case ID: {negotiation_letter.case_id}
                </div>
            </body>
        </html>
        """
        return html_content
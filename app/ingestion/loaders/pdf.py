import base64
import logfire
import pymupdf as fitz  # PyMuPDF
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from app.config import settings

def _vision_fallback(file_path: str) -> str:
    """Fallback to Azure OpenAI Vision (gpt-5-mini) for scanned or image-based pages."""
    logfire.info(f"Using vision OCR fallback for {file_path}")
    
    try:
        # Extract images using PyMuPDF (no external dependencies needed)
        doc = fitz.open(file_path)
        logfire.info(f"Converted {file_path} into {len(doc)} images for OCR.")
        
        # Initialize Azure OpenAI Chat model
        vision_model = AzureChatOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            max_tokens=2048,
        )
        
        extracted_text = []
        for i, page in enumerate(doc):
            logfire.info(f"Running OCR on page {i + 1}")
            
            # Render page to a pixmap (image)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("jpeg")
            base64_img = base64.b64encode(img_bytes).decode("utf-8")
            
            message = HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": "Extract all the text and tables from this image. Return the extracted content cleanly formatted as Markdown. Do not include any other conversational text."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                    },
                ]
            )
            
            response = vision_model.invoke([message])
            extracted_text.append(response.content)
            
        return "\n\n".join(extracted_text)
        
    except Exception as e:
        logfire.error(f"Vision OCR fallback failed for {file_path}: {e}")
        raise

def parse_pdf(file_path: str) -> str:
    """
    Extract structured Markdown from a PDF locally using Firecrawl's pdf-inspector.
    Falls back to Vision OCR for scanned/image-based documents.
    """
    with logfire.span("PDF Parsing (pdf-inspector)", filename=file_path):
        try:
            import pdf_inspector
            
            logfire.info(f"Inspecting {file_path}")
            result = pdf_inspector.process_pdf(file_path)
            
            logfire.info(f"PDF Type detected: {result.pdf_type}")
            
            if result.pdf_type in ["scanned", "image_based"]:
                logfire.info("Document is scanned. Routing to Vision OCR.")
                return _vision_fallback(file_path)
                
            elif result.pdf_type == "mixed":
                logfire.info("Document is mixed. Routing to Vision OCR for best results.")
                return _vision_fallback(file_path)
            
            # Native text extraction for text-based PDFs
            full_text = result.markdown
            
            if not full_text.strip():
                logfire.warning(f"No text extracted natively from {file_path}. Trying OCR fallback.")
                return _vision_fallback(file_path)
            else:
                logfire.info(f"Extracted natively {len(full_text)} characters from {file_path}.")
                return full_text

        except ImportError:
            logfire.error("pdf-inspector not installed. Please pip install pdf-inspector.")
            raise
        except Exception as e:
            logfire.error(f"PDF Parse Failed for {file_path}: {e}")
            raise

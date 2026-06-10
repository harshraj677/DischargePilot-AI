"""
PDF Image Extractor

Extracts images and page renderings from PDF documents
for OCR processing.
"""
from pathlib import Path
from typing import Optional, Tuple
import io
import fitz  # PyMuPDF
from PIL import Image  # Pillow

from app.utils.logging import get_logger

logger = get_logger(__name__)


class PDFImageExtractor:
    """Extracts images from PDF pages for OCR processing."""
    
    DEFAULT_DPI = 300  # Resolution for page rendering
    MIN_IMAGE_SIZE = (100, 100)  # Minimum useful image dimensions
    MAX_IMAGE_SIZE = (4000, 4000)  # Cap to prevent memory issues
    
    def __init__(self, dpi: int = DEFAULT_DPI):
        """
        Initialize extractor.
        
        Args:
            dpi: Resolution for rendering pages to images (default 300)
        """
        self.dpi = dpi
        self.logger = logger
    
    def extract_page_image(
        self,
        page: fitz.Page,
        page_number: int,
        output_format: str = "PNG",
    ) -> Optional[bytes]:
        """
        Render a PDF page to an image.
        
        Args:
            page: PyMuPDF page object
            page_number: 1-based page number (for logging)
            output_format: Image format ("PNG", "JPEG")
        
        Returns:
            Image bytes, or None if extraction failed
        """
        try:
            # Calculate zoom for desired DPI
            # PyMuPDF default is 72 DPI, so zoom = desired_dpi / 72
            zoom = self.dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            
            # Render page to image
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to PIL Image for validation and optimization
            image_bytes = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(image_bytes))
            
            # Validate size
            width, height = img.size
            if width < self.MIN_IMAGE_SIZE[0] or height < self.MIN_IMAGE_SIZE[1]:
                self.logger.warning(
                    "Page image too small",
                    page=page_number,
                    size=(width, height),
                )
                return None
            
            # Optionally resize if too large
            if width > self.MAX_IMAGE_SIZE[0] or height > self.MAX_IMAGE_SIZE[1]:
                ratio = min(
                    self.MAX_IMAGE_SIZE[0] / width,
                    self.MAX_IMAGE_SIZE[1] / height,
                )
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save to bytes in requested format
            output = io.BytesIO()
            img.save(output, format=output_format, optimize=True)
            output.seek(0)
            
            result = output.getvalue()
            self.logger.info(
                "Extracted page image",
                page=page_number,
                format=output_format,
                size=(img.size[0], img.size[1]),
                bytes=len(result),
            )
            
            return result
        
        except Exception as e:
            self.logger.error(
                "Failed to extract page image",
                page=page_number,
                error=str(e),
            )
            return None
    
    def extract_embedded_images(
        self,
        page: fitz.Page,
        page_number: int,
    ) -> list[Tuple[int, bytes]]:
        """
        Extract images embedded in a PDF page.
        
        Args:
            page: PyMuPDF page object
            page_number: 1-based page number (for logging)
        
        Returns:
            List of (image_index, image_bytes) tuples
        """
        extracted = []
        
        try:
            # Get all images on the page
            images = page.get_images(full=True)
            
            for img_index, (xref, *_) in enumerate(images):
                try:
                    # Extract image data
                    pix = fitz.Pixmap(page.parent, xref)
                    
                    # Convert CMYK to RGB if needed
                    if pix.n - pix.alpha > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    
                    # Get image bytes
                    image_bytes = pix.tobytes("png")
                    
                    # Validate size
                    img = Image.open(io.BytesIO(image_bytes))
                    width, height = img.size
                    
                    if (
                        width >= self.MIN_IMAGE_SIZE[0]
                        and height >= self.MIN_IMAGE_SIZE[1]
                    ):
                        extracted.append((img_index, image_bytes))
                        self.logger.debug(
                            "Extracted embedded image",
                            page=page_number,
                            image_index=img_index,
                            size=(width, height),
                        )
                
                except Exception as e:
                    self.logger.warning(
                        "Failed to extract embedded image",
                        page=page_number,
                        image_index=img_index,
                        error=str(e),
                    )
        
        except Exception as e:
            self.logger.warning(
                "Failed to extract images from page",
                page=page_number,
                error=str(e),
            )
        
        return extracted
    
    def save_page_image(
        self,
        page: fitz.Page,
        page_number: int,
        output_path: Path,
    ) -> Optional[Path]:
        """
        Save a rendered page image to disk.
        
        Args:
            page: PyMuPDF page object
            page_number: 1-based page number
            output_path: Where to save the image
        
        Returns:
            Path to saved image, or None if failed
        """
        try:
            image_bytes = self.extract_page_image(page, page_number)
            if image_bytes is None:
                return None
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            
            self.logger.info(
                "Saved page image",
                page=page_number,
                path=str(output_path),
            )
            
            return output_path
        
        except Exception as e:
            self.logger.error(
                "Failed to save page image",
                page=page_number,
                path=str(output_path),
                error=str(e),
            )
            return None

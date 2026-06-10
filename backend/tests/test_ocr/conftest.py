"""Tests for OCR module"""
import pytest
import io
from pathlib import Path
from PIL import Image

# Test fixtures and utilities for OCR testing


@pytest.fixture
def sample_image_png():
    """Create a sample PNG image for testing."""
    img = Image.new("RGB", (300, 300), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def sample_text_image():
    """Create an image with text for OCR testing."""
    from PIL import ImageDraw, ImageFont
    
    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)
    
    # Try to use default font, fall back to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    draw.text((10, 10), "Patient: John Doe\nMRN: 12345", fill="black", font=font)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def sample_handwriting_image():
    """Create an image simulating handwritten content."""
    img = Image.new("RGB", (400, 300), color="white")
    draw = ImageDraw.Draw(img)
    
    # Draw some irregular lines to simulate handwriting
    draw.line([(10, 50), (50, 60), (80, 55)], fill="black", width=2)
    draw.line([(10, 100), (60, 110), (100, 105)], fill="black", width=2)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()

import pytest
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.database import Base
from app.main import app
from app.dependencies import get_db

# ── Test database setup ───────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///./test_dischargepilot.db"

test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    from app.db import models as _  # noqa
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("test_dischargepilot.db"):
        os.remove("test_dischargepilot.db")


@pytest.fixture()
def db():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Sample clinical text fixtures ─────────────────────────────────────────────

SAMPLE_ADMISSION_NOTE_TEXT = """
ADMISSION NOTE

Patient: John Doe
MRN: MRN-2025-00123
DOB: 03/15/1971
Admission Date: 05/28/2025
Attending: Dr. Sarah Chen
Ward: Internal Medicine - 3B

CHIEF COMPLAINT:
Shortness of breath and elevated blood sugar for 3 days.

HISTORY OF PRESENT ILLNESS:
54-year-old male with known history of Type 2 Diabetes Mellitus (T2DM) presenting
with worsening shortness of breath and blood glucose readings exceeding 400 mg/dL
at home. Patient reports poor medication compliance over the past 2 weeks.

PAST MEDICAL HISTORY:
1. Type 2 Diabetes Mellitus
2. Hypertension
3. Chronic Kidney Disease Stage 3

ALLERGIES:
Penicillin - Anaphylaxis

MEDICATIONS ON ADMISSION:
1. Metformin 500mg PO BID
2. Lisinopril 10mg PO daily
3. Atorvastatin 40mg PO QHS

ASSESSMENT:
1. Type 2 Diabetes Mellitus, uncontrolled (HbA1c 9.2%)
2. Hypertension, uncontrolled
3. Chronic Kidney Disease, Stage 3

PLAN:
- Admit for glycemic management
- IV insulin drip
- Monitor renal function
"""

SAMPLE_LAB_REPORT_TEXT = """
LABORATORY RESULTS REPORT

Patient: John Doe
MRN: MRN-2025-00123
Collection Date: 05/28/2025
Report Date: 05/28/2025

COMPLETE BLOOD COUNT (CBC):
WBC: 9.2 K/uL (Reference: 4.0-11.0)
RBC: 4.1 M/uL (Reference: 4.5-5.5)
Hemoglobin: 11.8 g/dL (Reference: 13.5-17.5) LOW
Hematocrit: 35.4% (Reference: 41-53) LOW
Platelets: 248 K/uL (Reference: 150-400)

COMPREHENSIVE METABOLIC PANEL (CMP):
Sodium: 138 mEq/L (Reference: 136-145)
Potassium: 4.2 mEq/L (Reference: 3.5-5.0)
Creatinine: 1.8 mg/dL (Reference: 0.7-1.3) HIGH
BUN: 28 mg/dL (Reference: 7-20) HIGH
Glucose: 412 mg/dL (Reference: 70-100) CRITICAL HIGH

HbA1c: 9.2% (Reference: <5.7%) HIGH

Pending Results:
- Blood cultures (collected 05/28/2025) - PENDING
- Urine culture - PENDING
"""

SAMPLE_MEDICATION_RECORD_TEXT = """
MEDICATION ADMINISTRATION RECORD (MAR)

Patient: John Doe
MRN: MRN-2025-00123
Date: 06/01/2025

SCHEDULED MEDICATIONS:
1. Metformin 1000mg PO BID (DOSE UPDATED 06/01/2025 - previously 500mg)
   - 0800: Administered - RN J. Williams
   - 2000: Administered - RN K. Johnson

2. Lisinopril 10mg PO daily
   - 0900: Administered - RN J. Williams

3. Atorvastatin 40mg PO QHS
   - 2100: Administered - RN K. Johnson

4. Regular Insulin per sliding scale
   - 0700: Blood glucose 287 mg/dL - 6 units administered - RN J. Williams

PRN MEDICATIONS:
- Ondansetron 4mg IV PRN nausea - administered 1400
"""


@pytest.fixture()
def admission_note_text():
    return SAMPLE_ADMISSION_NOTE_TEXT


@pytest.fixture()
def lab_report_text():
    return SAMPLE_LAB_REPORT_TEXT


@pytest.fixture()
def medication_record_text():
    return SAMPLE_MEDICATION_RECORD_TEXT


@pytest.fixture()
def sample_pdf_path():
    """Creates a minimal valid PDF file for testing."""
    try:
        import fitz
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 100), SAMPLE_ADMISSION_NOTE_TEXT[:500])
        doc.save(path)
        doc.close()
        yield path
        if os.path.exists(path):
            os.remove(path)
    except ImportError:
        pytest.skip("PyMuPDF not installed")

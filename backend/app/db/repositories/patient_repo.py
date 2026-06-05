import uuid
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.db.models import Patient, Document
from app.models.patient import PatientCreate, PatientUpdate
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PatientRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: PatientCreate) -> Patient:
        patient = Patient(
            id=str(uuid.uuid4()),
            mrn=data.mrn,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            admission_date=data.admission_date,
            discharge_date=data.discharge_date,
            attending_md=data.attending_md,
            ward=data.ward,
        )
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        logger.info("Patient created", patient_id=patient.id, mrn=patient.mrn)
        return patient

    def get_by_id(self, patient_id: str) -> Optional[Patient]:
        return self.db.get(Patient, patient_id)

    def get_by_mrn(self, mrn: str) -> Optional[Patient]:
        return self.db.execute(
            select(Patient).where(Patient.mrn == mrn.upper(), Patient.deleted_at.is_(None))
        ).scalar_one_or_none()

    def mrn_exists(self, mrn: str) -> bool:
        return self.get_by_mrn(mrn) is not None

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        ward: Optional[str] = None,
    ) -> Tuple[List[Patient], int]:
        stmt = select(Patient).where(Patient.deleted_at.is_(None))

        if search:
            term = f"%{search.lower()}%"
            stmt = stmt.where(
                Patient.first_name.ilike(term)
                | Patient.last_name.ilike(term)
                | Patient.mrn.ilike(term)
            )
        if ward:
            stmt = stmt.where(Patient.ward == ward)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(total_stmt).scalar_one()

        stmt = stmt.order_by(Patient.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        patients = list(self.db.execute(stmt).scalars())
        return patients, total

    def update(self, patient_id: str, data: PatientUpdate) -> Optional[Patient]:
        patient = self.get_by_id(patient_id)
        if not patient:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(patient, field, value)
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def soft_delete(self, patient_id: str) -> bool:
        from datetime import datetime
        patient = self.get_by_id(patient_id)
        if not patient:
            return False
        patient.deleted_at = datetime.utcnow()
        self.db.commit()
        return True

    def document_count(self, patient_id: str) -> int:
        result = self.db.execute(
            select(func.count()).where(Document.patient_id == patient_id)
        ).scalar_one()
        return result

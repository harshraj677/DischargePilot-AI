from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

from app.models.enums import SummaryStatus


class PatientBase(BaseModel):
    mrn: str = Field(..., min_length=1, max_length=50, description="Medical Record Number")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: Optional[str] = Field(None, description="ISO 8601 date string: YYYY-MM-DD")
    gender: Optional[str] = Field(None, max_length=20)
    admission_date: Optional[datetime] = None
    discharge_date: Optional[datetime] = None
    attending_md: Optional[str] = Field(None, max_length=200)
    ward: Optional[str] = Field(None, max_length=100)

    @field_validator("mrn")
    @classmethod
    def clean_mrn(cls, v: str) -> str:
        return v.strip().upper()


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    admission_date: Optional[datetime] = None
    discharge_date: Optional[datetime] = None
    attending_md: Optional[str] = None
    ward: Optional[str] = None


class PatientDocumentSummary(BaseModel):
    id: str
    document_type: str
    file_name: str
    status: str
    page_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PatientResponse(PatientBase):
    id: str
    document_count: int = 0
    documents: List[PatientDocumentSummary] = []
    summary_status: Optional[SummaryStatus] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatientListItem(BaseModel):
    id: str
    mrn: str
    first_name: str
    last_name: str
    ward: Optional[str] = None
    admission_date: Optional[datetime] = None
    document_count: int = 0
    summary_status: Optional[SummaryStatus] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PatientListResponse(BaseModel):
    items: List[PatientListItem]
    total: int
    page: int
    page_size: int
    has_more: bool

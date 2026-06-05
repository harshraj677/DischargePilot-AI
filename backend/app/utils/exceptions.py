from typing import Optional


class DischargePilotException(Exception):
    def __init__(
        self,
        error: str,
        detail: str,
        code: str,
        status_code: int = 400,
    ):
        self.error = error
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


class PatientNotFoundException(DischargePilotException):
    def __init__(self, patient_id: str):
        super().__init__(
            error="Patient not found",
            detail=f"Patient with ID '{patient_id}' does not exist.",
            code="PATIENT_NOT_FOUND",
            status_code=404,
        )


class DocumentNotFoundException(DischargePilotException):
    def __init__(self, document_id: str):
        super().__init__(
            error="Document not found",
            detail=f"Document with ID '{document_id}' does not exist.",
            code="DOCUMENT_NOT_FOUND",
            status_code=404,
        )


class InvalidFileTypeException(DischargePilotException):
    def __init__(self, filename: str, allowed: list):
        super().__init__(
            error="Invalid file type",
            detail=f"File '{filename}' is not allowed. Accepted types: {', '.join(allowed)}.",
            code="INVALID_FILE_TYPE",
            status_code=400,
        )


class FileTooLargeException(DischargePilotException):
    def __init__(self, filename: str, max_mb: int):
        super().__init__(
            error="File too large",
            detail=f"File '{filename}' exceeds the {max_mb}MB size limit.",
            code="FILE_TOO_LARGE",
            status_code=413,
        )


class PDFExtractionException(DischargePilotException):
    def __init__(self, filename: str, reason: str):
        super().__init__(
            error="PDF extraction failed",
            detail=f"Could not extract text from '{filename}': {reason}",
            code="EXTRACTION_FAILED",
            status_code=422,
        )


class PDFCorruptedException(DischargePilotException):
    def __init__(self, filename: str):
        super().__init__(
            error="Corrupted PDF",
            detail=f"File '{filename}' appears to be corrupted or is not a valid PDF.",
            code="PDF_CORRUPTED",
            status_code=422,
        )


class PDFEmptyException(DischargePilotException):
    def __init__(self, filename: str):
        super().__init__(
            error="Empty PDF",
            detail=f"File '{filename}' contains no extractable text. It may be a scanned image-only PDF.",
            code="PDF_EMPTY",
            status_code=422,
        )


class DocumentNotReadyException(DischargePilotException):
    def __init__(self, document_ids: list):
        super().__init__(
            error="Documents not ready",
            detail=f"{len(document_ids)} document(s) are still processing. Wait for all to reach PROCESSED status.",
            code="DOCUMENTS_NOT_READY",
            status_code=400,
        )


class StorageException(DischargePilotException):
    def __init__(self, detail: str):
        super().__init__(
            error="Storage error",
            detail=detail,
            code="STORAGE_ERROR",
            status_code=500,
        )


class MRNAlreadyExistsException(DischargePilotException):
    def __init__(self, mrn: str):
        super().__init__(
            error="MRN already exists",
            detail=f"A patient with MRN '{mrn}' already exists.",
            code="MRN_ALREADY_EXISTS",
            status_code=409,
        )

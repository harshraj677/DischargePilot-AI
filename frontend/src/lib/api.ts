import type {
  Patient,
  PatientCreate,
  PatientListResponse,
  DocumentResponse,
  DocumentDetailResponse,
  DocumentListResponse,
  ProcessingStatus,
  DocumentType,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    let errorBody: { error?: string; detail?: string; code?: string } = {};
    try {
      errorBody = await res.json();
    } catch {}
    const message = errorBody.detail ?? errorBody.error ?? `HTTP ${res.status}`;
    throw new APIError(message, res.status, errorBody.code);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

export class APIError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "APIError";
  }
}

// ── Patients ──────────────────────────────────────────────────────────────────

export const patients = {
  create: (data: PatientCreate): Promise<Patient> =>
    request("/patients", { method: "POST", body: JSON.stringify(data) }),

  list: (params?: {
    page?: number;
    page_size?: number;
    search?: string;
    ward?: string;
  }): Promise<PatientListResponse> => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    if (params?.search) qs.set("search", params.search);
    if (params?.ward) qs.set("ward", params.ward);
    return request(`/patients?${qs}`);
  },

  get: (patientId: string): Promise<Patient> =>
    request(`/patients/${patientId}`),

  update: (
    patientId: string,
    data: Partial<PatientCreate>
  ): Promise<Patient> =>
    request(`/patients/${patientId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};

// ── Documents ─────────────────────────────────────────────────────────────────

export const documents = {
  upload: async (
    patientId: string,
    file: File,
    documentType: DocumentType | null,
    onProgress?: (pct: number) => void
  ): Promise<DocumentResponse> => {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append("file", file);
      if (documentType) formData.append("document_type", documentType);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE_URL}/patients/${patientId}/documents`);

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new APIError(err.detail ?? err.error ?? "Upload failed", xhr.status, err.code));
          } catch {
            reject(new APIError("Upload failed", xhr.status));
          }
        }
      });

      xhr.addEventListener("error", () => reject(new APIError("Network error", 0)));
      xhr.send(formData);
    });
  },

  list: (patientId: string): Promise<DocumentListResponse> =>
    request(`/patients/${patientId}/documents`),

  get: (documentId: string): Promise<DocumentDetailResponse> =>
    request(`/documents/${documentId}`),

  delete: (documentId: string): Promise<void> =>
    request(`/documents/${documentId}`, { method: "DELETE" }),

  retry: (documentId: string): Promise<DocumentResponse> =>
    request(`/documents/${documentId}/retry`, { method: "POST" }),

  pages: (documentId: string) => request(`/documents/${documentId}/pages`),

  logs: (documentId: string) => request(`/documents/${documentId}/logs`),

  processingStatus: (patientId: string): Promise<ProcessingStatus> =>
    request(`/patients/${patientId}/processing-status`),
};

export const health = {
  check: () => request<{ status: string }>("/health"),
};

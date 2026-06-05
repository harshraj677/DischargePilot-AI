"use client";

import { useState, useCallback, useRef } from "react";
import { documents as documentsApi, APIError } from "@/lib/api";
import type {
  DocumentResponse,
  ProcessingStatus,
  DocumentType,
  UploadingFile,
  UploadState,
} from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

export function useDocumentUpload(patientId: string) {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);

  const updateFile = useCallback(
    (id: string, patch: Partial<UploadingFile>) => {
      setUploadingFiles((prev) =>
        prev.map((f) => (f.id === id ? { ...f, ...patch } : f))
      );
    },
    []
  );

  const addFiles = useCallback(
    (files: File[], declaredType: DocumentType | null) => {
      const newEntries: UploadingFile[] = files.map((file) => ({
        id: `${file.name}-${Date.now()}-${Math.random()}`,
        file,
        declaredType,
        uploadState: "idle",
        progress: 0,
      }));
      setUploadingFiles((prev) => [...prev, ...newEntries]);
      return newEntries;
    },
    []
  );

  const uploadFile = useCallback(
    async (entry: UploadingFile): Promise<DocumentResponse | null> => {
      updateFile(entry.id, { uploadState: "uploading", progress: 0 });
      try {
        const doc = await documentsApi.upload(
          patientId,
          entry.file,
          entry.declaredType,
          (pct) => updateFile(entry.id, { progress: pct })
        );
        updateFile(entry.id, {
          uploadState: "processing",
          progress: 100,
          documentId: doc.id,
          document: doc,
        });
        return doc;
      } catch (err) {
        const message = err instanceof APIError ? err.message : "Upload failed";
        updateFile(entry.id, { uploadState: "failed", error: message });
        return null;
      }
    },
    [patientId, updateFile]
  );

  const uploadAll = useCallback(
    async (entries: UploadingFile[]) => {
      await Promise.all(entries.map(uploadFile));
    },
    [uploadFile]
  );

  const removeFile = useCallback((id: string) => {
    setUploadingFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearAll = useCallback(() => setUploadingFiles([]), []);

  return { uploadingFiles, addFiles, uploadFile, uploadAll, removeFile, clearAll, updateFile };
}

export function useProcessingStatus(patientId: string, enabled: boolean) {
  const [status, setStatus] = useState<ProcessingStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!patientId) return;
    try {
      const result = await documentsApi.processingStatus(patientId);
      setStatus(result);
      setError(null);

      // Stop polling once everything is ready or has failed
      if (result.all_ready || (result.processing === 0 && result.uploaded === 0)) {
        stopPolling();
      }
    } catch (err) {
      const message = err instanceof APIError ? err.message : "Failed to fetch status";
      setError(message);
    }
  }, [patientId]);

  const startPolling = useCallback(() => {
    if (pollingRef.current) return;
    setLoading(true);
    fetchStatus();
    pollingRef.current = setInterval(fetchStatus, POLL_INTERVAL_MS);
  }, [fetchStatus]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setLoading(false);
  }, []);

  const refresh = fetchStatus;

  return { status, loading, error, startPolling, stopPolling, refresh };
}

export function useDocumentList(patientId: string) {
  const [docs, setDocs] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    try {
      const result = await documentsApi.list(patientId);
      setDocs(result.items);
      setError(null);
    } catch (err) {
      setError(err instanceof APIError ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  const deleteDoc = useCallback(
    async (documentId: string) => {
      await documentsApi.delete(documentId);
      setDocs((prev) => prev.filter((d) => d.id !== documentId));
    },
    []
  );

  const retryDoc = useCallback(async (documentId: string) => {
    const updated = await documentsApi.retry(documentId);
    setDocs((prev) => prev.map((d) => (d.id === documentId ? updated : d)));
  }, []);

  return { docs, loading, error, fetch, deleteDoc, retryDoc };
}

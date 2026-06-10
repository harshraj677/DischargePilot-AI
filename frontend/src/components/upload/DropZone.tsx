"use client";

import { useCallback, useState } from "react";
import { Upload, FileText, AlertCircle } from "lucide-react";

interface DropZoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  maxSizeMB?: number;
}

const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"];
const ACCEPTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".webp"];

export function DropZone({
  onFilesSelected,
  disabled = false,
  maxSizeMB = 50,
}: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const validateAndFilter = (files: File[]): { valid: File[]; errors: string[] } => {
    const valid: File[] = [];
    const errors: string[] = [];

    for (const file of files) {
      if (!ACCEPTED_TYPES.includes(file.type) && !file.name.toLowerCase().match(/\.(pdf|jpg|jpeg|png|webp)$/)) {
        errors.push(`"${file.name}" is not a supported file type (PDF/Images).`);
        continue;
      }
      if (file.size > maxSizeMB * 1024 * 1024) {
        errors.push(`"${file.name}" exceeds the ${maxSizeMB}MB size limit.`);
        continue;
      }
      valid.push(file);
    }
    return { valid, errors };
  };

  const handleFiles = useCallback(
    (files: File[]) => {
      setValidationError(null);
      const { valid, errors } = validateAndFilter(files);
      if (errors.length > 0) setValidationError(errors.join(" "));
      if (valid.length > 0) onFilesSelected(valid);
    },
    [onFilesSelected, maxSizeMB]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;
      const files = Array.from(e.dataTransfer.files);
      handleFiles(files);
    },
    [disabled, handleFiles]
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      handleFiles(files);
      e.target.value = "";
    },
    [handleFiles]
  );

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        className={[
          "relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed",
          "px-8 py-12 text-center transition-colors duration-150",
          isDragging && !disabled
            ? "border-blue-500 bg-blue-50"
            : "border-slate-200 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/50",
          disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
        ].join(" ")}
      >
        <input
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          multiple
          disabled={disabled}
          onChange={onInputChange}
          className="absolute inset-0 cursor-pointer opacity-0 disabled:cursor-not-allowed"
          aria-label="Upload PDF or Image files"
        />

        <div className={[
          "mb-4 flex h-14 w-14 items-center justify-center rounded-full",
          isDragging ? "bg-blue-100" : "bg-slate-100",
        ].join(" ")}>
          {isDragging ? (
            <FileText className="h-7 w-7 text-blue-600" />
          ) : (
            <Upload className="h-7 w-7 text-slate-400" />
          )}
        </div>

        <p className="text-sm font-500 text-slate-700">
          {isDragging ? "Drop files here" : "Drag & drop PDF or Image files here"}
        </p>
        <p className="mt-1 text-xs text-slate-500">or click to browse</p>
        <p className="mt-3 text-xs text-slate-400">
          PDF & Images (JPG, PNG, WEBP) · Max {maxSizeMB}MB per file · Multiple files supported
        </p>
      </div>

      {validationError && (
        <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
          <span>{validationError}</span>
        </div>
      )}
    </div>
  );
}

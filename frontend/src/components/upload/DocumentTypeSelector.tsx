"use client";

import { DocumentType, DOCUMENT_TYPE_LABELS } from "@/lib/types";

interface DocumentTypeSelectorProps {
  value: DocumentType | null;
  onChange: (type: DocumentType | null) => void;
  disabled?: boolean;
}

const OPTIONS: { value: DocumentType; label: string; description: string }[] = [
  {
    value: "admission_note",
    label: "Admission Note",
    description: "Initial assessment on patient admission",
  },
  {
    value: "progress_note",
    label: "Progress Note",
    description: "Daily clinical progress documentation",
  },
  {
    value: "lab_report",
    label: "Lab Report",
    description: "Laboratory test results (CBC, CMP, etc.)",
  },
  {
    value: "medication_record",
    label: "Medication Record",
    description: "Medication administration record (MAR)",
  },
  {
    value: "discharge_instruction",
    label: "Discharge Instruction",
    description: "After-care and follow-up instructions",
  },
];

export function DocumentTypeSelector({
  value,
  onChange,
  disabled = false,
}: DocumentTypeSelectorProps) {
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-500 uppercase tracking-wide text-slate-500">
        Document Type
      </label>
      <select
        value={value ?? ""}
        onChange={(e) =>
          onChange(e.target.value ? (e.target.value as DocumentType) : null)
        }
        disabled={disabled}
        className={[
          "w-full rounded-md border border-slate-200 bg-white px-3 py-2",
          "text-sm text-slate-700 shadow-sm",
          "focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20",
          disabled ? "cursor-not-allowed opacity-50" : "",
        ].join(" ")}
      >
        <option value="">Auto-detect from content</option>
        {OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label} — {opt.description}
          </option>
        ))}
      </select>
      <p className="text-xs text-slate-400">
        Declaring the type improves extraction accuracy and skips LLM classification.
      </p>
    </div>
  );
}

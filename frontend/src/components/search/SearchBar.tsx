"use client";

import { useState } from "react";
import { Search as SearchIcon } from "lucide-react";

export type SearchField = "patient_name" | "mrn" | "summary_id" | "document_id";

const FIELD_LABELS: Record<SearchField, string> = {
  patient_name: "Patient Name",
  mrn: "MRN",
  summary_id: "Summary ID",
  document_id: "Document ID",
};

interface SearchBarProps {
  onSearch: (field: SearchField, query: string) => void;
  loading?: boolean;
}

export function SearchBar({ onSearch, loading }: SearchBarProps) {
  const [field, setField] = useState<SearchField>("patient_name");
  const [query, setQuery] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) onSearch(field, query.trim());
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row">
      <select
        value={field}
        onChange={(e) => setField(e.target.value as SearchField)}
        className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 sm:w-44"
      >
        {Object.entries(FIELD_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <div className="relative flex-1">
        <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search by ${FIELD_LABELS[field]}...`}
          className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm text-slate-700 placeholder:text-slate-400"
        />
      </div>
      <button type="submit" disabled={loading || !query.trim()} className="btn-primary sm:w-auto">
        {loading ? "Searching..." : "Search"}
      </button>
    </form>
  );
}

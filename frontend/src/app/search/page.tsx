"use client";

import { useState } from "react";
import Link from "next/link";
import { SearchX } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SearchBar, type SearchField } from "@/components/search/SearchBar";
import { EmptyState } from "@/components/ui/EmptyState";
import { search as searchApi } from "@/lib/api";
import { formatDate, formatScore } from "@/lib/utils";
import type { SearchResultItem } from "@/lib/types";

export default function SearchPage() {
  const [results, setResults] = useState<SearchResultItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(field: SearchField, query: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await searchApi.query({ [field]: query });
      setResults(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Search" subtitle="Find patients, summaries, and documents across the platform" />

      <SearchBar onSearch={handleSearch} loading={loading} />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center text-sm text-red-600">
          {error}
        </div>
      )}

      {!error && results !== null && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          {results.length === 0 ? (
            <EmptyState
              icon={<SearchX className="h-6 w-6" />}
              title="No results found"
              description="Try a different search field or check the spelling."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    <th className="py-2 pr-4">Patient</th>
                    <th className="py-2 pr-4">MRN</th>
                    <th className="py-2 pr-4">Summary Status</th>
                    <th className="py-2 pr-4">Safety Score</th>
                    <th className="py-2 pr-4">Completeness</th>
                    <th className="py-2 pr-4">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {results.map((item, i) => (
                    <tr key={`${item.patient_id}-${item.summary_id ?? i}`} className="text-slate-700">
                      <td className="py-2.5 pr-4">
                        <Link
                          href={`/patients/${item.patient_id}/timeline`}
                          className="font-medium text-medical-blue-600 hover:text-medical-blue-700"
                        >
                          {item.patient_name}
                        </Link>
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-slate-500">{item.mrn ?? "—"}</td>
                      <td className="py-2.5 pr-4 text-slate-600">{item.status ?? "No summary yet"}</td>
                      <td className="py-2.5 pr-4 text-slate-600">{formatScore(item.safety_score)}</td>
                      <td className="py-2.5 pr-4 text-slate-600">{formatScore(item.completeness_score)}</td>
                      <td className="py-2.5 pr-4 text-xs text-slate-400">{formatDate(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

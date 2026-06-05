"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  Plus,
  Users,
  ChevronLeft,
  ChevronRight,
  X,
  FileText,
  Calendar,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SummaryStatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { patients as patientsApi } from "@/lib/api";
import { formatDate, formatRelativeTime } from "@/lib/utils";
import type { PatientListItem, PatientCreate } from "@/lib/types";

const PAGE_SIZE = 20;

interface CreatePatientModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function CreatePatientModal({ onClose, onCreated }: CreatePatientModalProps) {
  const [form, setForm] = useState<PatientCreate>({
    mrn: "",
    first_name: "",
    last_name: "",
    ward: "",
    admission_date: "",
    attending_md: "",
    date_of_birth: "",
    gender: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: PatientCreate = {
        mrn: form.mrn,
        first_name: form.first_name,
        last_name: form.last_name,
        ...(form.ward && { ward: form.ward }),
        ...(form.admission_date && { admission_date: form.admission_date }),
        ...(form.attending_md && { attending_md: form.attending_md }),
        ...(form.date_of_birth && { date_of_birth: form.date_of_birth }),
        ...(form.gender && { gender: form.gender }),
      };
      await patientsApi.create(payload);
      onCreated();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create patient");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="relative w-full max-w-lg rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-900">Add New Patient</h2>
          <button onClick={onClose} className="btn-ghost h-8 w-8 p-0">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5">
          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-2.5 text-sm text-red-700">
              {error}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="label mb-1">
                MRN <span className="text-red-500">*</span>
              </label>
              <input
                className="input"
                placeholder="e.g. MRN-123456"
                value={form.mrn}
                onChange={(e) => setForm((f) => ({ ...f, mrn: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="label mb-1">
                First Name <span className="text-red-500">*</span>
              </label>
              <input
                className="input"
                placeholder="John"
                value={form.first_name}
                onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="label mb-1">
                Last Name <span className="text-red-500">*</span>
              </label>
              <input
                className="input"
                placeholder="Smith"
                value={form.last_name}
                onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="label mb-1">Date of Birth</label>
              <input
                className="input"
                type="date"
                value={form.date_of_birth ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, date_of_birth: e.target.value }))}
              />
            </div>
            <div>
              <label className="label mb-1">Gender</label>
              <select
                className="input"
                value={form.gender ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, gender: e.target.value }))}
              >
                <option value="">Select...</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div>
              <label className="label mb-1">Ward</label>
              <input
                className="input"
                placeholder="e.g. ICU, Cardiology"
                value={form.ward ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, ward: e.target.value }))}
              />
            </div>
            <div>
              <label className="label mb-1">Admission Date</label>
              <input
                className="input"
                type="date"
                value={form.admission_date ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, admission_date: e.target.value }))}
              />
            </div>
            <div className="col-span-2">
              <label className="label mb-1">Attending Physician</label>
              <input
                className="input"
                placeholder="Dr. Jane Doe"
                value={form.attending_md ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, attending_md: e.target.value }))}
              />
            </div>
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="btn-primary">
              {loading ? "Creating..." : "Create Patient"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PatientsPage() {
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const fetchPatients = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await patientsApi.list({ page, page_size: PAGE_SIZE, search: search || undefined });
      setPatients(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load patients");
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    fetchPatients();
  }, [fetchPatients]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Patients"
        subtitle={`${total} patient${total !== 1 ? "s" : ""} in the system`}
        actions={
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            <Plus className="h-4 w-4" />
            Add Patient
          </button>
        }
      />

      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            className="input pl-9 pr-4"
            placeholder="Search by name or MRN..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-secondary">Search</button>
        {search && (
          <button
            type="button"
            onClick={() => { setSearch(""); setSearchInput(""); setPage(1); }}
            className="btn-ghost"
          >
            <X className="h-4 w-4" />
            Clear
          </button>
        )}
      </form>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white">
        {loading ? (
          <div className="p-6 space-y-3">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        ) : error ? (
          <div className="p-10 text-center text-sm text-red-500">{error}</div>
        ) : patients.length === 0 ? (
          <EmptyState
            icon={<Users className="h-7 w-7" />}
            title={search ? "No patients match your search" : "No patients yet"}
            description={search ? "Try a different name or MRN." : "Add your first patient to begin generating discharge summaries."}
            action={
              !search ? (
                <button onClick={() => setShowCreate(true)} className="btn-primary">
                  <Plus className="h-4 w-4" />
                  Add First Patient
                </button>
              ) : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Patient</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">MRN</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Ward</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Admitted</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Documents</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Status</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {patients.map((patient) => (
                  <tr key={patient.id} className="group hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3.5">
                      <Link href={`/patients/${patient.id}`} className="flex items-center gap-2.5 group-hover:text-medical-blue-700">
                        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-medical-blue-100 text-xs font-bold text-medical-blue-600">
                          {patient.first_name[0]}{patient.last_name[0]}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-900">
                            {patient.first_name} {patient.last_name}
                          </p>
                          <p className="text-xs text-slate-400">Added {formatRelativeTime(patient.created_at)}</p>
                        </div>
                      </Link>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-xs text-slate-500">{patient.mrn}</span>
                    </td>
                    <td className="px-5 py-3.5 text-sm text-slate-500">{patient.ward ?? "—"}</td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1.5 text-xs text-slate-400">
                        <Calendar className="h-3.5 w-3.5" />
                        {patient.admission_date ? formatDate(patient.admission_date) : "—"}
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1.5 text-sm text-slate-700">
                        <FileText className="h-3.5 w-3.5 text-slate-400" />
                        {patient.document_count}
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      {patient.summary_status ? (
                        <SummaryStatusBadge status={patient.summary_status} />
                      ) : (
                        <span className="text-xs text-slate-400">No summary</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Link
                          href={`/patients/${patient.id}`}
                          className="text-xs font-medium text-medical-blue-600 hover:text-medical-blue-700"
                        >
                          View
                        </Link>
                        <span className="text-slate-200">|</span>
                        <Link
                          href={`/patients/${patient.id}/upload`}
                          className="text-xs font-medium text-slate-500 hover:text-slate-700"
                        >
                          Upload
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3">
            <p className="text-xs text-slate-400">
              Page {page} of {totalPages} ({total} patients)
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ghost h-8 w-8 p-0 disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const pageNum = i + 1;
                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={`h-8 w-8 rounded-lg text-xs font-medium transition-colors ${
                      page === pageNum
                        ? "bg-medical-blue-600 text-white"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-ghost h-8 w-8 p-0 disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {showCreate && (
        <CreatePatientModal
          onClose={() => setShowCreate(false)}
          onCreated={fetchPatients}
        />
      )}
    </div>
  );
}

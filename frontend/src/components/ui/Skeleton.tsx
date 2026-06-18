import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return <div className={cn("animate-pulse rounded bg-slate-200", className)} />;
}

export function SkeletonCard() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-3 h-8 w-16" />
    </div>
  );
}

export function SkeletonChart({ heightClass = "h-[220px]" }: { heightClass?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <Skeleton className="h-3 w-40" />
      <Skeleton className="mt-2 h-3 w-56" />
      <Skeleton className={cn("mt-4 w-full", heightClass)} />
    </div>
  );
}

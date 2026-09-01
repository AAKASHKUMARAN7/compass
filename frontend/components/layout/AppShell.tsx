"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { BarChart3, FileStack, MessagesSquare, ShieldCheck } from "lucide-react";

import { api } from "@/lib/api";
import { cn, formatNumber } from "@/lib/format";
import type { HealthResponse } from "@/types/api";

const NAV = [
  {
    href: "/",
    label: "Ask Compass",
    description: "Employee assistant",
    icon: MessagesSquare,
  },
  {
    href: "/admin",
    label: "Knowledge Base",
    description: "Policy documents",
    icon: FileStack,
  },
  {
    href: "/insights",
    label: "Insights",
    description: "Usage and gaps",
    icon: BarChart3,
  },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;

    const check = async () => {
      try {
        const result = await api.health();
        if (!active) return;
        setHealth(result);
        setReachable(true);
      } catch {
        if (!active) return;
        setReachable(false);
      }
    };

    void check();
    const timer = setInterval(check, 30_000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [pathname]);

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col bg-rail lg:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
            <ShieldCheck className="h-[18px] w-[18px]" aria-hidden />
          </div>
          <div className="leading-tight">
            <p className="text-[15px] font-semibold tracking-tight text-white">Compass</p>
            <p className="text-2xs text-slate-400">Policy Intelligence</p>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors",
                  active
                    ? "bg-rail-active text-white"
                    : "text-slate-400 hover:bg-rail-hover hover:text-slate-100",
                )}
              >
                <Icon className="h-[17px] w-[17px] shrink-0" aria-hidden />
                <span className="min-w-0 leading-tight">
                  <span className="block text-[13px] font-medium">{item.label}</span>
                  <span
                    className={cn(
                      "block text-2xs",
                      active ? "text-slate-400" : "text-slate-500",
                    )}
                  >
                    {item.description}
                  </span>
                </span>
              </Link>
            );
          })}
        </nav>

        <SystemPanel health={health} reachable={reachable} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <MobileNav pathname={pathname} />
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}

function SystemPanel({
  health,
  reachable,
}: {
  health: HealthResponse | null;
  reachable: boolean | null;
}) {
  const degraded =
    reachable === false ||
    health?.generation_mode === "extractive" ||
    health?.generation_mode === "degraded" ||
    health?.embedding_provider === "hashing-fallback";

  return (
    <div className="border-t border-white/5 px-5 py-4">
      <p className="label-caps text-slate-500">System</p>
      <div className="mt-2.5 space-y-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              reachable === false
                ? "bg-rose-500"
                : degraded
                  ? "bg-amber-400"
                  : "bg-emerald-400",
            )}
          />
          <span className="text-[12px] font-medium text-slate-300">
            {reachable === false
              ? "API unreachable"
              : reachable === null
                ? "Checking..."
                : degraded
                  ? "Degraded mode"
                  : "Operational"}
          </span>
        </div>

        {health ? (
          <dl className="space-y-1 text-2xs text-slate-500">
            <Row
              label="Model"
              value={
                health.generation_mode === "degraded"
                  ? `${health.llm_model ?? "model"} (fallback)`
                  : health.llm_model ?? "extractive"
              }
            />
            {health.generation_detail ? (
              <p className="pt-0.5 leading-snug text-amber-400/80">
                {health.generation_detail}
              </p>
            ) : null}
            <Row label="Embeddings" value={health.embedding_model} />
            <Row
              label="Indexed"
              value={`${formatNumber(health.chunks_indexed)} chunks`}
            />
          </dl>
        ) : reachable === false ? (
          <p className="text-2xs leading-relaxed text-slate-500">
            Start the API with{" "}
            <code className="font-mono text-slate-400">uvicorn app.main:app</code>
          </p>
        ) : null}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="shrink-0">{label}</dt>
      <dd className="truncate font-mono text-[10px] text-slate-400" title={value}>
        {value}
      </dd>
    </div>
  );
}

function MobileNav({ pathname }: { pathname: string }) {
  return (
    <div className="sticky top-0 z-30 flex items-center gap-1 border-b border-line bg-surface/90 px-3 py-2 backdrop-blur lg:hidden">
      <div className="mr-2 flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-white">
        <ShieldCheck className="h-4 w-4" aria-hidden />
      </div>
      {NAV.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors",
              active ? "bg-brand-50 text-brand-700" : "text-ink-muted hover:bg-canvas",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}

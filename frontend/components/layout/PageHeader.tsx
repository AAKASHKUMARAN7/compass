import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-4 px-6 py-6">
        <div className="min-w-0 space-y-1.5">
          {eyebrow ? <p className="label-caps">{eyebrow}</p> : null}
          <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
          {description ? (
            <p className="max-w-2xl text-[13.5px] leading-relaxed text-ink-muted">
              {description}
            </p>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </div>
  );
}

"use client";

import { Fragment, type ReactNode } from "react";

import { cn } from "@/lib/format";

/**
 * Renders the model's answer.
 *
 * Two things are handled deliberately: `[n]` citation markers become focusable
 * buttons that jump to the matching source card, and the light markdown the
 * model is allowed to emit (short lists, bold runs) is rendered rather than
 * shown as raw syntax. A full markdown parser is not warranted for a
 * constrained answer format.
 */
export function AnswerBody({
  text,
  validMarkers,
  onCitationClick,
}: {
  text: string;
  validMarkers: Set<number>;
  onCitationClick: (marker: number) => void;
}) {
  const blocks = parseBlocks(text);

  return (
    <div className="space-y-3 text-[14.5px] leading-[1.7] text-ink">
      {blocks.map((block, index) =>
        block.type === "list" ? (
          <ul key={index} className="ml-1 space-y-1.5">
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex} className="flex gap-2.5">
                <span
                  className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-ink-subtle"
                  aria-hidden
                />
                <span>
                  {renderInline(item, validMarkers, onCitationClick)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p key={index}>{renderInline(block.text, validMarkers, onCitationClick)}</p>
        ),
      )}
    </div>
  );
}

type Block = { type: "paragraph"; text: string } | { type: "list"; items: string[] };

function parseBlocks(text: string): Block[] {
  const lines = text.split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", text: paragraph.join(" ").trim() });
      paragraph = [];
    }
  };

  const flushList = () => {
    if (list.length) {
      blocks.push({ type: "list", items: [...list] });
      list = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    const bullet = line.match(/^(?:[-*•]|\d+[.)])\s+(.*)$/);

    if (bullet?.[1]) {
      flushParagraph();
      list.push(bullet[1]);
      continue;
    }

    if (!line) {
      flushList();
      flushParagraph();
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushList();
  flushParagraph();

  return blocks.length ? blocks : [{ type: "paragraph", text }];
}

const TOKEN = /(\[\d{1,2}\]|\*\*[^*]+\*\*)/g;

function renderInline(
  text: string,
  validMarkers: Set<number>,
  onCitationClick: (marker: number) => void,
): ReactNode[] {
  return text.split(TOKEN).filter(Boolean).map((part, index) => {
    const citation = part.match(/^\[(\d{1,2})\]$/);
    if (citation?.[1]) {
      const marker = Number(citation[1]);
      // A marker with no bound source is dropped: showing a reference the user
      // cannot open is worse than showing nothing.
      if (!validMarkers.has(marker)) return null;
      return (
        <button
          key={index}
          type="button"
          onClick={() => onCitationClick(marker)}
          title={`Jump to source ${marker}`}
          className={cn(
            "mx-0.5 inline-flex h-[18px] min-w-[18px] translate-y-[-1px] items-center justify-center",
            "rounded border border-brand-200 bg-brand-50 px-1 align-middle",
            "text-[10.5px] font-semibold text-brand-700 transition-colors",
            "hover:border-brand-400 hover:bg-brand-100",
          )}
        >
          {marker}
        </button>
      );
    }

    const bold = part.match(/^\*\*([^*]+)\*\*$/);
    if (bold?.[1]) {
      return (
        <strong key={index} className="font-semibold text-ink">
          {bold[1]}
        </strong>
      );
    }

    return <Fragment key={index}>{part}</Fragment>;
  });
}

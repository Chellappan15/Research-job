import { Search, X } from "lucide-react";
import { useEffect, useId, useState } from "react";

import type { Source } from "../../api/types";
import { useDebounced } from "../../lib/useDebounced";

const field =
  "h-9 rounded-md border border-line-strong bg-canvas px-3 text-sm text-fg placeholder:text-fg-subtle hover:border-fg-subtle focus-visible:outline-accent";

export function SearchInput({
  value,
  onChange,
  placeholder = "Search",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState(value);
  const debounced = useDebounced(draft, 350);
  useEffect(() => setDraft(value), [value]);
  useEffect(() => {
    if (debounced !== value) onChange(debounced.trim());
  }, [debounced]);
  return (
    <form
      role="search"
      className="relative min-w-0 flex-1"
      onSubmit={(e) => {
        e.preventDefault();
        onChange(draft.trim());
      }}
    >
      <label className="sr-only" htmlFor="feed-search">
        {placeholder}
      </label>
      <Search
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle"
        aria-hidden
      />
      <input
        id="feed-search"
        type="search"
        value={draft}
        maxLength={200}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={placeholder}
        className={`${field} w-full pr-9 pl-9`}
      />
      {draft && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => {
            setDraft("");
            onChange("");
          }}
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-fg-subtle hover:text-fg"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      )}
    </form>
  );
}

export function SourceSelect({
  sources,
  value,
  onChange,
  label = "Source",
}: {
  sources: Source[];
  value: string;
  onChange: (v: string) => void;
  label?: string;
}) {
  const id = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-fg-muted">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${field} max-w-full pr-8`}
      >
        <option value="">All sources</option>
        {sources.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export function DateInput({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  min?: string;
  max?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-fg-muted">
        {label}
      </label>
      <input
        id={id}
        type="date"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.value)}
        className={`${field} [color-scheme:dark]`}
      />
    </div>
  );
}

export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string; count?: number }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap rounded-md border border-line-strong bg-canvas p-0.5">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`rounded px-3 py-1 text-sm font-medium ${
              active ? "bg-elevated text-fg shadow-sm" : "text-fg-muted hover:text-fg"
            }`}
          >
            {o.label}
            {o.count !== undefined && (
              <span className="ml-1.5 text-xs text-fg-subtle tabular">{o.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

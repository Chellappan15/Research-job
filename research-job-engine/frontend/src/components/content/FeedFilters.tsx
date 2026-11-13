import { FilterX } from "lucide-react";

import type { Source } from "../../api/types";
import { DateInput, SearchInput, SourceSelect } from "../ui/Controls";

export interface FeedFilterValues {
  q: string;
  source: string;
  from: string;
  to: string;
}

export function FeedFilters({
  values,
  sources,
  onChange,
  onClear,
  searchPlaceholder,
}: {
  values: FeedFilterValues;
  sources: Source[];
  onChange: (key: keyof FeedFilterValues, value: string) => void;
  onClear: () => void;
  searchPlaceholder: string;
}) {
  const active = Object.values(values).some(Boolean);
  return (
    <div className="mb-5 flex flex-col gap-3 rounded-lg border border-line bg-surface p-3">
      <SearchInput
        value={values.q}
        onChange={(v) => onChange("q", v)}
        placeholder={searchPlaceholder}
      />
      <div className="flex flex-wrap items-end gap-3">
        <SourceSelect
          sources={sources}
          value={values.source}
          onChange={(v) => onChange("source", v)}
        />
        <DateInput
          label="From"
          value={values.from}
          max={values.to || undefined}
          onChange={(v) => onChange("from", v)}
        />
        <DateInput
          label="To"
          value={values.to}
          min={values.from || undefined}
          onChange={(v) => onChange("to", v)}
        />
        {active && (
          <button
            type="button"
            onClick={onClear}
            className="inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-sm font-medium text-fg-muted hover:bg-hover hover:text-fg"
          >
            <FilterX className="size-4" aria-hidden /> Clear filters
          </button>
        )}
      </div>
    </div>
  );
}

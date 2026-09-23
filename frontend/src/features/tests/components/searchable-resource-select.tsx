import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export interface SearchableResourceSelectProps<T> {
  label: string;
  value: string | null;
  items: T[];
  loading?: boolean;
  error?: string;
  placeholder: string;
  getId: (item: T) => string;
  getLabel: (item: T) => string;
  getMeta?: (item: T) => string;
  onChange: (id: string | null) => void;
}

/** A single-value searchable selector with a scrollable result list. */
export function SearchableResourceSelect<T>({
  label,
  value,
  items,
  loading = false,
  error,
  placeholder,
  getId,
  getLabel,
  getMeta,
  onChange,
}: SearchableResourceSelectProps<T>) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = items.find((item) => getId(item) === value);
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return items;
    return items.filter((item) => {
      const haystack = `${getLabel(item)} ${getId(item)} ${getMeta?.(item) ?? ""}`;
      return haystack.toLowerCase().includes(normalized);
    });
  }, [getId, getLabel, getMeta, items, query]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => {
      document.removeEventListener("mousedown", close);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative space-y-1.5">
      <label className="text-sm font-medium text-text-secondary">{label}</label>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex min-h-10 w-full items-center justify-between rounded-md border border-border-default bg-surface px-3 py-2 text-left text-sm hover:bg-surface-hover"
        onClick={() => {
          setOpen((current) => !current);
        }}
      >
        <span className={cn(selected ? "text-text-primary" : "text-text-tertiary")}>
          {selected ? getLabel(selected) : placeholder}
        </span>
        <ChevronDown className="h-4 w-4 text-text-tertiary" />
      </button>
      {error && <p className="text-xs text-error">{error}</p>}
      {open && (
        <div className="absolute z-30 mt-1 w-full rounded-md border border-border-strong bg-surface-elevated p-2 shadow-xl">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
            <input
              autoFocus
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
              }}
              placeholder={`Search ${label.toLowerCase()}...`}
              className="h-9 w-full rounded border border-border-default bg-surface pl-9 pr-3 text-sm text-text-primary outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
          <div role="listbox" className="mt-2 max-h-56 overflow-y-auto">
            {loading && (
              <p className="px-2 py-3 text-sm text-text-tertiary">Loading...</p>
            )}
            {!loading && filtered.length === 0 && (
              <p className="px-2 py-3 text-sm text-text-tertiary">No matches.</p>
            )}
            {filtered.map((item) => {
              const id = getId(item);
              const isSelected = id === value;
              return (
                <button
                  key={id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className="flex w-full items-center justify-between rounded px-2 py-2 text-left hover:bg-surface-hover"
                  onClick={() => {
                    onChange(id);
                    setOpen(false);
                    setQuery("");
                  }}
                >
                  <span>
                    <span className="block text-sm text-text-primary">
                      {getLabel(item)}
                    </span>
                    <span className="block text-xs text-text-tertiary">
                      {getMeta?.(item) ?? id}
                    </span>
                  </span>
                  {isSelected && <Check className="h-4 w-4 text-accent" />}
                </button>
              );
            })}
          </div>
          {value && (
            <button
              type="button"
              className="mt-1 w-full border-t border-border-default px-2 pt-2 text-left text-xs text-text-tertiary hover:text-text-primary"
              onClick={() => {
                onChange(null);
                setOpen(false);
              }}
            >
              Clear selection
            </button>
          )}
        </div>
      )}
    </div>
  );
}

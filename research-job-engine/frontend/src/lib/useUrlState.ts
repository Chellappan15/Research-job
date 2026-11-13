import { useCallback } from "react";
import { useSearchParams } from "react-router";

/**
 * Filters and page live in the URL so views survive refresh and can be shared.
 * Changing any filter resets the page to 1.
 */
export function useUrlState<K extends string>(keys: readonly K[]) {
  const [params, setParams] = useSearchParams();

  const values = Object.fromEntries(keys.map((k) => [k, params.get(k) ?? ""])) as Record<
    K,
    string
  >;
  const page = Math.max(1, Number.parseInt(params.get("page") ?? "1", 10) || 1);

  const setFilter = useCallback(
    (key: K, value: string) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (value) next.set(key, value);
          else next.delete(key);
          next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const setPage = useCallback(
    (p: number) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (p <= 1) next.delete("page");
        else next.set("page", String(p));
        return next;
      });
    },
    [setParams],
  );

  const clear = useCallback(() => setParams(new URLSearchParams(), { replace: true }), [setParams]);

  return { values, page, setFilter, setPage, clear };
}

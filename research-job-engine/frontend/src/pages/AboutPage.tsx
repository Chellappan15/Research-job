import { Link } from "react-router";

import { SourceTypeBadge } from "../components/ui/Badge";
import { PageHeader } from "../components/ui/PageHeader";
import { useSources } from "../hooks/queries";

export function AboutPage() {
  const sources = useSources();
  const active = (sources.data ?? []).filter((s) => s.enabled);
  return (
    <div className="max-w-2xl">
      <PageHeader title="About TechPulse" />
      <div className="space-y-4 leading-relaxed text-fg-muted">
        <p>
          TechPulse collects AI news, research, software releases and YouTube videos from public
          feeds and shows them in one place, newest first. Every item links to the original
          publisher; TechPulse doesn’t rewrite or summarise content.
        </p>
        <p>
          New content is checked for automatically throughout the day. Duplicates — the same story
          published by several sites — are shown only once.
        </p>
        <p>
          Curious how it works behind the scenes? The{" "}
          <Link to="/admin" className="font-medium text-accent hover:underline">
            system status page
          </Link>{" "}
          shows live ingestion runs, retries and source health.
        </p>
      </div>
      {active.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-base font-semibold text-fg">Where the content comes from</h2>
          <ul className="flex flex-col divide-y divide-line rounded-xl border border-line bg-surface">
            {active.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                <span className="text-fg">{s.name}</span>
                <SourceTypeBadge type={s.source_type} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

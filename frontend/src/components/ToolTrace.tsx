import type { ToolTrace as Trace } from "../types";

/** Shows which tools ran for a reply. Click a chip to see arguments / errors. */
export function ToolTrace({ tools }: { tools: Trace[] }) {
  if (tools.length === 0) return null;
  return (
    <div className="tools">
      {tools.map((t, i) => (
        <details key={i} className={t.ok ? "tool ok" : "tool failed"}>
          <summary>
            <span className="tool-icon">{t.ok ? "⚙" : "⚠"}</span>
            {t.name}
            <span className="tool-ms">{Math.round(t.duration_ms)} ms</span>
          </summary>
          <pre>{prettyJson(t.arguments)}</pre>
          {t.error && <div className="tool-error">{t.error}</div>}
        </details>
      ))}
    </div>
  );
}

function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw; // model sent invalid JSON; show it as-is
  }
}

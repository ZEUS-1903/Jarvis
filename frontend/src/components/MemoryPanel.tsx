import { useState, type FormEvent } from "react";
import { addMemory, approveMemory, deleteMemory } from "../api";
import type { Memory, MemoryCategory } from "../types";

const CATEGORIES: MemoryCategory[] = ["preference", "person", "project", "fact", "other"];

interface Props {
  active: Memory[];
  pending: Memory[];
  onChange: () => void; // re-fetch after any edit
  onClose: () => void;
}

/** Everything JARVIS remembers about you: review proposals, add, delete. */
export function MemoryPanel({ active, pending, onChange, onClose }: Props) {
  const [draft, setDraft] = useState("");
  const [category, setCategory] = useState<MemoryCategory>("preference");
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    run(async () => {
      await addMemory(text, category);
      setDraft("");
    });
  }

  return (
    <aside className="memory-panel" aria-label="Memory">
      <div className="memory-head">
        <h2>Memory</h2>
        <button className="ghost" onClick={onClose} aria-label="Close memory panel">✕</button>
      </div>

      {pending.length > 0 && (
        <section>
          <h3>Jarvis would like to remember</h3>
          {pending.map((m) => (
            <div key={m.id} className="memory-item pending">
              <span className="memory-text">{m.content}</span>
              <span className="memory-actions">
                <button onClick={() => run(() => approveMemory(m.id))}>Save</button>
                <button className="ghost" onClick={() => run(() => deleteMemory(m.id))}>Dismiss</button>
              </span>
            </div>
          ))}
        </section>
      )}

      <section>
        <h3>What Jarvis knows ({active.length})</h3>
        {active.length === 0 && <p className="muted">Nothing yet. Try: “Remember that I prefer meetings after 10 AM.”</p>}
        {active.map((m) => (
          <div key={m.id} className="memory-item">
            <span className="memory-cat">{m.category}</span>
            <span className="memory-text">{m.content}</span>
            <button className="ghost icon" onClick={() => run(() => deleteMemory(m.id))} aria-label={`Delete: ${m.content}`} title="Delete">✕</button>
          </div>
        ))}
      </section>

      <form className="memory-add" onSubmit={submit}>
        <input value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={300} placeholder="Add something to remember…" />
        <select value={category} onChange={(e) => setCategory(e.target.value as MemoryCategory)}>
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <button type="submit" disabled={!draft.trim()}>Add</button>
      </form>
      {error && <div className="error">{error}</div>}
    </aside>
  );
}

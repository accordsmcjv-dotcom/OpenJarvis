import { useCallback, useEffect, useState } from "react";
import { Plus, Search, Save, Trash2, X, StickyNote, RefreshCw } from "lucide-react";
import { createNote, deleteNote, fetchNotes, updateNote, type SmartNote } from "../lib/api";

export function NotesPage() {
  const [notes, setNotes] = useState<SmartNote[]>([]);
  const [selected, setSelected] = useState<SmartNote | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setNotes(await fetchNotes(query));
    } catch (e) {
      setError(e instanceof Error ? e.message : "नोंदी मिळवता आल्या नाहीत");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => { void refresh(); }, [refresh]);

  const newNote = () => {
    setSelected(null);
    setTitle("");
    setContent("");
    setError("");
  };

  const openNote = (note: SmartNote) => {
    setSelected(note);
    setTitle(note.title);
    setContent(note.content);
    setError("");
  };

  const save = async () => {
    if (!title.trim() || !content.trim()) {
      setError("शीर्षक आणि मजकूर दोन्ही लिहा.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const saved = selected
        ? await updateNote(selected.id, title, content)
        : await createNote(title, content);
      setSelected(saved);
      setTitle(saved.title);
      setContent(saved.content);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "नोंद जतन करता आली नाही");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!selected || !window.confirm("ही नोंद कायमची हटवायची आहे का?")) return;
    setSaving(true);
    try {
      await deleteNote(selected.id);
      newNote();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "नोंद हटवता आली नाही");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 p-4 md:p-6 gap-4 overflow-y-auto"
      style={{ color: "var(--color-text)" }}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <StickyNote size={24} style={{ color: "var(--color-accent)" }} />
          <div>
            <h1 className="text-xl font-semibold">माझ्या नोंदी</h1>
            <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>तुमच्या महत्त्वाच्या गोष्टी सुरक्षितपणे जतन करा</p>
          </div>
        </div>
        <button onClick={newNote} className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
          style={{ background: "var(--color-accent)", color: "var(--color-on-accent)" }}>
          <Plus size={16} /> नवीन नोंद
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-4 flex-1 min-h-0">
        <section className="w-full md:w-80 shrink-0 flex flex-col gap-3 min-h-0">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg"
            style={{ background: "var(--color-bg-secondary)", border: "1px solid var(--color-border)" }}>
            <Search size={16} />
            <input value={query} onChange={e => setQuery(e.target.value)}
              placeholder="नोंदी शोधा..." className="bg-transparent outline-none w-full text-sm"
              style={{ color: "var(--color-text)" }} />
            <button onClick={() => void refresh()} title="Refresh"><RefreshCw size={15} /></button>
          </div>
          <div className="flex-1 overflow-y-auto flex flex-col gap-2">
            {loading && <p className="text-sm p-3">नोंदी लोड होत आहेत...</p>}
            {!loading && notes.length === 0 && <p className="text-sm p-3" style={{ color: "var(--color-text-secondary)" }}>अजून कोणतीही नोंद नाही.</p>}
            {notes.map(note => (
              <button key={note.id} onClick={() => openNote(note)}
                className="text-left p-3 rounded-lg"
                style={{ background: selected?.id === note.id ? "var(--color-accent-subtle)" : "var(--color-bg-secondary)", border: "1px solid var(--color-border)" }}>
                <span className="block font-medium text-sm truncate">{note.title}</span>
                <span className="block text-xs mt-1 line-clamp-2" style={{ color: "var(--color-text-secondary)" }}>{note.content}</span>
                <span className="block text-[10px] mt-2" style={{ color: "var(--color-text-tertiary)" }}>{new Date(note.updated_at).toLocaleString("mr-IN")}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="flex-1 min-w-0 rounded-xl p-4 flex flex-col gap-3"
          style={{ background: "var(--color-bg-secondary)", border: "1px solid var(--color-border)" }}>
          <input value={title} onChange={e => setTitle(e.target.value)}
            maxLength={200} placeholder="नोंदीचे शीर्षक"
            className="w-full bg-transparent outline-none text-lg font-semibold"
            style={{ color: "var(--color-text)" }} />
          <textarea value={content} onChange={e => setContent(e.target.value)}
            maxLength={20000} placeholder="इथे तुमची नोंद लिहा..."
            className="flex-1 min-h-48 resize-y bg-transparent outline-none text-sm leading-6"
            style={{ color: "var(--color-text)" }} />
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>{content.length}/20000</span>
            <div className="flex gap-2">
              {selected && <button onClick={() => void remove()} disabled={saving}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
                style={{ color: "var(--color-error)", border: "1px solid var(--color-border)" }}>
                <Trash2 size={15} /> हटवा
              </button>}
              <button onClick={newNote} className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
                style={{ border: "1px solid var(--color-border)" }}>
                <X size={15} /> साफ करा
              </button>
              <button onClick={() => void save()} disabled={saving}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
                style={{ background: "var(--color-accent)", color: "var(--color-on-accent)", opacity: saving ? 0.6 : 1 }}>
                <Save size={15} /> {saving ? "जतन होत आहे..." : "जतन करा"}
              </button>
            </div>
          </div>
          {error && <p role="alert" className="text-sm" style={{ color: "var(--color-error)" }}>{error}</p>}
        </section>
      </div>
    </div>
  );
}

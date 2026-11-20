import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Building2, CalendarDays, IndianRupee, MapPin, Plus, Search, Trash2, X } from 'lucide-react';

type ProjectStatus = 'Planning' | 'In Progress' | 'On Hold' | 'Completed';
type Project = {
  id: string;
  name: string;
  client: string;
  siteAddress: string;
  contractAmount: number;
  startDate: string;
  targetDate: string;
  status: ProjectStatus;
  createdAt: string;
};

const STORAGE_KEY = 'shivam-construction-projects-v1';
const emptyForm = {
  name: '', client: '', siteAddress: '', contractAmount: '',
  startDate: '', targetDate: '', status: 'Planning' as ProjectStatus,
};

function loadProjects(): Project[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

const money = (value: number) => new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 0,
}).format(value);

const statusStyles: Record<ProjectStatus, string> = {
  Planning: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  'In Progress': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  'On Hold': 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  Completed: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
};

export function ConstructionPage() {
  const [projects, setProjects] = useState<Project[]>(loadProjects);
  const [showForm, setShowForm] = useState(false);
  const [query, setQuery] = useState('');
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
  }, [projects]);

  const filtered = useMemo(() => projects.filter((project) =>
    [project.name, project.client, project.siteAddress].join(' ').toLowerCase().includes(query.toLowerCase())
  ), [projects, query]);

  const totalValue = projects.reduce((sum, project) => sum + project.contractAmount, 0);
  const activeCount = projects.filter((project) => project.status === 'In Progress').length;

  const addProject = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.name.trim() || !form.client.trim()) {
      setError('प्रोजेक्टचे नाव आणि ग्राहकाचे नाव आवश्यक आहे.');
      return;
    }
    const amount = Number(form.contractAmount || 0);
    if (!Number.isFinite(amount) || amount < 0) {
      setError('कराराची रक्कम योग्य भरा.');
      return;
    }
    const project: Project = {
      ...form,
      id: crypto.randomUUID(),
      name: form.name.trim(),
      client: form.client.trim(),
      siteAddress: form.siteAddress.trim(),
      contractAmount: amount,
      createdAt: new Date().toISOString(),
    };
    setProjects((current) => [project, ...current]);
    setForm(emptyForm);
    setError('');
    setShowForm(false);
  };

  const deleteProject = (id: string) => {
    if (!window.confirm('हा प्रोजेक्ट हटवायचा आहे का?')) return;
    setProjects((current) => current.filter((project) => project.id !== id));
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-6 md:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-accent)' }}>
              <Building2 size={15} /> SHIVAM WORKSPACE
            </div>
            <h1 className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>Construction Manager</h1>
            <p className="mt-1 text-sm" style={{ color: 'var(--color-text-secondary)' }}>बंगले आणि Residential Buildings प्रोजेक्टचे व्यवस्थापन</p>
          </div>
          <button onClick={() => setShowForm(true)} className="inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium" style={{ background: 'var(--color-accent)', color: '#07111f' }}>
            <Plus size={17} /> नवीन प्रोजेक्ट
          </button>
        </header>

        <section className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>एकूण प्रोजेक्ट</p>
            <p className="mt-2 text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>{projects.length}</p>
          </div>
          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>सध्या सुरू असलेले</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-400">{activeCount}</p>
          </div>
          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>एकूण करार मूल्य</p>
            <p className="mt-2 text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>{money(totalValue)}</p>
          </div>
        </section>

        {showForm && (
          <section className="rounded-2xl border p-5" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>नवीन प्रोजेक्टची माहिती</h2>
              <button onClick={() => { setShowForm(false); setError(''); }} className="rounded-lg p-2" aria-label="Close"><X size={18} /></button>
            </div>
            <form onSubmit={addProject} className="grid gap-4 sm:grid-cols-2">
              {[
                { label: 'प्रोजेक्टचे नाव *', key: 'name', placeholder: 'उदा. Joshi Bungalow' },
                { label: 'ग्राहकाचे नाव *', key: 'client', placeholder: 'ग्राहकाचे पूर्ण नाव' },
                { label: 'साइटचा पत्ता', key: 'siteAddress', placeholder: 'गाव / परिसर / पत्ता' },
                { label: 'कराराची रक्कम (₹)', key: 'contractAmount', placeholder: 'उदा. 4500000', type: 'number' },
              ].map((field) => (
                <label key={field.key} className="space-y-1.5 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  {field.label}
                  <input
                    type={field.type || 'text'}
                    min={field.type === 'number' ? '0' : undefined}
                    value={form[field.key as keyof typeof form]}
                    onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}
                    placeholder={field.placeholder}
                    className="w-full rounded-xl border px-3 py-2.5 outline-none"
                    style={{ background: 'var(--color-bg)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
                  />
                </label>
              ))}
              <label className="space-y-1.5 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                काम सुरू तारीख
                <input type="date" value={form.startDate} onChange={(e) => setForm((c) => ({ ...c, startDate: e.target.value }))} className="w-full rounded-xl border px-3 py-2.5" style={{ background: 'var(--color-bg)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }} />
              </label>
              <label className="space-y-1.5 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                अपेक्षित पूर्णता तारीख
                <input type="date" value={form.targetDate} onChange={(e) => setForm((c) => ({ ...c, targetDate: e.target.value }))} className="w-full rounded-xl border px-3 py-2.5" style={{ background: 'var(--color-bg)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }} />
              </label>
              <label className="space-y-1.5 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                कामाची स्थिती
                <select value={form.status} onChange={(e) => setForm((c) => ({ ...c, status: e.target.value as ProjectStatus }))} className="w-full rounded-xl border px-3 py-2.5" style={{ background: 'var(--color-bg)', borderColor: 'var(--color-border)', color: 'var(--color-text)' }}>
                  <option value="Planning">नियोजन</option><option value="In Progress">काम सुरू</option><option value="On Hold">तात्पुरते थांबले</option><option value="Completed">पूर्ण</option>
                </select>
              </label>
              {error && <p className="text-sm text-red-400 sm:col-span-2">{error}</p>}
              <div className="flex justify-end gap-2 sm:col-span-2">
                <button type="button" onClick={() => setShowForm(false)} className="rounded-xl border px-4 py-2 text-sm" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>रद्द</button>
                <button type="submit" className="rounded-xl px-4 py-2 text-sm font-medium" style={{ background: 'var(--color-accent)', color: '#07111f' }}>प्रोजेक्ट जतन करा</button>
              </div>
            </form>
          </section>
        )}

        <section className="space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>तुझे प्रोजेक्ट</h2>
            <div className="flex items-center gap-2 rounded-xl border px-3 py-2" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <Search size={16} style={{ color: 'var(--color-text-tertiary)' }} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="प्रोजेक्ट शोधा..." className="w-full bg-transparent text-sm outline-none sm:w-56" style={{ color: 'var(--color-text)' }} />
            </div>
          </div>
          {filtered.length === 0 ? (
            <div className="rounded-2xl border border-dashed p-10 text-center" style={{ borderColor: 'var(--color-border)' }}>
              <Building2 size={32} className="mx-auto mb-3" style={{ color: 'var(--color-text-tertiary)' }} />
              <p className="font-medium" style={{ color: 'var(--color-text)' }}>{projects.length ? 'शोधाशी जुळणारा प्रोजेक्ट सापडला नाही.' : 'अजून कोणताही प्रोजेक्ट जोडलेला नाही.'}</p>
              <p className="mt-1 text-sm" style={{ color: 'var(--color-text-secondary)' }}>पहिला बंगला किंवा Residential Building प्रोजेक्ट जोडून सुरुवात कर.</p>
              {!projects.length && <button onClick={() => setShowForm(true)} className="mt-4 rounded-xl px-4 py-2 text-sm" style={{ background: 'var(--color-accent)', color: '#07111f' }}>पहिला प्रोजेक्ट जोडा</button>}
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {filtered.map((project) => (
                <article key={project.id} className="rounded-2xl border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate font-semibold" style={{ color: 'var(--color-text)' }}>{project.name}</h3>
                      <p className="mt-1 text-sm" style={{ color: 'var(--color-text-secondary)' }}>{project.client}</p>
                    </div>
                    <button onClick={() => deleteProject(project.id)} className="rounded-lg p-2 text-red-400 hover:bg-red-500/10" aria-label="Delete project"><Trash2 size={16} /></button>
                  </div>
                  <span className={`mt-3 inline-flex rounded-full border px-2.5 py-1 text-xs ${statusStyles[project.status]}`}>
                    {{ Planning: 'नियोजन', 'In Progress': 'काम सुरू', 'On Hold': 'तात्पुरते थांबले', Completed: 'पूर्ण' }[project.status]}
                  </span>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div className="flex items-center gap-2" style={{ color: 'var(--color-text-secondary)' }}><IndianRupee size={15} />{money(project.contractAmount)}</div>
                    <div className="flex items-center gap-2" style={{ color: 'var(--color-text-secondary)' }}><CalendarDays size={15} />{project.targetDate || 'पूर्णता तारीख नाही'}</div>
                    <div className="col-span-2 flex items-start gap-2" style={{ color: 'var(--color-text-secondary)' }}><MapPin size={15} className="mt-0.5 shrink-0" />{project.siteAddress || 'साइटचा पत्ता दिलेला नाही'}</div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
        <p className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>पहिल्या टप्प्यातील नोंदी या डिव्हाइसच्या App storage मध्ये जतन होतात. Cloud backup आणि Client Portal पुढील टप्प्यात जोडू.</p>
      </div>
    </div>
  );
}

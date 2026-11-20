import { useEffect, useMemo, useState } from "react";
import { Bell, CalendarDays, Check, Clock3, MapPin, Plus, Trash2, Volume2 } from "lucide-react";
import { Capacitor, registerPlugin } from "@capacitor/core";
import { useTtsStore } from "../lib/tts";

type SiteReminder = { id: string; title: string; site: string; date: string; time: string; done: boolean; createdAt: number };
interface SiteReminderApi {
  scheduleReminder(options: { id: string; title: string; site: string; triggerAt: number }): Promise<{ scheduled: boolean }>;
  cancelReminder(options: { id: string }): Promise<{ cancelled: boolean }>;
}
const SiteReminderNative = registerPlugin<SiteReminderApi>("SiteReminder");
const STORAGE_KEY = "shivam-site-reminders-v1";
const readReminders = (): SiteReminder[] => {
  try { const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); return Array.isArray(value) ? value : []; }
  catch { return []; }
};
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
};

export function SiteRemindersPage() {
  const [items, setItems] = useState<SiteReminder[]>(readReminders);
  const [title, setTitle] = useState("");
  const [site, setSite] = useState("");
  const [date, setDate] = useState(today());
  const [time, setTime] = useState("08:00");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const persist = (next: SiteReminder[]) => { setItems(next); localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); };
  const upcoming = useMemo(() => [...items].filter(x => !x.done).sort((a,b) => (a.date+a.time).localeCompare(b.date+b.time)), [items]);
  const speakToday = async () => {
    const tasks = upcoming.filter(x => x.date <= today());
    const text = tasks.length
      ? "आजची आणि बाकी राहिलेली साइटची कामे. " + tasks.map((x,i) => `${i+1}. ${x.site ? x.site + " येथे, " : ""}${x.title}.`).join(" ")
      : "आजसाठी कोणतेही साइटचे काम नोंदवलेले नाही.";
    await useTtsStore.getState().speak("site-reminders-manual-" + Date.now(), text);
  };

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    // Reschedule future reminders whenever this page is opened, in case Android cleared alarms.
    for (const item of items) {
      if (item.done) continue;
      const triggerAt = new Date(`${item.date}T${item.time}:00`).getTime();
      if (Number.isFinite(triggerAt) && triggerAt > Date.now()) {
        void SiteReminderNative.scheduleReminder({ id: item.id, title: item.title, site: item.site, triggerAt }).catch(() => {});
      }
    }
  }, []);

  const add = async () => {
    if (!title.trim() || !date || !time) { setError("कामाचे नाव, तारीख आणि वेळ भरा."); return; }
    const triggerAt = new Date(`${date}T${time}:00`).getTime();
    if (!Number.isFinite(triggerAt) || triggerAt <= Date.now()) { setError("भविष्यातील तारीख आणि वेळ निवडा."); return; }
    setSaving(true); setError("");
    const item: SiteReminder = { id: `${Date.now()}-${Math.random().toString(36).slice(2,8)}`, title: title.trim(), site: site.trim(), date, time, done: false, createdAt: Date.now() };
    try {
      if (Capacitor.isNativePlatform()) await SiteReminderNative.scheduleReminder({ id: item.id, title: item.title, site: item.site, triggerAt });
      persist([...items, item]); setTitle(""); setSite(""); setDate(today()); setTime("08:00");
    } catch (e) { setError(e instanceof Error ? e.message : "Reminder लावता आला नाही."); }
    finally { setSaving(false); }
  };

  const complete = async (item: SiteReminder) => {
    const next = items.map(x => x.id === item.id ? { ...x, done: true } : x);
    persist(next);
    if (Capacitor.isNativePlatform()) { try { await SiteReminderNative.cancelReminder({ id: item.id }); } catch { /* local completion is retained */ } }
  };
  const remove = async (item: SiteReminder) => {
    persist(items.filter(x => x.id !== item.id));
    if (Capacitor.isNativePlatform()) { try { await SiteReminderNative.cancelReminder({ id: item.id }); } catch { /* local removal is retained */ } }
  };

  return <div className="h-full min-h-0 overflow-y-auto p-4 md:p-6 flex flex-col gap-5" style={{color:"var(--color-text)"}}>
    <header className="flex items-center justify-between gap-3 flex-wrap">
      <div className="flex items-center gap-3"><CalendarDays size={25} style={{color:"var(--color-accent)"}}/><div><h1 className="text-xl font-semibold">Site Reminder</h1><p className="text-xs" style={{color:"var(--color-text-secondary)"}}>उद्याची कामे आणि साइट व्हिजिट लक्षात ठेवा</p></div></div>
      <button onClick={() => void speakToday()} className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm" style={{background:"var(--color-accent)",color:"var(--color-on-accent)"}}><Volume2 size={16}/> कामे ऐका</button>
    </header>
    <section className="rounded-xl p-4 flex flex-col gap-3" style={{background:"var(--color-bg-secondary)",border:"1px solid var(--color-border)"}}>
      <h2 className="font-medium flex items-center gap-2"><Plus size={17}/> नवीन कामाची आठवण</h2>
      <input value={title} onChange={e=>setTitle(e.target.value)} maxLength={180} placeholder="उदा. स्लॅबचे काम तपासायचे" className="rounded-lg px-3 py-2 bg-transparent border text-sm" style={{borderColor:"var(--color-border)"}}/>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="text-xs flex flex-col gap-1" style={{color:"var(--color-text-secondary)"}}>साइट / क्लायंटचे नाव<input value={site} onChange={e=>setSite(e.target.value)} maxLength={120} placeholder="उदा. Joshi यांचा बंगला" className="rounded-lg px-3 py-2 bg-transparent border text-sm" style={{color:"var(--color-text)",borderColor:"var(--color-border)"}}/></label>
        <label className="text-xs flex flex-col gap-1" style={{color:"var(--color-text-secondary)"}}>तारीख<input type="date" min={today()} value={date} onChange={e=>setDate(e.target.value)} className="rounded-lg px-3 py-2 bg-transparent border text-sm" style={{color:"var(--color-text)",borderColor:"var(--color-border)"}}/></label>
        <label className="text-xs flex flex-col gap-1" style={{color:"var(--color-text-secondary)"}}>वेळ<input type="time" value={time} onChange={e=>setTime(e.target.value)} className="rounded-lg px-3 py-2 bg-transparent border text-sm" style={{color:"var(--color-text)",borderColor:"var(--color-border)"}}/></label>
      </div>
      <div className="flex justify-end"><button onClick={()=>void add()} disabled={saving} className="px-4 py-2 rounded-lg text-sm flex items-center gap-2" style={{background:"var(--color-accent)",color:"var(--color-on-accent)",opacity:saving?0.6:1}}><Bell size={15}/>{saving?"जतन होत आहे...":"आठवण लावा"}</button></div>
      {error && <p role="alert" className="text-sm" style={{color:"var(--color-error)"}}>{error}</p>}
      <p className="text-[11px]" style={{color:"var(--color-text-tertiary)"}}>Android वर ठरलेल्या वेळी सूचना येईल. सूचना वेळेत येण्यासाठी SHIVAM च्या Notifications परवानगी सुरू ठेवा.</p>
    </section>
    <section className="flex flex-col gap-2">
      <h2 className="font-semibold">बाकीची कामे</h2>
      {upcoming.length===0 && <p className="text-sm p-4 rounded-lg" style={{background:"var(--color-bg-secondary)",color:"var(--color-text-secondary)"}}>अजून कोणतीही आठवण नाही.</p>}
      {upcoming.map(item=><article key={item.id} className="rounded-xl p-3 flex items-start gap-3" style={{background:"var(--color-bg-secondary)",border:"1px solid var(--color-border)"}}>
        <div className="flex-1 min-w-0"><p className="font-medium text-sm">{item.title}</p>{item.site && <p className="text-xs mt-1 flex items-center gap-1" style={{color:"var(--color-text-secondary)"}}><MapPin size={12}/>{item.site}</p>}<p className="text-xs mt-2 flex items-center gap-1" style={{color:"var(--color-text-tertiary)"}}><Clock3 size={12}/>{new Date(`${item.date}T${item.time}:00`).toLocaleString("mr-IN",{dateStyle:"medium",timeStyle:"short"})}</p></div>
        <button onClick={()=>void complete(item)} title="पूर्ण झाले" className="p-2 rounded-lg" style={{color:"var(--color-success)"}}><Check size={17}/></button><button onClick={()=>void remove(item)} title="हटवा" className="p-2 rounded-lg" style={{color:"var(--color-error)"}}><Trash2 size={16}/></button>
      </article>)}
    </section>
    {items.some(x=>x.done) && <section className="flex flex-col gap-2"><h2 className="font-semibold text-sm" style={{color:"var(--color-text-secondary)"}}>पूर्ण झालेली कामे</h2>{items.filter(x=>x.done).map(item=><div key={item.id} className="flex items-center justify-between gap-2 text-sm p-3 rounded-lg opacity-60" style={{background:"var(--color-bg-secondary)"}}><span className="line-through">{item.title} {item.site && "— "+item.site}</span><button onClick={()=>void remove(item)}><Trash2 size={15}/></button></div>)}</section>}
  </div>;
}

import { useMemo, useState } from "react";
import { ExternalLink, Search, Landmark, Sprout, GraduationCap, HeartPulse, House, BriefcaseBusiness, Users, FileText, ShieldCheck } from "lucide-react";

type SchemeLink = { name: string; description: string; url: string; category: string; tags: string };
const schemes: SchemeLink[] = [
  { name: "myScheme – सरकारी योजना शोध", description: "केंद्र व राज्य सरकारच्या योजनांचा शोध, पात्रता आणि अर्जाची माहिती.", url: "https://www.myscheme.gov.in/", category: "सर्व योजना", tags: "सर्व योजना केंद्र राज्य पात्रता" },
  { name: "MahaDBT – महाराष्ट्र", description: "महाराष्ट्रातील शिष्यवृत्ती, कृषी व इतर विभागांच्या लाभ योजना.", url: "https://mahadbt.maharashtra.gov.in/", category: "शिक्षण व शेतकरी", tags: "शिष्यवृत्ती शेतकरी विद्यार्थी महाराष्ट्र" },
  { name: "PM-KISAN", description: "पात्र शेतकरी कुटुंबांसाठी उत्पन्न सहाय्य आणि लाभार्थी माहिती.", url: "https://pmkisan.gov.in/", category: "शेतकरी", tags: "शेतकरी किसान पीएम किसान" },
  { name: "MahaDBT Farmer", description: "महाराष्ट्रातील कृषी यांत्रिकीकरण व इतर कृषी अनुदान योजना.", url: "https://mahadbt.maharashtra.gov.in/Farmer/", category: "शेतकरी", tags: "कृषी अनुदान ट्रॅक्टर सिंचन" },
  { name: "National Scholarship Portal", description: "केंद्र सरकारच्या विविध शिष्यवृत्ती योजनांसाठी अधिकृत पोर्टल.", url: "https://scholarships.gov.in/", category: "शिक्षण व शेतकरी", tags: "शिष्यवृत्ती विद्यार्थी शिक्षण" },
  { name: "PMAY – Urban", description: "शहरी भागातील घरकुल योजनांची अधिकृत माहिती.", url: "https://pmay-urban.gov.in/", category: "घरकुल", tags: "घर घरकुल प्रधानमंत्री आवास शहरी" },
  { name: "PMAY – Gramin", description: "ग्रामीण भागातील प्रधानमंत्री आवास योजनेची माहिती.", url: "https://pmayg.nic.in/", category: "घरकुल", tags: "घरकुल ग्रामीण आवास" },
  { name: "Ayushman Bharat – PM-JAY", description: "पात्र कुटुंबांसाठी आरोग्य संरक्षण व रुग्णालयांची माहिती.", url: "https://pmjay.gov.in/", category: "आरोग्य", tags: "आरोग्य आयुष्मान उपचार" },
  { name: "e-Shram", description: "असंघटित क्षेत्रातील कामगारांसाठी नोंदणी व योजना माहिती.", url: "https://eshram.gov.in/", category: "कामगार व रोजगार", tags: "कामगार श्रमिक रोजगार" },
  { name: "National Career Service", description: "नोकरी, कौशल्य आणि रोजगार सेवांसाठी सरकारी पोर्टल.", url: "https://www.ncs.gov.in/", category: "कामगार व रोजगार", tags: "नोकरी रोजगार कौशल्य" },
  { name: "Stand-Up India", description: "महिला व SC/ST उद्योजकांसाठी बँक कर्ज योजनेची माहिती.", url: "https://www.standupmitra.in/", category: "व्यवसाय व कर्ज", tags: "व्यवसाय उद्योग कर्ज महिला" },
  { name: "National Social Assistance Programme", description: "वृद्ध, विधवा व दिव्यांगांसाठी सामाजिक सहाय्य योजनांची माहिती.", url: "https://nsap.nic.in/", category: "पेन्शन व सामाजिक सहाय्य", tags: "पेन्शन वृद्ध विधवा दिव्यांग" },
];
const categories = ["सर्व योजना", "शेतकरी", "शिक्षण व शेतकरी", "घरकुल", "आरोग्य", "कामगार व रोजगार", "व्यवसाय व कर्ज", "पेन्शन व सामाजिक सहाय्य"];

export function GovernmentSchemesPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("सर्व योजना");
  const filtered = useMemo(() => schemes.filter((item) => {
    const matchesCategory = category === "सर्व योजना" || item.category === category;
    const text = (item.name + " " + item.description + " " + item.tags).toLocaleLowerCase("mr");
    return matchesCategory && (!query.trim() || text.includes(query.trim().toLocaleLowerCase("mr")));
  }), [query, category]);

  return <div className="h-full min-h-0 overflow-y-auto p-4 md:p-6 flex flex-col gap-5" style={{ color: "var(--color-text)" }}>
    <header className="flex items-center gap-3">
      <Landmark size={27} style={{ color: "var(--color-accent)" }} />
      <div><h1 className="text-xl font-semibold">Government Schemes</h1><p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>केंद्र सरकार आणि महाराष्ट्र शासनाच्या योजनांचे अधिकृत दुवे</p></div>
    </header>
    <section className="rounded-xl p-4 flex flex-col gap-2" style={{ background: "var(--color-bg-secondary)", border: "1px solid var(--color-border)" }}>
      <div className="flex items-center gap-2 font-medium"><ShieldCheck size={17}/> योग्य आणि अधिकृत माहिती</div>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>योजनेची पात्रता, लाभ, कागदपत्रे, अर्ज प्रक्रिया आणि सध्याची स्थिती बदलू शकते. अर्ज करण्यापूर्वी अधिकृत पोर्टलवरील ताजी माहिती तपासा. कोणताही लाभ निश्चित मिळेल असे गृहीत धरू नका.</p>
      <a href="https://www.myscheme.gov.in/" target="_blank" rel="noreferrer" className="text-sm font-medium inline-flex items-center gap-2" style={{ color: "var(--color-accent)" }}>myScheme वर सर्व योजना शोधा <ExternalLink size={14}/></a>
    </section>
    <div className="relative">
      <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--color-text-tertiary)" }}/>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="योजनेचे नाव किंवा विषय शोधा..." className="w-full rounded-lg pl-10 pr-3 py-3 text-sm bg-transparent border outline-none" style={{ borderColor: "var(--color-border)", color: "var(--color-text)" }}/>
    </div>
    <div className="flex gap-2 overflow-x-auto pb-1">{categories.map((item) => <button key={item} onClick={() => setCategory(item)} className="shrink-0 rounded-full px-3 py-2 text-xs" style={{ background: category === item ? "var(--color-accent)" : "var(--color-bg-secondary)", color: category === item ? "var(--color-on-accent)" : "var(--color-text-secondary)", border: "1px solid var(--color-border)" }}>{item}</button>)}</div>
    <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {filtered.map((item) => <article key={item.url} className="rounded-xl p-4 flex flex-col gap-2" style={{ background: "var(--color-bg-secondary)", border: "1px solid var(--color-border)" }}>
        <div className="flex items-start justify-between gap-2"><h2 className="font-semibold text-sm">{item.name}</h2><span className="text-[10px] rounded-full px-2 py-1 shrink-0" style={{ background: "var(--color-bg-tertiary)", color: "var(--color-text-secondary)" }}>{item.category}</span></div>
        <p className="text-xs flex-1" style={{ color: "var(--color-text-secondary)" }}>{item.description}</p>
        <a href={item.url} target="_blank" rel="noreferrer" className="text-xs font-medium inline-flex items-center gap-2" style={{ color: "var(--color-accent)" }}>अधिकृत वेबसाइट उघडा <ExternalLink size={13}/></a>
      </article>)}
      {filtered.length === 0 && <p className="text-sm p-4" style={{ color: "var(--color-text-secondary)" }}>या शोधासाठी योजना सापडली नाही.</p>}
    </section>
    <p className="text-[11px]" style={{ color: "var(--color-text-tertiary)" }}>ही सुरुवातीची अधिकृत पोर्टल यादी आहे; सर्व सरकारी योजनांची संपूर्ण यादी नाही. पात्रता आणि अर्जाच्या अंतिम निर्णयासाठी संबंधित सरकारी विभागाचे नियम लागू राहतील.</p>
  </div>;
}

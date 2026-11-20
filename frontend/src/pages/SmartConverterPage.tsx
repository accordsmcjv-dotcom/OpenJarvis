import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeftRight, Banknote, Calculator, Download, FileCog, Image as ImageIcon,
  RefreshCw, Upload, X,
} from 'lucide-react';

type Tab = 'units' | 'currency' | 'files';
type UnitCategory = 'length' | 'weight' | 'area' | 'volume' | 'temperature' | 'speed' | 'time' | 'data';
type UnitDef = { label: string; factor: number };
const UNIT_GROUPS: Record<UnitCategory, { label: string; units: Record<string, UnitDef> }> = {
  length: { label: 'लांबी', units: { mm: { label: 'मिलीमीटर', factor: .001 }, cm: { label: 'सेंटीमीटर', factor: .01 }, m: { label: 'मीटर', factor: 1 }, km: { label: 'किलोमीटर', factor: 1000 }, inch: { label: 'इंच', factor: .0254 }, ft: { label: 'फूट', factor: .3048 }, yard: { label: 'यार्ड', factor: .9144 }, mile: { label: 'मैल', factor: 1609.344 } } },
  weight: { label: 'वजन', units: { mg: { label: 'मिलीग्राम', factor: .000001 }, g: { label: 'ग्रॅम', factor: .001 }, kg: { label: 'किलोग्रॅम', factor: 1 }, tonne: { label: 'टन', factor: 1000 }, lb: { label: 'पाउंड', factor: .45359237 }, oz: { label: 'औंस', factor: .0283495 } } },
  area: { label: 'क्षेत्रफळ', units: { sqm: { label: 'चौरस मीटर', factor: 1 }, sqft: { label: 'चौरस फूट', factor: .09290304 }, acre: { label: 'एकर', factor: 4046.8564224 }, hectare: { label: 'हेक्टर', factor: 10000 }, guntha: { label: 'गुंठा', factor: 101.17141056 }, sqkm: { label: 'चौरस किलोमीटर', factor: 1000000 } } },
  volume: { label: 'घनफळ', units: { ml: { label: 'मिलीलीटर', factor: .001 }, litre: { label: 'लिटर', factor: 1 }, m3: { label: 'घन मीटर', factor: 1000 }, tsp: { label: 'टीस्पून', factor: .00492892 }, tbsp: { label: 'टेबलस्पून', factor: .0147868 }, gallon: { label: 'यूएस गॅलन', factor: 3.78541178 } } },
  temperature: { label: 'तापमान', units: { C: { label: 'सेल्सिअस', factor: 1 }, F: { label: 'फॅरेनहाइट', factor: 1 }, K: { label: 'केल्विन', factor: 1 } } },
  speed: { label: 'वेग', units: { mps: { label: 'मीटर/सेकंद', factor: 1 }, kmh: { label: 'किमी/तास', factor: 1 / 3.6 }, mph: { label: 'मैल/तास', factor: .44704 }, knot: { label: 'नॉट', factor: .514444 } } },
  time: { label: 'वेळ', units: { sec: { label: 'सेकंद', factor: 1 }, min: { label: 'मिनिट', factor: 60 }, hour: { label: 'तास', factor: 3600 }, day: { label: 'दिवस', factor: 86400 }, week: { label: 'आठवडा', factor: 604800 } } },
  data: { label: 'डिजिटल डेटा', units: { B: { label: 'बाइट', factor: 1 }, KB: { label: 'किलोबाइट', factor: 1024 }, MB: { label: 'मेगाबाइट', factor: 1048576 }, GB: { label: 'गिगाबाइट', factor: 1073741824 }, TB: { label: 'टेराबाइट', factor: 1099511627776 } } },
};
const CURRENCIES: Record<string, string> = { INR: 'भारतीय रुपया', USD: 'अमेरिकन डॉलर', EUR: 'युरो', GBP: 'ब्रिटिश पाउंड', AED: 'यूएई दिरहम', JPY: 'जपानी येन', CAD: 'कॅनेडियन डॉलर', AUD: 'ऑस्ट्रेलियन डॉलर', CHF: 'स्विस फ्रँक', SGD: 'सिंगापूर डॉलर' };
const formatNumber = (value: number) => Number.isFinite(value) ? new Intl.NumberFormat('en-IN', { maximumFractionDigits: 8 }).format(value) : '—';
const escapeHtml = (value: string) => value.replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch] || ch);

export function SmartConverterPage() {
  const [tab, setTab] = useState<Tab>('units');
  const [category, setCategory] = useState<UnitCategory>('length');
  const [amount, setAmount] = useState('1');
  const [fromUnit, setFromUnit] = useState('m');
  const [toUnit, setToUnit] = useState('ft');
  const [baseCurrency, setBaseCurrency] = useState('INR');
  const [targetCurrency, setTargetCurrency] = useState('USD');
  const [currencyAmount, setCurrencyAmount] = useState('1');
  const [rate, setRate] = useState<number | null>(null);
  const [rateDate, setRateDate] = useState('');
  const [rateLoading, setRateLoading] = useState(false);
  const [rateError, setRateError] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const [fileBusy, setFileBusy] = useState(false);
  const [textPreview, setTextPreview] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const imageUrl = useMemo(() => file && file.type.startsWith('image/') ? URL.createObjectURL(file) : '', [file]);
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);

  const units = UNIT_GROUPS[category].units;
  const unitResult = useMemo(() => {
    const value = Number(amount);
    if (!Number.isFinite(value)) return NaN;
    if (category !== 'temperature') return value * units[fromUnit].factor / units[toUnit].factor;
    if (fromUnit === toUnit) return value;
    const celsius = fromUnit === 'C' ? value : fromUnit === 'F' ? (value - 32) * 5 / 9 : value - 273.15;
    return toUnit === 'C' ? celsius : toUnit === 'F' ? celsius * 9 / 5 + 32 : celsius + 273.15;
  }, [amount, category, fromUnit, toUnit, units]);

  useEffect(() => {
    const keys = Object.keys(UNIT_GROUPS[category].units);
    if (!keys.includes(fromUnit) || !keys.includes(toUnit)) {
      setFromUnit(keys[0]); setToUnit(keys[1] || keys[0]);
    }
  }, [category, fromUnit, toUnit]);

  const loadRate = async () => {
    if (baseCurrency === targetCurrency) { setRate(1); setRateDate(new Date().toISOString().slice(0, 10)); setRateError(''); return; }
    setRateLoading(true); setRateError('');
    try {
      const response = await fetch(`https://api.frankfurter.dev/v1/latest?base=${encodeURIComponent(baseCurrency)}&symbols=${encodeURIComponent(targetCurrency)}`);
      if (!response.ok) throw new Error('सध्याचा दर मिळाला नाही. इंटरनेट तपासा.');
      const data = await response.json();
      const nextRate = Number(data?.rates?.[targetCurrency]);
      if (!Number.isFinite(nextRate) || nextRate <= 0) throw new Error('चलनाचा दर उपलब्ध नाही.');
      setRate(nextRate); setRateDate(String(data.date || ''));
    } catch (error) {
      setRate(null); setRateError(error instanceof Error ? error.message : 'चलन दर मिळवता आला नाही.');
    } finally { setRateLoading(false); }
  };
  useEffect(() => { void loadRate(); }, [baseCurrency, targetCurrency]);

  const chooseFile = (selected: File | null) => {
    setFile(selected); setFileError(''); setTextPreview('');
    if (!selected) return;
    const isImage = selected.type.startsWith('image/');
    const isText = selected.type.startsWith('text/') || /\.(txt|csv|tsv|md)$/i.test(selected.name);
    if (!isImage && !isText) {
      setFileError('सध्या फोटो (JPG, PNG, WebP) आणि मजकूर/CSV फाइल्स समर्थित आहेत. PDF/Word/Excel फाइल थेट उघडण्याची सुविधा पुढील टप्प्यात जोडता येईल.');
      return;
    }
    if (selected.size > 20 * 1024 * 1024) { setFileError('फाइल 20 MB पेक्षा लहान निवडा.'); return; }
    if (isText) {
      const reader = new FileReader();
      reader.onload = () => setTextPreview(String(reader.result || ''));
      reader.onerror = () => setFileError('फाइल वाचता आली नाही.');
      reader.readAsText(selected);
    }
  };

  const downloadBlob = (blob: Blob, name: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = name; document.body.appendChild(anchor); anchor.click(); anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 30000);
  };
  const convertImage = async (format: 'image/png' | 'image/jpeg' | 'image/webp') => {
    if (!file || !imageUrl) return;
    setFileBusy(true); setFileError('');
    try {
      const image = new Image(); image.src = imageUrl;
      await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error('फोटो उघडता आला नाही.')); });
      const canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d'); if (!context) throw new Error('फोटो रूपांतरित करता आला नाही.');
      if (format === 'image/jpeg') { context.fillStyle = '#ffffff'; context.fillRect(0, 0, canvas.width, canvas.height); }
      context.drawImage(image, 0, 0);
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('फोटो सेव्ह करता आला नाही.')), format, .92));
      const ext = format === 'image/jpeg' ? 'jpg' : format === 'image/png' ? 'png' : 'webp';
      downloadBlob(blob, file.name.replace(/\.[^.]+$/, '') + '.' + ext);
    } catch (error) { setFileError(error instanceof Error ? error.message : 'फोटो रूपांतरित करता आला नाही.'); }
    finally { setFileBusy(false); }
  };
  const convertText = (format: 'txt' | 'doc' | 'html' | 'csv' | 'xls') => {
    if (!file) return;
    const isCsv = /\.(csv|tsv)$/i.test(file.name);
    if (format === 'csv' && !isCsv) { setFileError('CSV फाइलसाठी CSV किंवा TSV फाइल निवडा.'); return; }
    const base = file.name.replace(/\.[^.]+$/, '');
    if (format === 'doc' || format === 'html') {
      const html = `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(base)}</title><style>body{font:12pt Arial,sans-serif;white-space:pre-wrap;line-height:1.6;margin:2cm}</style></head><body>${escapeHtml(textPreview)}</body></html>`;
      downloadBlob(new Blob([html], { type: 'application/msword;charset=utf-8' }), base + (format === 'doc' ? '.doc' : '.html'));
    } else if (format === 'xls') {
      const rows = textPreview.replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean).map((line) => line.split(file.name.toLowerCase().endsWith('.tsv') ? '\t' : ','));
      const table = rows.map((row) => '<tr>' + row.map((cell) => '<td>' + escapeHtml(cell.replace(/^"|"$/g, '').replace(/""/g, '"')) + '</td>').join('') + '</tr>').join('');
      const html = `<!doctype html><html><head><meta charset="utf-8"></head><body><table>${table}</table></body></html>`;
      downloadBlob(new Blob([html], { type: 'application/vnd.ms-excel;charset=utf-8' }), base + '.xls');
    } else {
      downloadBlob(new Blob([textPreview], { type: 'text/plain;charset=utf-8' }), base + (format === 'csv' ? '.csv' : '.txt'));
    }
  };

  const tabs = [
    { id: 'units' as const, label: 'मोजमाप', icon: Calculator },
    { id: 'currency' as const, label: 'चलन', icon: Banknote },
    { id: 'files' as const, label: 'फाइल', icon: FileCog },
  ];
  const fieldClass = 'w-full rounded-xl px-3 py-3 text-sm outline-none';
  const fieldStyle = { background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text)' };

  return <div className="h-full min-h-0 overflow-y-auto p-4 md:p-6 flex flex-col gap-5" style={{ color: 'var(--color-text)' }}>
    <header className="flex items-center gap-3">
      <div className="p-3 rounded-2xl" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}><ArrowLeftRight size={24} /></div>
      <div><h1 className="text-xl font-semibold">Smart Converter</h1><p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>मोजमाप, चलन आणि फाइल रूपांतरण एकाच ठिकाणी</p></div>
    </header>
    <div className="flex flex-wrap gap-2">
      {tabs.map((item) => <button key={item.id} onClick={() => setTab(item.id)} className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium" style={{ background: tab === item.id ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)', color: tab === item.id ? 'var(--color-accent)' : 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}><item.icon size={16} />{item.label}</button>)}
    </div>

    {tab === 'units' && <section className="rounded-2xl p-4 md:p-6 flex flex-col gap-4" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
      <div><label className="text-xs mb-2 block" style={{ color: 'var(--color-text-secondary)' }}>मोजमापाचा प्रकार</label><select className={fieldClass} style={fieldStyle} value={category} onChange={(e) => setCategory(e.target.value as UnitCategory)}>{Object.entries(UNIT_GROUPS).map(([key, group]) => <option key={key} value={key}>{group.label}</option>)}</select></div>
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-end">
        <div><label className="text-xs mb-2 block" style={{ color: 'var(--color-text-secondary)' }}>पासून</label><input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className={fieldClass} style={fieldStyle} /><select className={fieldClass + ' mt-2'} style={fieldStyle} value={fromUnit} onChange={(e) => setFromUnit(e.target.value)}>{Object.entries(units).map(([key, unit]) => <option key={key} value={key}>{unit.label}</option>)}</select></div>
        <button onClick={() => { setFromUnit(toUnit); setToUnit(fromUnit); }} className="p-3 rounded-xl justify-self-center" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }} aria-label="एकके बदला"><ArrowLeftRight size={20} /></button>
        <div><label className="text-xs mb-2 block" style={{ color: 'var(--color-text-secondary)' }}>मध्ये</label><div className="rounded-xl px-3 py-3 text-lg font-semibold min-h-12" style={fieldStyle}>{formatNumber(unitResult)}</div><select className={fieldClass + ' mt-2'} style={fieldStyle} value={toUnit} onChange={(e) => setToUnit(e.target.value)}>{Object.entries(units).map(([key, unit]) => <option key={key} value={key}>{unit.label}</option>)}</select></div>
      </div>
    </section>}

    {tab === 'currency' && <section className="rounded-2xl p-4 md:p-6 flex flex-col gap-4" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
      <div className="flex items-center justify-between gap-2"><div><h2 className="font-semibold">Live Currency Converter</h2><p className="text-xs mt-1" style={{ color: 'var(--color-text-secondary)' }}>Frankfurter मधील प्रकाशित विनिमय दर • इंटरनेट आवश्यक</p></div><button onClick={() => void loadRate()} disabled={rateLoading} className="p-2 rounded-lg" style={{ background: 'var(--color-bg-tertiary)' }}><RefreshCw size={17} className={rateLoading ? 'animate-spin' : ''} /></button></div>
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-end">
        <div><label className="text-xs mb-2 block" style={{ color: 'var(--color-text-secondary)' }}>रक्कम</label><input type="number" min="0" value={currencyAmount} onChange={(e) => setCurrencyAmount(e.target.value)} className={fieldClass} style={fieldStyle} /><select value={baseCurrency} onChange={(e) => setBaseCurrency(e.target.value)} className={fieldClass + ' mt-2'} style={fieldStyle}>{Object.entries(CURRENCIES).map(([code, name]) => <option key={code} value={code}>{code} — {name}</option>)}</select></div>
        <button onClick={() => { setBaseCurrency(targetCurrency); setTargetCurrency(baseCurrency); }} className="p-3 rounded-xl justify-self-center" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}><ArrowLeftRight size={20} /></button>
        <div><label className="text-xs mb-2 block" style={{ color: 'var(--color-text-secondary)' }}>मिळणारी रक्कम</label><div className="rounded-xl px-3 py-3 text-xl font-semibold min-h-12" style={fieldStyle}>{rate === null ? '—' : formatNumber((Number(currencyAmount) || 0) * rate)} {targetCurrency}</div><select value={targetCurrency} onChange={(e) => setTargetCurrency(e.target.value)} className={fieldClass + ' mt-2'} style={fieldStyle}>{Object.entries(CURRENCIES).map(([code, name]) => <option key={code} value={code}>{code} — {name}</option>)}</select></div>
      </div>
      {rate !== null && <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>1 {baseCurrency} = {formatNumber(rate)} {targetCurrency} {rateDate ? '• दर दिनांक: ' + rateDate : ''}. बँक/कार्डचे प्रत्यक्ष दर आणि शुल्क वेगळे असू शकतात.</p>}
      {rateError && <p className="text-sm" style={{ color: 'var(--color-error)' }}>{rateError}</p>}
    </section>}

    {tab === 'files' && <section className="rounded-2xl p-4 md:p-6 flex flex-col gap-4" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
      <div><h2 className="font-semibold">File Converter</h2><p className="text-xs mt-1" style={{ color: 'var(--color-text-secondary)' }}>फोटो, मजकूर आणि CSV फाइल्सचे रूपांतर</p></div>
      <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp,text/plain,text/csv,.txt,.csv,.tsv,.md" className="hidden" onChange={(e) => chooseFile(e.target.files?.[0] || null)} />
      <button onClick={() => fileInput.current?.click()} className="flex flex-col items-center gap-2 rounded-xl border border-dashed p-6 text-sm" style={{ borderColor: 'var(--color-accent)', color: 'var(--color-accent)' }}><Upload size={24} />फाइल निवडा (कमाल 20 MB)</button>
      {file && <div className="flex items-center gap-3 rounded-xl p-3" style={{ background: 'var(--color-bg-tertiary)' }}><div className="flex-1 min-w-0"><p className="text-sm font-medium truncate">{file.name}</p><p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{(file.size / 1024).toFixed(1)} KB</p></div><button onClick={() => chooseFile(null)} className="p-2"><X size={17} /></button></div>}
      {imageUrl && !fileError && <div className="rounded-xl overflow-hidden max-h-64 flex justify-center"><img src={imageUrl} alt="निवडलेला फोटो" className="max-h-64 object-contain" /></div>}
      {file && imageUrl && !fileError && <div className="flex flex-wrap gap-2">{(['image/jpeg', 'image/png', 'image/webp'] as const).map((format) => <button key={format} disabled={fileBusy} onClick={() => void convertImage(format)} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>{fileBusy ? 'रूपांतर सुरू…' : format === 'image/jpeg' ? 'JPG करा' : format === 'image/png' ? 'PNG करा' : 'WebP करा'}</button>)}</div>}
      {file && textPreview !== '' && !fileError && <div className="flex flex-wrap gap-2">{(['txt', 'doc', 'html'] as const).map((format) => <button key={format} onClick={() => convertText(format)} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>{format.toUpperCase()} डाउनलोड</button>)}{/\.(csv|tsv)$/i.test(file.name) && <><button onClick={() => convertText('csv')} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>CSV डाउनलोड</button><button onClick={() => convertText('xls')} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>Excel XLS डाउनलोड</button></>}</div>}
      {textPreview !== '' && <pre className="max-h-48 overflow-auto rounded-xl p-3 text-xs whitespace-pre-wrap" style={{ background: 'var(--color-bg-tertiary)' }}>{textPreview.slice(0, 5000)}{textPreview.length > 5000 ? '…' : ''}</pre>}
      {fileError && <p className="text-sm" style={{ color: 'var(--color-error)' }}>{fileError}</p>}
      <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>फाइल रूपांतरण फोन/ब्राउझरमध्येच होते; फाइल सर्व्हरवर अपलोड होत नाही. DOC हे Word-सुसंगत HTML स्वरूप आहे आणि XLS हे Excel-सुसंगत HTML टेबल स्वरूप आहे. PDF किंवा विद्यमान DOCX/XLSX फाइल थेट वाचणे/रूपांतरित करणे सध्या समर्थित नाही.</p>
    </section>}
  </div>;
}

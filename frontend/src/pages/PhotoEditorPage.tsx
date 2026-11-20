import { useEffect, useRef, useState } from 'react';
import {
  ImagePlus, RotateCcw, RotateCw, FlipHorizontal, Crop, Download,
  Sun, Contrast, Palette, SlidersHorizontal, Sparkles, X, Type,
} from 'lucide-react';

type Adjustments = { brightness: number; contrast: number; saturation: number };

const DEFAULT_ADJUSTMENTS: Adjustments = { brightness: 100, contrast: 100, saturation: 100 };

export function PhotoEditorPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [fileName, setFileName] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [rotation, setRotation] = useState(0);
  const [flip, setFlip] = useState(false);
  const [cropRatio, setCropRatio] = useState<number | null>(null);
  const [adjustments, setAdjustments] = useState<Adjustments>(DEFAULT_ADJUSTMENTS);
  const [filter, setFilter] = useState<'none' | 'warm' | 'mono' | 'vivid'>('none');
  const [overlayText, setOverlayText] = useState('');
  const [overlaySize, setOverlaySize] = useState(42);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!imageUrl) return;
    const image = new Image();
    image.onload = () => {
      imageRef.current = image;
      drawImage();
    };
    image.onerror = () => setError('हा फोटो उघडता आला नाही. दुसरा फोटो निवडा.');
    image.src = imageUrl;
    return () => { imageRef.current = null; };
  }, [imageUrl]);

  useEffect(() => { drawImage(); }, [rotation, flip, cropRatio, adjustments, filter, overlayText, overlaySize]);

  useEffect(() => () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
  }, [imageUrl]);

  function drawImage() {
    const canvas = canvasRef.current;
    const image = imageRef.current;
    if (!canvas || !image || !image.naturalWidth) return;

    const maxSide = 3000;
    const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
    const sourceWidth = Math.round(image.naturalWidth * scale);
    const sourceHeight = Math.round(image.naturalHeight * scale);
    let sx = 0, sy = 0, sw = sourceWidth, sh = sourceHeight;
    if (cropRatio) {
      const sourceRatio = sourceWidth / sourceHeight;
      if (sourceRatio > cropRatio) {
        sw = Math.round(sourceHeight * cropRatio);
        sx = Math.floor((sourceWidth - sw) / 2);
      } else {
        sh = Math.round(sourceWidth / cropRatio);
        sy = Math.floor((sourceHeight - sh) / 2);
      }
    }

    const sideways = Math.abs(rotation % 180) === 90;
    canvas.width = sideways ? sh : sw;
    canvas.height = sideways ? sw : sh;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const tone = filter === 'warm' ? 'sepia(0.28) saturate(1.12)' :
      filter === 'mono' ? 'grayscale(1)' :
      filter === 'vivid' ? 'saturate(1.45) contrast(1.08)' : '';
    ctx.filter = `brightness(${adjustments.brightness}%) contrast(${adjustments.contrast}%) saturate(${adjustments.saturation}%) ${tone}`;
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((rotation * Math.PI) / 180);
    ctx.scale(flip ? -1 : 1, 1);
    ctx.drawImage(image, sx / scale, sy / scale, sw / scale, sh / scale, -sw / 2, -sh / 2, sw, sh);
    ctx.restore();
    if (overlayText.trim()) {
      ctx.save();
      ctx.filter = 'none';
      const fontSize = Math.max(12, Math.round(Math.min(canvas.width, canvas.height) * overlaySize / 1000));
      ctx.font = `600 ${fontSize}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = 'rgba(0,0,0,0.72)';
      ctx.lineWidth = Math.max(2, fontSize * 0.12);
      ctx.fillStyle = '#ffffff';
      const maxWidth = canvas.width * 0.9;
      const words = overlayText.trim().split(/\\s+/);
      const rows: string[] = [];
      let row = '';
      for (const word of words) {
        const next = row ? `${row} ${word}` : word;
        if (row && ctx.measureText(next).width > maxWidth) {
          rows.push(row);
          row = word;
        } else row = next;
      }
      if (row) rows.push(row);
      const lineHeight = fontSize * 1.25;
      const startY = canvas.height - Math.max(18, fontSize * 0.45) - (rows.length - 1) * lineHeight;
      rows.forEach((line, index) => {
        const y = startY + index * lineHeight;
        ctx.strokeText(line, canvas.width / 2, y, maxWidth);
        ctx.fillText(line, canvas.width / 2, y, maxWidth);
      });
      ctx.restore();
    }
  }

  function choosePhoto(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('कृपया image format मधील फोटो निवडा.');
      return;
    }
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setError('');
    setFileName(file.name.replace(/\.[^.]+$/, '') || 'SHIVAM-Edited');
    setRotation(0);
    setFlip(false);
    setCropRatio(null);
    setAdjustments(DEFAULT_ADJUSTMENTS);
    setFilter('none');
    setOverlayText('');
    setOverlaySize(42);
    setImageUrl(URL.createObjectURL(file));
    event.target.value = '';
  }

  function resetEdits() {
    setRotation(0);
    setFlip(false);
    setCropRatio(null);
    setAdjustments(DEFAULT_ADJUSTMENTS);
    setFilter('none');
    setOverlayText('');
    setOverlaySize(42);
  }

  function savePhoto() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `${fileName || 'SHIVAM-Edited'}.jpg`;
    link.href = canvas.toDataURL('image/jpeg', 0.94);
    link.click();
  }

  const controlStyle = { background: 'var(--color-bg-secondary)', color: 'var(--color-text)', border: '1px solid var(--color-border)' };
  const actionClass = 'inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors disabled:opacity-40';
  const setAdjustment = (key: keyof Adjustments, value: number) =>
    setAdjustments((current) => ({ ...current, [key]: value }));

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6">
      <div className="mx-auto max-w-5xl space-y-5">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="hud-reticle"><Sparkles size={14} style={{ color: 'var(--color-accent)' }} /></span>
              <h1 className="text-xl font-semibold">SHIVAM Photo Studio</h1>
              <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>FREE • ON DEVICE</span>
            </div>
            <p className="mt-1 text-sm" style={{ color: 'var(--color-text-secondary)' }}>फोटो तुमच्या फोनवरच edit करा. फोटो कुठेही upload होत नाही.</p>
          </div>
          <label className={`${actionClass} cursor-pointer font-medium`} style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)' }}>
            <ImagePlus size={17} /> फोटो निवडा
            <input type="file" accept="image/*" className="hidden" onChange={choosePhoto} />
          </label>
        </header>

        {error && <div className="rounded-xl p-3 text-sm" style={{ background: 'color-mix(in srgb, var(--color-error) 10%, transparent)', color: 'var(--color-error)' }}>{error}</div>}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <section className="hud-panel flex min-h-[320px] flex-col items-center justify-center gap-3 p-3 sm:p-5" style={{ background: 'color-mix(in srgb, var(--color-bg-secondary) 72%, transparent)' }}>
            {imageUrl ? (
              <>
                <div className="flex min-h-[260px] w-full items-center justify-center overflow-hidden rounded-xl" style={{ background: 'repeating-conic-gradient(var(--color-bg-secondary) 0% 25%, var(--color-bg-tertiary) 0% 50%) 50% / 20px 20px' }}>
                  <canvas ref={canvasRef} className="max-h-[58vh] max-w-full object-contain" />
                </div>
                <p className="max-w-full truncate text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{fileName}</p>
              </>
            ) : (
              <div className="flex flex-col items-center gap-3 py-12 text-center">
                <div className="rounded-2xl p-5" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}><ImagePlus size={34} /></div>
                <div>
                  <p className="font-medium">Edit करण्यासाठी फोटो निवडा</p>
                  <p className="mt-1 text-sm" style={{ color: 'var(--color-text-secondary)' }}>Gallery मधून फोटो निवडा.</p>
                </div>
              </div>
            )}
          </section>

          <aside className="space-y-3">
            <section className="hud-panel space-y-3 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold"><SlidersHorizontal size={16} /> मूलभूत बदल</div>
              <div className="grid grid-cols-2 gap-2">
                <button disabled={!imageUrl} className={actionClass} style={controlStyle} onClick={() => setRotation((v) => (v + 270) % 360)}><RotateCcw size={16} /> डावीकडे</button>
                <button disabled={!imageUrl} className={actionClass} style={controlStyle} onClick={() => setRotation((v) => (v + 90) % 360)}><RotateCw size={16} /> उजवीकडे</button>
                <button disabled={!imageUrl} className={actionClass} style={controlStyle} onClick={() => setFlip((v) => !v)}><FlipHorizontal size={16} /> Flip</button>
                <button disabled={!imageUrl} className={actionClass} style={controlStyle} onClick={() => setCropRatio((v) => v === 1 ? null : 1)}><Crop size={16} /> 1:1 crop</button>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <button disabled={!imageUrl} className={actionClass} style={{ ...controlStyle, color: cropRatio === 0.8 ? 'var(--color-accent)' : controlStyle.color }} onClick={() => setCropRatio((v) => v === 0.8 ? null : 0.8)}>4:5</button>
                <button disabled={!imageUrl} className={actionClass} style={{ ...controlStyle, color: cropRatio === 16 / 9 ? 'var(--color-accent)' : controlStyle.color }} onClick={() => setCropRatio((v) => v === 16 / 9 ? null : 16 / 9)}>16:9</button>
                <button disabled={!imageUrl} className={actionClass} style={{ ...controlStyle, color: cropRatio === null ? 'var(--color-accent)' : controlStyle.color }} onClick={() => setCropRatio(null)}>Original</button>
              </div>
            </section>

            <section className="hud-panel space-y-4 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold"><Sun size={16} /> प्रकाश आणि रंग</div>
              {([
                ['brightness', 'Brightness', Sun, 0, 200],
                ['contrast', 'Contrast', Contrast, 0, 200],
                ['saturation', 'Saturation', Palette, 0, 200],
              ] as const).map(([key, label, Icon, min, max]) => (
                <label key={key} className="block space-y-1.5">
                  <span className="flex items-center justify-between text-xs"><span className="flex items-center gap-2"><Icon size={14} /> {label}</span><span style={{ color: 'var(--color-text-secondary)' }}>{adjustments[key]}%</span></span>
                  <input type="range" min={min} max={max} value={adjustments[key]} disabled={!imageUrl} onChange={(e) => setAdjustment(key, Number(e.target.value))} className="w-full accent-cyan-500" />
                </label>
              ))}
            </section>

            <section className="hud-panel space-y-3 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold"><Type size={16} /> फोटोवर मजकूर</div>
              <input
                type="text"
                value={overlayText}
                onChange={(event) => setOverlayText(event.target.value)}
                disabled={!imageUrl}
                maxLength={100}
                placeholder="तुमचा मजकूर लिहा..."
                className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                style={controlStyle}
              />
              <label className="block space-y-1">
                <span className="flex justify-between text-xs"><span>मजकुराचा आकार</span><span>{overlaySize}</span></span>
                <input type="range" min="20" max="90" value={overlaySize} disabled={!imageUrl || !overlayText} onChange={(event) => setOverlaySize(Number(event.target.value))} className="w-full accent-cyan-500" />
              </label>
            </section>

            <section className="hud-panel space-y-3 p-4">
              <div className="text-sm font-semibold">फिल्टर्स</div>
              <div className="grid grid-cols-2 gap-2">
                {([
                  ['none', 'Original'], ['warm', 'Warm'], ['mono', 'B&W'], ['vivid', 'Vivid'],
                ] as const).map(([value, label]) => (
                  <button key={value} disabled={!imageUrl} onClick={() => setFilter(value)} className={`${actionClass} ${filter === value ? 'font-semibold' : ''}`} style={{ ...controlStyle, color: filter === value ? 'var(--color-accent)' : controlStyle.color, borderColor: filter === value ? 'var(--color-accent)' : 'var(--color-border)' }}>{label}</button>
                ))}
              </div>
            </section>

            <div className="grid grid-cols-2 gap-2">
              <button disabled={!imageUrl} onClick={resetEdits} className={actionClass} style={controlStyle}><X size={16} /> Reset</button>
              <button disabled={!imageUrl} onClick={savePhoto} className={actionClass + ' font-semibold'} style={{ background: 'var(--color-accent)', color: 'var(--color-on-accent)' }}><Download size={16} /> Save फोटो</button>
            </div>
            <p className="text-[11px] leading-relaxed" style={{ color: 'var(--color-text-tertiary)' }}>टीप: मोठे फोटो फोनच्या क्षमतेनुसार 3000px पर्यंत कमी केले जाऊ शकतात. मूळ फोटो बदलला जात नाही.</p>
          </aside>
        </div>
      </div>
    </div>
  );
}

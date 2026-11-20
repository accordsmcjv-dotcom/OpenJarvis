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
  const [flipVertical, setFlipVertical] = useState(false);
  const [cropRatio, setCropRatio] = useState<number | null>(null);
  const [adjustments, setAdjustments] = useState<Adjustments>(DEFAULT_ADJUSTMENTS);
  const [filter, setFilter] = useState<'none' | 'warm' | 'mono' | 'vivid' | 'cool' | 'vintage' | 'fade' | 'dramatic'>('none');
  const [overlayText, setOverlayText] = useState('');
  const [overlaySize, setOverlaySize] = useState(42);
  const [overlayColor, setOverlayColor] = useState('#ffffff');
  const [overlayPosition, setOverlayPosition] = useState<'top' | 'center' | 'bottom'>('bottom');
  const [sticker, setSticker] = useState('');
  const [stickerSize, setStickerSize] = useState(13);
  const [stickerPosition, setStickerPosition] = useState<'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'>('bottom-right');
  const [frameColor, setFrameColor] = useState('#ffffff');
  const [frameSize, setFrameSize] = useState(0);
  const [vignette, setVignette] = useState(0);
  const [blur, setBlur] = useState(0);
  const [exportFormat, setExportFormat] = useState<'jpeg' | 'png'>('jpeg');
  const [exportQuality, setExportQuality] = useState(94);
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

  useEffect(() => { drawImage(); }, [rotation, flip, flipVertical, cropRatio, adjustments, filter, overlayText, overlaySize, overlayColor, overlayPosition, sticker, stickerSize, stickerPosition, frameColor, frameSize, vignette, blur]);

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
      filter === 'vivid' ? 'saturate(1.45) contrast(1.08)' :
      filter === 'cool' ? 'hue-rotate(12deg) saturate(1.12) brightness(1.04)' :
      filter === 'vintage' ? 'sepia(0.48) contrast(0.92) saturate(0.78)' :
      filter === 'fade' ? 'contrast(0.82) brightness(1.1) saturate(0.72)' :
      filter === 'dramatic' ? 'contrast(1.32) saturate(1.18)' : '';
    ctx.filter = `brightness(${adjustments.brightness}%) contrast(${adjustments.contrast}%) saturate(${adjustments.saturation}%) ${tone} blur(${blur}px)`;
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((rotation * Math.PI) / 180);
    ctx.scale(flip ? -1 : 1, flipVertical ? -1 : 1);
    ctx.drawImage(image, sx / scale, sy / scale, sw / scale, sh / scale, -sw / 2, -sh / 2, sw, sh);
    ctx.restore();
    if (vignette > 0) {
      ctx.save();
      ctx.filter = 'none';
      const radius = Math.max(canvas.width, canvas.height) * 0.78;
      const gradient = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, Math.min(canvas.width, canvas.height) * 0.18, canvas.width / 2, canvas.height / 2, radius);
      gradient.addColorStop(0, 'rgba(0,0,0,0)');
      gradient.addColorStop(0.58, `rgba(0,0,0,${vignette / 100 * 0.18})`);
      gradient.addColorStop(1, `rgba(0,0,0,${vignette / 100 * 0.68})`);
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.restore();
    }
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
      ctx.fillStyle = overlayColor;
      const maxWidth = canvas.width * 0.9;
      const words = overlayText.trim().split(/\s+/);
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
      const margin = Math.max(18, fontSize * 0.45);
      const startY = overlayPosition === 'top'
        ? margin + fontSize
        : overlayPosition === 'center'
          ? (canvas.height - rows.length * lineHeight) / 2 + fontSize
          : canvas.height - margin - (rows.length - 1) * lineHeight;
      rows.forEach((line, index) => {
        const y = startY + index * lineHeight;
        ctx.strokeText(line, canvas.width / 2, y, maxWidth);
        ctx.fillText(line, canvas.width / 2, y, maxWidth);
      });
      ctx.restore();
    }
    if (sticker) {
      ctx.save();
      ctx.filter = 'none';
      const sizePx = Math.max(28, Math.round(Math.min(canvas.width, canvas.height) * stickerSize / 100));
      ctx.font = `${sizePx}px sans-serif`;
      ctx.textAlign = stickerPosition.endsWith('left') ? 'left' : 'right';
      ctx.textBaseline = stickerPosition.startsWith('top') ? 'top' : 'bottom';
      ctx.shadowColor = 'rgba(0,0,0,0.35)';
      ctx.shadowBlur = sizePx * 0.18;
      const x = stickerPosition.endsWith('left') ? sizePx * 0.35 : canvas.width - sizePx * 0.35;
      const y = stickerPosition.startsWith('top') ? sizePx * 0.35 : canvas.height - sizePx * 0.35;
      ctx.fillText(sticker, x, y);
      ctx.restore();
    }
    if (frameSize > 0) {
      ctx.save();
      ctx.filter = 'none';
      ctx.strokeStyle = frameColor;
      ctx.lineWidth = Math.max(2, Math.min(canvas.width, canvas.height) * frameSize / 100);
      ctx.strokeRect(ctx.lineWidth / 2, ctx.lineWidth / 2, canvas.width - ctx.lineWidth, canvas.height - ctx.lineWidth);
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
    setFlipVertical(false);
    setCropRatio(null);
    setAdjustments(DEFAULT_ADJUSTMENTS);
    setFilter('none');
    setOverlayText('');
    setOverlaySize(42);
    setOverlayColor('#ffffff');
    setOverlayPosition('bottom');
    setSticker('');
    setStickerSize(13);
    setStickerPosition('bottom-right');
    setFrameSize(0);
    setFrameColor('#ffffff');
    setVignette(0);
    setBlur(0);
    setExportFormat('jpeg');
    setExportQuality(94);
    setImageUrl(URL.createObjectURL(file));
    event.target.value = '';
  }

  function resetEdits() {
    setRotation(0);
    setFlip(false);
    setFlipVertical(false);
    setCropRatio(null);
    setAdjustments(DEFAULT_ADJUSTMENTS);
    setFilter('none');
    setOverlayText('');
    setOverlaySize(42);
    setOverlayColor('#ffffff');
    setOverlayPosition('bottom');
    setSticker('');
    setStickerSize(13);
    setStickerPosition('bottom-right');
    setFrameSize(0);
    setFrameColor('#ffffff');
    setVignette(0);
    setBlur(0);
  }

  function savePhoto() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const mimeType = exportFormat === 'png' ? 'image/png' : 'image/jpeg';
    const extension = exportFormat === 'png' ? 'png' : 'jpg';
    const downloadName = `${fileName || 'SHIVAM-Edited'}.${extension}`;
    try {
      canvas.toBlob((blob) => {
        if (!blob) {
          setError('फोटो तयार करता आला नाही. पुन्हा प्रयत्न करा.');
          return;
        }
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = downloadName;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
        setError('');
      }, mimeType, exportFormat === 'jpeg' ? exportQuality / 100 : undefined);
    } catch {
      setError('फोटो सेव्ह करता आला नाही. पुन्हा प्रयत्न करा.');
    }
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
                <button disabled={!imageUrl} className={actionClass} style={controlStyle} onClick={() => setFlip((v) => !v)}><FlipHorizontal size={16} /> आडवे Flip</button>
                <button disabled={!imageUrl} className={actionClass} style={controlStyle} onClick={() => setFlipVertical((v) => !v)}>उभे Flip</button>
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
              <label className="flex items-center justify-between gap-3 text-xs">
                <span>मजकूर कुठे ठेवायचा?</span>
                <select value={overlayPosition} disabled={!imageUrl || !overlayText} onChange={(event) => setOverlayPosition(event.target.value as 'top' | 'center' | 'bottom')} className="rounded-lg px-2 py-2 text-xs" style={controlStyle}>
                  <option value="top">वर</option>
                  <option value="center">मध्यभागी</option>
                  <option value="bottom">खाली</option>
                </select>
              </label>
              <label className="flex items-center justify-between gap-3 text-xs">
                <span>मजकुराचा रंग</span>
                <input type="color" value={overlayColor} disabled={!imageUrl || !overlayText} onChange={(event) => setOverlayColor(event.target.value)} className="h-9 w-12 cursor-pointer rounded border-0 bg-transparent" aria-label="मजकुराचा रंग" />
              </label>
              <label className="block space-y-1">
                <span className="flex justify-between text-xs"><span>मजकुराचा आकार</span><span>{overlaySize}</span></span>
                <input type="range" min="20" max="90" value={overlaySize} disabled={!imageUrl || !overlayText} onChange={(event) => setOverlaySize(Number(event.target.value))} className="w-full accent-cyan-500" />
              </label>
            </section>

            <section className="hud-panel space-y-3 p-4">
              <div className="text-sm font-semibold">Sticker आणि Emoji</div>
              <div className="grid grid-cols-5 gap-2">
                {['❤️', '⭐', '🔥', '😍', '✨', '🌸', '🎉', '👍', '😎', '💯'].map((emoji) => (
                  <button key={emoji} type="button" disabled={!imageUrl} onClick={() => setSticker((current) => current === emoji ? '' : emoji)} className={`${actionClass} text-xl`} style={{ ...controlStyle, outline: sticker === emoji ? '2px solid var(--color-accent)' : 'none' }} aria-label={`Sticker ${emoji}`}>{emoji}</button>
                ))}
              </div>
              <label className="block space-y-1">
                <span className="flex justify-between text-xs"><span>Sticker चा आकार</span><span>{stickerSize}%</span></span>
                <input type="range" min="6" max="28" value={stickerSize} disabled={!imageUrl || !sticker} onChange={(event) => setStickerSize(Number(event.target.value))} className="w-full accent-cyan-500" />
              </label>
              <label className="flex items-center justify-between gap-3 text-xs">
                <span>Sticker ची जागा</span>
                <select value={stickerPosition} disabled={!imageUrl || !sticker} onChange={(event) => setStickerPosition(event.target.value as typeof stickerPosition)} className="rounded-lg px-2 py-2 text-xs" style={controlStyle}>
                  <option value="top-left">वर डावीकडे</option>
                  <option value="top-right">वर उजवीकडे</option>
                  <option value="bottom-left">खाली डावीकडे</option>
                  <option value="bottom-right">खाली उजवीकडे</option>
                </select>
              </label>
              <button type="button" disabled={!imageUrl || !sticker} onClick={() => setSticker('')} className={actionClass} style={controlStyle}>Sticker काढा</button>
            </section>

            <section className="hud-panel space-y-3 p-4">
              <div className="text-sm font-semibold">Blur Effect</div>
              <label className="block space-y-1">
                <span className="flex justify-between text-xs"><span>फोटो Blur</span><span>{blur}px</span></span>
                <input type="range" min="0" max="8" step="0.5" value={blur} disabled={!imageUrl} onChange={(event) => setBlur(Number(event.target.value))} className="w-full accent-cyan-500" />
              </label>
            </section>
            <section className="hud-panel space-y-3 p-4">
              <div className="text-sm font-semibold">Vignette Effect</div>
              <label className="block space-y-1">
                <span className="flex justify-between text-xs"><span>कडांचा गडदपणा</span><span>{vignette}%</span></span>
                <input type="range" min="0" max="100" value={vignette} disabled={!imageUrl} onChange={(event) => setVignette(Number(event.target.value))} className="w-full accent-cyan-500" />
              </label>
            </section>
            <section className="hud-panel space-y-3 p-4">
              <div className="text-sm font-semibold">फोटो फ्रेम</div>
              <label className="flex items-center justify-between gap-3 text-xs">
                <span>फ्रेमचा रंग</span>
                <input type="color" value={frameColor} disabled={!imageUrl || frameSize === 0} onChange={(event) => setFrameColor(event.target.value)} className="h-9 w-12 cursor-pointer rounded border-0 bg-transparent" aria-label="फ्रेमचा रंग" />
              </label>
              <label className="block space-y-1">
                <span className="flex justify-between text-xs"><span>फ्रेमची जाडी</span><span>{frameSize}%</span></span>
                <input type="range" min="0" max="5" step="0.5" value={frameSize} disabled={!imageUrl} onChange={(event) => setFrameSize(Number(event.target.value))} className="w-full accent-cyan-500" />
              </label>
            </section>

            <section className="hud-panel space-y-3 p-4">
              <div className="text-sm font-semibold">फिल्टर्स</div>
              <div className="grid grid-cols-2 gap-2">
                {([
                  ['none', 'Original'], ['warm', 'Warm'], ['mono', 'B&W'], ['vivid', 'Vivid'],
                  ['cool', 'Cool'], ['vintage', 'Vintage'], ['fade', 'Fade'], ['dramatic', 'Dramatic'],
                ] as const).map(([value, label]) => (
                  <button key={value} disabled={!imageUrl} onClick={() => setFilter(value)} className={`${actionClass} ${filter === value ? 'font-semibold' : ''}`} style={{ ...controlStyle, color: filter === value ? 'var(--color-accent)' : controlStyle.color, borderColor: filter === value ? 'var(--color-accent)' : 'var(--color-border)' }}>{label}</button>
                ))}
              </div>
            </section>

            <section className="hud-panel space-y-3 p-4">
              <div className="text-sm font-semibold">Save पर्याय</div>
              <label className="flex items-center justify-between gap-3 text-xs">
                <span>फाईल प्रकार</span>
                <select value={exportFormat} disabled={!imageUrl} onChange={(event) => setExportFormat(event.target.value as 'jpeg' | 'png')} className="rounded-lg px-2 py-2 text-xs" style={controlStyle}>
                  <option value="jpeg">JPG</option>
                  <option value="png">PNG</option>
                </select>
              </label>
              <label className="block space-y-1">
                <span className="flex justify-between text-xs"><span>JPG गुणवत्ता</span><span>{exportQuality}%</span></span>
                <input type="range" min="60" max="100" value={exportQuality} disabled={!imageUrl || exportFormat === 'png'} onChange={(event) => setExportQuality(Number(event.target.value))} className="w-full accent-cyan-500" />
              </label>
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

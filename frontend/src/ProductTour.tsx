import { ArrowLeft, ArrowRight, Check, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useLang } from './i18n';
import './app/styles/product-tour.css';

type TourStep = { selector: string; page: string; title: string; text: string };
type Props = { open: boolean; stepIndex: number; onStepChange: (index: number) => void; onClose: () => void; onNavigate: (page: string) => void };

export default function ProductTour({ open, stepIndex, onStepChange, onClose, onNavigate }: Props) {
  const { lang } = useLang();
  const tr = lang === 'tr';
  const steps: TourStep[] = tr ? [
    { selector: '[data-tour="new-experiment"]', page: 'getstarted', title: 'Yeni deney', text: 'Yeni bir backtest oluşturmak için bu düğmeyi kullan. Deney sihirbazı seni adım adım yönlendirir.' },
    { selector: '[data-tour="nav-platform"]', page: 'platform', title: 'Deney platformu', text: 'Veri, indikatör, model, optimizasyon ve validasyon seçimlerini burada yaparsın.' },
    { selector: '[data-tour="nav-data"]', page: 'data', title: 'Veri merkezi', text: 'CSV yükle, sentetik veriyi seç ve deneyden önce zaman aralığı ile kolonları kontrol et.' },
    { selector: '[data-tour="nav-models"]', page: 'models', title: 'Uzman modeller', text: 'Trend, momentum ve volatilite davranışlarını arayan modelleri karşılaştır.' },
    { selector: '[data-tour="nav-regimes"]', page: 'regimes', title: 'Piyasa rejimleri', text: 'Piyasanın farklı durumlarını, geçişlerini ve her durumdaki performansı incele.' },
    { selector: '[data-tour="nav-notebook"]', page: 'notebook', title: 'Notebook Lab', text: 'Notebook yükle, çalıştır ve başarılı notebooku deneye dönüştür.' },
    { selector: '[data-tour="nav-history"]', page: 'history', title: 'Deney geçmişi', text: 'Önceki deneyleri bul, durumlarını gör ve sonuçlarını tekrar aç.' },
    { selector: '[data-tour="profile"]', page: 'history', title: 'Profil ve hesap', text: 'Dil, tema, hesap güvenliği ve aktif oturumlarını profil menüsünden yönet.' },
    { selector: '[data-tour="nav-method"]', page: 'method', title: 'Metodoloji', text: 'Veri sızıntısını önleme, validasyon, maliyetler ve sonuçları yorumlama kurallarını burada oku.' }
  ] : [
    { selector: '[data-tour="new-experiment"]', page: 'getstarted', title: 'New experiment', text: 'Use this button to create a backtest. The experiment wizard guides you step by step.' },
    { selector: '[data-tour="nav-platform"]', page: 'platform', title: 'Experiment platform', text: 'Choose data, indicators, models, optimization, and validation here.' },
    { selector: '[data-tour="nav-data"]', page: 'data', title: 'Data hub', text: 'Upload CSV data, choose synthetic data, and inspect dates and columns before running.' },
    { selector: '[data-tour="nav-models"]', page: 'models', title: 'Expert models', text: 'Compare specialists that look for trend, momentum, and volatility behaviour.' },
    { selector: '[data-tour="nav-regimes"]', page: 'regimes', title: 'Market regimes', text: 'Inspect market states, transitions, and performance in each state.' },
    { selector: '[data-tour="nav-notebook"]', page: 'notebook', title: 'Notebook Lab', text: 'Upload and run a notebook, then convert a successful notebook into an experiment.' },
    { selector: '[data-tour="nav-history"]', page: 'history', title: 'Experiment history', text: 'Find earlier experiments, inspect their status, and reopen their results.' },
    { selector: '[data-tour="profile"]', page: 'history', title: 'Profile and account', text: 'Manage language, theme, account security, and active sessions from the profile menu.' },
    { selector: '[data-tour="nav-method"]', page: 'method', title: 'Methodology', text: 'Read how leakage prevention, validation, costs, and result interpretation work.' }
  ];
  const current = steps[Math.min(stepIndex, steps.length - 1)];
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!open) return;
    onNavigate(current.page);
    setRect(null);
    let timer: number | undefined;
    let attempts = 0;
    const locate = () => {
      const target = document.querySelector(current.selector) as HTMLElement | null;
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
        window.setTimeout(() => setRect(target.getBoundingClientRect()), 180);
      } else if (attempts < 12) {
        attempts += 1;
        timer = window.setTimeout(locate, 80);
      }
    };
    locate();
    const update = () => {
      const target = document.querySelector(current.selector) as HTMLElement | null;
      if (target) setRect(target.getBoundingClientRect());
    };
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      if (timer) window.clearTimeout(timer);
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [current.page, current.selector, open, onNavigate]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight') onStepChange(Math.min(steps.length - 1, stepIndex + 1));
      if (event.key === 'ArrowLeft') onStepChange(Math.max(0, stepIndex - 1));
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose, onStepChange, stepIndex, steps.length]);

  if (!open) return null;
  const padding = 7;
  const safeRect = rect || { top: 76, left: 24, width: 220, height: 45 };
  const left = Math.max(8, Math.min(window.innerWidth - safeRect.width - 8, safeRect.left - padding));
  const top = Math.max(8, safeRect.top - padding);
  const width = Math.min(window.innerWidth - 16, safeRect.width + padding * 2);
  const height = safeRect.height + padding * 2;
  const last = stepIndex === steps.length - 1;
  return <div className="product-tour" role="dialog" aria-modal="true" aria-label={tr ? 'Uygulama turu' : 'Application tour'}>
    <div className="product-tour-backdrop" />
    <div className="product-tour-spotlight" style={{ top, left, width, height }} />
    <section className="product-tour-card" style={{ top: Math.min(window.innerHeight - 215, Math.max(16, top + height + 16)) }}>
      <button className="product-tour-close" onClick={onClose} aria-label={tr ? 'Turu kapat' : 'Close tour'}><X size={16} /></button>
      <span className="product-tour-progress">{stepIndex + 1} / {steps.length}</span>
      <h3>{current.title}</h3>
      <p>{current.text}</p>
      <div className="product-tour-actions">
        <button className="text-button" onClick={onClose}>{tr ? 'Atla' : 'Skip'}</button>
        <span className="product-tour-spacer" />
        <button className="secondary" disabled={stepIndex === 0} onClick={() => onStepChange(stepIndex - 1)}><ArrowLeft size={14} />{tr ? 'Geri' : 'Back'}</button>
        <button className="primary" onClick={() => last ? onClose() : onStepChange(stepIndex + 1)}>{last ? <Check size={14} /> : <ArrowRight size={14} />}{last ? (tr ? 'Tamamla' : 'Finish') : (tr ? 'İleri' : 'Next')}</button>
      </div>
    </section>
  </div>;
}

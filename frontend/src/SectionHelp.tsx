import { CircleHelp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useLang } from './i18n';
import './app/styles/section-help.css';

type Props = { title: string; purpose: string; impact: string };

export default function SectionHelp({ title, purpose, impact }: Props) {
  const { lang } = useLang();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);
  return <span className="section-help" ref={ref}>
    <button type="button" className="section-help-trigger" aria-label={lang === 'tr' ? `${title} açıklaması` : `${title} explanation`} aria-expanded={open} onClick={() => setOpen(value => !value)}><CircleHelp size={15} /></button>
    {open && <span className="section-help-popover" role="tooltip"><b>{title}</b><span><strong>{lang === 'tr' ? 'Ne işe yarar?' : 'Purpose'}</strong>{purpose}</span><span><strong>{lang === 'tr' ? 'Sonuca etkisi' : 'Impact on result'}</strong>{impact}</span></span>}
  </span>;
}

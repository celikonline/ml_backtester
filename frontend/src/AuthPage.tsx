import { useMemo, useState } from 'react';
import {
  Activity,
  ArrowRight,
  AtSign,
  Check,
  Eye,
  EyeOff,
  FlaskConical,
  Layers3,
  Loader2,
  Lock,
  Moon,
  ShieldCheck,
  Sun,
  User,
} from 'lucide-react';
import { DEMO_USER, useAuth } from './auth';
import { useLang } from './i18n';
import './app/styles/auth.css';

type Mode = 'login' | 'register';

const emailOk = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());

function passwordScore(pw: string): number {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return Math.min(s, 4);
}

export default function AuthPage() {
  const { t, lang, setLang } = useLang();
  const { login, register, loginWithDemo } = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [theme, setTheme] = useState<'dark' | 'light'>(() =>
    typeof localStorage !== 'undefined' && localStorage.getItem('regimelab.theme') === 'light' ? 'light' : 'dark',
  );

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [remember, setRemember] = useState(true);
  const [kvkk, setKvkk] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [showPw2, setShowPw2] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);

  const score = useMemo(() => passwordScore(password), [password]);

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem('regimelab.theme', next);
    } catch {
      /* ignore */
    }
  };

  const switchMode = (m: Mode) => {
    setMode(m);
    setErrors({});
    setFormError('');
  };

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (mode === 'register' && name.trim().length < 2) e.name = t('auth.errName');
    if (!emailOk(email)) e.email = t('auth.errEmail');
    if (password.length < 8) e.password = t('auth.errPassword');
    if (mode === 'register') {
      if (confirm !== password) e.confirm = t('auth.errConfirm');
      if (!kvkk) e.kvkk = t('auth.errKvkk');
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    setFormError('');
    if (!validate()) return;
    setBusy(true);
    try {
      if (mode === 'login') await login(email, password, remember);
      else await register(name, email, password);
    } catch (err) {
      const message = err instanceof Error ? err.message : '';
      // Preserve server-side validation/conflict messages. Previously every
      // non-i18n backend error became the unhelpful generic error banner.
      setFormError(message.startsWith('auth.') ? t(message) : message || t('auth.genericError'));
    } finally {
      setBusy(false);
    }
  }

  async function demo() {
    setFormError('');
    setDemoBusy(true);
    try {
      await loginWithDemo();
    } catch {
      setFormError(t('auth.genericError'));
    } finally {
      setDemoBusy(false);
    }
  }

  const strengthLabel = [t('auth.pwWeak'), t('auth.pwFair'), t('auth.pwGood'), t('auth.pwStrong'), t('auth.pwStrong')][score];

  return (
    <div className="auth-shell">
      {/* Sol: marka paneli */}
      <aside className="auth-brand">
        <div className="auth-glow" aria-hidden />
        <a className="brand auth-brand-logo" href="#" onClick={(e) => e.preventDefault()}>
          <span className="brand-mark">
            <Activity size={23} />
          </span>
          <span>
            regime<span className="brand-light">lab</span>
            <small>{t('brand.sub')}</small>
          </span>
        </a>
        <div className="auth-hero">
          <span className="eyebrow">EUR/USD · {lang === 'en' ? 'REGIME-AWARE MODELING' : 'REJİM ODAKLI MODELLEME'}</span>
          <h1>{t('auth.heroTitle')}</h1>
          <p>{t('auth.heroSub')}</p>
        </div>
        <ul className="auth-points">
          <li>
            <span className="auth-point-icon">
              <FlaskConical size={17} />
            </span>
            <div>
              <b>{t('auth.point1t')}</b>
              <span>{t('auth.point1s')}</span>
            </div>
          </li>
          <li>
            <span className="auth-point-icon">
              <Layers3 size={17} />
            </span>
            <div>
              <b>{t('auth.point2t')}</b>
              <span>{t('auth.point2s')}</span>
            </div>
          </li>
          <li>
            <span className="auth-point-icon">
              <ShieldCheck size={17} />
            </span>
            <div>
              <b>{t('auth.point3t')}</b>
              <span>{t('auth.point3s')}</span>
            </div>
          </li>
        </ul>
        <div className="auth-equity" aria-hidden>
          <svg viewBox="0 0 320 96" preserveAspectRatio="none">
            <defs>
              <linearGradient id="authEqFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#55dfb0" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#55dfb0" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path
              d="M0,78 C25,74 35,60 55,62 C75,64 82,48 105,50 C128,52 132,66 155,60 C178,54 185,30 210,34 C235,38 240,52 265,44 C285,38 300,22 320,18 L320,96 L0,96 Z"
              fill="url(#authEqFill)"
            />
            <path
              d="M0,78 C25,74 35,60 55,62 C75,64 82,48 105,50 C128,52 132,66 155,60 C178,54 185,30 210,34 C235,38 240,52 265,44 C285,38 300,22 320,18"
              fill="none"
              stroke="#55dfb0"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path
              d="M0,84 C40,82 80,70 120,72 C170,74 220,60 320,58"
              fill="none"
              stroke="#858fa5"
              strokeWidth="1.5"
              strokeDasharray="5 5"
            />
            <circle cx="320" cy="18" r="4" fill="#55dfb0" />
          </svg>
          <div className="auth-equity-stats">
            <div>
              <small>{t('metric.sharpe')}</small>
              <b className="positive">+2,41</b>
            </div>
            <div>
              <small>{t('metric.totalReturn')}</small>
              <b className="positive">+18,6%</b>
            </div>
            <div>
              <small>{t('metric.maxDd')}</small>
              <b className="negative">−4,2%</b>
            </div>
          </div>
        </div>
        <p className="auth-brand-foot">{t('footer.local')}</p>
      </aside>

      {/* Sağ: form paneli */}
      <main className="auth-main">
        <div className="auth-topbar">
          <div className="segmented" role="group" aria-label={t('lang.label')}>
            <button className={lang === 'tr' ? 'chosen' : ''} onClick={() => setLang('tr')} aria-pressed={lang === 'tr'}>
              TR
            </button>
            <button className={lang === 'en' ? 'chosen' : ''} onClick={() => setLang('en')} aria-pressed={lang === 'en'}>
              EN
            </button>
          </div>
          <button
            className="icon-button theme-toggle"
            title={theme === 'dark' ? t('topbar.light') : t('topbar.dark')}
            aria-label={theme === 'dark' ? t('topbar.light') : t('topbar.dark')}
            onClick={toggleTheme}
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>

        <div className="auth-card">
          <span className="auth-card-badge">
            <Activity size={14} />
            {t('auth.cardBadge')}
          </span>
          <h2>{mode === 'login' ? t('auth.loginTitle') : t('auth.registerTitle')}</h2>
          <p className="auth-card-sub">{mode === 'login' ? t('auth.loginSub') : t('auth.registerSub')}</p>

          <div className="auth-tabs" role="tablist" aria-label={t('auth.cardBadge')}>
            <button
              role="tab"
              aria-selected={mode === 'login'}
              className={mode === 'login' ? 'chosen' : ''}
              onClick={() => switchMode('login')}
            >
              {t('auth.tabLogin')}
            </button>
            <button
              role="tab"
              aria-selected={mode === 'register'}
              className={mode === 'register' ? 'chosen' : ''}
              onClick={() => switchMode('register')}
            >
              {t('auth.tabRegister')}
            </button>
          </div>

          <form onSubmit={submit} noValidate>
            {formError && (
              <div className="alert auth-alert" role="alert">
                <span>{formError}</span>
              </div>
            )}

            {mode === 'register' && (
              <label className={errors.name ? 'has-error' : ''}>
                {t('auth.name')}
                <span className="auth-field">
                  <User size={16} />
                  <input
                    type="text"
                    autoComplete="name"
                    placeholder={t('auth.namePh')}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </span>
                {errors.name && <small className="field-error">{errors.name}</small>}
              </label>
            )}

            <label className={errors.email ? 'has-error' : ''}>
              {t('auth.email')}
              <span className="auth-field">
                <AtSign size={16} />
                <input
                  type="email"
                  autoComplete="email"
                  placeholder="ornek@eposta.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </span>
              {errors.email && <small className="field-error">{errors.email}</small>}
            </label>

            <label className={errors.password ? 'has-error' : ''}>
              {t('auth.password')}
              <span className="auth-field">
                <Lock size={16} />
                <input
                  type={showPw ? 'text' : 'password'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="auth-eye"
                  aria-label={showPw ? 'hide' : 'show'}
                  onClick={() => setShowPw((v) => !v)}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </span>
              {errors.password && <small className="field-error">{errors.password}</small>}
            </label>

            {mode === 'register' && (
              <>
                {password.length > 0 && (
                  <div className="auth-strength" aria-live="polite">
                    <div className="auth-strength-track">
                      {[0, 1, 2, 3].map((i) => (
                        <span key={i} className={i <= score ? `on s${score}` : ''} />
                      ))}
                    </div>
                    <small>{strengthLabel}</small>
                  </div>
                )}
                <label className={errors.confirm ? 'has-error' : ''}>
                  {t('auth.confirm')}
                  <span className="auth-field">
                    <Lock size={16} />
                    <input
                      type={showPw2 ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="••••••••"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                    />
                    <button
                      type="button"
                      className="auth-eye"
                      aria-label={showPw2 ? 'hide' : 'show'}
                      onClick={() => setShowPw2((v) => !v)}
                    >
                      {showPw2 ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </span>
                  {errors.confirm && <small className="field-error">{errors.confirm}</small>}
                </label>
              </>
            )}

            {mode === 'login' ? (
              <div className="auth-row">
                <label className="auth-check">
                  <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
                  <span className="auth-box" aria-hidden>
                    {remember && <Check size={12} />}
                  </span>
                  {t('auth.remember')}
                </label>
                <button type="button" className="text-button auth-link" onClick={() => setFormError(t('auth.forgotInfo'))}>
                  {t('auth.forgot')}
                </button>
              </div>
            ) : (
              <label className={`auth-check auth-kvkk ${errors.kvkk ? 'has-error' : ''}`}>
                <input type="checkbox" checked={kvkk} onChange={(e) => setKvkk(e.target.checked)} />
                <span className="auth-box" aria-hidden>
                  {kvkk && <Check size={12} />}
                </span>
                <small>{t('auth.kvkk')}</small>
              </label>
            )}
            {mode === 'register' && errors.kvkk && <small className="field-error">{errors.kvkk}</small>}

            <button className="primary full-width auth-submit" type="submit" disabled={busy}>
              {busy ? <Loader2 size={16} className="spin" /> : null}
              {mode === 'login' ? t('auth.loginBtn') : t('auth.registerBtn')}
              {!busy && <ArrowRight size={16} />}
            </button>
          </form>

          <div className="auth-divider">
            <span>{t('auth.or')}</span>
          </div>

          <button className="secondary full-width auth-demo" type="button" onClick={demo} disabled={demoBusy}>
            {demoBusy ? <Loader2 size={16} className="spin" /> : <FlaskConical size={16} />}
            {t('auth.demoBtn')}
          </button>
          <p className="auth-demo-hint">
            {DEMO_USER.email} · {DEMO_USER.password}
          </p>

          <p className="auth-switch">
            {mode === 'login' ? t('auth.noAccount') : t('auth.hasAccount')}{' '}
            <button type="button" className="text-button auth-link" onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}>
              {mode === 'login' ? t('auth.tabRegister') : t('auth.tabLogin')}
            </button>
          </p>
        </div>

        <p className="auth-foot">
          <ShieldCheck size={13} />
          {t('auth.localNote')}
        </p>
      </main>
    </div>
  );
}

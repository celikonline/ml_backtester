import { useEffect, useState } from 'react';
import { LogOut, User, Mail, Lock, ShieldOff, KeyRound, Users, Archive, Globe2, Moon, Sun, AlertTriangle } from 'lucide-react';
import { useAuth } from './auth';
import { useLang } from './i18n';
import { api } from './App';

type AccountStats = {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at?: string;
  last_login_at?: string;
  projects: number;
  backtests: number;
  live_volume: number;
  public_algorithms: number;
  live_deployments: number;
  lines_of_code: number;
};

type Session = {
  id: string;
  issued_at: string;
  expires_at: string;
  last_used: string;
  user_agent: string;
  active: boolean;
};

function StatCard({ label, value, sub = '', kind = '' }: { label: string; value: string | number; sub?: string; kind?: string }) {
  const { t } = useLang();
  return (
    <div className={`account-stat ${kind}`}>
      <div className="account-stat-label">{t(label)}</div>
      <div className={`account-stat-value ${kind}`}>{value}</div>
      {sub && <div className="account-stat-sub">{sub}</div>}
    </div>
  );
}

export default function AccountPage() {
  const { t, lang, fmt, fmtDate } = useLang();
  const { user, logout } = useAuth();
  const [stats, setStats] = useState<AccountStats | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState<'summary' | 'settings' | 'security' | 'sessions' | 'deactivation'>('summary');

  // Name edit state
  const [name, setName] = useState(user?.name ?? '');
  const [nameSaving, setNameSaving] = useState(false);

  // Email change state
  const [email, setEmail] = useState(user?.email ?? '');
  const [emailPassword, setEmailPassword] = useState('');
  const [emailSaving, setEmailSaving] = useState(false);

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);

  // Deactivation confirm
  const [deactivating, setDeactivating] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const s = await api<AccountStats>('/auth/stats', { headers: { Authorization: `Bearer ${localStorage.getItem('regimelab.token')}` } });
      setStats(s);
      const sess = await api<{ sessions: Session[] }>('/auth/sessions', { headers: { Authorization: `Bearer ${localStorage.getItem('regimelab.token')}` } });
      setSessions(sess.sessions);
    } catch {
      // ignore
    }
  }

  async function saveName() {
    if (!name.trim() || name.trim().length < 2) { setError(t('auth.errName')); return; }
    setError('');
    setNameSaving(true);
    try {
      const token = localStorage.getItem('regimelab.token') ?? '';
      const res = await fetch('/api/auth/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || t('account.success')); }
      setError(t('account.success'));
      setTimeout(()=>setError(''), 2500);
    } catch (e) {
      setError((e as Error).message || t('account.success'));
      setTimeout(()=>setError(''), 2500);
    } finally {
      setNameSaving(false);
    }
  }

  async function saveEmail() {
    if (!email.trim() || !emailPassword) { setError(t('account.inputEmail') + ' + ' + t('account.inputPassword')); return; }
    setError('');
    setEmailSaving(true);
    try {
      const token = localStorage.getItem('regimelab.token') ?? '';
      const res = await fetch('/api/auth/email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password: emailPassword }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        if (d.detail === 'Bu e-posta zaten kullanılıyor.' || d.detail === 'This email is already in use.') throw new Error(t('account.emailTakenError'));
        throw new Error(d.detail || t('account.success'));
      }
      setError(t('account.success'));
      setTimeout(()=>setError(''), 2500);
      load();
    } catch (e) {
      setError((e as Error).message || t('account.success'));
      setTimeout(()=>setError(''), 2500);
    } finally {
      setEmailSaving(false);
    }
  }

  async function savePassword() {
    if (!currentPassword || !newPassword || !confirmPassword) { setError(t('account.inputPassword') + ' + ' + t('account.inputNewPassword') + ' + ' + t('account.inputConfirmNew')); return; }
    if (newPassword.length < 8) { setError(t('account.passwordTooShort')); return; }
    if (newPassword !== confirmPassword) { setError(t('account.passwordsMismatch')); return; }
    setError('');
    setPasswordSaving(true);
    try {
      const token = localStorage.getItem('regimelab.token') ?? '';
      const res = await fetch('/api/auth/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ old_password: currentPassword, new_password: newPassword }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        if (d.detail === 'Eski şifre hatalı.' || d.detail === 'Current password is incorrect.') throw new Error(t('account.oldPasswordError'));
        throw new Error(d.detail || t('account.success'));
      }
      setError(t('account.success'));
      setTimeout(()=>{ setError(''); setCurrentPassword(''); setNewPassword(''); setConfirmPassword(''); }, 2500);
    } catch (e) {
      setError((e as Error).message || t('account.success'));
      setTimeout(()=>setError(''), 2500);
    } finally {
      setPasswordSaving(false);
    }
  }

  async function revokeAllSessions() {
    if (!confirm(t('account.revokeAllConfirm'))) return;
    setBusy(true);
    try {
      const token = localStorage.getItem('regimelab.token') ?? '';
      const res = await fetch('/api/auth/token/revoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ token_id: '' }),
      });
      if (!res.ok) throw new Error(t('api.genericError'));
      load();
      setError(t('account.success'));
      setTimeout(()=>setError(''), 2500);
    } catch (e) {
      setError((e as Error).message || t('api.genericError'));
    } finally {
      setBusy(false);
    }
  }

  async function deactivateAccount() {
    if (!confirm(t('account.deactivationDesc'))) return;
    setDeactivating(true);
    try {
      // In a real app this would call something like POST /auth/deactivate
      logout();
      window.location.href = '/';
    } catch {
      setDeactivating(false);
    }
  }

  return (
    <div className="account-shell">
      <aside className="account-nav">
        <button className={`account-nav-item ${section === 'summary' ? 'active' : ''}`} onClick={() => setSection('summary')}>
          <User size={16} /> {t('account.summary')}
        </button>
        <button className={`account-nav-item ${section === 'settings' ? 'active' : ''}`} onClick={() => setSection('settings')}>
          <Globe2 size={16} /> {t('account.settings')}
        </button>
        <button className={`account-nav-item ${section === 'security' ? 'active' : ''}`} onClick={() => setSection('security')}>
          <ShieldOff size={16} /> {t('account.security')}
        </button>
        <button className={`account-nav-item ${section === 'sessions' ? 'active' : ''}`} onClick={() => setSection('sessions')}>
          <Users size={16} /> {t('account.activeSessions')}
        </button>
        <button className={`account-nav-item ${section === 'deactivation' ? 'active' : ''}`} onClick={() => setSection('deactivation')}>
          <Archive size={16} /> {t('account.deactivation')}
        </button>
      </aside>

      <main className="account-main">
        {section === 'summary' && (
          <section className="account-section">
            <div className="account-section-header">
              <h2>{t('account.summary')}</h2>
              <button className="text-button" onClick={() => setSection('settings')}>{t('account.settings')} <Sun size={14} /></button>
            </div>
            <div className="account-summary-grid">
              <StatCard label="account.projects" value={stats?.projects ?? 0} sub="" kind="" />
              <StatCard label="account.backtests" value={stats?.backtests ?? 0} sub="" kind="" />
              <StatCard label="account.liveVolume" value={stats?.live_volume ?? 0} sub="" kind="" />
              <StatCard label="account.publicAlgo" value={stats?.public_algorithms ?? 0} sub="" kind="" />
              <StatCard label="account.liveDeploy" value={stats?.live_deployments ?? 0} sub="" kind="" />
              <StatCard label="account.loc" value={stats?.lines_of_code ?? 1} sub="" kind="" />
            </div>
            <div className="account-profile-card">
              <div className="account-avatar">{((stats?.name || user?.name || user?.email || '?').trim().charAt(0).toUpperCase())}</div>
              <div className="account-profile-info">
                <div><b>{stats?.name || user?.name || ''}</b></div>
                <small>{stats?.email || user?.email || ''}</small>
                <span className="badge">{stats?.role || 'user'}</span>
              </div>
            </div>
            {stats?.created_at && (
              <div className="account-meta">
                <div><b>{t('account.createdAt')}</b> <span>{fmtDate(stats.created_at)}</span></div>
                <div><b>{t('account.lastLogin')}</b> <span>{stats.last_login_at ? fmtDate(stats.last_login_at) : '—'}</span></div>
              </div>
            )}
          </section>
        )}

        {section === 'settings' && (
          <section className="account-section">
            <div className="account-section-header"><h2>{t('account.settings')}</h2></div>

            <div className="settings-block">
              <h3 className="settings-block-title">{t('account.inputName')}</h3>
              <div className="settings-field">
                <input className="account-input" value={name} onChange={e => setName(e.target.value)} placeholder={user?.name || ''} disabled={nameSaving} />
                <button className="primary account-btn" disabled={nameSaving || !name.trim() || name.trim().length < 2} onClick={saveName}>
                  {nameSaving ? <span className="spin-loader" /> : <><User size={15} /> {t('account.save')}</>}
                </button>
              </div>
              {nameSaving && <div className="account-save-note">Kaydediliyor…</div>}
            </div>

            <div className="settings-block">
              <h3 className="settings-block-title">{t('account.prefLang')}</h3>
              <div className="settings-field">
                <div className="segmented">
                  <button className={lang === 'tr' ? 'chosen' : ''} onClick={() => {}}>TR</button>
                  <button className={lang === 'en' ? 'chosen' : ''} onClick={() => {}}>EN</button>
                </div>
              </div>
            </div>

            <div className="settings-block">
              <h3 className="settings-block-title">{t('account.prefTheme')}</h3>
              <div className="settings-field">
                <div className="segmented">
                  <button className={`theme-toggle-btn ${document.documentElement.dataset.theme === 'dark' ? 'chosen' : ''}`} onClick={() => {}}>
                    <Moon size={15} /> Koyu
                  </button>
                  <button className={`theme-toggle-btn ${document.documentElement.dataset.theme === 'light' ? 'chosen' : ''}`} onClick={() => {}}>
                    <Sun size={15} /> Beyaz
                  </button>
                </div>
              </div>
            </div>

            <div className="settings-block">
              <h3 className="settings-block-title">{t('account.changeEmail')}</h3>
              <div className="settings-field">
                <input className="account-input" value={email} onChange={e => setEmail(e.target.value)} placeholder={user?.email || ''} />
                <input className="account-input password" value={emailPassword} onChange={e => setEmailPassword(e.target.value)} type="password" placeholder={t('account.inputPassword')} />
                <button className="primary account-btn" disabled={emailSaving || !email.trim() || !emailPassword} onClick={saveEmail}>
                  {emailSaving ? <span className="spin-loader" /> : <><Mail size={15} /> {t('account.save')}</>}
                </button>
              </div>
            </div>

            <div className="settings-block">
              <h3 className="settings-block-title">{t('account.changePassword')}</h3>
              <div className="settings-field settings-grid">
                <input className="account-input password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} type="password" placeholder={t('account.inputPassword')} />
                <input className="account-input password" value={newPassword} onChange={e => setNewPassword(e.target.value)} type="password" placeholder={t('account.inputNewPassword')} />
                <input className="account-input password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} type="password" placeholder={t('account.inputConfirmNew')} />
                <button className="primary account-btn" disabled={passwordSaving || !currentPassword || !newPassword || !confirmPassword || newPassword.length < 8 || newPassword !== confirmPassword} onClick={savePassword}>
                  {passwordSaving ? <span className="spin-loader" /> : <><Lock size={15} /> {t('account.save')}</>}
                </button>
              </div>
            </div>

            <div className="settings-block">
              <h3 className="settings-block-title">{t('account.subscriptions')}</h3>
              <div className="settings-desc">{t('account.manageEmailSub')}</div>
            </div>
          </section>
        )}

        {section === 'security' && (
          <section className="account-section">
            <div className="account-section-header"><h2>{t('account.security')}</h2></div>

            <div className="security-card">
              <div className="security-card-header"><KeyRound size={20} /> <b>{t('account.tokenInfo')}</b></div>
              <div className="security-card-body">
                <p>{t('account.token')}</p>
                <div className="token-display">
                  <pre className="token-code">{user?.id || stats?.id || '—'}</pre>
                </div>
                <div className="token-meta">
                  <div><b>{t('account.tokenCreated')}</b> <span>{stats?.created_at ? fmtDate(stats.created_at) : '—'}</span></div>
                  <div><b>{t('account.tokenLastUsed')}</b> <span>{stats?.last_login_at ? fmtDate(stats.last_login_at) : '—'}</span></div>
                  <div><b>{t('account.tokenAgent')}</b> <span>{user?.id ? 'local-user' : '—'}</span></div>
                </div>
                <button className="primary account-btn" onClick={() => setSection('sessions')}>
                  <Users size={15} /> {t('account.activeSessions')}
                </button>
              </div>
            </div>

            <div className="security-card">
              <div className="security-card-header"><ShieldOff size={20} /> <b>{t('account.activate2fa')}</b></div>
              <div className="security-card-body">
                <p>{t('account.no2fa')}</p>
                <div className="security-placeholder">2FA feature coming soon.</div>
              </div>
            </div>
          </section>
        )}

        {section === 'sessions' && (
          <section className="account-section">
            <div className="account-section-header">
              <h2>{t('account.activeSessions')}</h2>
              <button className="secondary account-btn" disabled={busy || !sessions.length} onClick={revokeAllSessions}>
                <AlertTriangle size={14} /> {t('account.revokeAll')}
              </button>
            </div>
            {!sessions.length ? (
              <div className="small-empty"><Users size={25} /> <span>{t('account.noSession')}</span></div>
            ) : (
              <div className="sessions-table-wrap">
                <table className="sessions-table">
                  <thead>
                    <tr>
                      <th>{t('account.sessionCreated')}</th>
                      <th>{t('account.sessionLastUsed')}</th>
                      <th>{t('account.sessionAgent')}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map(s => (
                      <tr key={s.id}>
                        <td>{fmtDate(s.issued_at)}</td>
                        <td>{fmtDate(s.expires_at)}</td>
                        <td><span className="session-agent" title={s.user_agent}>{s.user_agent.slice(0, 50)}{s.user_agent.length > 50 ? '…' : ''}</span></td>
                        <td><button className="text-button session-revoke" disabled={busy} onClick={() => {
                          fetch('/api/auth/token/revoke', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('regimelab.token')}` },
                            body: JSON.stringify({ token_id: s.id }),
                          }).then(r => { if (r.ok) return load(); });
                        }}>
                          {t('account.sessionSignOut')} <LogOut size={12} />
                        </button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {section === 'deactivation' && (
          <section className="account-section">
            <div className="account-section-header"><h2>{t('account.deactivation')}</h2></div>
            <div className="deactivation-card">
              <AlertTriangle size={24} className="deactivation-icon" />
              <div>
                <h3>{t('account.deactivation')}</h3>
                <p>{t('account.deactivationDesc')}</p>
              </div>
            </div>
            <div className="deactivation-actions">
              <a className="secondary" href={t('account.learnMore')} target="_blank" rel="noreferrer">{t('account.learnMore')}</a>
              <a className="secondary" href={t('account.contactUs')} target="_blank" rel="noreferrer">{t('account.contactUs')}</a>
              <button className="primary account-btn" disabled={deactivating} onClick={deactivateAccount}>
                {deactivating ? <span className="spin-loader" /> : <><Archive size={15} /> Hesabı devre dışı bırak</>}
              </button>
            </div>
          </section>
        )}

        {error && <div className="account-alert" role="alert"><span>{error}</span><button aria-label={t('alert.closeError')} onClick={() => setError('')}><span aria-hidden="true">×</span></button></div>}
      </main>
    </div>
  );
}

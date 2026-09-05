/**
 * RegimeLab — Notebook Lab UI
 *
 * Features:
 *  - Notebook registry (list, upload, archive, inspect)
 *  - Version history
 *  - Run dialog (experiment + dataset + environment + parameters)
 *  - Live run progress via SSE
 *  - Artifact browser
 *  - Metrics viewer
 *  - Workspace secrets manager
 */
import { useEffect, useRef, useState } from 'react';
import {
  AlertCircle, Archive, ArrowRight, BookOpen, Check, ChevronDown,
  ChevronRight, Clock3, FileCode2, FlaskConical, Folder, Key, Loader2,
  Package, Play, Plus, RefreshCw, Square, Terminal, Trash2,
  Upload, X, Zap
} from 'lucide-react';
import { request, headers, terminal as isTerminal } from './platform-api';
import type { Event } from './platform-api';
import { useWorkspace } from './workspace';
import { useLang } from './i18n';
import './notebook.css';

// ── Types ────────────────────────────────────────────────────────────────────

interface NbEnvironment { id: string; environment_code: string; name: string; python_version: string; status: string; }
interface NbVersion { id: string; version: number; content_hash: string; change_summary: string; created_at: string; }
interface Notebook {
  id: string; notebook_code: string; workspace_id: string;
  name: string; description: string; source_filename: string;
  content_hash: string; version: number; status: string;
  tags: string[]; created_at: string; updated_at: string;
  versions?: NbVersion[];
}
interface NbRun {
  id: string; run_code: string; workspace_id: string;
  notebook_id: string; notebook_version_id: string;
  experiment_id: string | null; dataset_snapshot_id: string | null;
  environment_id: string | null; status: string;
  parameters: Record<string, unknown>;
  network_mode: string; started_at: string | null;
  completed_at: string | null; duration_seconds: number | null;
  exit_code: number | null; error_type: string | null;
  error_message: string | null; metrics: Record<string, number> | null;
  artifact_count: number; created_at: string;
  artifacts?: Artifact[];
}
interface Artifact { name: string; size_bytes: number; sha256: string; content_type: string; path: string; }
interface Inspection {
  compatible: boolean; python_version: string; parameter_cell_found: boolean;
  imports: string[]; issues: { severity: string; code: string; detail: string }[];
  cells_inspected: number;
}
interface WorkspaceSecret { id: string; key_name: string; description: string; created_at: string; updated_at: string; }
interface Experiment { id: string; code: string; name: string; status: string; }
interface Snapshot { id: string; sha256: string; details: { name: string; rows: number }; created_at: string; }

const NB_TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'POLICY_REJECTED']);

function statusColor(s: string) {
  if (s === 'COMPLETED') return 'var(--color-emerald)';
  if (s === 'RUNNING' || s === 'PREPARING') return 'var(--color-sky)';
  if (s === 'QUEUED') return 'var(--color-amber)';
  if (s === 'FAILED' || s === 'TIMEOUT') return 'var(--color-rose)';
  if (s === 'CANCELLED') return 'var(--color-muted)';
  return 'var(--color-muted)';
}

function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

function fmtDuration(s: number | null) {
  if (!s) return '—';
  const m = Math.floor(s / 60), sec = Math.round(s % 60);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function NotebookLab() {
  const { currentId: wsId } = useWorkspace();
  const { t } = useLang();

  const [view, setView] = useState<'list' | 'detail' | 'run' | 'secrets'>('list');
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [selectedNb, setSelectedNb] = useState<Notebook | null>(null);
  const [runs, setRuns] = useState<NbRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<NbRun | null>(null);
  const [envs, setEnvs] = useState<NbEnvironment[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [secrets, setSecrets] = useState<WorkspaceSecret[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [detailTab, setDetailTab] = useState('overview');
  const [runLogs, setRunLogs] = useState<Event[]>([]);
  const [liveRunId, setLiveRunId] = useState<string | null>(null);

  // Run dialog state
  const [runDlgOpen, setRunDlgOpen] = useState(false);
  const [runParams, setRunParams] = useState({ experiment_id: '', dataset_snapshot_id: '', environment_id: '', network_mode: 'SNAPSHOT_ONLY', params_raw: '{}' });

  // Secret dialog state
  const [secretDlg, setSecretDlg] = useState(false);
  const [secretForm, setSecretForm] = useState({ key: '', value: '', description: '' });

  const uploadRef = useRef<HTMLInputElement>(null);
  const runDlgRef = useRef<HTMLDialogElement>(null);

  // ── Data loading ──────────────────────────────────────────────────────────

  async function loadAll() {
    if (!wsId) return;
    try {
      const [nbs, ev, snaps] = await Promise.all([
        request<Notebook[]>(`/workspaces/${wsId}/notebooks`),
        request<Experiment[]>(`/experiments?workspace_id=${wsId}`),
        request<Snapshot[]>(`/datasets`),
      ]);
      setNotebooks(nbs);
      setExperiments(ev);
      setSnapshots(snaps as unknown as Snapshot[]);
      const e = await request<NbEnvironment[]>('/notebook-environments');
      setEnvs(e);
    } catch (e) { setError(String(e)); }
  }

  async function loadSecrets() {
    if (!wsId) return;
    try { setSecrets(await request<WorkspaceSecret[]>(`/workspaces/${wsId}/secrets`)); }
    catch (e) { setError(String(e)); }
  }

  async function loadRuns(nbId?: string) {
    if (!wsId) return;
    try {
      const qs = nbId ? `&notebook_id=${nbId}` : '';
      setRuns(await request<NbRun[]>(`/workspaces/${wsId}/notebook-runs?limit=50${qs}`));
    } catch (e) { setError(String(e)); }
  }

  useEffect(() => { loadAll(); }, [wsId]);

  useEffect(() => {
    if (runDlgOpen && runDlgRef.current && !runDlgRef.current.open) runDlgRef.current.showModal();
    if (!runDlgOpen && runDlgRef.current?.open) runDlgRef.current.close();
  }, [runDlgOpen]);

  // ── SSE for live run ──────────────────────────────────────────────────────

  useEffect(() => {
    if (!liveRunId || !wsId) return;
    const ctrl = new AbortController(); let cursor = 0;
    async function listen() {
      try {
        const res = await fetch(`/api/v1/workspaces/${wsId}/notebook-runs/${liveRunId}/events?after=${cursor}`, { headers: headers(), signal: ctrl.signal });
        if (!res.ok || !res.body) return;
        const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = '';
        while (true) {
          const { done, value } = await reader.read(); if (done) break;
          buf += dec.decode(value, { stream: true }); let pos: number;
          while ((pos = buf.indexOf('\n\n')) >= 0) {
            const block = buf.slice(0, pos); buf = buf.slice(pos + 2);
            const line = block.split('\n').find(l => l.startsWith('data: '));
            if (line && !block.includes('event: done')) {
              const ev = JSON.parse(line.slice(6)) as Event;
              cursor = ev.id;
              setRunLogs(prev => prev.some(e => e.id === ev.id) ? prev : [...prev, ev]);
            }
            if (block.includes('event: done')) {
              const updated = await request<NbRun>(`/workspaces/${wsId}/notebook-runs/${liveRunId}`);
              setSelectedRun(updated);
              setRuns(prev => prev.map(r => r.id === liveRunId ? updated : r));
              setLiveRunId(null); return;
            }
          }
        }
      } catch { /* aborted */ }
    }
    listen();
    return () => ctrl.abort();
  }, [liveRunId, wsId]);

  // ── Actions ───────────────────────────────────────────────────────────────

  async function uploadNotebook(file: File) {
    if (!wsId) return;
    setUploading(true); setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`/api/v1/workspaces/${wsId}/notebooks?name=${encodeURIComponent(file.name)}`, {
        method: 'POST', headers: Object.fromEntries(Object.entries(headers()).filter(([k]) => k !== 'Content-Type')), body: form,
      });
      if (!res.ok) { const b = await res.json(); throw new Error(b.error?.message || 'Upload failed'); }
      const nb = await res.json() as { inspection: Inspection } & Notebook;
      await loadAll();
      if (nb.inspection && nb.inspection.issues.length) {
        setError(`Notebook yüklendi. Uyarılar: ${nb.inspection.issues.map(i => i.code).join(', ')}`);
      }
    } catch (e) { setError(String(e)); }
    finally { setUploading(false); if (uploadRef.current) uploadRef.current.value = ''; }
  }

  async function openNotebook(nb: Notebook) {
    if (!wsId) return;
    try {
      const full = await request<Notebook>(`/workspaces/${wsId}/notebooks/${nb.id}`);
      setSelectedNb(full); setDetailTab('overview'); setView('detail');
      await loadRuns(nb.id);
    } catch (e) { setError(String(e)); }
  }

  async function archiveNotebook(nb: Notebook) {
    if (!wsId || !confirm(`"${nb.name}" arşivlensin mi?`)) return;
    try {
      await request(`/workspaces/${wsId}/notebooks/${nb.id}/archive`, 'POST');
      await loadAll(); setView('list'); setSelectedNb(null);
    } catch (e) { setError(String(e)); }
  }

  async function submitRun() {
    if (!wsId || !selectedNb) return;
    setBusy(true); setError('');
    try {
      let params: Record<string, unknown> = {};
      try { params = JSON.parse(runParams.params_raw); } catch { setError('Parametreler geçerli JSON değil.'); setBusy(false); return; }
      const body = {
        notebook_id: selectedNb.id,
        experiment_id: runParams.experiment_id || null,
        dataset_snapshot_id: runParams.dataset_snapshot_id || null,
        environment_id: runParams.environment_id || null,
        parameters: params,
        network_mode: runParams.network_mode,
      };
      const run = await request<NbRun>(`/workspaces/${wsId}/notebook-runs`, 'POST', body);
      setRunDlgOpen(false);
      setRuns(prev => [run, ...prev]);
      setSelectedRun(run);
      setRunLogs([]);
      setLiveRunId(run.id);
      setDetailTab('runs');
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function cancelRun(runId: string) {
    if (!wsId) return;
    try { await request(`/workspaces/${wsId}/notebook-runs/${runId}/cancel`, 'POST'); }
    catch (e) { setError(String(e)); }
  }

  async function openRun(run: NbRun) {
    if (!wsId) return;
    try {
      const full = await request<NbRun>(`/workspaces/${wsId}/notebook-runs/${run.id}`);
      setSelectedRun(full); setRunLogs([]);
      if (!NB_TERMINAL.has(full.status)) { setLiveRunId(full.id); }
    } catch (e) { setError(String(e)); }
  }

  async function saveSecret() {
    if (!wsId || !secretForm.key) return;
    try {
      await request(`/workspaces/${wsId}/secrets/${encodeURIComponent(secretForm.key)}`, 'PUT', { value: secretForm.value, description: secretForm.description });
      setSecretDlg(false); setSecretForm({ key: '', value: '', description: '' });
      await loadSecrets();
    } catch (e) { setError(String(e)); }
  }

  async function deleteSecret(key: string) {
    if (!wsId || !confirm(`"${key}" silinsin mi?`)) return;
    try { await request(`/workspaces/${wsId}/secrets/${encodeURIComponent(key)}`, 'DELETE'); await loadSecrets(); }
    catch (e) { setError(String(e)); }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="nb-lab">
      {/* Header */}
      <div className="nb-header">
        <div className="nb-header-left">
          {view !== 'list' && (
            <button className="text-button" onClick={() => { setView('list'); setSelectedNb(null); setSelectedRun(null); }}>
              <ChevronRight size={14} style={{ transform: 'rotate(180deg)' }} /> Geri
            </button>
          )}
          <h2 className="nb-title">
            <BookOpen size={20} />
            {view === 'list' ? 'Notebook Lab' : view === 'secrets' ? 'Workspace Secrets' : selectedNb?.name || 'Notebook Lab'}
          </h2>
          {view === 'list' && <span className="badge">{notebooks.length} notebook</span>}
        </div>
        <div className="nb-header-right">
          {view === 'list' && (
            <>
              <button className="secondary" onClick={() => { setView('secrets'); loadSecrets(); }}>
                <Key size={15} /> Secrets
              </button>
              <button className="secondary" onClick={loadAll} title="Yenile">
                <RefreshCw size={15} />
              </button>
              <label className="primary" style={{ cursor: 'pointer' }}>
                {uploading ? <><Loader2 size={15} className="spin" /> Yükleniyor…</> : <><Upload size={15} /> Notebook Yükle</>}
                <input ref={uploadRef} type="file" accept=".ipynb" hidden onChange={e => { const f = e.target.files?.[0]; if (f) uploadNotebook(f); }} />
              </label>
            </>
          )}
          {view === 'detail' && selectedNb && (
            <button className="primary" onClick={() => setRunDlgOpen(true)}>
              <Play size={15} /> Çalıştır
            </button>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="alert" role="alert" style={{ margin: '0 0 1rem' }}>
          <AlertCircle size={15} /> <span>{error}</span>
          <button onClick={() => setError('')}><X size={14} /></button>
        </div>
      )}

      {/* Secrets view */}
      {view === 'secrets' && (
        <div className="nb-secrets">
          <div className="nb-section-header">
            <h3>Workspace Secrets</h3>
            <button className="primary" onClick={() => setSecretDlg(true)}><Plus size={15} /> Ekle</button>
          </div>
          <p className="nb-desc">Secret değerleri loglanmaz, artifact'e yazılmaz. Notebook içinde <code>os.environ["KEY"]</code> ile kullanın.</p>
          {secrets.length === 0 ? (
            <div className="nb-empty"><Key size={32} /><p>Henüz secret yok.</p></div>
          ) : (
            <table className="nb-table">
              <thead><tr><th>Anahtar</th><th>Açıklama</th><th>Güncelleme</th><th /></tr></thead>
              <tbody>
                {secrets.map(s => (
                  <tr key={s.id}>
                    <td><code>{s.key_name}</code></td>
                    <td>{s.description || '—'}</td>
                    <td><small>{s.updated_at.slice(0, 16).replace('T', ' ')}</small></td>
                    <td><button className="text-button" onClick={() => deleteSecret(s.key_name)}><Trash2 size={13} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {secretDlg && (
            <div className="nb-overlay">
              <div className="nb-dialog">
                <div className="nb-dialog-head">
                  <h3><Key size={16} /> Secret Ekle</h3>
                  <button className="icon-button" onClick={() => setSecretDlg(false)}><X size={18} /></button>
                </div>
                <label>Anahtar adı (büyük harf)<input value={secretForm.key} onChange={e => setSecretForm(p => ({ ...p, key: e.target.value.toUpperCase() }))} placeholder="FRED_API_KEY" /></label>
                <label>Değer<input type="password" value={secretForm.value} onChange={e => setSecretForm(p => ({ ...p, value: e.target.value }))} /></label>
                <label>Açıklama<input value={secretForm.description} onChange={e => setSecretForm(p => ({ ...p, description: e.target.value }))} /></label>
                <button className="primary" onClick={saveSecret}>Kaydet</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Notebook list */}
      {view === 'list' && (
        <div className="nb-list-view">
          {notebooks.length === 0 ? (
            <div className="nb-empty-state">
              <BookOpen size={48} strokeWidth={1} />
              <h3>Notebook Lab</h3>
              <p>Araştırma notebook'larını workspace'e bağlı, versiyonlanmış ve parameterize edilmiş şekilde çalıştırın.</p>
              <label className="primary" style={{ cursor: 'pointer', display: 'inline-flex', gap: '0.5rem', alignItems: 'center' }}>
                <Upload size={16} /> İlk Notebook'u Yükle
                <input type="file" accept=".ipynb" hidden onChange={e => { const f = e.target.files?.[0]; if (f) uploadNotebook(f); }} />
              </label>
            </div>
          ) : (
            <div className="nb-grid">
              {notebooks.map(nb => (
                <div key={nb.id} className="nb-card" onClick={() => openNotebook(nb)}>
                  <div className="nb-card-top">
                    <FileCode2 size={20} />
                    <span className={`badge ${nb.status === 'ARCHIVED' ? 'muted' : ''}`}>{nb.status === 'ARCHIVED' ? 'Arşiv' : `v${nb.version}`}</span>
                  </div>
                  <h3>{nb.name}</h3>
                  <p>{nb.description || nb.source_filename}</p>
                  <div className="nb-card-footer">
                    <small>{nb.notebook_code}</small>
                    <small>{nb.updated_at.slice(0, 10)}</small>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Notebook detail */}
      {view === 'detail' && selectedNb && (
        <div className="nb-detail">
          {/* Tabs */}
          <div className="nb-tabs">
            {['overview', 'runs', 'versions', 'artifacts'].map(tab => (
              <button key={tab} className={`nb-tab ${detailTab === tab ? 'active' : ''}`} onClick={() => setDetailTab(tab)}>
                {tab === 'overview' ? 'Genel Bakış' : tab === 'runs' ? 'Çalıştırmalar' : tab === 'versions' ? 'Versiyonlar' : 'Artifacts'}
              </button>
            ))}
          </div>

          {/* Overview tab */}
          {detailTab === 'overview' && (
            <div className="nb-overview">
              <div className="nb-meta-grid">
                <div className="nb-meta-item"><small>Kod</small><b>{selectedNb.notebook_code}</b></div>
                <div className="nb-meta-item"><small>Versiyon</small><b>v{selectedNb.version}</b></div>
                <div className="nb-meta-item"><small>Dosya</small><b>{selectedNb.source_filename}</b></div>
                <div className="nb-meta-item"><small>Durum</small><b>{selectedNb.status}</b></div>
                <div className="nb-meta-item"><small>Oluşturulma</small><b>{selectedNb.created_at.slice(0, 16).replace('T', ' ')}</b></div>
                <div className="nb-meta-item"><small>Güncelleme</small><b>{selectedNb.updated_at.slice(0, 16).replace('T', ' ')}</b></div>
              </div>
              {selectedNb.description && <p className="nb-desc">{selectedNb.description}</p>}
              <div className="nb-actions-row">
                <button className="primary" onClick={() => setRunDlgOpen(true)}><Play size={15} /> Çalıştır</button>
                <button className="secondary" onClick={() => archiveNotebook(selectedNb)}>
                  <Archive size={15} /> Arşivle
                </button>
              </div>
            </div>
          )}

          {/* Runs tab */}
          {detailTab === 'runs' && (
            <div className="nb-runs-view">
              {/* Live run progress */}
              {selectedRun && !NB_TERMINAL.has(selectedRun.status) && (
                <div className="nb-live-run">
                  <div className="nb-live-header">
                    <Loader2 size={16} className="spin" />
                    <span>{selectedRun.run_code} — {selectedRun.status}</span>
                    <button className="text-button" onClick={() => cancelRun(selectedRun.id)}>
                      <Square size={13} /> İptal
                    </button>
                  </div>
                  <div className="nb-log-stream">
                    {runLogs.slice(-20).map(ev => (
                      <div key={ev.id} className="nb-log-line">
                        <code>{ev.type}</code>
                        <span>{ev.created_at.slice(11, 19)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Completed run detail */}
              {selectedRun && NB_TERMINAL.has(selectedRun.status) && (
                <div className="nb-run-detail">
                  <div className="nb-run-header" style={{ color: statusColor(selectedRun.status) }}>
                    <b>{selectedRun.run_code}</b>
                    <span>{selectedRun.status}</span>
                    <small>{fmtDuration(selectedRun.duration_seconds)}</small>
                  </div>
                  {selectedRun.error_message && (
                    <div className="alert"><AlertCircle size={13} />{selectedRun.error_message}</div>
                  )}
                  {selectedRun.metrics && Object.keys(selectedRun.metrics).length > 0 && (
                    <div className="nb-metrics-grid">
                      {Object.entries(selectedRun.metrics).map(([k, v]) => (
                        <div key={k} className="nb-metric-card">
                          <small>{k}</small>
                          <b>{typeof v === 'number' ? v.toFixed(4) : String(v)}</b>
                        </div>
                      ))}
                    </div>
                  )}
                  {selectedRun.artifacts && selectedRun.artifacts.length > 0 && (
                    <div className="nb-artifacts">
                      <h4><Folder size={15} /> Artifacts ({selectedRun.artifacts.length})</h4>
                      <div className="nb-artifact-list">
                        {selectedRun.artifacts.map(a => (
                          <div key={a.name} className="nb-artifact-item">
                            <Package size={13} />
                            <span>{a.name}</span>
                            <small>{fmtBytes(a.size_bytes)}</small>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Run history table */}
              <div className="nb-section-header" style={{ marginTop: '1.5rem' }}>
                <h4>Tüm Çalıştırmalar</h4>
                <button className="text-button" onClick={() => loadRuns(selectedNb.id)}><RefreshCw size={13} /></button>
              </div>
              {runs.length === 0 ? (
                <div className="nb-empty"><Clock3 size={28} /><p>Henüz çalıştırma yok.</p></div>
              ) : (
                <table className="nb-table">
                  <thead>
                    <tr><th>Kod</th><th>Durum</th><th>Süre</th><th>Artifacts</th><th>Tarih</th><th /></tr>
                  </thead>
                  <tbody>
                    {runs.map(run => (
                      <tr key={run.id} className={selectedRun?.id === run.id ? 'selected-row' : ''}>
                        <td><code>{run.run_code}</code></td>
                        <td><span style={{ color: statusColor(run.status) }}>{run.status}</span></td>
                        <td>{fmtDuration(run.duration_seconds)}</td>
                        <td>{run.artifact_count}</td>
                        <td><small>{run.created_at.slice(0, 16).replace('T', ' ')}</small></td>
                        <td>
                          <button className="text-button" onClick={() => openRun(run)}>
                            {run.id === liveRunId ? <Loader2 size={13} className="spin" /> : <ChevronRight size={13} />}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* Versions tab */}
          {detailTab === 'versions' && (
            <div>
              {(selectedNb.versions || []).map(v => (
                <div key={v.id} className="nb-version-row">
                  <span className="badge">v{v.version}</span>
                  <div>
                    <b>{v.change_summary}</b>
                    <small>{v.created_at.slice(0, 16).replace('T', ' ')}</small>
                  </div>
                  <code style={{ fontSize: '0.7rem', opacity: 0.5 }}>{v.content_hash.slice(0, 12)}…</code>
                </div>
              ))}
            </div>
          )}

          {/* Artifacts tab — shows last completed run */}
          {detailTab === 'artifacts' && (
            <div>
              {selectedRun?.artifacts?.length ? (
                <div className="nb-artifact-list">
                  {selectedRun.artifacts.map(a => (
                    <div key={a.name} className="nb-artifact-item">
                      <Package size={14} />
                      <span>{a.name}</span>
                      <small>{fmtBytes(a.size_bytes)}</small>
                      <span style={{ opacity: 0.5, fontSize: '0.75rem' }}>{a.content_type}</span>
                    </div>
                  ))}
                </div>
              ) : <div className="nb-empty"><Folder size={32} /><p>Artifact bulunamadı.</p></div>}
            </div>
          )}
        </div>
      )}

      {/* Run dialog */}
      <dialog ref={runDlgRef} onCancel={() => setRunDlgOpen(false)} onClick={e => { if (e.target === runDlgRef.current) setRunDlgOpen(false); }}>
        <div className="nb-dialog">
          <div className="nb-dialog-head">
            <h3><Play size={16} /> Notebook Çalıştır</h3>
            <button className="icon-button" onClick={() => setRunDlgOpen(false)}><X size={18} /></button>
          </div>
          <div className="nb-dialog-body">
            <label>Experiment (opsiyonel)
              <select value={runParams.experiment_id} onChange={e => setRunParams(p => ({ ...p, experiment_id: e.target.value }))}>
                <option value="">— Seçme —</option>
                {experiments.map(e => <option key={e.id} value={e.id}>{e.code} — {e.name}</option>)}
              </select>
            </label>
            <label>Dataset Snapshot (opsiyonel)
              <select value={runParams.dataset_snapshot_id} onChange={e => setRunParams(p => ({ ...p, dataset_snapshot_id: e.target.value }))}>
                <option value="">— Seçme (Exploratory mode) —</option>
                {snapshots.map(s => <option key={s.id} value={s.id}>{(s as any).name || s.id} ({s.id.slice(0, 8)})</option>)}
              </select>
            </label>
            <label>Environment
              <select value={runParams.environment_id} onChange={e => setRunParams(p => ({ ...p, environment_id: e.target.value }))}>
                <option value="">— Varsayılan —</option>
                {envs.map(e => <option key={e.id} value={e.id}>{e.name} (Python {e.python_version})</option>)}
              </select>
            </label>
            <label>Network Mode
              <select value={runParams.network_mode} onChange={e => setRunParams(p => ({ ...p, network_mode: e.target.value }))}>
                <option value="SNAPSHOT_ONLY">SNAPSHOT_ONLY (Reproducible)</option>
                <option value="EXPLORATORY_NETWORK">EXPLORATORY_NETWORK (Non-reproducible)</option>
              </select>
            </label>
            <label>
              Ek Parametreler (JSON)
              <textarea
                rows={4}
                style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
                value={runParams.params_raw}
                onChange={e => setRunParams(p => ({ ...p, params_raw: e.target.value }))}
                placeholder='{"SYMBOL": "EURUSD", "RANDOM_SEED": 42}'
              />
            </label>
            {runParams.network_mode === 'EXPLORATORY_NETWORK' && (
              <div className="alert" style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)' }}>
                <AlertCircle size={14} /> Exploratory mode — sonuçlar reproducible değil.
              </div>
            )}
          </div>
          <div className="nb-dialog-foot">
            <button className="secondary" onClick={() => setRunDlgOpen(false)}>İptal</button>
            <button className="primary" onClick={submitRun} disabled={busy}>
              {busy ? <Loader2 size={15} className="spin" /> : <Play size={15} />} Çalıştır
            </button>
          </div>
        </div>
      </dialog>
    </div>
  );
}

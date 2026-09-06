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
  AlertCircle, Archive, BookOpen,
  ChevronRight, Clock3, FileCode2, Folder, Key, Loader2,
  Package, Play, Plus, RefreshCw, Square, Trash2, Pencil, ArrowUp, ArrowDown,
  LayoutGrid, List,
  GitCompare, RotateCcw,
  Search, Upload, X
} from 'lucide-react';
import { request, headers } from './platform-api';
import type { Event } from './platform-api';
import { useWorkspace } from './workspace';
import { useLang } from './i18n';
import './app/styles/notebook.css';

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
  executed_notebook_path?: string | null;
  artifacts?: Artifact[];
}
interface Artifact { name: string; size_bytes: number; sha256: string; content_type: string; path: string; }
interface Inspection {
  compatible: boolean; python_version: string; parameter_cell_found: boolean;
  imports: string[]; issues: { severity: string; code: string; detail: string }[];
  cells_inspected: number; analysis?: StaticAnalysis;
}
interface StaticAnalysis { datasets: string[]; features: string[]; models: string[]; validation: string[]; backtest: string[]; warnings: { severity: string; code: string; detail: string }[]; }
interface WorkspaceSecret { id: string; key_name: string; description: string; created_at: string; updated_at: string; }
interface Experiment { id: string; code: string; name: string; status: string; }
interface Snapshot { id: string; sha256: string; details: { name?: string; rows?: number }; created_at: string; }
interface NotebookOutput { output_type: string; execution_count?: number | null; text?: string; html?: string; json?: unknown; image?: { mime: string; base64: string }; ename?: string; evalue?: string; traceback?: string[]; }
interface NotebookCell { cell_id: string; index: number; cell_type: 'code' | 'markdown' | 'raw'; classification: string; execution_count: number | null; source: string; outputs: NotebookOutput[]; tags: string[]; }
interface NotebookContent { notebook_id: string; notebook_code: string; version: number; cells: NotebookCell[]; outline: { cell_index: number; level: number; title: string }[]; statistics: { total_cells: number; code: number; markdown: number; raw: number; outputs: number }; }
interface VersionDiff { from_version: number; to_version: number; added_cells: string[]; removed_cells: string[]; changed_cells: string[]; }

const NB_TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'POLICY_REJECTED']);

function statusColor(s: string) {
  if (s === 'COMPLETED') return 'var(--green)';
  if (s === 'RUNNING' || s === 'PREPARING') return 'var(--color-sky)';
  if (s === 'QUEUED') return 'var(--color-amber)';
  if (s === 'FAILED' || s === 'TIMEOUT') return 'var(--color-rose)';
  if (s === 'CANCELLED') return 'var(--muted)';
  return 'var(--muted)';
}

function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

function fmtDuration(s: number | null) {
  if (s == null) return '—';
  const m = Math.floor(s / 60), sec = Math.round(s % 60);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function NotebookLab({ onExperimentCreated }: { onExperimentCreated?: () => void }) {
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
  const [issues, setIssues] = useState<Inspection['issues']>([]);
  const [notebookContent, setNotebookContent] = useState<NotebookContent | null>(null);
  const [notebookAnalysis, setNotebookAnalysis] = useState<StaticAnalysis | null>(null);
  const [editorMode, setEditorMode] = useState(false);
  const [versionDiff, setVersionDiff] = useState<VersionDiff | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [detailTab, setDetailTab] = useState('overview');
  const [notebookListMode, setNotebookListMode] = useState<'grid' | 'list'>('grid');
  const [notebookSearch, setNotebookSearch] = useState('');
  const [notebookStatus, setNotebookStatus] = useState<'all' | 'ACTIVE' | 'ARCHIVED'>('all');
  const [notebookDataFilter, setNotebookDataFilter] = useState('all');
  const [runLogs, setRunLogs] = useState<Event[]>([]);
  const [liveRunId, setLiveRunId] = useState<string | null>(null);
  const [currentCellIndex, setCurrentCellIndex] = useState<number | null>(null);

  // Run dialog state
  const [runDlgOpen, setRunDlgOpen] = useState(false);
  const [runParams, setRunParams] = useState({ experiment_id: '', dataset_snapshot_id: '', environment_id: '', network_mode: 'SNAPSHOT_ONLY', execution_mode: 'all', start_index: 0, params_raw: '{}' });

  // Secret dialog state
  const [secretDlg, setSecretDlg] = useState(false);
  const [secretForm, setSecretForm] = useState({ key: '', value: '', description: '' });

  const uploadRef = useRef<HTMLInputElement>(null);
  const runDlgRef = useRef<HTMLDialogElement>(null);

  // ── Data loading ──────────────────────────────────────────────────────────

  async function loadAll() {
    if (!wsId) return;
    setError('');
    try {
      setNotebooks(await request<Notebook[]>(`/workspaces/${wsId}/notebooks?include_archived=true`));
    } catch (e) { setError(String(e)); }
    try {
      setExperiments(await request<Experiment[]>(`/experiments?workspace_id=${wsId}`));
    } catch (e) { setError(String(e)); }
    try {
      setSnapshots(await request<Snapshot[]>(`/workspaces/${wsId}/snapshots`));
    } catch (e) { setError(String(e)); }
    try {
      setEnvs(await request<NbEnvironment[]>('/notebook-environments'));
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

  useEffect(() => { setSelectedNb(null); setNotebookContent(null); setNotebookAnalysis(null); setSelectedRun(null); setLiveRunId(null); setRuns([]); setSnapshots([]); setNotebooks([]); setIssues([]); setView('list'); setRunDlgOpen(false); setEditorMode(false); setVersionDiff(null); setRunParams({ experiment_id: '', dataset_snapshot_id: '', environment_id: '', network_mode: 'SNAPSHOT_ONLY', execution_mode: 'all', start_index: 0, params_raw: '{}' }); loadAll(); }, [wsId]);

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
        const res = await fetch(`/api/v1/workspaces/${wsId}/notebook-runs/${liveRunId}/events?after=${cursor}`, { headers: Object.fromEntries(Object.entries(headers()).filter(([k]) => k.toLowerCase() !== 'content-type')), signal: ctrl.signal });
        if (!res.ok || !res.body) throw new Error(t('nb.streamFailed'));
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
              if (ev.type === 'notebook.cell.started' && typeof ev.payload.cell_index === 'number') setCurrentCellIndex(ev.payload.cell_index);
            }
            if (block.includes('event: done')) {
              const updated = await request<NbRun>(`/workspaces/${wsId}/notebook-runs/${liveRunId}`);
              setSelectedRun(updated);
              setRuns(prev => prev.map(r => r.id === liveRunId ? updated : r));
              setLiveRunId(null); return;
            }
          }
        }
      } catch (e) { if (!ctrl.signal.aborted) setError(String(e)); }
    }
    listen();
    return () => ctrl.abort();
  }, [liveRunId, wsId]);

  // ── Actions ───────────────────────────────────────────────────────────────

  async function uploadNotebook(file: File, version = false) {
    if (!wsId) return;
    setUploading(true); setError(''); setIssues([]);
    try {
      const form = new FormData();
      form.append('file', file);
      const url = version && selectedNb ? `/api/v1/workspaces/${wsId}/notebooks/${selectedNb.id}/versions` : `/api/v1/workspaces/${wsId}/notebooks?name=${encodeURIComponent(file.name)}`;
      const res = await fetch(url, {
        method: 'POST', headers: Object.fromEntries(Object.entries(headers()).filter(([k]) => k !== 'Content-Type')), body: form,
      });
      if (!res.ok) { const b = await res.json(); throw new Error(b.error?.message || b.detail || t('nb.uiUploadFailed')); }
      const nb = await res.json() as { inspection: Inspection } & Notebook;
      await loadAll();
      setIssues(nb.inspection?.issues || []);
      if (version) await openNotebook(nb);
    } catch (e) { setError(String(e)); }
    finally { setUploading(false); if (uploadRef.current) uploadRef.current.value = ''; }
  }

  async function openNotebook(nb: Notebook) {
    if (!wsId) return;
    try {
      const full = await request<Notebook>(`/workspaces/${wsId}/notebooks/${nb.id}`);
      setSelectedRun(null); setLiveRunId(null); setRunLogs([]); setCurrentCellIndex(null);
      setSelectedNb(full); setNotebookContent(null); setNotebookAnalysis(null); setEditorMode(false); setVersionDiff(null); setDetailTab('notebook'); setView('detail');
      try { setNotebookContent(await request<NotebookContent>(`/workspaces/${wsId}/notebooks/${nb.id}/cells`)); }
      catch (e) { setError(String(e)); }
      try { setNotebookAnalysis((await request<{ analysis?: StaticAnalysis } & StaticAnalysis>(`/workspaces/${wsId}/notebooks/${nb.id}/analysis`)).analysis || null); }
      catch (e) { setError(String(e)); }
      await loadRuns(nb.id);
    } catch (e) { setError(String(e)); }
  }

  function editCell(index: number, patch: Partial<NotebookCell>) {
    setNotebookContent(prev => prev ? { ...prev, cells: prev.cells.map((cell, i) => i === index ? { ...cell, ...patch } : cell) } : prev);
  }

  function moveCell(index: number, direction: -1 | 1) {
    setNotebookContent(prev => {
      if (!prev) return prev;
      const next = [...prev.cells]; const target = index + direction;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return { ...prev, cells: next.map((c, i) => ({ ...c, index: i })) };
    });
  }

  function addCell(afterIndex: number, cellType: 'code' | 'markdown' = 'code') {
    setNotebookContent(prev => {
      if (!prev) return prev;
      const cell: NotebookCell = { cell_id: `new-${Date.now()}`, index: afterIndex + 1, cell_type: cellType, classification: 'OTHER', execution_count: null, source: '', outputs: [], tags: [] };
      const next = [...prev.cells]; next.splice(afterIndex + 1, 0, cell);
      return { ...prev, cells: next.map((c, i) => ({ ...c, index: i })) };
    });
  }

  async function saveEditedNotebook() {
    if (!wsId || !selectedNb || !notebookContent) return;
    setBusy(true); setError('');
    try {
      const saved = await request<Notebook>(`/workspaces/${wsId}/notebooks/${selectedNb.id}/cells/version`, 'POST', { cells: notebookContent.cells, change_summary: 'Notebook editörü ile güncellendi' });
      setSelectedNb(saved); setEditorMode(false); setVersionDiff(null);
      await openNotebook(saved);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function compareVersion(version: number) {
    if (!wsId || !selectedNb || version === selectedNb.version) return;
    try { setVersionDiff(await request<VersionDiff>(`/workspaces/${wsId}/notebooks/${selectedNb.id}/versions/diff?from_version=${version}&to_version=${selectedNb.version}`)); }
    catch (e) { setError(String(e)); }
  }

  async function restoreVersion(version: number) {
    if (!wsId || !selectedNb || !confirm(`v${version} yeni bir versiyon olarak geri yüklensin mi?`)) return;
    try { const restored = await request<Notebook>(`/workspaces/${wsId}/notebooks/${selectedNb.id}/versions/${version}/restore`, 'POST'); await openNotebook(restored); }
    catch (e) { setError(String(e)); }
  }

  async function convertToExperiment() {
    if (!wsId || !selectedNb) return;
    try {
      const preview = await request<{ requires_confirmation: boolean; dataset: string[]; target: string; features: string[]; models: string[]; validation: string[]; backtest: string[]; spec: Record<string, unknown> }>(`/workspaces/${wsId}/notebooks/${selectedNb.id}/convert-to-experiment`, 'POST', { confirm: false });
      const summary = `Notebook → Experiment\n\nDataset: ${preview.dataset.join(', ')}\nTarget: ${preview.target}\nFeatures: ${preview.features.length}\nModels: ${preview.models.join(', ')}\nValidation: ${preview.validation.join(', ') || '—'}\n\nTaslağı oluşturmak istiyor musunuz?`;
      if (!confirm(summary)) return;
      const created = await request<{ code?: string; name?: string }>(`/workspaces/${wsId}/notebooks/${selectedNb.id}/convert-to-experiment`, 'POST', { confirm: true });
      setNotice(`Deney oluşturuldu: ${created.code || created.name || 'başarılı'}`);
      await loadAll();
      onExperimentCreated?.();
    } catch (e) { setError(String(e)); }
  }

  async function archiveNotebook(nb: Notebook) {
    if (!wsId || !confirm(t('nb.archiveConfirm').replace('{name}', nb.name))) return;
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
      try { params = JSON.parse(runParams.params_raw); if (!params || Array.isArray(params) || typeof params !== 'object') throw new Error(); } catch { setError(t('nb.uiParametersMustBeAValidJsonObject')); setBusy(false); return; }
      const body = {
        notebook_id: selectedNb.id,
        experiment_id: runParams.experiment_id || null,
        dataset_snapshot_id: runParams.dataset_snapshot_id || null,
        environment_id: runParams.environment_id || null,
        parameters: params,
        network_mode: runParams.network_mode,
        execution_mode: runParams.execution_mode,
        start_index: runParams.start_index,
      };
      const run = await request<NbRun>(`/workspaces/${wsId}/notebook-runs`, 'POST', body);
      setRunDlgOpen(false);
      setRuns(prev => [run, ...prev]);
      setSelectedRun(run);
      setRunLogs([]);
      setCurrentCellIndex(null);
      setLiveRunId(run.id);
      setDetailTab('runs');
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  function openRunDialog(mode: string = 'all', startIndex = 0) {
    setRunParams(p => ({ ...p, execution_mode: mode, start_index: startIndex }));
    setRunDlgOpen(true);
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
      setSelectedRun(full); setRunLogs([]); setCurrentCellIndex(null);
      setLiveRunId(NB_TERMINAL.has(full.status) ? null : full.id);
    } catch (e) { setError(String(e)); }
  }

  async function downloadArtifact(run: NbRun, name: string) {
    if (!wsId) return;
    try {
      const res = await fetch(`/api/v1/workspaces/${wsId}/notebook-runs/${run.id}/artifacts/${name.split('/').map(encodeURIComponent).join('/')}`, {
        headers: Object.fromEntries(Object.entries(headers()).filter(([k]) => k.toLowerCase() !== 'content-type')),
      });
      if (!res.ok) throw new Error(t('nb.downloadFailed'));
      const url = URL.createObjectURL(await res.blob());
      const link = document.createElement('a'); link.href = url; link.download = name.split('/').pop() || name;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
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
    if (!wsId || !confirm(t('nb.deleteConfirm').replace('{name}', key))) return;
    try { await request(`/workspaces/${wsId}/secrets/${encodeURIComponent(key)}`, 'DELETE'); await loadSecrets(); }
    catch (e) { setError(String(e)); }
  }

  const notebookTags = Array.from(new Set(notebooks.flatMap(nb => nb.tags || []))).sort((a, b) => a.localeCompare(b));
  const searchTerm = notebookSearch.trim().toLocaleLowerCase('tr-TR');
  const filteredNotebooks = notebooks.filter(nb => {
    const matchesStatus = notebookStatus === 'all' || nb.status === notebookStatus;
    const matchesData = notebookDataFilter === 'all' || (nb.tags || []).includes(notebookDataFilter);
    const haystack = [nb.name, nb.notebook_code, nb.source_filename, nb.description, ...(nb.tags || [])].join(' ').toLocaleLowerCase('tr-TR');
    return matchesStatus && matchesData && (!searchTerm || haystack.includes(searchTerm));
  });

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="nb-lab">
      {/* Header */}
      <div className="nb-header">
        <div className="nb-header-left">
          {view !== 'list' && (
            <button className="text-button" onClick={() => { setView('list'); setSelectedNb(null); setSelectedRun(null); setLiveRunId(null); }}>
              <ChevronRight size={14} style={{ transform: 'rotate(180deg)' }} /> {t('nb.uiBack')}
            </button>
          )}
          <h2 className="nb-title">
            <BookOpen size={20} />
            {view === 'list' ? t('nb.uiNotebookLab') : view === 'secrets' ? t('nb.uiWorkspaceSecrets') : selectedNb?.name || t('nb.uiNotebookLab')}
          </h2>
          {view === 'list' && <span className="badge">{notebooks.length} {t('nb.notebooks')}</span>}
        </div>
        <div className="nb-header-right">
          {view === 'list' && (
            <>
              <button className="secondary" onClick={() => { setView('secrets'); loadSecrets(); }}>
                <Key size={15} /> {t('nb.uiSecrets')}
              </button>
              <button className="secondary" onClick={loadAll} title={t('nb.uiRefresh')}>
                <RefreshCw size={15} />
              </button>
              <label className="primary" style={{ cursor: 'pointer' }}>
                {uploading ? <><Loader2 size={15} className="spin" /> {t('nb.uiUploading')}</> : <><Upload size={15} /> {t('nb.uiUploadNotebook')}</>}
                <input ref={uploadRef} type="file" accept=".ipynb" hidden onChange={e => { const f = e.target.files?.[0]; if (f) uploadNotebook(f); }} />
              </label>
            </>
          )}
          {view === 'detail' && selectedNb && (
            <button className="primary" onClick={() => openRunDialog('all')}>
              <Play size={15} /> {t('nb.uiRun')}
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
      {notice && <div className="nb-success" role="status"><span>{notice}</span><button onClick={() => setNotice('')}><X size={14} /></button></div>}

      {issues.map((issue, index) => (
        <div key={index} className={`nb-inspection ${issue.severity === 'critical' ? 'critical' : 'warning'}`} role="status">
          <AlertCircle size={15} /><strong>{issue.code}</strong><span>{issue.detail}</span>
        </div>
      ))}

      {/* Secrets view */}
      {view === 'secrets' && (
        <div className="nb-secrets">
          <div className="nb-section-header">
            <h3>{t('nb.uiWorkspaceSecrets')}</h3>
            <button className="primary" onClick={() => setSecretDlg(true)}><Plus size={15} /> {t('nb.uiAdd')}</button>
          </div>
          <p className="nb-desc">{t('nb.secretHelp')} <code>os.environ["KEY"]</code>.</p>
          {secrets.length === 0 ? (
            <div className="nb-empty"><Key size={32} /><p>{t('nb.uiNoSecretsYet')}</p></div>
          ) : (
            <table className="nb-table">
              <thead><tr><th>{t('nb.uiKey')}</th><th>{t('nb.uiDescription')}</th><th>{t('nb.uiUpdated')}</th><th /></tr></thead>
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
                  <h3><Key size={16} /> {t('nb.uiAddSecret')}</h3>
                  <button className="icon-button" onClick={() => setSecretDlg(false)}><X size={18} /></button>
                </div>
                <label>{t('nb.uiKeyNameUppercase')}<input value={secretForm.key} onChange={e => setSecretForm(p => ({ ...p, key: e.target.value.toUpperCase() }))} placeholder="FRED_API_KEY" /></label>
                <label>{t('nb.uiValue')}<input type="password" value={secretForm.value} onChange={e => setSecretForm(p => ({ ...p, value: e.target.value }))} /></label>
                <label>{t('nb.uiDescription')}<input value={secretForm.description} onChange={e => setSecretForm(p => ({ ...p, description: e.target.value }))} /></label>
                <button className="primary" onClick={saveSecret}>{t('nb.uiSave')}</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Notebook list */}
      {view === 'list' && (
        <div className="nb-list-view">
          <div className="nb-search-bar">
            <select value={notebookStatus} onChange={e => setNotebookStatus(e.target.value as typeof notebookStatus)} aria-label="Durum filtresi">
              <option value="all">Durum: Tümü</option><option value="ACTIVE">Durum: Aktif</option><option value="ARCHIVED">Durum: Arşivlenmiş</option>
            </select>
            <select value={notebookDataFilter} onChange={e => setNotebookDataFilter(e.target.value)} aria-label="Veri veya etiket filtresi">
              <option value="all">Veri: Tümü</option>{notebookTags.map(tag => <option key={tag} value={tag}>Etiket: {tag}</option>)}
            </select>
            <div className="nb-search-field"><Search size={17} /><input value={notebookSearch} onChange={e => setNotebookSearch(e.target.value)} placeholder="Notebook, dosya veya etiket ara" aria-label="Notebook ara" /></div>
          </div>
          <div className="nb-list-toolbar">
            <div><b>Notebooklar</b><small>{filteredNotebooks.length} / {notebooks.length} sonuç</small></div>
            <div className="nb-view-toggle" role="group" aria-label="Notebook görünümü">
              <button className={notebookListMode === 'grid' ? 'active' : ''} onClick={() => setNotebookListMode('grid')} title="Grid görünümü"><LayoutGrid size={15} /> Grid</button>
              <button className={notebookListMode === 'list' ? 'active' : ''} onClick={() => setNotebookListMode('list')} title="Liste görünümü"><List size={15} /> Liste</button>
            </div>
          </div>
          {notebooks.length === 0 ? (
            <div className="nb-empty-state">
              <BookOpen size={48} strokeWidth={1} />
              <h3>{t('nb.uiNotebookLab')}</h3>
              <p>{t('nb.uiRunVersionedParameterizedResearchNotebooksInYourWorkspace')}</p>
              <label className="primary" style={{ cursor: 'pointer', display: 'inline-flex', gap: '0.5rem', alignItems: 'center' }}>
                <Upload size={16} /> {t('nb.uiUploadYourFirstNotebook')}
                <input type="file" accept=".ipynb" hidden onChange={e => { const f = e.target.files?.[0]; if (f) uploadNotebook(f); }} />
              </label>
            </div>
          ) : filteredNotebooks.length === 0 ? (
            <div className="nb-filter-empty"><Search size={28} /><p>Filtrelerle eşleşen notebook bulunamadı.</p><button className="secondary" onClick={() => { setNotebookSearch(''); setNotebookStatus('all'); setNotebookDataFilter('all'); }}>Filtreleri temizle</button></div>
          ) : (
            notebookListMode === 'grid' ? <div className="nb-grid">
              {filteredNotebooks.map(nb => (
                <div key={nb.id} className="nb-card" onClick={() => openNotebook(nb)}>
                  <div className="nb-card-top">
                    <FileCode2 size={20} />
                    <span className={`badge ${nb.status === 'ARCHIVED' ? 'muted' : ''}`}>{nb.status === 'ARCHIVED' ? t('nb.uiArchived') : `v${nb.version}`}</span>
                  </div>
                  <h3>{nb.name}</h3>
                  <p>{nb.description || nb.source_filename}</p>
                  <div className="nb-card-footer">
                    <small>{nb.notebook_code}</small>
                    <small>{nb.updated_at.slice(0, 10)}</small>
                  </div>
                </div>
              ))}
            </div> : <div className="nb-notebook-list-table"><table className="nb-table"><thead><tr><th>Notebook</th><th>Versiyon</th><th>Durum</th><th>Güncellendi</th><th /></tr></thead><tbody>{filteredNotebooks.map(nb => <tr key={nb.id} onClick={() => openNotebook(nb)}><td><b>{nb.name}</b><small>{nb.notebook_code} · {nb.source_filename}</small></td><td>v{nb.version}</td><td>{nb.status}</td><td>{nb.updated_at.slice(0, 10)}</td><td><ChevronRight size={14} /></td></tr>)}</tbody></table></div>
          )}
        </div>
      )}

      {/* Notebook detail */}
      {view === 'detail' && selectedNb && (
        <div className="nb-detail">
          {/* Tabs */}
          <div className="nb-tabs">
            {['notebook', 'overview', 'runs', 'versions', 'artifacts'].map(tab => (
              <button key={tab} className={`nb-tab ${detailTab === tab ? 'active' : ''}`} onClick={() => setDetailTab(tab)}>
                {tab === 'notebook' ? 'Notebook' : tab === 'overview' ? t('nb.uiOverview') : tab === 'runs' ? t('nb.uiRuns') : tab === 'versions' ? t('nb.uiVersions') : t('nb.uiArtifacts')}
              </button>
            ))}
          </div>

          {/* Notebook viewer/editor */}
          {detailTab === 'notebook' && (
            <div className="nb-viewer-layout">
              <aside className="nb-outline">
                <div className="nb-viewer-label">OUTLINE</div>
                <div className="nb-mode-switch">
                  <button className={!editorMode ? 'active' : ''} onClick={() => setEditorMode(false)}>Görüntüle</button>
                  <button className={editorMode ? 'active' : ''} onClick={() => setEditorMode(true)}><Pencil size={12} /> Düzenle</button>
                </div>
                {!notebookContent ? <small>Yükleniyor…</small> : notebookContent.outline.length === 0 ? <small>Markdown başlığı bulunamadı.</small> : notebookContent.outline.map(item => (
                  <button key={`${item.cell_index}-${item.title}`} style={{ paddingLeft: `${8 + item.level * 8}px` }} onClick={() => document.getElementById(`nb-cell-${item.cell_index}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{item.title}</button>
                ))}
              </aside>
              <div className="nb-cells">
                {notebookContent && <div className="nb-viewer-stats"><span>{notebookContent.statistics.total_cells} hücre</span><span>{notebookContent.statistics.code} code</span><span>{notebookContent.statistics.markdown} markdown</span><span>{notebookContent.statistics.outputs} output</span></div>}
                {!notebookContent ? <div className="nb-empty"><Loader2 size={24} className="spin" /><p>Notebook içeriği yükleniyor…</p></div> : notebookContent.cells.map((cell, cellIndex) => (
                  <article className="nb-cell" id={`nb-cell-${cell.index}`} key={cell.cell_id}>
                    <div className="nb-cell-head"><span>HÜCRE {cell.index + 1}</span><b>{cell.cell_type.toUpperCase()}</b><em>{cell.classification}</em>{cell.execution_count != null && <small>[{cell.execution_count}]</small>}<button className="nb-cell-run" title="Bu hücreyi çalıştır" onClick={() => openRunDialog('cell', cell.index)}><Play size={12} /></button>
                      {editorMode && <span className="nb-cell-actions"><button title="Yukarı taşı" onClick={() => moveCell(cellIndex, -1)}><ArrowUp size={13} /></button><button title="Aşağı taşı" onClick={() => moveCell(cellIndex, 1)}><ArrowDown size={13} /></button><button title="Sil" onClick={() => setNotebookContent(prev => prev ? { ...prev, cells: prev.cells.filter((_, i) => i !== cellIndex).map((c, i) => ({ ...c, index: i })) } : prev)}><Trash2 size={13} /></button></span>}
                    </div>
                    {editorMode ? <><select className="nb-cell-type" value={cell.cell_type} onChange={e => editCell(cellIndex, { cell_type: e.target.value as NotebookCell['cell_type'] })}><option value="code">code</option><option value="markdown">markdown</option><option value="raw">raw</option></select><textarea className="nb-editor-textarea" value={cell.source} onChange={e => editCell(cellIndex, { source: e.target.value })} /></> : cell.cell_type === 'markdown' ? <pre className="nb-markdown">{cell.source}</pre> : <pre className="nb-code">{cell.source || ' '}</pre>}
                    {cell.outputs.map((output, index) => <div className="nb-output" key={`${cell.cell_id}-output-${index}`}>
                      <div className="nb-output-label">OUTPUT {index + 1}{output.output_type === 'error' ? ' · ERROR' : ''}</div>
                      {output.image && <img src={`data:${output.image.mime};base64,${output.image.base64}`} alt="Notebook output" className="nb-output-image" />}
                      {output.html && <div className="nb-output-html" dangerouslySetInnerHTML={{ __html: output.html }} />}
                      {output.text && <pre className="nb-output-text">{output.text}</pre>}
                      {output.json != null && <pre className="nb-output-text">{JSON.stringify(output.json, null, 2)}</pre>}
                      {output.output_type === 'error' && <><b className="nb-output-error">{output.ename}: {output.evalue}</b><pre className="nb-output-text">{(output.traceback || []).join('\n')}</pre></>}
                    </div>)}
                    {editorMode && <button className="text-button nb-add-cell" onClick={() => addCell(cellIndex)}><Plus size={13} /> Hücre ekle</button>}
                  </article>
                ))}
              </div>
              <aside className="nb-analysis-mini">
                <div className="nb-viewer-label">ANALYSIS</div>
                {notebookContent ? <><b>{notebookContent.statistics.total_cells}</b><small>Total cells</small><b>{notebookContent.statistics.code}</b><small>Code cells</small><b>{notebookContent.statistics.outputs}</b><small>Outputs</small>{notebookAnalysis && <div className="nb-analysis-block"><small>Models</small><span>{notebookAnalysis.models.length ? notebookAnalysis.models.join(', ') : '—'}</span><small>Validation</small><span>{notebookAnalysis.validation.length ? notebookAnalysis.validation.join(', ') : '—'}</span><small>Features</small><span>{notebookAnalysis.features.length || '—'}</span><small>Warnings</small><span className={notebookAnalysis.warnings.length ? 'nb-analysis-warning' : ''}>{notebookAnalysis.warnings.length}</span></div>}{editorMode && <button className="primary nb-save-editor" onClick={saveEditedNotebook} disabled={busy}><Pencil size={13} /> {busy ? 'Kaydediliyor…' : 'Yeni versiyon olarak kaydet'}</button>}</> : <small>—</small>}
              </aside>
            </div>
          )}

          {/* Overview tab */}
          {detailTab === 'overview' && (
            <div className="nb-overview">
              <div className="nb-meta-grid">
                <div className="nb-meta-item"><small>{t('nb.uiCode')}</small><b>{selectedNb.notebook_code}</b></div>
                <div className="nb-meta-item"><small>{t('nb.uiVersion')}</small><b>v{selectedNb.version}</b></div>
                <div className="nb-meta-item"><small>{t('nb.uiFile')}</small><b>{selectedNb.source_filename}</b></div>
                <div className="nb-meta-item"><small>{t('nb.uiStatus')}</small><b>{selectedNb.status}</b></div>
                <div className="nb-meta-item"><small>{t('nb.uiCreated')}</small><b>{selectedNb.created_at.slice(0, 16).replace('T', ' ')}</b></div>
                <div className="nb-meta-item"><small>{t('nb.uiUpdated')}</small><b>{selectedNb.updated_at.slice(0, 16).replace('T', ' ')}</b></div>
              </div>
              {selectedNb.description && <p className="nb-desc">{selectedNb.description}</p>}
              <div className="nb-actions-row">
                <label className="secondary">
                  <Upload size={15} /> {t('nb.newVersion')}
                  <input type="file" accept=".ipynb" hidden disabled={uploading} onChange={e => { const f = e.target.files?.[0]; if (f) uploadNotebook(f, true); e.target.value = ''; }} />
                </label>
                <button className="primary" onClick={() => openRunDialog('all')}><Play size={15} /> {t('nb.uiRun')}</button>
                <button className="secondary" onClick={convertToExperiment}><GitCompare size={15} /> Deneye dönüştür</button>
                <button className="secondary" onClick={() => archiveNotebook(selectedNb)}>
                  <Archive size={15} /> {t('nb.uiArchive')}
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
                    {currentCellIndex != null && <small>Hücre {currentCellIndex + 1}{notebookContent ? ` / ${notebookContent.statistics.total_cells}` : ''}</small>}
                    <button className="text-button" onClick={() => cancelRun(selectedRun.id)}>
                      <Square size={13} /> {t('nb.uiCancel')}
                    </button>
                  </div>
                  <div className="nb-log-stream">
                    {runLogs.slice(-20).map(ev => (
                      <div key={ev.id} className="nb-log-line">
                        <code>{ev.type} {JSON.stringify(ev.payload)}</code>
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
                    <div className="alert"><AlertCircle size={13} />{selectedRun.error_message}{currentCellIndex != null && <button className="text-button" onClick={() => document.getElementById(`nb-cell-${currentCellIndex}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>Hücreye git</button>}</div>
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
                      <h4><Folder size={15} /> {t('nb.uiArtifacts')} ({selectedRun.artifacts.length})</h4>
                      <div className="nb-artifact-list">
                        {selectedRun.artifacts.map(a => (
                          <div key={a.name} className="nb-artifact-item">
                            <Package size={13} />
                            <span>{a.name}</span>
                            <small>{fmtBytes(a.size_bytes)}</small>
                            <button className="text-button" onClick={() => downloadArtifact(selectedRun, a.name)}>{t('nb.download')}</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Run history table */}
              <div className="nb-section-header" style={{ marginTop: '1.5rem' }}>
                <h4>{t('nb.uiAllRuns')}</h4>
                <button className="text-button" onClick={() => loadRuns(selectedNb.id)}><RefreshCw size={13} /></button>
              </div>
              {runs.length === 0 ? (
                <div className="nb-empty"><Clock3 size={28} /><p>{t('nb.uiNoRunsYet')}</p></div>
              ) : (
                <table className="nb-table">
                  <thead>
                    <tr><th>{t('nb.uiCode')}</th><th>{t('nb.uiStatus')}</th><th>{t('nb.uiDuration')}</th><th>{t('nb.uiArtifacts')}</th><th>{t('nb.uiDate')}</th><th /></tr>
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
                  <div className="nb-version-actions">
                    {v.version !== selectedNb.version && <><button className="text-button" onClick={() => compareVersion(v.version)}><GitCompare size={13} /> Karşılaştır</button><button className="text-button" onClick={() => restoreVersion(v.version)}><RotateCcw size={13} /> Geri dön</button></>}
                  </div>
                </div>
              ))}
              {versionDiff && <div className="nb-diff-box"><b>v{versionDiff.from_version} → v{versionDiff.to_version}</b><span>Eklenen: {versionDiff.added_cells.length}</span><span>Silinen: {versionDiff.removed_cells.length}</span><span>Değişen: {versionDiff.changed_cells.length}</span></div>}
            </div>
          )}

          {/* Artifacts across run history */}
          {detailTab === 'artifacts' && (
            <div>
              <label>{t('nb.selectRun')}
                <select value={selectedRun?.id || ''} onChange={e => { const run = runs.find(r => r.id === e.target.value); if (run) openRun(run); else setSelectedRun(null); }}>
                  <option value="">{t('nb.selectRun')}</option>
                  {runs.map(run => <option key={run.id} value={run.id}>{run.run_code} — {run.status} ({run.artifact_count})</option>)}
                </select>
              </label>
              {selectedRun?.executed_notebook_path && <button className="secondary" onClick={() => downloadArtifact(selectedRun, 'executed.ipynb')}>{t('nb.executed')}</button>}
              {selectedRun?.artifacts?.length ? (
                <div className="nb-artifact-list">
                  {selectedRun.artifacts.map(a => (
                    <div key={a.name} className="nb-artifact-item">
                      <Package size={14} />
                      <span>{a.name}</span>
                      <small>{fmtBytes(a.size_bytes)}</small>
                            <button className="text-button" onClick={() => downloadArtifact(selectedRun, a.name)}>{t('nb.download')}</button>
                      <span style={{ opacity: 0.5, fontSize: '0.75rem' }}>{a.content_type}</span>
                    </div>
                  ))}
                </div>
              ) : <div className="nb-empty"><Folder size={32} /><p>{t('nb.uiNoArtifactsFound')}</p></div>}
            </div>
          )}
        </div>
      )}

      {/* Run dialog */}
      <dialog ref={runDlgRef} onCancel={() => setRunDlgOpen(false)} onClick={e => { if (e.target === runDlgRef.current) setRunDlgOpen(false); }}>
        <div className="nb-dialog">
          <div className="nb-dialog-head">
            <h3><Play size={16} /> {t('nb.uiRunNotebook')}</h3>
            <button className="icon-button" onClick={() => setRunDlgOpen(false)}><X size={18} /></button>
          </div>
          <div className="nb-dialog-body">
            {error && <div className="alert" role="alert">{error}</div>}
            <label>{t('nb.uiExperimentOptional')}
              <select value={runParams.experiment_id} onChange={e => setRunParams(p => ({ ...p, experiment_id: e.target.value }))}>
                <option value="">{t('nb.uiNone')}</option>
                {experiments.map(e => <option key={e.id} value={e.id}>{e.code} — {e.name}</option>)}
              </select>
              {experiments.length === 0 && (
                <small style={{ opacity: 0.65 }}>{t('nb.uiNoExperimentsInWorkspace')} <button type="button" className="text-button" onClick={loadAll}>{t('nb.uiRefresh')}</button></small>
              )}
            </label>
            <label>{t('nb.uiDatasetSnapshotOptional')}
              <select value={runParams.dataset_snapshot_id} onChange={e => setRunParams(p => ({ ...p, dataset_snapshot_id: e.target.value }))}>
                <option value="">{t('nb.uiNoneExploratoryMode')}</option>
                {snapshots.map(s => <option key={s.id} value={s.id}>{s.details.name || s.id} ({s.id.slice(0, 8)}){s.details.rows ? ` — ${s.details.rows}` : ''}</option>)}
              </select>
              {snapshots.length === 0 && (
                <small style={{ opacity: 0.65 }}>{t('nb.uiNoSnapshotsInWorkspace')} <button type="button" className="text-button" onClick={loadAll}>{t('nb.uiRefresh')}</button></small>
              )}
            </label>
            <label>{t('nb.uiEnvironment')}
              <select value={runParams.environment_id} onChange={e => setRunParams(p => ({ ...p, environment_id: e.target.value }))}>
                <option value="">{t('nb.uiDefault')}</option>
                {envs.map(e => <option key={e.id} value={e.id}>{e.name} (Python {e.python_version})</option>)}
              </select>
            </label>
            <label>{t('nb.uiNetworkMode')}
              <select value={runParams.network_mode} onChange={e => setRunParams(p => ({ ...p, network_mode: e.target.value }))}>
                <option value="SNAPSHOT_ONLY">{t('nb.uiSnapshotOnlyReproducible')}</option>
                <option value="EXPLORATORY_NETWORK">{t('nb.uiExploratoryNetworkNonReproducible')}</option>
              </select>
            </label>
            <label>Çalıştırma modu
              <select value={runParams.execution_mode} onChange={e => setRunParams(p => ({ ...p, execution_mode: e.target.value }))}>
                <option value="all">Tümünü çalıştır</option>
                <option value="cell">Seçili hücreyi çalıştır</option>
                <option value="from">Buradan itibaren çalıştır</option>
                <option value="restart">Kernel'i yeniden başlat ve tümünü çalıştır</option>
              </select>
            </label>
            {runParams.execution_mode === 'cell' || runParams.execution_mode === 'from' ? <label>Başlangıç hücresi
              <select value={runParams.start_index} onChange={e => setRunParams(p => ({ ...p, start_index: Number(e.target.value) }))}>
                {(notebookContent?.cells || []).map(cell => <option key={cell.index} value={cell.index}>Hücre {cell.index + 1} — {cell.source.split('\n')[0].slice(0, 60) || cell.cell_type}</option>)}
              </select>
            </label> : null}
            <label>
              {t('nb.uiExtraParametersJson')}
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
                <AlertCircle size={14} /> {t('nb.uiExploratoryModeResultsAreNotReproducible')}
              </div>
            )}
          </div>
          <div className="nb-dialog-foot">
            <button className="secondary" onClick={() => setRunDlgOpen(false)}>{t('nb.uiCancel')}</button>
            <button className="primary" onClick={submitRun} disabled={busy}>
              {busy ? <Loader2 size={15} className="spin" /> : <Play size={15} />} {t('nb.uiRun')}
            </button>
          </div>
        </div>
      </dialog>
    </div>
  );
}

import React, { useState, useEffect, useCallback } from 'react';
import { Activity, CheckCircle2, AlertCircle, Loader2, RefreshCw } from 'lucide-react';

// System Status (DEC-051): shows what the backend reports, nothing hard-coded.
export default function SettingsView() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);

  const check = useCallback(async () => {
    setLoading(true);
    const start = performance.now();
    const get = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    const [health, config, runs] = await Promise.all([get('/api/health'), get('/api/config'), get('/api/runs?limit=1')]);
    setStatus({
      health,
      config,
      totalRuns: runs?.summary?.total_runs ?? null,
      latency: Math.round(performance.now() - start),
      time: new Date().toLocaleTimeString(),
    });
    setLoading(false);
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  const ok = Boolean(status?.health);
  const cfg = status?.config || {};
  const Row = ({ label, value, help }) => (
    <div className="flex items-start justify-between gap-4 py-2.5 border-b border-slate-800 last:border-0">
      <div>
        <div className="text-sm text-slate-300">{label}</div>
        {help && <div className="text-xs text-slate-500">{help}</div>}
      </div>
      <div className="text-sm font-medium text-slate-100 text-right">{value ?? '-'}</div>
    </div>
  );

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
            <Activity className="w-6 h-6 text-cyan-500" />
            <span>System Status</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">Whether the backend is running, and the settings it is using.</p>
        </div>
        <button
          onClick={check}
          disabled={loading}
          className="px-4 py-2 bg-white border border-slate-700 hover:bg-slate-925 text-slate-200 rounded-md text-sm font-semibold flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Check again
        </button>
      </div>

      {status && (
        <div
          className={`p-4 rounded-lg border text-sm flex items-center gap-3 ${
            ok ? 'bg-emerald-950 border-emerald-800 text-emerald-300' : 'bg-rose-950 border-rose-800 text-rose-300'
          }`}
        >
          {ok ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <div>
            <div className="font-semibold">{ok ? 'Backend is running' : 'Cannot reach the backend'}</div>
            <div className="text-xs opacity-80">
              {ok
                ? `Answered in ${status.latency} ms · checked at ${status.time}`
                : 'Start it with: python -m uvicorn mas.api.main:app --port 8000'}
            </div>
          </div>
        </div>
      )}

      <div className="bg-white border border-slate-800 rounded-lg px-5 py-2">
        <div className="text-xs font-semibold uppercase text-slate-500 pt-3 pb-1">AI model</div>
        <Row label="Benchmark model" help="Set by BENCH_MODEL in .env" value={cfg.bench_model || 'Not set'} />
        <Row label="Provider" help="Host from PROVIDER_BASE_URL in .env" value={cfg.provider_host || 'Not set'} />
        <Row label="API key" help="The key itself is never shown" value={cfg.api_key_configured ? 'Set' : 'Missing'} />
        <Row label="Temperature" help="0 means the same input gives the most repeatable output" value={cfg.temperature} />
        <Row label="Seed" value={cfg.seed} />
      </div>

      <div className="bg-white border border-slate-800 rounded-lg px-5 py-2">
        <div className="text-xs font-semibold uppercase text-slate-500 pt-3 pb-1">Daily API limit</div>
        <Row
          label="Requests used today"
          help={cfg.quota_day ? `Quota day ${cfg.quota_day}; resets at midnight Pacific time` : 'Resets at midnight Pacific time'}
          value={cfg.requests_used_today != null ? `${cfg.requests_used_today} of ${cfg.daily_request_cap}` : null}
        />
        <Row label="Requests left today" value={cfg.requests_left_today} />
      </div>

      <div className="bg-white border border-slate-800 rounded-lg px-5 py-2">
        <div className="text-xs font-semibold uppercase text-slate-500 pt-3 pb-1">Storage</div>
        <Row label="Database" help="Runs, agent steps and scores" value={cfg.database} />
        <Row label="Runs saved" value={status?.totalRuns} />
        <Row label="Generated code" help="One folder per run" value="workspace/ and eval/workspaces/" />
        <Row label="Final reports" value="reports/" />
      </div>
    </div>
  );
}

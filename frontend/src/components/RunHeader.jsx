import React from 'react';
import { AlertTriangle, CheckCircle, ShieldAlert, Cpu, Hash, Database, Box } from 'lucide-react';

export default function RunHeader({ runData }) {
  if (!runData) return null;

  const isSimulated = runData.execution_mode === 'SIMULATED' || runData.model === 'fake' || (runData.token_provenance === 'SIMULATED');
  const isFailed = runData.status === 'FAILED' || runData.execution_mode === 'FAILED';

  return (
    <header className="bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-lg mb-6">
      {/* Top Banner for Provenance */}
      <div className="mb-4">
        {isSimulated ? (
          <div className="bg-amber-950/80 border border-amber-600/80 text-amber-200 px-4 py-2.5 rounded-lg flex items-center justify-between text-xs font-semibold shadow-inner">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0 animate-pulse" />
              <span className="tracking-wide uppercase font-bold text-amber-300">
                SIMULATED — NOT RESEARCH EVIDENCE
              </span>
            </div>
            <span className="text-[11px] font-mono text-amber-400/90 hidden sm:inline">
              Deterministic Mock / Offline Mode
            </span>
          </div>
        ) : (runData.model?.includes(':free') || runData.benchmark === 'FREE_MODEL_EXPLORATORY') ? (
          <div className="bg-cyan-950/80 border border-cyan-600/80 text-cyan-200 px-4 py-2.5 rounded-lg flex items-center justify-between text-xs font-semibold shadow-inner">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-cyan-400 flex-shrink-0" />
              <span className="tracking-wide uppercase font-bold text-cyan-300">
                FREE MODEL EXPLORATORY — NOT GPT-4o BASELINE EVIDENCE
              </span>
            </div>
            <span className="text-[11px] font-mono text-cyan-400/90 hidden sm:inline">
              Exploratory Condition · Model: {runData.actual_model || runData.model}
            </span>
          </div>
        ) : (
          <div className="bg-emerald-950/80 border border-emerald-600/80 text-emerald-200 px-4 py-2.5 rounded-lg flex items-center justify-between text-xs font-semibold shadow-inner">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span className="tracking-wide uppercase font-bold text-emerald-300">
                LIVE API — EMPIRICAL RESEARCH EVIDENCE (GPT-4o)
              </span>
            </div>
            <span className="text-[11px] font-mono text-emerald-400/90 hidden sm:inline">
              Verified Model Execution
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase font-mono tracking-wider text-indigo-400 bg-indigo-950/60 px-2.5 py-0.5 rounded border border-indigo-800/40">
              Execution Provenance
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
              Mode: {runData.execution_mode || (isSimulated ? 'SIMULATED' : 'LIVE_API')}
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
              Provenance: {runData.token_provenance || 'UNAVAILABLE'}
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white mt-2">
            Run: <span className="font-mono text-cyan-400">{runData.run_id}</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 flex flex-wrap items-center gap-3">
            <span>Task ID: <strong className="font-mono text-slate-200">{runData.task_id || 'custom'}</strong></span>
            {runData.provider_request_id && (
              <span>Request ID: <strong className="font-mono text-cyan-300">{runData.provider_request_id}</strong></span>
            )}
            {runData.failure_reason && (
              <span className="text-rose-400">Failure: <strong>{runData.failure_reason}</strong></span>
            )}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          <div className="bg-slate-800/90 px-3.5 py-2 rounded-lg border border-slate-700/60 min-w-[90px]">
            <div className="text-[10px] text-slate-400 font-medium uppercase">System</div>
            <div className="text-sm font-semibold text-slate-100 uppercase mt-0.5">{runData.system || 'MAS'}</div>
          </div>
          <div className="bg-slate-800/90 px-3.5 py-2 rounded-lg border border-slate-700/60 min-w-[120px]">
            <div className="text-[10px] text-slate-400 font-medium uppercase">Model (Req / Act)</div>
            <div className="text-xs font-semibold text-emerald-400 font-mono mt-0.5 truncate max-w-[140px]" title={runData.actual_model || runData.model}>
              {runData.actual_model || runData.model || 'gpt-4o'}
            </div>
          </div>
          <div className="bg-slate-800/90 px-3.5 py-2 rounded-lg border border-slate-700/60 min-w-[90px]">
            <div className="text-[10px] text-slate-400 font-medium uppercase">Total Tokens</div>
            <div className="text-sm font-semibold text-amber-400 font-mono mt-0.5">
              {runData.total_tokens ? runData.total_tokens.toLocaleString() : (runData.token_provenance === 'UNAVAILABLE' ? 'N/A' : '0')}
            </div>
          </div>
          <div className="bg-slate-800/90 px-3.5 py-2 rounded-lg border border-slate-700/60 min-w-[90px]">
            <div className="text-[10px] text-slate-400 font-medium uppercase">Est. Cost</div>
            <div className="text-sm font-semibold text-violet-400 font-mono mt-0.5">
              ${(runData.estimated_cost || 0).toFixed(4)}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

import React from 'react';
import { ShieldAlert, CheckCircle } from 'lucide-react';

const SYSTEM_NAMES = { mas: 'MAS', chatdev: 'ChatDev', single: 'Single agent' };

export default function RunHeader({ runData }) {
  if (!runData) return null;

  const isTest = runData.execution_mode === 'SIMULATED' || runData.model === 'fake' || runData.token_provenance === 'SIMULATED';
  const model = runData.actual_model || runData.model || '-';
  const tokens = runData.total_tokens
    ? runData.total_tokens.toLocaleString()
    : runData.token_provenance === 'UNAVAILABLE'
    ? 'N/A'
    : '0';

  return (
    <header className="bg-white border border-slate-800 p-5 rounded-lg mb-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          {isTest ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800">
              <ShieldAlert className="w-3.5 h-3.5" />
              Offline test run: not used in any results
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
              <CheckCircle className="w-3.5 h-3.5" />
              Live run with the real model
            </span>
          )}
          <h1 className="text-xl font-semibold text-slate-100 mt-2 break-all">{runData.run_id}</h1>
          <p className="text-xs text-slate-500 mt-1 flex flex-wrap gap-x-4 gap-y-1">
            <span>
              Task: <span className="text-slate-300">{runData.task_id || 'custom'}</span>
            </span>
            {runData.failure_reason && (
              <span className="text-rose-400">
                Failed: <span className="font-medium">{runData.failure_reason}</span>
              </span>
            )}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {[
            ['System', SYSTEM_NAMES[runData.system] || runData.system || 'MAS'],
            ['Model', model],
            ['Tokens used', tokens],
          ].map(([label, value]) => (
            <div key={label} className="bg-slate-925 px-3 py-2 rounded-md border border-slate-800 min-w-[100px]">
              <div className="text-[11px] text-slate-500">{label}</div>
              <div className="text-sm font-semibold text-slate-100 mt-0.5 truncate max-w-[180px]" title={String(value)}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </header>
  );
}

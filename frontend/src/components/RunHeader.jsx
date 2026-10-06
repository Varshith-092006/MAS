import React from 'react';

export default function RunHeader({ runData }) {
  if (!runData) return null;

  return (
    <header className="bg-slate-900 border-b border-slate-800 p-6 rounded-xl shadow-lg mb-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="text-xs uppercase font-mono tracking-wider text-indigo-400 bg-indigo-950/60 px-2.5 py-1 rounded-md border border-indigo-800/40">
            MAS Execution Dashboard
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-white mt-2">
            Run: <span className="font-mono text-cyan-400">{runData.run_id}</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Task ID: <span className="font-mono text-slate-200">{runData.task_id || 'custom'}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="bg-slate-800/80 px-4 py-2 rounded-lg border border-slate-700/60">
            <div className="text-xs text-slate-400 font-medium">System</div>
            <div className="text-sm font-semibold text-slate-100 uppercase">{runData.system || 'MAS'}</div>
          </div>
          <div className="bg-slate-800/80 px-4 py-2 rounded-lg border border-slate-700/60">
            <div className="text-xs text-slate-400 font-medium">Model</div>
            <div className="text-sm font-semibold text-emerald-400 font-mono">{runData.model || 'gpt-4o'}</div>
          </div>
          <div className="bg-slate-800/80 px-4 py-2 rounded-lg border border-slate-700/60">
            <div className="text-xs text-slate-400 font-medium">Tokens</div>
            <div className="text-sm font-semibold text-amber-400 font-mono">{runData.total_tokens?.toLocaleString() || 0}</div>
          </div>
          <div className="bg-slate-800/80 px-4 py-2 rounded-lg border border-slate-700/60">
            <div className="text-xs text-slate-400 font-medium">Est. Cost</div>
            <div className="text-sm font-semibold text-violet-400 font-mono">${(runData.estimated_cost || 0).toFixed(4)}</div>
          </div>
        </div>
      </div>
    </header>
  );
}

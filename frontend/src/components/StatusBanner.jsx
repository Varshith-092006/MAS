import React from 'react';

export default function StatusBanner({ status, complexity, iteration, stopReason }) {
  const getStatusBadge = () => {
    switch (status) {
      case 'COMPLETED':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'FAILED':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
      case 'RUNNING':
        return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30 animate-pulse';
      case 'CANCELLED':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'MODEL_MISMATCH_DIAGNOSTIC':
      case 'DIAGNOSTIC_RUN':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      default:
        return 'bg-slate-700/50 text-slate-300 border-slate-600';
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-md mb-6 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${getStatusBadge()}`}>
          {status || 'UNKNOWN'}
        </span>
        <div className="text-sm text-slate-300">
          Complexity Route: <span className="font-semibold text-white">{complexity || 'SIMPLE'}</span>
        </div>
        <div className="text-sm text-slate-300">
          Iteration: <span className="font-semibold text-white">{iteration || 1}</span> / 3
        </div>
      </div>

      {stopReason && (
        <div className="text-xs font-mono bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 text-slate-400 max-w-lg truncate">
          Stop Reason: <span className="text-slate-200">{stopReason}</span>
        </div>
      )}
    </div>
  );
}

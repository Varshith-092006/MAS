import React from 'react';

const STATUS = {
  COMPLETED: ['Finished', 'bg-emerald-950 text-emerald-400 border-emerald-800'],
  FAILED: ['Failed', 'bg-rose-950 text-rose-400 border-rose-800'],
  RUNNING: ['Running', 'bg-cyan-950 text-cyan-400 border-cyan-800'],
  CANCELLED: ['Cancelled', 'bg-amber-950 text-amber-400 border-amber-800'],
  SKIPPED: ['Skipped', 'bg-slate-850 text-slate-400 border-slate-700'],
};

export default function StatusBanner({ status, complexity, iteration, stopReason }) {
  const [label, cls] = STATUS[status] || [status || 'Unknown', 'bg-slate-850 text-slate-400 border-slate-700'];
  const route = (complexity || '').toUpperCase() === 'SIMPLE' ? 'Small project (no Architect step)' : complexity ? 'Larger project (with Architect step)' : '-';

  return (
    <div className="bg-white border border-slate-800 px-4 py-3 rounded-lg mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cls}`}>{label}</span>
      {complexity && (
        <span className="text-slate-400">
          Plan: <span className="text-slate-200">{route}</span>
        </span>
      )}
      <span className="text-slate-400">
        Improvement rounds: <span className="text-slate-200">{iteration || 1}</span>
      </span>
      {stopReason && (
        <span className="text-xs text-slate-500 truncate max-w-lg" title={stopReason}>
          Stopped because: <span className="text-slate-300">{stopReason}</span>
        </span>
      )}
    </div>
  );
}

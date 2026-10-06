import React from 'react';

export default function TokenCostChart({ tokens, cost, quality }) {
  const cap = 60000;
  const tokenCount = tokens || 0;
  const pctUsed = Math.min(100, Math.round((tokenCount / cap) * 100));

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg p-5">
      <h2 className="text-base font-semibold text-white mb-3">Token & Cost Budget (60,000 Cap)</h2>

      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>Provider Token Usage</span>
            <span className="font-mono text-slate-200">
              {tokenCount.toLocaleString()} / {cap.toLocaleString()} ({pctUsed}%)
            </span>
          </div>
          <div className="w-full bg-slate-950 rounded-full h-3 border border-slate-800 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                pctUsed > 85 ? 'bg-rose-500' : pctUsed > 60 ? 'bg-amber-500' : 'bg-cyan-500'
              }`}
              style={{ width: `${pctUsed}%` }}
            ></div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2">
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-400">Recorded Provider Cost</div>
            <div className="text-lg font-bold text-violet-400 font-mono">${(cost || 0).toFixed(4)}</div>
            <div className="text-[10px] text-slate-500">From provider usage fields</div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-400">Tokens Remaining to Cap</div>
            <div className="text-lg font-bold text-emerald-400 font-mono">
              {Math.max(0, cap - tokenCount).toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500">Hard stop at 60k</div>
          </div>
        </div>
      </div>
    </div>
  );
}

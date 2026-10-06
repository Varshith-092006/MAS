import React from 'react';

export default function MetricsTable({ metrics, tokens }) {
  const neutral = metrics?.neutral || {};
  const internal = metrics?.internal || {};

  const quality = neutral.quality !== undefined ? neutral.quality : null;
  const tokensCount = tokens || 1;
  const qualityPer1k = quality !== null ? (quality / (tokensCount / 1000)).toFixed(4) : '-';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg p-5">
      <h2 className="text-base font-semibold text-white mb-4 flex items-center justify-between">
        <span>Evaluation Metrics & Diagnostics</span>
        <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded">Scope Isolated</span>
      </h2>

      {/* Neutral Cross-System Primary Table */}
      <div className="mb-6">
        <div className="text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-2">
          Neutral Cross-System Metrics (Direct Comparison)
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-950 p-3 rounded-lg border border-cyan-900/40">
            <div className="text-xs text-slate-400">Quality</div>
            <div className="text-lg font-bold text-cyan-300 font-mono">
              {quality !== null ? quality.toFixed(3) : '-'}
            </div>
            <div className="text-[10px] text-slate-500">Comp × Exec × Cons</div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-cyan-900/40">
            <div className="text-xs text-slate-400">Quality / 1k Tokens</div>
            <div className="text-lg font-bold text-emerald-400 font-mono">{qualityPer1k}</div>
            <div className="text-[10px] text-slate-500">Efficiency Index</div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-400">Completeness</div>
            <div className="text-lg font-semibold text-slate-200 font-mono">
              {neutral.completeness !== undefined ? neutral.completeness.toFixed(2) : '-'}
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-400">Executability</div>
            <div className="text-lg font-semibold text-slate-200 font-mono">
              {neutral.executability !== undefined ? neutral.executability.toFixed(2) : '-'}
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-400">Consistency</div>
            <div className="text-lg font-semibold text-slate-200 font-mono">
              {neutral.consistency !== undefined ? neutral.consistency.toFixed(3) : '-'}
            </div>
            <div className="text-[10px] text-slate-500">MiniLM Embedding</div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-400">Shared Fixed Test</div>
            <div className="text-lg font-semibold text-slate-200 font-mono">
              {neutral.shared_test !== undefined ? neutral.shared_test.toFixed(2) : '-'}
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-400">Ruff Violations</div>
            <div className="text-lg font-semibold text-slate-200 font-mono">
              {neutral.ruff !== undefined ? neutral.ruff : 0}
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-400">Bandit / Radon</div>
            <div className="text-sm font-semibold text-slate-200 font-mono mt-1">
              High: {neutral.bandit || 0} | MI: {neutral.radon || 100}
            </div>
          </div>
        </div>
      </div>

      {/* Internal MAS Diagnostic Diagnostics Table */}
      <div>
        <div className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-2">
          MAS Internal Diagnostics (Internal Scope Only — Excluded from Comparison)
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-950/60 p-3 rounded-lg border border-purple-900/40">
            <div className="text-xs text-slate-400">pytest Pass Rate</div>
            <div className="text-base font-semibold text-purple-300 font-mono">
              {internal.pytest_pass_rate !== undefined ? `${(internal.pytest_pass_rate * 100).toFixed(1)}%` : '-'}
            </div>
          </div>

          <div className="bg-slate-950/60 p-3 rounded-lg border border-purple-900/40">
            <div className="text-xs text-slate-400">pytest Coverage</div>
            <div className="text-base font-semibold text-purple-300 font-mono">
              {internal.coverage !== undefined ? `${internal.coverage.toFixed(1)}%` : '-'}
            </div>
          </div>

          <div className="bg-slate-950/60 p-3 rounded-lg border border-purple-900/40">
            <div className="text-xs text-slate-400">Adaptive Score (S_t)</div>
            <div className="text-base font-semibold text-purple-300 font-mono">
              {internal.adaptive_score !== undefined ? internal.adaptive_score.toFixed(4) : '-'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

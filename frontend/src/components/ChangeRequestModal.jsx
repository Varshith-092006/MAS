import React, { useState } from 'react';
import {
  GitPullRequest,
  Sparkles,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  FileCode,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react';

export default function ChangeRequestModal({ runId, originalRequirement, onClose, onSuccess }) {
  const [newRequirement, setNewRequirement] = useState(
    originalRequirement
      ? `${originalRequirement}\n\nAdditionally, add input validation error handling and comprehensive unit tests for edge cases.`
      : ''
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!newRequirement.trim()) {
      setError('Please provide an updated requirement specification.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/runs/${runId}/change`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_requirement: newRequirement.trim(),
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Failed to apply change request (${res.status})`);
      }

      const data = await res.json();
      setResult(data);
      if (onSuccess) onSuccess(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
              <GitPullRequest className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-50">Change the requirement</h2>
              <span className="text-xs font-mono text-slate-400">Target Run: {runId}</span>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-50 hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {error && (
            <div className="bg-rose-950/70 border border-rose-800 text-rose-300 p-4 rounded-xl text-xs flex items-center gap-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {result ? (
            /* Results View */
            <div className="space-y-4">
              <div className="bg-emerald-950/60 border border-emerald-800/80 p-4 rounded-xl flex items-center justify-between text-xs">
                <div className="flex items-center gap-3 text-emerald-300">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                  <div>
                    <div className="font-bold">Change applied</div>
                    <div className="text-[11px] text-emerald-400 font-mono">The affected code was updated and the project was scored again.</div>
                  </div>
                </div>
                <div className="text-right font-mono">
                  <div className="text-emerald-400 font-bold text-base">
                    Quality: {result.final_quality != null ? result.final_quality.toFixed(3) : '-'}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    Regression: {result.regression_score !== undefined ? `${(result.regression_score * 100).toFixed(0)}%` : '100%'}
                  </div>
                </div>
              </div>

              {/* Impact Breakdown Cards */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-1">
                  <span className="text-slate-500 text-[10px] block">Files changed directly:</span>
                  <div className="font-bold text-indigo-300">
                    {result.seeds && result.seeds.length > 0 ? result.seeds.join(', ') : 'None detected'}
                  </div>
                </div>

                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-1">
                  <span className="text-slate-500 text-[10px] block">Files affected indirectly:</span>
                  <div className="font-bold text-cyan-300">
                    {result.affected_modules && result.affected_modules.length > 0
                      ? result.affected_modules.join(', ')
                      : 'None'}
                  </div>
                </div>
              </div>

              {/* Updated Files List */}
              {result.affected_files && result.affected_files.length > 0 && (
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <FileCode className="w-4 h-4 text-emerald-400" />
                    <span>Updated Code Files ({result.affected_files.length})</span>
                  </div>
                  <div className="space-y-1 font-mono text-xs text-slate-300">
                    {result.affected_files.map((fp, i) => (
                      <div key={i} className="flex items-center gap-2 bg-slate-900/60 p-2 rounded">
                        <span className="text-emerald-400 font-bold">✓</span>
                        <span>{fp}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="pt-2 flex justify-end">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg transition-colors"
                >
                  Close and view the updated run
                </button>
              </div>
            </div>
          ) : (
            /* Input Form */
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-1.5">
                  New or changed requirement
                </label>
                <textarea
                  rows={6}
                  value={newRequirement}
                  onChange={(e) => setNewRequirement(e.target.value)}
                  placeholder="Describe what should change or be added…"
                  className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg p-3 text-xs text-slate-200 font-mono focus:outline-none"
                  required
                />
                <span className="text-[11px] text-slate-500 mt-1 block">
                  MAS works out which files the change affects and updates only those files.
                </span>
              </div>

              <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>Safety checks:</span>
                </div>
                <div>• A copy of the project is saved before the change.</div>
                <div>• The same tests run before and after, so breakages are caught.</div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={loading}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900 text-white text-xs font-bold rounded-lg shadow-md transition-colors flex items-center gap-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Applying change…</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Apply change</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

import React from 'react';

// Scores for one run (DEC-051). Same values as before, plain labels.
export default function MetricsTable({ metrics }) {
  const neutral = metrics?.neutral || {};
  const internal = metrics?.internal || {};
  const f = (v, digits) => (v != null ? Number(v).toFixed(digits) : '-');

  const scores = [
    { name: 'Quality score', value: f(neutral.quality, 3), help: 'Complete × Runs × Matches requirement (0 to 1)', main: true },
    { name: 'Completeness', value: f(neutral.completeness, 2), help: 'Share of functions that are fully written' },
    {
      name: 'Runs without error',
      value: neutral.executability != null ? (neutral.executability >= 1 ? 'Yes' : 'No') : '-',
      help: 'The program starts and exits cleanly',
    },
    { name: 'Matches the requirement', value: f(neutral.consistency, 3), help: 'Text similarity, requirement vs code (0 to 1)' },
  ];

  const internalRows = [
    ['MAS self-check score', f(internal.adaptive_score, 3)],
    ['Own unit tests passed', internal.pytest_pass_rate != null ? `${Math.round(internal.pytest_pass_rate * 100)}%` : '-'],
    ['Shared test', f(neutral.shared_test, 2)],
  ];

  return (
    <div className="bg-white border border-slate-800 rounded-lg p-5 space-y-5">
      <div>
        <h2 className="text-sm font-semibold text-slate-200">Scores</h2>
        <p className="text-xs text-slate-500">Measured by the same scoring code for every system.</p>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {scores.map((s) => (
          <div
            key={s.name}
            className={`p-3 rounded-md border ${s.main ? 'bg-cyan-950 border-cyan-800' : 'bg-slate-925 border-slate-800'}`}
          >
            <div className="text-xs text-slate-500">{s.name}</div>
            <div className={`text-xl font-semibold mt-0.5 ${s.main ? 'text-cyan-400' : 'text-slate-100'}`}>{s.value}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{s.help}</div>
          </div>
        ))}
      </div>
      <div className="border-t border-slate-800 pt-3">
        <div className="text-xs text-slate-500 mb-2">MAS internal checks (used inside the agent loop, not in the comparison)</div>
        <div className="flex flex-wrap gap-x-8 gap-y-1 text-xs">
          {internalRows.map(([k, v]) => (
            <span key={k} className="text-slate-400">
              {k}: <span className="font-medium text-slate-200">{v}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

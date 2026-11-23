import React, { useMemo } from 'react';
import { BarChart3, Info } from 'lucide-react';

const SYSTEMS = [
  { id: 'mas', name: 'MAS', bar: 'bg-cyan-600' },
  { id: 'chatdev', name: 'ChatDev', bar: 'bg-amber-500' },
  { id: 'single', name: 'Single agent', bar: 'bg-slate-500' },
];

// Timings of 0 mean "not recorded" (ChatDev runs store their time only in results.csv).
const avg = (rows, field) => {
  const vals = rows.map((r) => r[field]).filter((v) => v != null && !(field === 'duration_seconds' && v <= 0));
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
};

export default function AnalyticsDashboard({ runs, analyticsData }) {
  // Averages per system over every scored live run. A run that did not finish but was scored
  // (quality 0) still counts, as in the official results.
  const stats = useMemo(() => {
    const out = {};
    for (const s of SYSTEMS) {
      const rows = (runs || []).filter(
        (r) => r.system === s.id && r.quality != null && r.model !== 'fake' && r.execution_mode !== 'SIMULATED'
      );
      out[s.id] = {
        n: rows.length,
        quality: avg(rows, 'quality'),
        completeness: avg(rows, 'completeness'),
        executability: avg(rows, 'executability'),
        consistency: avg(rows, 'consistency'),
        tokens: avg(rows, 'tokens'),
        duration: avg(rows, 'duration_seconds'),
      };
    }
    return out;
  }, [runs]);

  const shown = SYSTEMS.filter((s) => stats[s.id].n > 0);
  const tokenData = analyticsData?.token_analytics;

  const charts = [
    { key: 'quality', title: 'Quality score', help: 'Complete × Runs × Matches requirement. 0 to 1, higher is better.', max: 1, fmt: (v) => v.toFixed(3) },
    { key: 'executability', title: 'Programs that run', help: 'Share of projects that start without an error.', max: 1, fmt: (v) => `${Math.round(v * 100)}%` },
    { key: 'completeness', title: 'Completeness', help: 'Share of functions that are fully written (no empty stubs).', max: 1, fmt: (v) => v.toFixed(2) },
    { key: 'consistency', title: 'Matches the requirement', help: 'Text similarity between the requirement and the code. 0 to 1.', max: 1, fmt: (v) => v.toFixed(3) },
    {
      key: 'tokens',
      title: 'Tokens per run',
      help: 'Model input + output tokens. Lower is cheaper.',
      max: Math.max(1, ...shown.map((s) => stats[s.id].tokens || 0)),
      fmt: (v) => Math.round(v).toLocaleString(),
    },
    {
      key: 'duration',
      title: 'Time per run',
      help: 'Seconds from start to finish.',
      max: Math.max(1, ...shown.map((s) => stats[s.id].duration || 0)),
      fmt: (v) => `${Math.round(v)}s`,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-cyan-500" />
          <span>Scores & Charts</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">Average scores and token use for each system.</p>
      </div>

      <div className="bg-cyan-950 border border-cyan-800 text-slate-300 p-3 rounded-lg text-xs flex gap-2">
        <Info className="w-4 h-4 text-cyan-500 flex-shrink-0 mt-0.5" />
        <span>
          These are the official runs of the final 20-task benchmark (the same runs as <code>reports/benchmark_report.md</code>).
          ChatDev run times were not stored in the database, so they show as "-"; the report has them.
        </span>
      </div>

      <div className="bg-white border border-slate-800 rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-925 text-slate-500 text-xs border-b border-slate-800">
            <tr>
              <th className="text-left py-2.5 px-4 font-semibold">System</th>
              <th className="text-right py-2.5 px-3 font-semibold">Runs</th>
              <th className="text-right py-2.5 px-3 font-semibold">Quality</th>
              <th className="text-right py-2.5 px-3 font-semibold">Programs that run</th>
              <th className="text-right py-2.5 px-3 font-semibold">Completeness</th>
              <th className="text-right py-2.5 px-3 font-semibold">Matches req.</th>
              <th className="text-right py-2.5 px-3 font-semibold">Tokens / run</th>
              <th className="text-right py-2.5 px-4 font-semibold">Time / run</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {shown.length === 0 && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-slate-500">No finished live runs yet.</td>
              </tr>
            )}
            {shown.map((s) => {
              const st = stats[s.id];
              const f = (v, fn) => (v == null ? '-' : fn(v));
              return (
                <tr key={s.id}>
                  <td className="py-2.5 px-4 font-medium text-slate-200">
                    <span className={`inline-block w-2.5 h-2.5 rounded-sm mr-2 ${s.bar}`} />
                    {s.name}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-400">{st.n}</td>
                  <td className="py-2.5 px-3 text-right font-semibold text-slate-100">{f(st.quality, (v) => v.toFixed(3))}</td>
                  <td className="py-2.5 px-3 text-right">{f(st.executability, (v) => `${Math.round(v * 100)}%`)}</td>
                  <td className="py-2.5 px-3 text-right">{f(st.completeness, (v) => v.toFixed(2))}</td>
                  <td className="py-2.5 px-3 text-right">{f(st.consistency, (v) => v.toFixed(3))}</td>
                  <td className="py-2.5 px-3 text-right">{f(st.tokens, (v) => Math.round(v).toLocaleString())}</td>
                  <td className="py-2.5 px-4 text-right">{f(st.duration, (v) => `${Math.round(v)}s`)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {charts.map((c) => (
          <div key={c.key} className="bg-white border border-slate-800 rounded-lg p-4">
            <div className="text-sm font-semibold text-slate-200">{c.title}</div>
            <div className="text-xs text-slate-500 mb-3">{c.help}</div>
            <div className="space-y-2">
              {shown.map((s) => {
                const v = stats[s.id][c.key];
                const pct = v == null ? 0 : Math.min(100, Math.max(0, (v / c.max) * 100));
                return (
                  <div key={s.id} className="flex items-center gap-3 text-xs">
                    <span className="w-24 text-slate-400">{s.name}</span>
                    <div className="flex-1 h-2.5 bg-slate-850 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${s.bar}`} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-16 text-right text-slate-300">{v == null ? '-' : c.fmt(v)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {tokenData && (
        <div className="bg-white border border-slate-800 rounded-lg p-4">
          <div className="text-sm font-semibold text-slate-200">Total token use</div>
          <div className="text-xs text-slate-500 mb-3">As reported by the model provider, across all live runs.</div>
          <div className="grid grid-cols-3 gap-3 text-sm">
            {[
              ['Input tokens', tokenData.input_tokens],
              ['Output tokens', tokenData.output_tokens],
              ['Total tokens', tokenData.total_tokens],
            ].map(([label, value]) => (
              <div key={label} className="bg-slate-925 border border-slate-800 rounded-md p-3">
                <div className="text-xs text-slate-500">{label}</div>
                <div className="text-lg font-semibold text-slate-100">{(value || 0).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

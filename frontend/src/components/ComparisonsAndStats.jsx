import React, { useMemo } from 'react';
import { Scale, Info } from 'lucide-react';

// Compare Systems (DEC-052): computed from the official runs themselves, so the numbers match
// reports/benchmark_report.md. Confidence intervals and significance tests live in eval/stats_report.md.
const SYSTEMS = [
  { id: 'mas', name: 'MAS' },
  { id: 'chatdev', name: 'ChatDev' },
  { id: 'single', name: 'Single agent' },
];

const METRICS = [
  { key: 'quality', name: 'Quality score', help: 'Complete × Runs × Matches requirement', fmt: (v) => v.toFixed(3) },
  { key: 'executability', name: 'Programs that run', help: 'Share that start without an error', fmt: (v) => `${Math.round(v * 100)}%` },
  { key: 'completeness', name: 'Completeness', help: 'Share of functions fully written', fmt: (v) => v.toFixed(3) },
  { key: 'consistency', name: 'Matches the requirement', help: 'Text similarity, requirement vs code', fmt: (v) => v.toFixed(3) },
  { key: 'tokens', name: 'Tokens per run', help: 'Lower is cheaper', fmt: (v) => Math.round(v).toLocaleString(), lowerIsBetter: true },
];

const mean = (vals) => (vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null);

export default function ComparisonsAndStats({ runs }) {
  const data = useMemo(() => {
    const scored = (runs || []).filter((r) => r.quality != null && r.model !== 'fake' && r.execution_mode !== 'SIMULATED');
    const bySys = {};
    for (const s of SYSTEMS) {
      const rows = scored.filter((r) => r.system === s.id);
      const byTask = Object.fromEntries(rows.map((r) => [r.task_id, r]));
      bySys[s.id] = { rows, byTask };
    }
    // Head-to-head on the same task: how often MAS scored higher, lower or the same.
    const h2h = (other) => {
      let win = 0, loss = 0, tie = 0;
      for (const [task, m] of Object.entries(bySys.mas.byTask)) {
        const o = bySys[other].byTask[task];
        if (!o) continue;
        const d = m.quality - o.quality;
        if (Math.abs(d) < 1e-9) tie += 1;
        else if (d > 0) win += 1;
        else loss += 1;
      }
      return { win, loss, tie };
    };
    return { bySys, h2h: { chatdev: h2h('chatdev'), single: h2h('single') } };
  }, [runs]);

  const shown = SYSTEMS.filter((s) => data.bySys[s.id].rows.length > 0);
  const avgOf = (sysId, key) => mean(data.bySys[sysId].rows.map((r) => r[key]).filter((v) => v != null));

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
          <Scale className="w-6 h-6 text-cyan-500" />
          <span>Compare Systems</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          MAS, ChatDev and a single agent on the same 20 tasks, with the same model and the same scoring code.
        </p>
      </div>

      {shown.length < 2 ? (
        <div className="bg-white border border-slate-800 rounded-lg p-6 text-sm text-slate-500 text-center">
          NOT RUN: fewer than two systems have scored runs.
        </div>
      ) : (
        <>
          <div className="bg-white border border-slate-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-925 text-slate-500 text-xs border-b border-slate-800">
                <tr>
                  <th className="text-left py-2.5 px-4 font-semibold">Score</th>
                  {shown.map((s) => (
                    <th key={s.id} className="text-right py-2.5 px-3 font-semibold">
                      {s.name}
                      <span className="block font-normal">{data.bySys[s.id].rows.length} runs</span>
                    </th>
                  ))}
                  <th className="text-right py-2.5 px-4 font-semibold">MAS minus ChatDev</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {METRICS.map((m) => {
                  const vals = Object.fromEntries(shown.map((s) => [s.id, avgOf(s.id, m.key)]));
                  const best = m.lowerIsBetter
                    ? Math.min(...Object.values(vals).filter((v) => v != null))
                    : Math.max(...Object.values(vals).filter((v) => v != null));
                  const diff = vals.mas != null && vals.chatdev != null ? vals.mas - vals.chatdev : null;
                  return (
                    <tr key={m.key}>
                      <td className="py-2.5 px-4">
                        <div className="font-medium text-slate-200">{m.name}</div>
                        <div className="text-xs text-slate-500">{m.help}</div>
                      </td>
                      {shown.map((s) => (
                        <td
                          key={s.id}
                          className={`py-2.5 px-3 text-right ${vals[s.id] === best ? 'font-semibold text-slate-100' : 'text-slate-300'}`}
                        >
                          {vals[s.id] == null ? '-' : m.fmt(vals[s.id])}
                        </td>
                      ))}
                      <td className="py-2.5 px-4 text-right text-slate-300">
                        {diff == null
                          ? '-'
                          : m.key === 'tokens'
                          ? `${diff > 0 ? '+' : ''}${Math.round(diff).toLocaleString()}`
                          : m.key === 'executability'
                          ? `${diff > 0 ? '+' : ''}${Math.round(diff * 100)} pts`
                          : `${diff > 0 ? '+' : ''}${diff.toFixed(3)}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              ['chatdev', 'MAS vs ChatDev'],
              ['single', 'MAS vs single agent'],
            ].map(([other, title]) => {
              const h = data.h2h[other];
              const total = h.win + h.loss + h.tie;
              return (
                <div key={other} className="bg-white border border-slate-800 rounded-lg p-4">
                  <div className="text-sm font-semibold text-slate-200">{title}, task by task</div>
                  <div className="text-xs text-slate-500 mb-3">Quality on the same task, {total} tasks</div>
                  {total === 0 ? (
                    <div className="text-sm text-slate-500">NOT RUN</div>
                  ) : (
                    <>
                      <div className="flex h-3 rounded-full overflow-hidden bg-slate-850">
                        <div className="bg-cyan-600" style={{ width: `${(h.win / total) * 100}%` }} />
                        <div className="bg-slate-600" style={{ width: `${(h.tie / total) * 100}%` }} />
                        <div className="bg-amber-500" style={{ width: `${(h.loss / total) * 100}%` }} />
                      </div>
                      <div className="flex justify-between text-xs mt-2 text-slate-400">
                        <span>MAS higher: <span className="font-semibold text-slate-200">{h.win}</span></span>
                        <span>Same: <span className="font-semibold text-slate-200">{h.tie}</span></span>
                        <span>MAS lower: <span className="font-semibold text-slate-200">{h.loss}</span></span>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      <div className="bg-cyan-950 border border-cyan-800 text-slate-300 p-3 rounded-lg text-xs flex gap-2">
        <Info className="w-4 h-4 text-cyan-500 flex-shrink-0 mt-0.5" />
        <span>
          Confidence intervals and the significance tests (paired Wilcoxon test, effect sizes) for these runs are in{' '}
          <code>eval/stats_report.md</code> and DECISIONS.md (DEC-049). A run that did not finish is scored 0, as in the report.
        </span>
      </div>
    </div>
  );
}

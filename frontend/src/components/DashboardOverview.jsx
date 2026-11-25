import React from 'react';
import {
  Activity,
  CheckCircle2,
  XCircle,
  Coins,
  Cpu,
  Award,
  Zap,
  DollarSign,
  PlayCircle,
  Layers,
  ArrowRight,
  TrendingUp,
  FlaskConical,
  AlertTriangle,
} from 'lucide-react';

export default function DashboardOverview({
  summary,
  recentRuns,
  onNavigate,
  onSelectRun,
}) {
  const fmtNum = (v) => (v != null ? Number(v).toLocaleString() : '0');
  const cards = [
    { title: 'Runs recorded', value: summary?.total_runs ?? 0, icon: Activity, color: 'text-indigo-400', bg: 'bg-indigo-950' },
    { title: 'Finished', value: summary?.completed_runs ?? 0, icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-950' },
    { title: 'Failed', value: summary?.failed_runs ?? 0, icon: XCircle, color: 'text-rose-400', bg: 'bg-rose-950' },
    {
      title: 'Average quality score',
      value: summary?.total_runs > 0 && summary?.average_quality != null ? summary.average_quality.toFixed(3) : 'No data',
      hint: '0 to 1, higher is better',
      icon: Award,
      color: 'text-cyan-400',
      bg: 'bg-cyan-950',
    },
    {
      title: 'Average tokens per run',
      value: summary?.average_tokens_per_run ? Math.round(summary.average_tokens_per_run).toLocaleString() : '0',
      hint: 'Model input + output',
      icon: Coins,
      color: 'text-amber-400',
      bg: 'bg-amber-950',
    },
    { title: 'Total tokens used', value: fmtNum(summary?.total_tokens), icon: Cpu, color: 'text-amber-400', bg: 'bg-amber-950' },
  ];

  const steps = [
    { n: 1, title: 'Write a requirement', text: 'Describe the program you want in plain English.' },
    { n: 2, title: 'Agents build it', text: 'Manager, Architect, Developer, Tester and Reviewer agents plan, write and check the code.' },
    { n: 3, title: 'Score the result', text: 'Each project is scored on completeness, whether it runs, and how well it matches the requirement.' },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="bg-white border border-slate-800 rounded-lg p-6">
        <h1 className="text-2xl font-semibold text-slate-100">Overview</h1>
        <p className="text-sm text-slate-400 mt-1 max-w-2xl">
          MAS turns a written requirement into a working Python project using a team of AI agents.
          This app lets you generate projects, run benchmarks, and compare MAS with ChatDev.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
          {steps.map((s) => (
            <div key={s.n} className="flex gap-3">
              <div className="w-7 h-7 rounded-full bg-cyan-950 text-cyan-400 text-sm font-semibold flex items-center justify-center flex-shrink-0">
                {s.n}
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-200">{s.title}</div>
                <div className="text-xs text-slate-500 mt-0.5 leading-relaxed">{s.text}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-baseline justify-between mb-3 px-1">
          <h2 className="text-sm font-semibold text-slate-200">At a glance</h2>
          <span className="text-xs text-slate-500">
            The official runs of the final 20-task benchmark: MAS, ChatDev and a single agent on the same tasks.
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {cards.map((card) => {
            const Icon = card.icon;
            return (
              <div key={card.title} className="p-4 rounded-lg border border-slate-800 bg-white">
                <div className="flex items-start justify-between">
                  <span className="text-xs font-medium text-slate-400">{card.title}</span>
                  <div className={`p-1.5 rounded-md ${card.bg}`}>
                    <Icon className={`w-3.5 h-3.5 ${card.color}`} />
                  </div>
                </div>
                <div className="text-2xl font-semibold text-slate-100 mt-2 leading-none">{card.value}</div>
                {card.hint && <div className="text-[11px] text-slate-500 mt-1.5">{card.hint}</div>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm mb-1.5">
              <PlayCircle className="w-4 h-4 text-cyan-500" />
              <span>Generate a project</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Type one requirement and watch the agents build the project step by step.
            </p>
          </div>
          <button
            onClick={() => onNavigate('generate')}
            className="mt-4 self-start flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-md text-xs font-semibold"
          >
            <span>Start</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="bg-white border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm mb-1.5">
              <Layers className="w-4 h-4 text-cyan-500" />
              <span>Run a benchmark</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Run many benchmark tasks on MAS and ChatDev. Use a dry run first to see the plan without using the API.
            </p>
          </div>
          <button
            onClick={() => onNavigate('benchmark')}
            className="mt-4 self-start flex items-center gap-2 px-4 py-2 bg-white border border-slate-700 hover:bg-slate-925 text-slate-200 rounded-md text-xs font-semibold"
          >
            <span>Open</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Recent Runs Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-slate-50 uppercase tracking-wider">
              Latest runs
            </h2>
          </div>
          <button
            onClick={() => onNavigate('runs')}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1 transition-colors"
          >
            <span>See all runs</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950 text-slate-500 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="py-2.5 px-4">Run</th>
                <th className="py-2.5 px-3">Task</th>
                <th className="py-2.5 px-3">System</th>
                <th className="py-2.5 px-3">Model</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Quality</th>
                <th className="py-2.5 px-3 text-right">Tokens</th>
                <th className="py-2.5 px-3 text-right">Duration</th>
                <th className="py-2.5 px-3 text-center"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {recentRuns && recentRuns.length > 0 ? (
                recentRuns.slice(0, 8).map((r) => (
                  <tr
                    key={r.run_id}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                    onClick={() => onSelectRun(r.run_id)}
                  >
                    <td className="py-2.5 px-4">
                      <span className="font-semibold text-slate-200 font-mono text-[11px]">
                        {r.run_id.slice(0, 12)}…
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 max-w-[120px] truncate">
                      {r.task_id}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          r.system === 'chatdev'
                            ? 'bg-amber-950 text-amber-400 border border-amber-800/60'
                            : 'bg-indigo-950 text-indigo-400 border border-indigo-800/60'
                        }`}
                      >
                        {r.system}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 text-[11px] max-w-[90px] truncate">
                      {r.model}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          r.status === 'COMPLETED'
                            ? 'bg-emerald-950 text-emerald-400'
                            : r.status === 'RUNNING'
                            ? 'bg-cyan-950 text-cyan-300 animate-pulse'
                            : r.status === 'MODEL_MISMATCH_DIAGNOSTIC' || r.status === 'DIAGNOSTIC_RUN'
                            ? 'bg-amber-950 text-amber-300 border border-amber-800/40'
                            : 'bg-rose-950 text-rose-400'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right text-cyan-300 font-bold">
                      {r.quality != null ? r.quality.toFixed(3) : '-'}
                    </td>
                    <td className="py-2.5 px-3 text-right text-amber-300">
                      {r.tokens ? r.tokens.toLocaleString() : '0'}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-400">
                      {r.duration_seconds ? `${r.duration_seconds}s` : '-'}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={(e) => { e.stopPropagation(); onSelectRun(r.run_id); }}
                        className="px-2.5 py-1 bg-cyan-900/50 hover:bg-cyan-800/70 text-cyan-300 rounded text-[11px] transition-colors border border-cyan-800/40"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="py-10 text-center text-slate-500 italic">
                    <div className="flex flex-col items-center gap-2">
                      <FlaskConical className="w-8 h-8 text-slate-700" />
                      <span>No runs recorded yet. Use Single Task Run to initiate an execution.</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

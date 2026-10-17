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
  const cards = [
    {
      title: 'Total Runs',
      value: summary?.total_runs ?? 0,
      icon: Activity,
      color: 'text-indigo-400',
      bg: 'bg-indigo-950/40',
      border: 'border-indigo-800/40',
      accent: 'from-indigo-500/10 to-transparent',
    },
    {
      title: 'Completed Runs',
      value: summary?.completed_runs ?? 0,
      icon: CheckCircle2,
      color: 'text-emerald-400',
      bg: 'bg-emerald-950/40',
      border: 'border-emerald-800/40',
      accent: 'from-emerald-500/10 to-transparent',
    },
    {
      title: 'Failed Runs',
      value: summary?.failed_runs ?? 0,
      icon: XCircle,
      color: 'text-rose-400',
      bg: 'bg-rose-950/40',
      border: 'border-rose-800/40',
      accent: 'from-rose-500/10 to-transparent',
    },
    {
      title: 'Total Tokens',
      value: summary?.total_tokens ? summary.total_tokens.toLocaleString() : '0',
      icon: Cpu,
      color: 'text-amber-400',
      bg: 'bg-amber-950/40',
      border: 'border-amber-800/40',
      accent: 'from-amber-500/10 to-transparent',
    },
    {
      title: 'Avg Tokens / Run',
      value: summary?.average_tokens_per_run ? summary.average_tokens_per_run.toLocaleString() : '0',
      icon: Coins,
      color: 'text-amber-300',
      bg: 'bg-amber-950/30',
      border: 'border-amber-800/30',
      accent: 'from-amber-400/8 to-transparent',
    },
    {
      title: 'Average Quality',
      value: (summary?.total_runs > 0 && summary?.average_quality !== undefined) ? summary.average_quality.toFixed(3) : 'No data',
      icon: Award,
      color: 'text-cyan-400',
      bg: 'bg-cyan-950/40',
      border: 'border-cyan-800/40',
      accent: 'from-cyan-500/10 to-transparent',
    },
    {
      title: 'Quality / 1K Tokens',
      value: (summary?.total_runs > 0 && summary?.quality_per_1k_tokens !== undefined && summary?.quality_per_1k_tokens !== null) ? summary.quality_per_1k_tokens.toFixed(4) : 'No data',
      icon: Zap,
      color: 'text-teal-400',
      bg: 'bg-teal-950/40',
      border: 'border-teal-800/40',
      accent: 'from-teal-500/10 to-transparent',
    },
    {
      title: 'Estimated Cost',
      value: `$${(summary?.estimated_cost ?? 0).toFixed(4)}`,
      icon: DollarSign,
      color: 'text-violet-400',
      bg: 'bg-violet-950/40',
      border: 'border-violet-800/40',
      accent: 'from-violet-500/10 to-transparent',
    },
  ];

  const hasData = summary?.total_runs > 0;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero Header */}
      <div className="relative overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl p-7 shadow-xl">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 via-indigo-500/5 to-transparent pointer-events-none" />
        <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-indigo-500/10 to-transparent rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none" />

        <div className="relative">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5 mb-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                  <FlaskConical className="w-4 h-4 text-white" />
                </div>
                <span className="text-[11px] font-mono font-bold text-cyan-400 uppercase tracking-widest bg-cyan-950/60 px-2.5 py-0.5 rounded border border-cyan-800/50">
                  Research Phase Active
                </span>
              </div>
              <h1 className="text-3xl font-bold tracking-tight text-white leading-tight">
                MAS Research Dashboard
              </h1>
              <p className="text-sm text-slate-400 mt-1.5 max-w-xl leading-relaxed">
                Empirical multi-agent benchmark evaluation, token-level analytics, statistical
                hypothesis testing, and reproducibility monitoring for the Final Year Project.
              </p>
            </div>

            {/* Live status */}
            <div className="flex flex-col items-end gap-2 text-[11px] font-mono text-slate-400">
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-emerald-400 font-semibold">Backend API :8000</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                <span>SRDD-20 Benchmark Suite</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                <span>Temperature: 0 · Seed: 42</span>
              </div>
            </div>
          </div>

          {/* Quick stat bar */}
          {hasData && (
            <div className="mt-5 pt-4 border-t border-slate-800/60 flex flex-wrap items-center gap-6 text-xs font-mono">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-slate-400">
                  {summary.completed_runs} completed
                </span>
              </div>
              {summary.failed_runs > 0 && (
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                  <span className="text-slate-400">{summary.failed_runs} failed</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <Award className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-slate-400">
                  Mean quality: <span className="text-cyan-300 font-bold">{(summary.average_quality ?? 0).toFixed(3)}</span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Cpu className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-slate-400">
                  Total tokens: <span className="text-amber-300 font-bold">{(summary.total_tokens ?? 0).toLocaleString()}</span>
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Top 8 Metric Cards */}
      <div>
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-3 px-1">
          Research Metrics Overview
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {cards.map((card, idx) => {
            const Icon = card.icon;
            return (
              <div
                key={idx}
                className={`relative overflow-hidden p-4 rounded-xl border bg-slate-900 shadow-md
                            transition-all duration-200 hover:shadow-lg hover:scale-[1.01] ${card.border}`}
              >
                {/* Subtle gradient accent */}
                <div
                  className={`absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r ${card.accent}`}
                />
                <div className="flex items-start justify-between">
                  <span className="text-xs font-medium text-slate-400 leading-tight">{card.title}</span>
                  <div className={`p-1.5 rounded-lg ${card.bg} flex-shrink-0`}>
                    <Icon className={`w-3.5 h-3.5 ${card.color}`} />
                  </div>
                </div>
                <div className="text-2xl font-bold font-mono text-white mt-2 leading-none">
                  {card.value}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section Quick Launches */}
      <div>
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-3 px-1">
          Quick Actions
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Single Task Run */}
          <div className="bg-slate-900 border border-indigo-900/40 rounded-xl p-5 flex flex-col justify-between hover:border-indigo-700/60 transition-colors group">
            <div>
              <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm mb-2">
                <PlayCircle className="w-4 h-4" />
                <span>Single Task Run</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Execute a single requirement on MAS or ChatDev with custom models (GPT-4o or GPT-4o-mini)
                and monitor real-time multi-agent pipeline execution.
              </p>
            </div>
            <button
              onClick={() => onNavigate('single_run')}
              className="mt-4 flex items-center justify-between px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-all shadow-sm group-hover:shadow-indigo-500/20"
            >
              <span>Launch Task Runner</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Batch Benchmark */}
          <div className="bg-slate-900 border border-cyan-900/40 rounded-xl p-5 flex flex-col justify-between hover:border-cyan-700/60 transition-colors group">
            <div>
              <div className="flex items-center gap-2 text-cyan-400 font-semibold text-sm mb-2">
                <Layers className="w-4 h-4" />
                <span>Batch Benchmark & Dry Run</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Configure multi-task benchmarks (SRDD-20), dry-run planning envelopes with 0 model calls,
                and validate 120 or 300-run experiments before real execution.
              </p>
            </div>
            <button
              onClick={() => onNavigate('batch')}
              className="mt-4 flex items-center justify-between px-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold transition-all shadow-sm group-hover:shadow-cyan-500/20"
            >
              <span>Open Batch Benchmark</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Recent Runs Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Recent Executions
            </h2>
          </div>
          <button
            onClick={() => onNavigate('runs')}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1 transition-colors"
          >
            <span>View All Runs</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950 text-slate-500 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="py-2.5 px-4">Run ID</th>
                <th className="py-2.5 px-3">Task</th>
                <th className="py-2.5 px-3">System</th>
                <th className="py-2.5 px-3">Model</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Quality</th>
                <th className="py-2.5 px-3 text-right">Tokens</th>
                <th className="py-2.5 px-3 text-right">Duration</th>
                <th className="py-2.5 px-3 text-center">Action</th>
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
                      {r.quality !== undefined ? r.quality.toFixed(3) : '-'}
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

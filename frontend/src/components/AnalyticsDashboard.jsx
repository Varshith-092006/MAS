import React, { useMemo } from 'react';
import {
  BarChart3,
  Award,
  Cpu,
  Coins,
  Zap,
  DollarSign,
  Clock,
  CheckCircle2,
  Shield,
  Layers,
  TrendingUp,
} from 'lucide-react';

export default function AnalyticsDashboard({ runs, analyticsData }) {
  // Aggregate empirical statistics from runs
  const stats = useMemo(() => {
    if (!runs || runs.length === 0) {
      return {
        mas: { count: 0, quality: 0, comp: 0, exec: 0, cons: 0, test: 0, ruff: 0, bandit: 0, radon: 0, tokens: 0, duration: 0 },
        chatdev: { count: 0, quality: 0, comp: 0, exec: 0, cons: 0, test: 0, ruff: 0, bandit: 0, radon: 0, tokens: 0, duration: 0 },
      };
    }

    const calc = (sys) => {
      const match = runs.filter((r) => r.system?.toLowerCase() === sys && r.status === 'COMPLETED');
      if (match.length === 0) {
        return { count: 0, quality: 0, comp: 0, exec: 0, cons: 0, test: 0, ruff: 0, bandit: 0, radon: 0, tokens: 0, duration: 0 };
      }
      const sum = (field) => match.reduce((acc, r) => acc + (r[field] || 0), 0);
      const n = match.length;
      return {
        count: n,
        quality: sum('quality') / n,
        comp: sum('completeness') / n,
        exec: sum('executability') / n,
        cons: sum('consistency') / n,
        test: sum('shared_test') / n,
        ruff: sum('ruff') / n,
        bandit: sum('bandit') / n,
        radon: sum('radon') / n,
        tokens: sum('tokens') / n,
        duration: sum('duration_seconds') / n,
      };
    };

    return {
      mas: calc('mas'),
      chatdev: calc('chatdev'),
    };
  }, [runs]);

  const tokenData = analyticsData?.token_analytics || {
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
    average_tokens_per_run: 0,
    median_tokens_per_run: 0,
    maximum_tokens_per_run: 0,
    estimated_cost: 0,
    quality_per_1k_tokens: 0,
  };

  const provFilter = analyticsData?.provenance_filter || {
    eligible_live_runs: 0,
    excluded_simulated_runs: 0,
    excluded_failed_runs: 0,
    runs_with_missing_usage: 0,
    runs_with_missing_artifacts: 0,
    total_runs_in_db: 0,
  };

  const topCards = [
    { title: 'Average Quality', value: stats.mas.count > 0 ? stats.mas.quality.toFixed(3) : 'No data', subtitle: 'MAS System Mean', icon: Award, color: 'text-cyan-400' },
    { title: 'Average Completeness', value: stats.mas.count > 0 ? stats.mas.comp.toFixed(2) : 'No data', subtitle: 'AST & Schema Valid', icon: CheckCircle2, color: 'text-emerald-400' },
    { title: 'Average Executability', value: stats.mas.count > 0 ? stats.mas.exec.toFixed(2) : 'No data', subtitle: 'Sandbox Run Pass', icon: Zap, color: 'text-indigo-400' },
    { title: 'Average Consistency', value: stats.mas.count > 0 ? stats.mas.cons.toFixed(3) : 'No data', subtitle: 'Embedding Cosine', icon: Layers, color: 'text-violet-400' },
    { title: 'Average Tokens / Run', value: (stats.mas.count > 0 && stats.mas.tokens > 0) ? Math.round(stats.mas.tokens).toLocaleString() : 'N/A', subtitle: 'Actual Provider Usage', icon: Cpu, color: 'text-amber-400' },
    { title: 'Quality / 1K Tokens', value: (stats.mas.count > 0 && stats.mas.tokens > 0 && stats.mas.quality > 0) ? (stats.mas.quality / (stats.mas.tokens / 1000)).toFixed(4) : 'N/A', subtitle: 'Efficiency Index', icon: TrendingUp, color: 'text-teal-400' },
    { title: 'Estimated Cost', value: `$${tokenData.estimated_cost.toFixed(4)}`, subtitle: 'Eligible Provider Fees', icon: DollarSign, color: 'text-rose-400' },
    { title: 'Average Duration', value: stats.mas.count > 0 ? `${stats.mas.duration.toFixed(1)}s` : '0.0s', subtitle: 'Latency per Execution', icon: Clock, color: 'text-slate-300' },
  ];

  const metricComparisons = [
    { name: '1. Quality Score', mas: stats.mas.quality, cd: stats.chatdev.quality, max: 1.0, format: (v) => v.toFixed(3) },
    { name: '2. Token Consumption', mas: stats.mas.tokens, cd: stats.chatdev.tokens, max: Math.max(stats.mas.tokens, stats.chatdev.tokens, 1000), format: (v) => Math.round(v).toLocaleString() },
    { name: '3. Quality / 1K Tokens', mas: (stats.mas.tokens > 0 && stats.mas.quality > 0) ? stats.mas.quality / (stats.mas.tokens / 1000) : 0, cd: (stats.chatdev.tokens > 0 && stats.chatdev.quality > 0) ? stats.chatdev.quality / (stats.chatdev.tokens / 1000) : 0, max: 2.0, format: (v) => (v > 0 ? v.toFixed(4) : 'N/A') },
    { name: '4. Completeness', mas: stats.mas.comp, cd: stats.chatdev.comp, max: 1.0, format: (v) => v.toFixed(2) },
    { name: '5. Executability', mas: stats.mas.exec, cd: stats.chatdev.exec, max: 1.0, format: (v) => v.toFixed(2) },
    { name: '6. Consistency', mas: stats.mas.cons, cd: stats.chatdev.cons, max: 1.0, format: (v) => v.toFixed(3) },
    { name: '7. Shared Test Pass Rate', mas: stats.mas.test, cd: stats.chatdev.test, max: 1.0, format: (v) => v.toFixed(2) },
    { name: '8. Ruff Code Health', mas: stats.mas.ruff, cd: stats.chatdev.ruff, max: 1.0, format: (v) => v.toFixed(2) },
    { name: '9. Bandit Security Score', mas: stats.mas.bandit, cd: stats.chatdev.bandit, max: 1.0, format: (v) => v.toFixed(2) },
    { name: '10. Radon Maintainability', mas: stats.mas.radon, cd: stats.chatdev.radon, max: 1.0, format: (v) => v.toFixed(2) },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-cyan-400" />
          <span>Empirical Analytics & Metrics Dashboard</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Rigorous evaluation metrics and token consumption comparisons derived strictly from backend stored results.
        </p>
      </div>

      {/* Research Provenance & Integrity Banner */}
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-md space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Empirical Research Provenance & Quarantine
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Total DB Records: {provFilter.total_runs_in_db}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
          <div className="bg-slate-950 p-2.5 rounded-lg border border-emerald-900/40">
            <div className="text-[10px] text-emerald-400">Eligible Live Runs</div>
            <div className="text-base font-bold text-emerald-300 mt-0.5">{provFilter.eligible_live_runs}</div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-lg border border-amber-900/40">
            <div className="text-[10px] text-amber-400">Excluded Simulated Runs</div>
            <div className="text-base font-bold text-amber-300 mt-0.5">{provFilter.excluded_simulated_runs}</div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-lg border border-rose-900/40">
            <div className="text-[10px] text-rose-400">Excluded Failed Runs</div>
            <div className="text-base font-bold text-rose-300 mt-0.5">{provFilter.excluded_failed_runs}</div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            <div className="text-[10px] text-slate-400">Missing Usage Runs</div>
            <div className="text-base font-bold text-slate-300 mt-0.5">{provFilter.runs_with_missing_usage}</div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            <div className="text-[10px] text-slate-400">Missing Artifacts Runs</div>
            <div className="text-base font-bold text-slate-300 mt-0.5">{provFilter.runs_with_missing_artifacts}</div>
          </div>
        </div>

        {provFilter.eligible_live_runs === 0 && (
          <div className="text-xs text-amber-300/90 bg-amber-950/40 border border-amber-900/60 p-2 rounded-lg font-mono flex items-center gap-2">
            <span>Notice:</span>
            <span>All {provFilter.excluded_simulated_runs} simulated/fake records are safely quarantined and excluded from empirical statistics. Run a live model execution to generate valid empirical research data.</span>
          </div>
        )}
      </div>

      {/* Top 8 Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {topCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div key={idx} className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-md">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400 font-medium">{card.title}</span>
                <Icon className={`w-4 h-4 ${card.color}`} />
              </div>
              <div className="text-xl font-bold font-mono text-white mt-1">{card.value}</div>
              <div className="text-[10px] text-slate-500 font-mono mt-0.5">{card.subtitle}</div>
            </div>
          );
        })}
      </div>

      {/* 10 Comparative Metric Charts: MAS vs ChatDev */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-6">
        <div className="flex flex-wrap items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-base font-bold text-white uppercase tracking-wider">
              10-Metric Comparative Benchmark (MAS vs ChatDev)
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Identical prompt and task-level execution evaluation.
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-indigo-400">
              <span className="w-3 h-3 rounded bg-indigo-500 inline-block"></span> MAS
            </span>
            <span className="flex items-center gap-1.5 text-amber-400">
              <span className="w-3 h-3 rounded bg-amber-500 inline-block"></span> ChatDev
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {metricComparisons.map((m, idx) => {
            const masPct = Math.min(100, Math.max(0, (m.mas / (m.max || 1)) * 100));
            const cdPct = Math.min(100, Math.max(0, (m.cd / (m.max || 1)) * 100));

            return (
              <div key={idx} className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-slate-200">{m.name}</span>
                  <div className="flex gap-4 font-mono">
                    <span className="text-indigo-400">MAS: {m.format(m.mas)}</span>
                    <span className="text-amber-400">CD: {m.format(m.cd)}</span>
                  </div>
                </div>

                {/* Comparative Progress Bars */}
                <div className="space-y-1.5">
                  <div className="h-2.5 w-full bg-slate-900 rounded-full overflow-hidden flex">
                    <div
                      className="bg-indigo-500 h-full rounded-full transition-all duration-500"
                      style={{ width: `${masPct}%` }}
                    />
                  </div>
                  <div className="h-2.5 w-full bg-slate-900 rounded-full overflow-hidden flex">
                    <div
                      className="bg-amber-500 h-full rounded-full transition-all duration-500"
                      style={{ width: `${cdPct}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section G: Dedicated Token Analytics Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-6">
        <div className="border-b border-slate-800 pb-3 flex flex-wrap items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Cpu className="w-5 h-5 text-amber-400" />
              <span>Token Consumption & Provider Usage Analytics</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Accurate token telemetry captured directly from OpenAI/OpenRouter provider headers.
            </p>
          </div>
          <span className="text-[11px] font-mono bg-amber-950 text-amber-400 border border-amber-800 px-2.5 py-1 rounded">
            NO TEXT-LENGTH ESTIMATES
          </span>
        </div>

        {/* Token Metric Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-xs">
          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
            <div className="text-slate-400">Input Tokens</div>
            <div className="text-lg font-bold text-slate-200">{tokenData.input_tokens.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
            <div className="text-slate-400">Output Tokens</div>
            <div className="text-lg font-bold text-slate-200">{tokenData.output_tokens.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
            <div className="text-slate-400">Total Tokens</div>
            <div className="text-lg font-bold text-amber-300">{tokenData.total_tokens.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
            <div className="text-slate-400">Estimated Cost</div>
            <div className="text-lg font-bold text-violet-300">${tokenData.estimated_cost.toFixed(4)}</div>
          </div>

          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
            <div className="text-slate-400">Average Tokens / Run</div>
            <div className="text-lg font-bold text-slate-200">{tokenData.average_tokens_per_run.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
            <div className="text-slate-400">Median Tokens / Run</div>
            <div className="text-lg font-bold text-slate-200">{tokenData.median_tokens_per_run.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
            <div className="text-slate-400">Maximum Tokens / Run</div>
            <div className="text-lg font-bold text-slate-200">{tokenData.maximum_tokens_per_run.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
            <div className="text-slate-400">Quality / 1K Tokens</div>
            <div className="text-lg font-bold text-teal-300">{tokenData.quality_per_1k_tokens.toFixed(4)}</div>
          </div>
        </div>

        {/* Task vs Token Consumption Chart */}
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-300">Task vs Token Consumption (Sample Runs)</span>
            <span className="text-[11px] font-mono text-slate-500">Provider Measured</span>
          </div>

          <div className="space-y-2 font-mono text-[11px]">
            {runs && runs.slice(0, 6).map((r) => {
              const maxTok = Math.max(...runs.map(x => x.tokens || 1), 1000);
              const pct = Math.min(100, Math.max(5, ((r.tokens || 0) / maxTok) * 100));

              return (
                <div key={r.run_id} className="space-y-1">
                  <div className="flex justify-between text-slate-400 text-[10px]">
                    <span className="truncate max-w-[200px]">{r.task_id} ({r.system})</span>
                    <span className="text-amber-300">{r.tokens?.toLocaleString() || 0} tokens</span>
                  </div>
                  <div className="h-2 w-full bg-slate-900 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${r.system === 'chatdev' ? 'bg-amber-500' : 'bg-indigo-500'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

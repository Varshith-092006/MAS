import React from 'react';
import {
  GitCompare,
  TrendingUp,
  Percent,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Sparkles,
} from 'lucide-react';

export default function ComparisonsAndStats({ analyticsData }) {
  const stats = analyticsData?.statistical_summary || {};
  const qStat = stats.quality || {};
  const masDist = stats.mas_quality_distribution || {};
  const cdDist = stats.chatdev_quality_distribution || {};
  const masMini = analyticsData?.mas_gpt4o_mini || { mean_quality: 0, n_runs: 0 };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <GitCompare className="w-6 h-6 text-indigo-400" />
          <span>Statistical Analysis & Experimental Comparisons</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Task-level paired comparisons across repeats using permutation testing and Cohen's d effect sizes.
        </p>
      </div>

      {/* Main Statistical Summary Table (Section I) */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-6">
        <div className="border-b border-slate-800 pb-3 flex flex-wrap items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-cyan-400" />
              <span>Paired Task Comparison: MAS vs ChatDev (Quality)</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Empirical statistics calculated directly by the backend statistical analysis engine.
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300">
            N = {masDist.n || 0} MAS / {cdDist.n || 0} ChatDev
          </span>
        </div>

        {/* Statistical Grid Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-xs">
          <div className="bg-slate-950 p-4 rounded-xl border border-indigo-900/40">
            <div className="text-slate-400">MAS Mean Quality</div>
            <div className="text-xl font-bold text-indigo-300 mt-1">
              {(masDist?.count > 0 && qStat.mas_mean !== undefined) ? qStat.mas_mean.toFixed(4) : 'No data'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              SD: {(masDist?.count > 0 && qStat.mas_std !== undefined) ? qStat.mas_std.toFixed(4) : '-'}
            </div>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl border border-amber-900/40">
            <div className="text-slate-400">ChatDev Mean Quality</div>
            <div className="text-xl font-bold text-amber-300 mt-1">
              {(cdDist?.count > 0 && qStat.chatdev_mean !== undefined) ? qStat.chatdev_mean.toFixed(4) : 'No data'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              SD: {(cdDist?.count > 0 && qStat.chatdev_std !== undefined) ? qStat.chatdev_std.toFixed(4) : '-'}
            </div>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl border border-cyan-900/40">
            <div className="text-slate-400">Mean Difference (Δ)</div>
            <div className="text-xl font-bold text-cyan-300 mt-1">
              {(masDist?.count > 0 && cdDist?.count > 0 && qStat.difference !== undefined) ? (qStat.difference > 0 ? `+${qStat.difference.toFixed(4)}` : qStat.difference.toFixed(4)) : 'No data'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              Relative: {(masDist?.count > 0 && cdDist?.count > 0 && qStat.percentage_gain !== undefined) ? `+${qStat.percentage_gain.toFixed(2)}%` : '-'}
            </div>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl border border-emerald-900/40">
            <div className="text-slate-400">Permutation P-Value</div>
            <div className="text-xl font-bold text-emerald-300 mt-1">
              {(masDist?.count > 0 && cdDist?.count > 0 && qStat.p_value !== undefined) ? (qStat.p_value < 0.001 ? '< 0.001' : qStat.p_value.toFixed(4)) : 'No data'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              {(masDist?.count > 0 && cdDist?.count > 0) ? (qStat.statistically_significant ? 'Significant (p < 0.05)' : 'Not significant (p ≥ 0.05)') : 'Awaiting experimental runs'}
            </div>
          </div>
        </div>

        {/* Detailed Hypothesis Testing Breakdown */}
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3 font-mono text-xs">
          <div className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Hypothesis Testing & Distribution Parameters
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-slate-400">
            <div>
              <span className="block text-slate-500 text-[11px]">Effect Size (Cohen's d):</span>
              <span className="text-sm font-bold text-slate-200">
                {qStat.effect_size_cohens_d !== undefined ? qStat.effect_size_cohens_d.toFixed(4) : '-'}
              </span>
            </div>
            <div>
              <span className="block text-slate-500 text-[11px]">MAS Median Quality:</span>
              <span className="text-sm font-bold text-slate-200">
                {masDist.median !== undefined ? masDist.median.toFixed(4) : '-'}
              </span>
            </div>
            <div>
              <span className="block text-slate-500 text-[11px]">95% Confidence Interval:</span>
              <span className="text-sm font-bold text-slate-200">
                {masDist.ci_95 ? `[${masDist.ci_95[0]}, ${masDist.ci_95[1]}]` : '-'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* MAS-only GPT-4o-mini Results Card (Section 7) */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold text-white">MAS-Only GPT-4o-mini Cheaper Model Arm</h2>
          </div>
          <span className="text-xs font-mono bg-indigo-950 text-indigo-400 border border-indigo-800 px-2 py-0.5 rounded">
            Research Evaluation Arm
          </span>
        </div>
        <p className="text-xs text-slate-400">
          Evaluates MAS architectural resilience and quality degradation when switching from GPT-4o to GPT-4o-mini for all roles (Reviewer already defaults to GPT-4o-mini).
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 font-mono text-xs">
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
            <div className="text-slate-400">Cheaper Arm Quality</div>
            <div className="text-xl font-bold text-indigo-300 mt-1">
              {masMini.mean_quality ? masMini.mean_quality.toFixed(4) : 'Pending Runs'}
            </div>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
            <div className="text-slate-400">Recorded Runs</div>
            <div className="text-xl font-bold text-slate-200 mt-1">{masMini.n_runs || 0}</div>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
            <div className="text-slate-400">Token Cost Factor</div>
            <div className="text-xl font-bold text-emerald-300 mt-1">~12x Cheaper</div>
          </div>
        </div>
      </div>
    </div>
  );
}

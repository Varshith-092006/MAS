import React, { useState } from 'react';
import { BookOpen, AlertCircle, ExternalLink, ShieldCheck, Info, FileText } from 'lucide-react';

export default function ICoderReference({ analyticsData }) {
  const [selectedCondition, setSelectedCondition] = useState('gpt-4o');

  const refData = analyticsData?.icoder_reference;
  const gpt4o = refData?.gpt_4o || {
    model_condition: 'gpt-4o',
    tasks_evaluated: 20,
    source_paper: 'You et al., Information and Software Technology 198 (2026) 108224',
    quality_table: 'Table 2, Page 12',
    overhead_table: 'Table 4, Page 13',
    icoder_quality: 0.792398,
    chatdev_quality: 0.654990,
    icoder_completeness: 0.995992,
    chatdev_completeness: 1.0,
    icoder_executability: 0.95,
    chatdev_executability: 0.80,
    icoder_consistency: 0.837460,
    chatdev_consistency: 0.818738,
    icoder_tokens_per_task: 104883.2,
    chatdev_tokens_per_task: 30416.6,
    icoder_duration_seconds: 1620.05,
    chatdev_duration_seconds: 1058.7,
  };

  const gpt35 = refData?.gpt_35_turbo || {
    model_condition: 'gpt-3.5-turbo',
    tasks_evaluated: 100,
    source_paper: 'You et al., Information and Software Technology 198 (2026) 108224',
    quality_table: 'Table 1, Page 12',
    overhead_table: 'Table 3, Page 13',
    icoder_quality: 0.690192,
    chatdev_quality: 0.590626,
    icoder_completeness: 0.952062,
    chatdev_completeness: 0.902194,
    icoder_executability: 0.88,
    chatdev_executability: 0.81,
    icoder_consistency: 0.823800,
    chatdev_consistency: 0.808389,
    icoder_tokens_per_task: 411144.62,
    chatdev_tokens_per_task: 22327.02,
    icoder_duration_seconds: 2700.43,
    chatdev_duration_seconds: 439.59,
  };

  const active = selectedCondition === 'gpt-4o' ? gpt4o : gpt35;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <BookOpen className="w-6 h-6 text-amber-400" />
          <span>Published Literature References: iCoder Baseline</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Static benchmark baseline metrics cited directly from the published paper (You et al., <em>Information and Software Technology</em>, 2026).
        </p>
      </div>

      {/* Prominent Mandatory Academic Provenance Notice */}
      <div className="bg-amber-950/30 border-2 border-amber-600/70 rounded-xl p-5 shadow-lg space-y-2">
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded bg-amber-500/20 text-amber-400 border border-amber-500/50 text-xs font-bold font-mono tracking-wider uppercase">
            PUBLISHED REFERENCE — NOT EXECUTED LOCALLY
          </span>
          <span className="text-xs text-amber-200 font-mono font-medium">Citation: IST 198 (2026) 108224</span>
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          The official iCoder multi-agent platform implementation is not released as an open-source runnable package. These baseline scores are strictly extracted from the published paper's evaluation tables. They are presented solely for literature comparison and are never represented as locally executed experiments.
        </p>
      </div>

      {/* Model Condition Selector Tabs */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSelectedCondition('gpt-4o')}
          className={`px-4 py-2 rounded-lg font-mono text-xs font-bold transition-all border ${
            selectedCondition === 'gpt-4o'
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/60 shadow-lg shadow-amber-500/10'
              : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-white'
          }`}
        >
          Condition A: GPT-4o (Tables 2 & 4 · 20 Tasks)
        </button>
        <button
          onClick={() => setSelectedCondition('gpt-3.5-turbo')}
          className={`px-4 py-2 rounded-lg font-mono text-xs font-bold transition-all border ${
            selectedCondition === 'gpt-3.5-turbo'
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/60 shadow-lg shadow-amber-500/10'
              : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-white'
          }`}
        >
          Condition B: GPT-3.5 Turbo (Tables 1 & 3 · 100 Tasks)
        </button>
      </div>

      {/* Main Reference Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4 text-xs font-mono">
          <div>
            <span className="text-slate-400">Model Condition: </span>
            <span className="text-white font-bold">{active.model_condition}</span>
            <span className="text-slate-500 ml-3">({active.tasks_evaluated} SRDD Tasks)</span>
          </div>
          <div className="text-slate-400 flex items-center gap-3">
            <span>Quality: <strong className="text-amber-400">{active.quality_table}</strong></span>
            <span>·</span>
            <span>Overhead: <strong className="text-amber-400">{active.overhead_table}</strong></span>
          </div>
        </div>

        {/* 4 Core Comparison Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono text-xs">
          <div className="bg-slate-950 p-4 rounded-xl border border-amber-900/40 space-y-1">
            <div className="text-slate-400">Published iCoder Quality</div>
            <div className="text-2xl font-bold text-amber-400">{active.icoder_quality}</div>
            <div className="text-[10px] text-slate-500">C × E × S (Cited from {active.quality_table})</div>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
            <div className="text-slate-400">Published ChatDev Quality</div>
            <div className="text-2xl font-bold text-slate-300">{active.chatdev_quality}</div>
            <div className="text-[10px] text-slate-500">Literature baseline in paper</div>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
            <div className="text-slate-400">iCoder Tokens / Task</div>
            <div className="text-xl font-bold text-amber-300">
              {Number(active.icoder_tokens_per_task).toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500">Cited from {active.overhead_table}</div>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
            <div className="text-slate-400">ChatDev Tokens / Task</div>
            <div className="text-xl font-bold text-slate-300">
              {Number(active.chatdev_tokens_per_task).toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500">Cited from {active.overhead_table}</div>
          </div>
        </div>

        {/* Sub-Metrics Breakdown Table */}
        <div className="bg-slate-950 rounded-xl border border-slate-800 overflow-hidden">
          <div className="p-3 bg-slate-900/60 border-b border-slate-800 text-xs font-bold text-slate-200">
            Component Sub-Metrics Breakdown ({active.quality_table})
          </div>
          <table className="w-full text-xs font-mono text-left">
            <thead className="bg-slate-900/40 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-4 font-medium">Metric Dimension</th>
                <th className="py-2.5 px-4 font-medium text-amber-400">iCoder (Published)</th>
                <th className="py-2.5 px-4 font-medium text-slate-300">ChatDev (Published)</th>
                <th className="py-2.5 px-4 font-medium text-slate-400">Definition / Protocol</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              <tr>
                <td className="py-2.5 px-4 font-semibold text-white">Completeness (C)</td>
                <td className="py-2.5 px-4 text-amber-400">{active.icoder_completeness}</td>
                <td className="py-2.5 px-4">{active.chatdev_completeness}</td>
                <td className="py-2.5 px-4 text-slate-400 text-[11px]">1 - (unimplemented_funcs / total_funcs)</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-semibold text-white">Executability (E)</td>
                <td className="py-2.5 px-4 text-amber-400">{active.icoder_executability}</td>
                <td className="py-2.5 px-4">{active.chatdev_executability}</td>
                <td className="py-2.5 px-4 text-slate-400 text-[11px]">Proportion of projects executing with exit code 0</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-semibold text-white">Consistency (S)</td>
                <td className="py-2.5 px-4 text-amber-400">{active.icoder_consistency}</td>
                <td className="py-2.5 px-4">{active.chatdev_consistency}</td>
                <td className="py-2.5 px-4 text-slate-400 text-[11px]">Cosine similarity between prompt and code embedding</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-semibold text-white">Average Duration</td>
                <td className="py-2.5 px-4 text-amber-400">{active.icoder_duration_seconds}s</td>
                <td className="py-2.5 px-4">{active.chatdev_duration_seconds}s</td>
                <td className="py-2.5 px-4 text-slate-400 text-[11px]">Total development time per software task</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Scientific Framing Reminder */}
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl text-xs space-y-2">
          <div className="font-bold text-slate-300 uppercase tracking-wider text-[11px]">
            Academic Methodology Boundary:
          </div>
          <p className="text-slate-400 leading-relaxed">
            The direct empirical research comparison in this project is strictly between <strong>MAS and ChatDev</strong>, evaluated locally under identical model endpoints, identical seeds, identical prompts, and the identical neutral evaluation harness. iCoder values are displayed purely as literature reference points.
          </p>
        </div>
      </div>
    </div>
  );
}

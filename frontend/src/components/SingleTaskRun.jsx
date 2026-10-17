import React, { useState, useMemo } from 'react';
import {
  PlayCircle,
  Loader2,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Bookmark,
  Zap,
  Network,
  Cpu,
} from 'lucide-react';

export default function SingleTaskRun({ onRunCreated }) {
  const [requirement, setRequirement] = useState(
    'Create a Python calculator with add, subtract, multiply, and divide functions.'
  );
  const [system, setSystem] = useState('mas');
  const [model, setModel] = useState('openrouter/free');
  const [repeats, setRepeats] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successInfo, setSuccessInfo] = useState(null);

  // Presets
  const presets = [
    {
      title: 'Simple Calculator',
      category: 'Creation',
      prompt: 'Create a Python calculator with add, subtract, multiply, and divide functions with zero division error handling.',
    },
    {
      title: 'Personal Expense Tracker',
      category: 'Life',
      prompt: 'Build a CLI personal expense tracker with SQLite database persistence, budget categories, expense logging, and monthly summary reporting.',
    },
    {
      title: 'Flashcard Quiz System',
      category: 'Education',
      prompt: 'Build a flashcard study tool with spaced repetition intervals, quiz review sessions, card decks, and accuracy statistics.',
    },
    {
      title: 'Authentication Service',
      category: 'Work',
      prompt: 'Create an authentication service with user registration, password hashing, JWT token verification, and role-based access control.',
    },
  ];

  // Client-side preflight complexity estimation (matching mas/agents/router.py heuristics)
  const estimatedComplexity = useMemo(() => {
    const text = requirement.toLowerCase();
    let score = 0;
    const triggers = [];

    if (/database|sqlite|sql|store|persist|storage|save/.test(text)) {
      score += 2;
      triggers.push('Persistence (+2)');
    }
    if (/auth|login|password|jwt|token|role|permission/.test(text)) {
      score += 2;
      triggers.push('Auth & Security (+2)');
    }
    if (/api|endpoint|rest|http|fastapi|flask/.test(text)) {
      score += 1;
      triggers.push('API / Interface (+1)');
    }
    if (/workflow|pipeline|multi-step|state/.test(text)) {
      score += 1;
      triggers.push('Workflow (+1)');
    }

    const words = text.split(/\s+/).filter(Boolean).length;
    if (words > 60) {
      score += 1;
      triggers.push('Word count > 60 (+1)');
    }

    const isStructured = score >= 4;
    return {
      score,
      triggers,
      type: isStructured ? 'STRUCTURED' : 'SIMPLE',
      invokesArchitect: isStructured,
    };
  }, [requirement]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!requirement.trim()) {
      setError('Please provide a task requirement specification.');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessInfo(null);

    try {
      const res = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement: requirement.trim(),
          task_id: `task_${Date.now().toString(36)}`,
          system: system,
          model: model,
          repeats: Number(repeats) || 1,
          workspace_base: './workspace',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned error status ${res.status}`);
      }

      const data = await res.json();
      setSuccessInfo(data);

      if (data.run_id && onRunCreated) {
        setTimeout(() => {
          onRunCreated(data.run_id);
        }, 800);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <PlayCircle className="w-6 h-6 text-indigo-400" />
          <span>Single Task Manual Execution</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Execute an isolated software engineering task on MAS or ChatDev with deterministic logging and neutral evaluation.
        </p>
      </div>

      {/* Preset Buttons */}
      <div className="space-y-2">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
          <Bookmark className="w-3.5 h-3.5 text-cyan-400" />
          <span>Quick Task Presets</span>
        </span>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {presets.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setRequirement(p.prompt)}
              className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-cyan-500/50 hover:bg-slate-850 text-left transition-all group"
            >
              <div className="text-xs font-semibold text-slate-200 group-hover:text-cyan-300 truncate">
                {p.title}
              </div>
              <div className="text-[10px] text-slate-500 font-mono mt-0.5">{p.category}</div>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-rose-950/70 border border-rose-800 text-rose-300 p-4 rounded-xl text-xs space-y-2">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-rose-200">Execution Error</div>
              <div className="mt-1 leading-relaxed text-rose-300 font-mono text-[11px] break-words">{error}</div>
            </div>
          </div>
          {(error.includes('Insufficient Credits') || error.includes('402')) && (
            <div className="pt-2 border-t border-rose-900/60 flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-slate-300">Quick fix:</span>
              <button
                type="button"
                onClick={() => { setModel('openrouter/free'); setError(null); }}
                className="px-2.5 py-1 bg-emerald-700 hover:bg-emerald-600 text-white rounded text-[11px] font-medium"
              >
                Switch to openrouter/free (Zero Cost)
              </button>
              <button
                type="button"
                onClick={() => { setModel('fake'); setError(null); }}
                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] font-medium"
              >
                Switch to Fake Provider (Deterministic Offline)
              </button>
            </div>
          )}
        </div>
      )}

      {successInfo && (
        <div className="bg-emerald-950/70 border border-emerald-800 text-emerald-300 p-4 rounded-xl text-xs flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
            <div>
              <div className="font-semibold">Run successfully initiated!</div>
              <div className="font-mono text-[11px] text-emerald-400">Run ID: {successInfo.run_id}</div>
            </div>
          </div>
          <span className="text-[11px] text-emerald-400 animate-pulse">Redirecting to Live Visualizer...</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-6">
        {/* Requirement Input */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
            Task Requirement Specification
          </label>
          <textarea
            rows={4}
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            placeholder="Describe the software application, functions, and architecture required..."
            className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg p-3 text-xs text-slate-200 font-mono focus:outline-none"
            required
          />

          {/* Preflight Complexity Estimation Bar */}
          <div className="mt-3 p-3 bg-slate-950 rounded-lg border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Pre-flight Router Estimate:</span>
              <span
                className={`font-mono font-bold px-2 py-0.5 rounded text-[11px] border ${
                  estimatedComplexity.type === 'STRUCTURED'
                    ? 'bg-purple-950 text-purple-300 border-purple-800'
                    : 'bg-emerald-950 text-emerald-300 border-emerald-800'
                }`}
              >
                {estimatedComplexity.type} (Score: {estimatedComplexity.score})
              </span>
            </div>

            <div className="text-[11px] font-mono text-slate-400">
              {estimatedComplexity.invokesArchitect ? (
                <span className="text-purple-300">✓ Architect Agent (UML + Stories) will be invoked</span>
              ) : (
                <span className="text-emerald-300">✓ Direct Manager → Developer path (Zero Architect overhead)</span>
              )}
            </div>
          </div>
        </div>

        {/* System & Model Selectors */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* System Selector */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
              System Architecture
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setSystem('mas')}
                className={`py-2 px-3 rounded-lg text-xs font-semibold border transition-all ${
                  system === 'mas'
                    ? 'bg-indigo-600 text-white border-indigo-500 shadow-sm'
                    : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
                }`}
              >
                MAS (Proposed)
              </button>
              <button
                type="button"
                onClick={() => setSystem('chatdev')}
                className={`py-2 px-3 rounded-lg text-xs font-semibold border transition-all ${
                  system === 'chatdev'
                    ? 'bg-amber-600 text-white border-amber-500 shadow-sm'
                    : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
                }`}
              >
                ChatDev (Baseline)
              </button>
            </div>
          </div>

          {/* Model Selector */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
              Model Condition
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none"
            >
              <option value="openrouter/free">openrouter/free (Recommended Free Auto-Router · 0 Cost)</option>
              <option value="meta-llama/llama-3.3-70b-instruct:free">Llama 3.3 70B Free (OpenRouter · 0 Cost)</option>
              <option value="google/gemma-4-31b-it:free">Gemma 4 31B Free (OpenRouter · 0 Cost)</option>
              <option value="qwen/qwen-2.5-coder-32b-instruct:free">Qwen 2.5 Coder 32B Free (OpenRouter · 0 Cost)</option>
              <option value="fake">FakeLLMProvider (Deterministic Offline Unit Mode · 0 Cost)</option>
              <option value="openai/gpt-4o-mini">GPT-4o-mini (OpenAI Paid · Requires Credits)</option>
              <option value="openai/gpt-4o">GPT-4o (OpenAI Paid · Requires Credits)</option>
            </select>
          </div>
        </div>

        {/* Repeats & Settings */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
              Execution Repeats
            </label>
            <input
              type="number"
              min={1}
              max={5}
              value={repeats}
              onChange={(e) => setRepeats(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none"
            />
          </div>

          <div className="flex flex-col justify-end">
            <div className="text-[11px] text-slate-400 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
              <span className="font-semibold text-slate-300">Execution Safety:</span> All calls recorded in append-only audit log with token-level accounting.
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="pt-2 flex items-center justify-end">
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900 text-white rounded-lg text-xs font-bold shadow-md transition-colors"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Executing Run...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Start Run</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

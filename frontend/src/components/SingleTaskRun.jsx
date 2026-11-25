import React, { useState, useMemo, useEffect } from 'react';
import { Wand2, Loader2, AlertCircle, CheckCircle2, Info } from 'lucide-react';

const OFFLINE = 'fake';

export default function SingleTaskRun({ onRunCreated }) {
  const [requirement, setRequirement] = useState(
    'Create a Python calculator with add, subtract, multiply, and divide functions.'
  );
  const [system, setSystem] = useState('mas');
  // Offline by default so a click never spends the daily API quota by accident.
  const [model, setModel] = useState(OFFLINE);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successInfo, setSuccessInfo] = useState(null);

  useEffect(() => {
    fetch('/api/config')
      .then((r) => (r.ok ? r.json() : null))
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  const liveModel = config?.bench_model || null;
  const liveReady = Boolean(liveModel && config?.api_key_configured);

  const examples = [
    { title: 'Calculator', prompt: 'Create a Python calculator with add, subtract, multiply, and divide functions with zero division error handling.' },
    { title: 'Expense tracker', prompt: 'Build a command-line personal expense tracker that saves expenses to a SQLite database, groups them by category, and prints a monthly summary.' },
    { title: 'Flashcard quiz', prompt: 'Build a flashcard study tool with card decks, quiz sessions, spaced repetition, and accuracy statistics.' },
    { title: 'Login service', prompt: 'Create an authentication service with user registration, password hashing, token verification, and role-based access control.' },
  ];

  // Rough preview of the route the Router agent will pick (same keyword rules as mas/agents/router.py).
  const plan = useMemo(() => {
    const text = requirement.toLowerCase();
    let score = 0;
    if (/database|sqlite|sql|store|persist|storage|save/.test(text)) score += 2;
    if (/auth|login|password|jwt|token|role|permission/.test(text)) score += 2;
    if (/api|endpoint|rest|http|fastapi|flask/.test(text)) score += 1;
    if (/workflow|pipeline|multi-step|state/.test(text)) score += 1;
    if (text.split(/\s+/).filter(Boolean).length > 60) score += 1;
    return score >= 4 ? 'larger' : 'small';
  }, [requirement]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!requirement.trim()) {
      setError('Please write a requirement first.');
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
          system,
          model,
          workspace_base: './workspace',
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `The server returned status ${res.status}`);
      }
      const data = await res.json();
      setSuccessInfo(data);
      if (data.run_id && onRunCreated) setTimeout(() => onRunCreated(data.run_id), 800);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const choiceClass = (active) =>
    `py-2.5 px-3 rounded-md text-sm border text-left transition-colors ${
      active ? 'bg-cyan-950 border-cyan-500 text-cyan-400 font-semibold' : 'bg-white border-slate-700 text-slate-300 hover:bg-slate-925'
    }`;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
          <Wand2 className="w-6 h-6 text-cyan-500" />
          <span>Generate a Project</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Describe a program in plain English. The agents will plan it, write the code, test it and score it.
        </p>
      </div>

      {error && (
        <div className="bg-rose-950 border border-rose-800 text-rose-300 p-4 rounded-lg text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" />
          <div>
            <div className="font-semibold">The run could not start</div>
            <div className="mt-1 text-xs break-words">{error}</div>
          </div>
        </div>
      )}

      {successInfo && (
        <div className="bg-emerald-950 border border-emerald-800 text-emerald-300 p-4 rounded-lg text-sm flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <div>
            <div className="font-semibold">Run finished. Opening the run details…</div>
            <div className="text-xs">Run: {successInfo.run_id}</div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white border border-slate-800 rounded-lg p-6 space-y-6">
        <div>
          <label className="block text-sm font-semibold text-slate-200 mb-1">1. What should the program do?</label>
          <div className="flex flex-wrap gap-2 mb-2">
            <span className="text-xs text-slate-500 self-center">Examples:</span>
            {examples.map((p) => (
              <button
                key={p.title}
                type="button"
                onClick={() => setRequirement(p.prompt)}
                className="px-2.5 py-1 rounded-full border border-slate-700 text-xs text-slate-300 hover:bg-slate-925"
              >
                {p.title}
              </button>
            ))}
          </div>
          <textarea
            rows={5}
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            placeholder="For example: a to-do list app that saves tasks to a file…"
            className="w-full bg-white border border-slate-700 focus:border-cyan-500 rounded-md p-3 text-sm text-slate-200 focus:outline-none"
            required
          />
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5" />
            {plan === 'larger'
              ? 'Looks like a larger project: the Architect agent will design it before coding.'
              : 'Looks like a small project: the Developer agent will code it directly.'}
          </div>
        </div>

        <div>
          <label className="block text-sm font-semibold text-slate-200 mb-2">2. Which system should build it?</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button type="button" onClick={() => setSystem('mas')} className={choiceClass(system === 'mas')}>
              MAS
              <span className="block text-xs font-normal text-slate-500">Our multi-agent system</span>
            </button>
            <button type="button" onClick={() => setSystem('chatdev')} className={choiceClass(system === 'chatdev')}>
              ChatDev
              <span className="block text-xs font-normal text-slate-500">The baseline we compare against</span>
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-semibold text-slate-200 mb-2">3. Which AI model?</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button type="button" onClick={() => setModel(OFFLINE)} className={choiceClass(model === OFFLINE)}>
              Offline test mode
              <span className="block text-xs font-normal text-slate-500">No API calls. Uses a built-in sample answer.</span>
            </button>
            <button
              type="button"
              disabled={!liveReady}
              onClick={() => liveReady && setModel(liveModel)}
              className={`${choiceClass(model === liveModel && liveReady)} disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              Live model{liveModel ? `: ${liveModel}` : ''}
              <span className="block text-xs font-normal text-slate-500">
                {liveReady
                  ? 'Uses your daily API quota.'
                  : 'Not set up: add BENCH_MODEL and the API key to .env, then restart the backend.'}
              </span>
            </button>
          </div>
        </div>

        <div className="pt-2 flex items-center justify-between gap-4 border-t border-slate-800">
          <span className="text-xs text-slate-500 pt-4">
            A run can take from a few seconds (offline) to a few minutes (live). Every model call is logged.
          </span>
          <button
            type="submit"
            disabled={loading}
            className="mt-4 flex items-center gap-2 px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-white rounded-md text-sm font-semibold flex-shrink-0"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Building…</span>
              </>
            ) : (
              <span>Generate project</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

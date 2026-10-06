import React, { useRef, useEffect } from 'react';

export default function AgentLog({ events }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-lg p-5 flex flex-col h-[460px]">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <h2 className="text-base font-semibold text-white flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping"></span>
          Agent Live Audit Log (Append-Only)
        </h2>
        <span className="text-xs font-mono text-slate-400">
          {events.length} Events Logged
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-2.5 font-mono text-xs pr-2">
        {events.length === 0 ? (
          <div className="text-slate-500 italic p-4 text-center">No agent events recorded yet.</div>
        ) : (
          events.map((ev, index) => {
            const isFailure = ev.status === 'failure' || ev.event === 'artifact_rejected';
            const isSuccess = ev.status === 'success';

            return (
              <div
                key={index}
                className="bg-slate-950/70 border border-slate-800/80 p-2.5 rounded-lg flex items-start gap-3 hover:border-slate-700 transition-colors"
              >
                <span className="text-slate-500 font-bold select-none min-w-[28px]">
                  #{ev.seq || index + 1}
                </span>

                <span className="font-semibold text-indigo-300 min-w-[90px] uppercase tracking-wide">
                  [{ev.agent}]
                </span>

                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase min-w-[60px] text-center ${
                    isFailure ? 'bg-rose-950 text-rose-400' : 'bg-slate-800 text-slate-300'
                  }`}
                >
                  {ev.event}
                </span>

                <span className="flex-1 text-slate-300 break-words">
                  {ev.summary || ev.redacted_summary}
                </span>

                <span className="text-[10px] text-slate-600 whitespace-nowrap">
                  {ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : ''}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

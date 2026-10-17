import React from 'react';
import {
  LayoutDashboard,
  PlayCircle,
  Layers,
  TableProperties,
  BarChart3,
  GitCompare,
  BookOpen,
  MonitorDot,
  Settings,
  Sparkles,
  FlaskConical,
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, currentRunId }) {
  const navGroups = [
    {
      label: 'Overview',
      items: [
        { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
      ],
    },
    {
      label: 'Execution',
      items: [
        { id: 'single_run', label: 'Single Task Run', icon: PlayCircle },
        { id: 'batch', label: 'Batch Benchmark', icon: Layers },
      ],
    },
    {
      label: 'Data & Analysis',
      items: [
        { id: 'runs', label: 'Runs & Results', icon: TableProperties },
        { id: 'analytics', label: 'Analytics & Charts', icon: BarChart3 },
        { id: 'comparisons', label: 'Comparisons & Stats', icon: GitCompare },
      ],
    },
    {
      label: 'Research',
      items: [
        { id: 'icoder', label: 'iCoder Reference', icon: BookOpen },
        {
          id: 'visualizer',
          label: 'Run Visualizer',
          icon: MonitorDot,
          badge: currentRunId ? 'Active' : null,
        },
      ],
    },
    {
      label: 'System',
      items: [
        { id: 'settings', label: 'Settings', icon: Settings },
      ],
    },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col flex-shrink-0 min-h-screen">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-violet-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20 flex-shrink-0">
            <FlaskConical className="w-4.5 h-4.5" style={{ width: '18px', height: '18px' }} />
          </div>
          <div>
            <div className="text-sm font-bold text-white tracking-wide leading-tight">
              MAS RESEARCH
            </div>
            <div className="text-[11px] text-slate-400 font-mono leading-tight mt-0.5">
              Benchmark Laboratory
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="p-3 space-y-4 flex-1 overflow-y-auto">
        {navGroups.map((group) => (
          <div key={group.label}>
            <div className="px-3 mb-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-600">
              {group.label}
            </div>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 border ${
                      isActive
                        ? 'bg-gradient-to-r from-cyan-500/10 to-indigo-500/10 text-cyan-400 border-cyan-500/30 shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon
                        className={`w-4 h-4 flex-shrink-0 ${
                          isActive ? 'text-cyan-400' : 'text-slate-500'
                        }`}
                      />
                      <span>{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60 animate-pulse">
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800/80 text-[11px] text-slate-500 font-mono space-y-1.5">
        <div className="flex items-center justify-between">
          <span>Backend API</span>
          <span className="text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            :8000
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span>Benchmark Suite</span>
          <span className="text-slate-400">SRDD-20</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Version</span>
          <span className="text-slate-400">0.1.0</span>
        </div>
      </div>
    </aside>
  );
}

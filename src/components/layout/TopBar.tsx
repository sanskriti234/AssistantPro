import { useAuth } from '../../context/AuthContext';

export function TopBar({ title }: { title: string }) {
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between px-5 md:px-8 py-4 border-b border-border-soft bg-base/85 backdrop-blur">
      <h1 className="font-display text-lg font-semibold tracking-tight">{title}</h1>
      <div className="flex items-center gap-3">
        <div className="text-right hidden sm:block">
          <p className="text-sm text-text leading-tight">{user?.name}</p>
          <p className="text-[11px] text-text-faint uppercase tracking-wider">{user?.role}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-surface-3 flex items-center justify-center font-mono text-xs text-text-dim">
          {user?.name?.slice(0, 1)}
        </div>
        <button onClick={logout} className="text-xs text-text-dim hover:text-blocked transition-colors">
          Sign out
        </button>
      </div>
    </header>
  );
}

import { NavLink } from 'react-router-dom';
import type { Role } from '../../types';

const navByRole: Record<Role, { label: string; to: string }[]> = {
  admin: [
    { label: 'Dashboard', to: '/admin' },
    { label: 'Academic Sessions', to: '/admin/sessions' },
    { label: 'Batches', to: '/admin/batches' },
    { label: 'Faculty', to: '/admin/faculty' },
    { label: 'Attendance', to: '/admin/attendance' },
    { label: 'Analytics', to: '/admin/analytics' },
    { label: 'Settings', to: '/admin/settings' },
  ],
  faculty: [
    { label: 'Dashboard', to: '/faculty' },
    { label: 'Live Attendance', to: '/faculty/live' },
    { label: 'Attendance History', to: '/faculty/history' },
    { label: 'My Batches', to: '/faculty/batches' },
  ],
  student: [
    { label: 'Home', to: '/student' },
    { label: 'My Profile', to: '/student/profile' },
    { label: 'Face Enrollment', to: '/student/enrollment' },
    { label: 'My Attendance', to: '/student/attendance' },
  ],
};

export function Sidebar({ role }: { role: Role }) {
  const items = navByRole[role];
  return (
    <aside className="hidden md:flex md:flex-col w-56 shrink-0 border-r border-border-soft bg-surface/60 h-screen sticky top-0">
      <div className="px-5 py-6">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-md bg-gradient-to-br from-accent to-accent-2 flex items-center justify-center">
            <span className="w-2 h-2 rounded-full bg-base" />
          </span>
          <span className="font-display text-base font-semibold tracking-tight">CoreSight</span>
        </div>
        <p className="text-[11px] text-text-faint mt-1 uppercase tracking-wider">{role}</p>
      </div>
      <nav className="flex-1 px-3 space-y-0.5">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === `/${role}`}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive ? 'bg-accent/10 text-accent font-medium' : 'text-text-dim hover:text-text hover:bg-surface-2'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

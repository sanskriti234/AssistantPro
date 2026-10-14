import { NavLink } from 'react-router-dom';
import type { Role } from '../../types';

const navByRole: Record<Role, { label: string; to: string }[]> = {
  admin: [
    { label: 'Home', to: '/admin' },
    { label: 'Batches', to: '/admin/batches' },
    { label: 'Attendance', to: '/admin/attendance' },
    { label: 'Analytics', to: '/admin/analytics' },
    { label: 'Settings', to: '/admin/settings' },
  ],
  faculty: [
    { label: 'Home', to: '/faculty' },
    { label: 'Live', to: '/faculty/live' },
    { label: 'History', to: '/faculty/history' },
    { label: 'Batches', to: '/faculty/batches' },
  ],
  student: [
    { label: 'Home', to: '/student' },
    { label: 'Profile', to: '/student/profile' },
    { label: 'Enroll', to: '/student/enrollment' },
    { label: 'Attendance', to: '/student/attendance' },
  ],
};

export function MobileNav({ role }: { role: Role }) {
  const items = navByRole[role];
  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-surface/95 backdrop-blur border-t border-border-soft flex">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === `/${role}`}
          className={({ isActive }) =>
            `flex-1 text-center py-2.5 text-[11px] font-medium ${isActive ? 'text-accent' : 'text-text-faint'}`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

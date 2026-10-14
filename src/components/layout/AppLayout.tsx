import type { ReactNode } from 'react';
import type { Role } from '../../types';
import { Sidebar } from './Sidebar';
import { MobileNav } from './MobileNav';
import { TopBar } from './TopBar';

export function AppLayout({ role, title, children }: { role: Role; title: string; children: ReactNode }) {
  return (
    <div className="min-h-screen flex bg-base">
      <Sidebar role={role} />
      <div className="flex-1 min-w-0">
        <TopBar title={title} />
        <main className="px-5 md:px-8 py-6 pb-24 md:pb-6">{children}</main>
      </div>
      <MobileNav role={role} />
    </div>
  );
}

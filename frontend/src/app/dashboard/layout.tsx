import { Sidebar } from '@/components/Sidebar';
import { ReactNode } from 'react';

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#09090b] flex">
      <Sidebar />
      <main className="flex-1 ml-64 min-h-screen relative overflow-y-auto">
        {/* Subtle background glow */}
        <div className="absolute top-0 left-0 w-full h-[500px] bg-blue-500/5 rounded-full blur-[150px] pointer-events-none" />
        
        <div className="p-8 max-w-7xl mx-auto relative z-10">
          {children}
        </div>
      </main>
    </div>
  );
}

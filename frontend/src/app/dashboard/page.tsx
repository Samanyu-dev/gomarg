'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';

export default function DashboardHome() {
  const [stats, setStats] = useState({ leads: 0, campaigns: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [leadsRes, campaignsRes] = await Promise.all([
          api.get('/leads'),
          api.get('/campaigns')
        ]);
        setStats({
          leads: leadsRes.data.length,
          campaigns: campaignsRes.data.length
        });
      } catch (err) {
        console.error('Failed to load stats');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  return (
    <div className="animate-in">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Welcome to GoMarg</h1>
        <p className="text-muted-foreground">Here is an overview of your sales engine.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          { label: 'Total Leads', value: loading ? '...' : stats.leads.toString(), trend: 'Active Contacts' },
          { label: 'Active Campaigns', value: loading ? '...' : stats.campaigns.toString(), trend: 'Running Now' },
          { label: 'Emails Generated', value: loading ? '...' : (stats.leads * 1).toString(), trend: 'Drafts Created' },
        ].map((stat, i) => (
          <div key={i} className="glass p-6 rounded-2xl hover:border-blue-500/30 transition-all duration-300">
            <p className="text-muted-foreground font-medium mb-2">{stat.label}</p>
            <h3 className="text-4xl font-bold mb-2">{stat.value}</h3>
            <p className="text-sm text-blue-400">{stat.trend}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

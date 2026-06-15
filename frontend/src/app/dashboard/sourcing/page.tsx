'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { RefreshCw, Search } from 'lucide-react';
import toast from 'react-hot-toast';

interface Lead {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  job_title: string;
  company: string;
  status: string;
}

export default function SourcingPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const res = await api.get('/leads');
      setLeads(res.data);
    } catch (err: any) {
      toast.error('Failed to load leads');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    const toastId = toast.loading('Syncing Apollo contacts...');
    try {
      const res = await api.post('/sourcing/apollo', {
        page: 1,
        per_page: 50
      });
      toast.success(res.data.message, { id: toastId });
      await fetchLeads(); // refresh the table
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to sync leads', { id: toastId });
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="animate-in">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Lead Sourcing</h1>
          <p className="text-muted-foreground">Manage and sync your contacts from Apollo.</p>
        </div>
        
        <button
          onClick={handleSync}
          disabled={syncing}
          className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-medium flex items-center gap-2 transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50"
        >
          <RefreshCw className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Syncing...' : 'Sync Apollo Contacts'}
        </button>
      </div>

      <div className="glass rounded-2xl overflow-hidden border border-white/5">
        <div className="p-4 border-b border-white/10 flex items-center justify-between bg-secondary/20">
          <div className="relative w-64">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input 
              type="text" 
              placeholder="Search leads..." 
              className="w-full bg-black/20 border border-white/10 rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <div className="text-sm text-muted-foreground">
            {leads.length} total leads
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-secondary/10">
                <th className="p-4 text-sm font-medium text-muted-foreground">Name</th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Title</th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Company</th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading ? (
                <tr>
                  <td colSpan={4} className="p-8 text-center text-muted-foreground">
                    Loading leads...
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={4} className="p-12 text-center">
                    <p className="text-lg font-medium mb-2">No leads found</p>
                    <p className="text-muted-foreground mb-4">You haven't synced any contacts from Apollo yet.</p>
                  </td>
                </tr>
              ) : (
                leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-white/5 transition-colors">
                    <td className="p-4">
                      <p className="font-medium">{lead.first_name} {lead.last_name}</p>
                      <p className="text-sm text-muted-foreground">{lead.email}</p>
                    </td>
                    <td className="p-4 text-sm">{lead.job_title}</td>
                    <td className="p-4 text-sm">{lead.company}</td>
                    <td className="p-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        {lead.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

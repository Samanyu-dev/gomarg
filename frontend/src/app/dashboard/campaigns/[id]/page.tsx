'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { useParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { Megaphone, Users, ArrowLeft, Bot, Activity } from 'lucide-react';
import Link from 'next/link';

interface Campaign {
  id: string;
  name: string;
  status: string;
  created_at: string;
}

interface CampaignLead {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  job_title: string;
  company: string;
  lead_score?: string;
  draft_email: {
    subject: string;
    body: string;
    status: string;
  } | null;
}

export default function CampaignDetailPage() {
  const params = useParams();
  const campaignId = params?.id as string;
  
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [leads, setLeads] = useState<CampaignLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmail, setSelectedEmail] = useState<{subject: string, body: string} | null>(null);

  const fetchData = async () => {
    try {
      const [campRes, leadsRes] = await Promise.all([
        api.get(`/campaigns/${campaignId}`),
        api.get(`/campaigns/${campaignId}/leads`)
      ]);
      setCampaign(campRes.data);
      setLeads(leadsRes.data);
    } catch (err) {
      toast.error('Failed to load campaign data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (campaignId) {
      fetchData();
    }
  }, [campaignId]);

  // Polling mechanism when campaign is active
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (campaign?.status === 'active') {
      interval = setInterval(() => {
        fetchData();
      }, 5000); // poll every 5s
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [campaign?.status]);

  const toggleAgent = async () => {
    if (!campaign) return;
    const newStatus = campaign.status === 'active' ? 'draft' : 'active';
    const toastId = toast.loading(`${newStatus === 'active' ? 'Activating' : 'Deactivating'} AI Agent...`);
    
    try {
      await api.patch(`/campaigns/${campaign.id}`, { status: newStatus });
      setCampaign(prev => prev ? { ...prev, status: newStatus } : null);
      toast.success(`Agent ${newStatus === 'active' ? 'Activated' : 'Paused'}!`, { id: toastId });
    } catch (err) {
      toast.error('Failed to update agent status', { id: toastId });
    }
  };

  if (loading) {
    return <div className="p-12 text-center text-muted-foreground animate-pulse">Loading campaign details...</div>;
  }

  if (!campaign) {
    return <div className="p-12 text-center text-destructive">Campaign not found.</div>;
  }

  const emailsGenerated = leads.filter(l => l.draft_email).length;
  const emailsSent = leads.filter(l => l.draft_email?.status === 'sent').length;

  return (
    <div className="animate-in relative">
      <Link href="/dashboard/campaigns" className="inline-flex items-center text-sm text-muted-foreground hover:text-white mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4 mr-2" /> Back to Campaigns
      </Link>

      <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
              <Megaphone className="w-6 h-6" />
            </div>
            <h1 className="text-3xl font-bold">{campaign.name}</h1>
          </div>
          <p className="text-muted-foreground flex items-center gap-2">
            Status: 
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${campaign.status === 'active' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'}`}>
              {campaign.status === 'active' ? 'Agent Running' : 'Paused'}
            </span>
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={toggleAgent}
            className={`px-6 py-3 rounded-xl font-medium flex items-center gap-2 transition-all shadow-lg ${
              campaign.status === 'active' 
              ? 'bg-red-600 hover:bg-red-500 text-white shadow-red-500/20' 
              : 'bg-green-600 hover:bg-green-500 text-white shadow-green-500/20'
            }`}
          >
            {campaign.status === 'active' ? (
              <>
                <Bot className="w-5 h-5 fill-current" />
                Stop AI Agent
              </>
            ) : (
              <>
                <Activity className="w-5 h-5" />
                Activate AI Agent
              </>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="glass rounded-2xl p-6 border border-white/5">
          <h2 className="text-xl font-semibold mb-4">Live Agent Stats</h2>
          <div className="space-y-4">
            <div className="p-4 bg-black/20 rounded-xl border border-white/5 flex justify-between items-center">
              <p className="text-sm text-muted-foreground mb-1">Total Leads Assigned</p>
              <p className="text-2xl font-bold">{leads.length}</p>
            </div>
            <div className="p-4 bg-black/20 rounded-xl border border-white/5 flex justify-between items-center">
              <p className="text-sm text-muted-foreground mb-1">Drafts Generated</p>
              <p className="text-2xl font-bold text-purple-400">{emailsGenerated}</p>
            </div>
            <div className="p-4 bg-black/20 rounded-xl border border-white/5 flex justify-between items-center">
              <p className="text-sm text-muted-foreground mb-1">Emails Sent</p>
              <p className="text-2xl font-bold text-green-400">{emailsSent}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="glass rounded-2xl overflow-hidden border border-white/5 relative">
        {/* If active, show an animated scanning line at the top to indicate background worker is running */}
        {campaign.status === 'active' && (
          <div className="absolute top-0 left-0 h-1 bg-green-500/50 w-full animate-pulse shadow-[0_0_10px_rgba(34,197,94,0.5)]"></div>
        )}

        <div className="p-4 border-b border-white/10 flex items-center justify-between bg-secondary/20">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Users className="w-5 h-5 text-blue-400" /> Pipeline Queue
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-secondary/10">
                <th className="p-4 text-sm font-medium text-muted-foreground">Prospect Name</th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Company</th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Score</th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Agent Status</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={4} className="p-12 text-center text-muted-foreground">
                    No leads assigned to this campaign yet. Go to Sourcing to add leads.
                  </td>
                </tr>
              ) : (
                leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-white/5 transition-colors">
                    <td className="p-4">
                      <p className="font-medium">{lead.first_name} {lead.last_name}</p>
                      <p className="text-sm text-muted-foreground">{lead.email}</p>
                    </td>
                    <td className="p-4 text-sm">{lead.company}</td>
                    <td className="p-4">
                      {lead.lead_score === 'hot' && <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30">🔥 Hot</span>}
                      {lead.lead_score === 'warm' && <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-500/20 text-orange-400 border border-orange-500/30">Warm</span>}
                      {lead.lead_score === 'low' && <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">Low</span>}
                      {(!lead.lead_score || lead.lead_score === 'cold') && <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-500/20 text-slate-400 border border-slate-500/30">❄️ Cold</span>}
                    </td>
                    <td className="p-4">
                      {!lead.draft_email ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                          {campaign.status === 'active' ? 'Scanning...' : 'Pending'}
                        </span>
                      ) : lead.draft_email.status === 'sent' ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                          ✓ Sent Successfully
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
                          Draft Generated
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-right">
                      {lead.draft_email && (
                        <button
                          onClick={() => setSelectedEmail(lead.draft_email)}
                          className="text-sm font-medium text-blue-400 hover:text-blue-300 transition-colors"
                        >
                          View Email
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Email Viewer Modal */}
      {selectedEmail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass w-full max-w-2xl p-8 rounded-2xl border border-white/10 animate-in">
            <h2 className="text-2xl font-bold mb-4 text-gradient">AI Generated Draft</h2>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Subject</label>
                <div className="mt-1 p-3 bg-secondary/30 rounded-lg border border-white/5 font-medium">
                  {selectedEmail.subject}
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Body</label>
                <div className="mt-1 p-4 bg-secondary/30 rounded-lg border border-white/5 whitespace-pre-wrap text-sm leading-relaxed">
                  {selectedEmail.body}
                </div>
              </div>
            </div>
            <div className="mt-8 flex justify-end">
              <button 
                onClick={() => setSelectedEmail(null)}
                className="px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-medium transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

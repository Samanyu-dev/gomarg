'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { useParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { Megaphone, Users, ArrowLeft, Bot, Activity, Download, ListTree, Plus, Trash2, Mail, Clock, Sparkles } from 'lucide-react';
import Link from 'next/link';

interface Campaign {
  id: string;
  name: string;
  status: string;
  created_at: string;
  steps: CampaignStep[];
  settings: any;
}

interface CampaignStep {
  id: string;
  order_index: number;
  step_type: 'email' | 'wait' | 'ai_task';
  config: any;
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
    id: string;
    subject: string;
    body: string;
    status: string;
  } | null;
}

interface CampaignStats {
  total_sent: number;
  total_opens: number;
  total_clicks: number;
  total_replies: number;
  total_bounces: number;
  open_rate: number;
  ctr: number;
  reply_rate: number;
  bounce_rate: number;
  lead_score_breakdown: Record<string, number>;
}

export default function CampaignDetailPage() {
  const params = useParams();
  const campaignId = params?.id as string;
  
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [leads, setLeads] = useState<CampaignLead[]>([]);
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedEmail, setSelectedEmail] = useState<{id: string, subject: string, body: string, status: string} | null>(null);
  const [activeTab, setActiveTab] = useState<'queue' | 'playbook' | 'sourcing'>('queue');

  // Step builder state
  const [newStepType, setNewStepType] = useState<'email' | 'wait' | 'ai_task'>('email');
  const [newStepConfig, setNewStepConfig] = useState<any>({ goal: '' });
  const [isAddingStep, setIsAddingStep] = useState(false);

  // Sourcing settings state
  const [icpSettings, setIcpSettings] = useState({
    keywords: '',
    company: '',
    seniorities: [] as string[],
    limit_per_day: 5
  });
  const [isSavingIcp, setIsSavingIcp] = useState(false);

  const fetchData = async () => {
    try {
      const [campRes, leadsRes, statsRes] = await Promise.all([
        api.get(`/campaigns/${campaignId}`),
        api.get(`/campaigns/${campaignId}/leads`),
        api.get(`/campaigns/${campaignId}/stats`)
      ]);
      setCampaign(campRes.data);
      if (campRes.data.settings?.icp) {
        setIcpSettings(campRes.data.settings.icp);
      }
      setLeads(leadsRes.data);
      setStats(statsRes.data);
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
    
    if (campaign.status !== 'active' && (!campaign.steps || campaign.steps.length === 0)) {
      toast.error('Cannot activate agent: No steps in Playbook!');
      setActiveTab('playbook');
      return;
    }

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

  const handleAddStep = async () => {
    if (!campaign) return;
    setIsAddingStep(true);
    try {
      const order_index = campaign.steps ? campaign.steps.length : 0;
      await api.post(`/campaigns/${campaign.id}/steps`, {
        order_index,
        step_type: newStepType,
        config: newStepConfig
      });
      toast.success("Step added!");
      setNewStepConfig(newStepType === 'email' ? { goal: '' } : newStepType === 'wait' ? { wait_hours: 72 } : { task_name: 'analyze_reply' });
      fetchData(); // Refresh steps
    } catch (err) {
      toast.error("Failed to add step");
    } finally {
      setIsAddingStep(false);
    }
  };

  const handleDeleteStep = async (stepId: string) => {
    if (!campaign) return;
    try {
      await api.delete(`/campaigns/${campaign.id}/steps/${stepId}`);
      toast.success("Step deleted");
      fetchData(); // Refresh steps
    } catch (err) {
      toast.error("Failed to delete step");
    }
  };

  const handleSaveIcp = async () => {
    if (!campaign) return;
    setIsSavingIcp(true);
    try {
      await api.patch(`/campaigns/${campaign.id}`, {
        settings: { ...campaign.settings, icp: icpSettings }
      });
      toast.success("Autopilot sourcing settings saved!");
      fetchData();
    } catch (err) {
      toast.error("Failed to save ICP settings");
    } finally {
      setIsSavingIcp(false);
    }
  };

  const handleApproveEmail = async (emailId: string) => {
    const toastId = toast.loading('Approving and sending email...');
    try {
      await api.post(`/campaigns/${campaignId}/emails/${emailId}/approve`);
      toast.success('Email approved! The agent will send it shortly.', { id: toastId });
      setSelectedEmail(null);
      fetchData();
    } catch (err) {
      toast.error('Failed to approve email', { id: toastId });
    }
  };

  if (loading) {
    return <div className="p-12 text-center text-muted-foreground animate-pulse">Loading campaign details...</div>;
  }

  if (!campaign) {
    return <div className="p-12 text-center text-destructive">Campaign not found.</div>;
  }

  const downloadCSV = () => {
    if (!leads.length) {
      toast.error("No leads to export");
      return;
    }
    
    const headers = ['First Name', 'Last Name', 'Email', 'Company', 'Job Title', 'Score', 'Status'];
    const csvContent = [
      headers.join(','),
      ...leads.map(l => [
        `"${l.first_name}"`,
        `"${l.last_name}"`,
        `"${l.email}"`,
        `"${l.company}"`,
        `"${l.job_title}"`,
        `"${l.lead_score || 'cold'}"`,
        `"${l.draft_email?.status || 'pending'}"`
      ].join(','))
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `campaign_${campaign.name.replace(/\s+/g, '_')}_leads.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

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
        
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={downloadCSV}
            className="px-4 py-3 rounded-xl font-medium flex items-center gap-2 transition-all bg-white/5 hover:bg-white/10 border border-white/10"
            title="Export to CSV"
          >
            <Download className="w-5 h-5" />
            <span className="hidden sm:inline">Export CSV</span>
          </button>
          
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

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="glass rounded-2xl p-6 border border-white/5 flex flex-col justify-between">
          <p className="text-sm font-medium text-muted-foreground mb-2">Total Sent</p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-3xl font-bold">{stats?.total_sent || 0}</h3>
            <span className="text-xs text-muted-foreground">emails</span>
          </div>
        </div>
        
        <div className="glass rounded-2xl p-6 border border-white/5 flex flex-col justify-between">
          <p className="text-sm font-medium text-muted-foreground mb-2">Open Rate</p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-3xl font-bold text-blue-400">{stats?.open_rate || 0}%</h3>
            <span className="text-xs text-muted-foreground">({stats?.total_opens || 0})</span>
          </div>
        </div>

        <div className="glass rounded-2xl p-6 border border-white/5 flex flex-col justify-between">
          <p className="text-sm font-medium text-muted-foreground mb-2">Click Rate</p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-3xl font-bold text-purple-400">{stats?.ctr || 0}%</h3>
            <span className="text-xs text-muted-foreground">({stats?.total_clicks || 0})</span>
          </div>
        </div>

        <div className="glass rounded-2xl p-6 border border-white/5 flex flex-col justify-between">
          <p className="text-sm font-medium text-muted-foreground mb-2">Reply Rate</p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-3xl font-bold text-green-400">{stats?.reply_rate || 0}%</h3>
            <span className="text-xs text-muted-foreground">({stats?.total_replies || 0})</span>
          </div>
        </div>
      </div>

      <div className="flex border-b border-white/10 mb-6">
        <button
          onClick={() => setActiveTab('queue')}
          className={`px-6 py-3 font-medium text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'queue' ? 'border-blue-500 text-blue-400' : 'border-transparent text-muted-foreground hover:text-white'
          }`}
        >
          <Users className="w-4 h-4" /> Pipeline Queue
        </button>
        <button
          onClick={() => setActiveTab('playbook')}
          className={`px-6 py-3 font-medium text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'playbook' ? 'border-purple-500 text-purple-400' : 'border-transparent text-muted-foreground hover:text-white'
          }`}
        >
          <ListTree className="w-4 h-4" /> Sequence Playbook
        </button>
        <button
          onClick={() => setActiveTab('sourcing')}
          className={`px-6 py-3 font-medium text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'sourcing' ? 'border-green-500 text-green-400' : 'border-transparent text-muted-foreground hover:text-white'
          }`}
        >
          <Sparkles className="w-4 h-4" /> Autopilot Sourcing
        </button>
      </div>

      {activeTab === 'queue' && (
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
      )}

      {activeTab === 'playbook' && (
        <div className="space-y-6">
          <div className="glass rounded-2xl p-6 border border-white/5">
            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
              <ListTree className="w-5 h-5 text-purple-400" /> Campaign Playbook
            </h2>

            {/* Timeline */}
            <div className="space-y-4 mb-8">
              {(!campaign.steps || campaign.steps.length === 0) ? (
                <div className="p-8 text-center border border-white/10 rounded-xl bg-black/20 text-muted-foreground">
                  No steps defined yet. The agent will not run without a playbook.
                </div>
              ) : (
                campaign.steps.map((step, idx) => (
                  <div key={step.id} className="relative pl-8">
                    {idx !== campaign.steps.length - 1 && (
                      <div className="absolute left-[15px] top-8 bottom-[-16px] w-0.5 bg-white/10"></div>
                    )}
                    <div className="absolute left-0 top-2 w-8 h-8 rounded-full bg-secondary border border-white/10 flex items-center justify-center z-10">
                      <span className="text-xs font-bold text-muted-foreground">{idx + 1}</span>
                    </div>
                    
                    <div className="glass p-5 rounded-xl border border-white/5 flex items-center justify-between group">
                      <div className="flex items-center gap-4">
                        <div className={`p-3 rounded-xl ${
                          step.step_type === 'email' ? 'bg-blue-500/10 text-blue-400' :
                          step.step_type === 'wait' ? 'bg-yellow-500/10 text-yellow-400' :
                          'bg-purple-500/10 text-purple-400'
                        }`}>
                          {step.step_type === 'email' && <Mail className="w-5 h-5" />}
                          {step.step_type === 'wait' && <Clock className="w-5 h-5" />}
                          {step.step_type === 'ai_task' && <Sparkles className="w-5 h-5" />}
                        </div>
                        <div>
                          <h4 className="font-semibold capitalize text-lg">
                            {step.step_type === 'ai_task' ? 'AI Task' : step.step_type} Step
                          </h4>
                          <p className="text-sm text-muted-foreground mt-1">
                            {step.step_type === 'email' && `Goal: ${step.config.goal || 'General Outreach'}`}
                            {step.step_type === 'wait' && `Wait for ${step.config.wait_hours || 72} hours`}
                            {step.step_type === 'ai_task' && `Task: ${step.config.task_name}`}
                          </p>
                        </div>
                      </div>
                      <button 
                        onClick={() => handleDeleteStep(step.id)}
                        className="p-2 text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all bg-white/5 hover:bg-red-500/10 rounded-lg"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Add Step Builder */}
            <div className="mt-8 p-6 bg-secondary/30 rounded-xl border border-white/10">
              <h3 className="font-medium mb-4 flex items-center gap-2">
                <Plus className="w-4 h-4" /> Add New Step
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                <div className="md:col-span-1">
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5 uppercase tracking-wider">Step Type</label>
                  <select 
                    value={newStepType}
                    onChange={(e) => {
                      const type = e.target.value as any;
                      setNewStepType(type);
                      setNewStepConfig(type === 'email' ? { goal: '' } : type === 'wait' ? { wait_hours: 72 } : { task_name: 'analyze_reply' });
                    }}
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2.5 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all outline-none"
                  >
                    <option value="email">Email Draft</option>
                    <option value="wait">Time Delay</option>
                    <option value="ai_task">AI Task</option>
                  </select>
                </div>
                
                <div className="md:col-span-2">
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5 uppercase tracking-wider">Configuration</label>
                  {newStepType === 'email' && (
                    <input 
                      type="text" 
                      placeholder="e.g. Value-add follow up" 
                      value={newStepConfig.goal || ''}
                      onChange={e => setNewStepConfig({ goal: e.target.value })}
                      className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2.5 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all outline-none"
                    />
                  )}
                  {newStepType === 'wait' && (
                    <div className="relative">
                      <input 
                        type="number" 
                        min="1"
                        placeholder="Hours to wait" 
                        value={newStepConfig.wait_hours || ''}
                        onChange={e => setNewStepConfig({ wait_hours: parseInt(e.target.value) || 0 })}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2.5 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all outline-none pr-12"
                      />
                      <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">hrs</span>
                    </div>
                  )}
                  {newStepType === 'ai_task' && (
                    <select 
                      value={newStepConfig.task_name || 'analyze_reply'}
                      onChange={e => setNewStepConfig({ task_name: e.target.value })}
                      className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2.5 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all outline-none"
                    >
                      <option value="analyze_reply">Analyze Latest Reply</option>
                      <option value="update_score">Force Rescore Lead</option>
                    </select>
                  )}
                </div>

                <div className="md:col-span-1">
                  <button 
                    onClick={handleAddStep}
                    disabled={isAddingStep}
                    className="w-full bg-white/10 hover:bg-white/20 text-white font-medium py-2.5 px-4 rounded-lg transition-colors border border-white/5 disabled:opacity-50"
                  >
                    {isAddingStep ? 'Adding...' : 'Save Step'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'sourcing' && (
        <div className="space-y-6 animate-in">
          <div className="glass rounded-2xl p-6 border border-white/5 max-w-3xl">
            <h2 className="text-xl font-semibold mb-2 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-green-400" /> Autopilot Sourcing
            </h2>
            <p className="text-sm text-muted-foreground mb-6">
              Define your Ideal Customer Profile (ICP). While the agent is active, it will automatically search Apollo for new contacts matching these filters and inject them into this campaign daily.
            </p>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">Keywords</label>
                <input 
                  type="text" 
                  placeholder="e.g. Data Engineering, Growth" 
                  value={icpSettings.keywords || ''}
                  onChange={e => setIcpSettings({ ...icpSettings, keywords: e.target.value })}
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-green-500/50 focus:ring-1 focus:ring-green-500/50 transition-all outline-none"
                />
                <p className="text-xs text-muted-foreground mt-1.5">Searches profiles and titles for these keywords.</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Company Name</label>
                <input 
                  type="text" 
                  placeholder="e.g. Optum, Microsoft" 
                  value={icpSettings.company || ''}
                  onChange={e => setIcpSettings({ ...icpSettings, company: e.target.value })}
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-green-500/50 focus:ring-1 focus:ring-green-500/50 transition-all outline-none"
                />
                <p className="text-xs text-muted-foreground mt-1.5">Target a specific company name.</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Seniority Levels</label>
                <select 
                  multiple
                  value={icpSettings.seniorities || []}
                  onChange={e => {
                    const values = Array.from(e.target.selectedOptions, option => option.value);
                    setIcpSettings({ ...icpSettings, seniorities: values });
                  }}
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-green-500/50 focus:ring-1 focus:ring-green-500/50 transition-all outline-none min-h-[120px]"
                >
                  <option value="owner">Owner / Founder</option>
                  <option value="c_suite">CXO / C-Suite</option>
                  <option value="vp">VP</option>
                  <option value="director">Director</option>
                  <option value="manager">Manager</option>
                </select>
                <p className="text-xs text-muted-foreground mt-1.5">Hold CMD/CTRL to select multiple seniorities.</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Daily Sourcing Limit</label>
                <select 
                  value={icpSettings.limit_per_day}
                  onChange={e => setIcpSettings({ ...icpSettings, limit_per_day: parseInt(e.target.value) })}
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-green-500/50 focus:ring-1 focus:ring-green-500/50 transition-all outline-none"
                >
                  <option value={5}>5 leads per day</option>
                  <option value={10}>10 leads per day</option>
                  <option value={25}>25 leads per day</option>
                  <option value={50}>50 leads per day</option>
                </select>
                <p className="text-xs text-muted-foreground mt-1.5">Maximum number of new leads the agent will add automatically every 24 hours.</p>
              </div>

              <div className="pt-4 border-t border-white/5">
                <button 
                  onClick={handleSaveIcp}
                  disabled={isSavingIcp}
                  className="bg-green-600 hover:bg-green-500 text-white font-medium py-3 px-6 rounded-xl transition-all shadow-lg shadow-green-500/20 disabled:opacity-50"
                >
                  {isSavingIcp ? 'Saving...' : 'Save Autopilot Settings'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
            <div className="mt-8 flex justify-end gap-3">
              <button 
                onClick={() => setSelectedEmail(null)}
                className="px-6 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-medium transition-colors"
              >
                Close
              </button>
              {selectedEmail.status === 'draft' && (
                <button 
                  onClick={() => handleApproveEmail(selectedEmail.id)}
                  className="px-6 py-2 bg-green-600 hover:bg-green-500 rounded-lg font-medium transition-colors shadow-lg shadow-green-500/20 flex items-center gap-2"
                >
                  <Mail className="w-4 h-4" />
                  Approve & Send
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

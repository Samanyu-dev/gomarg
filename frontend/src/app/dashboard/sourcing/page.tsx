'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import toast from 'react-hot-toast';
import { RefreshCw, Search, CheckSquare } from 'lucide-react';

interface Lead {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  job_title: string;
  company: string;
  phone_number?: string;
  city?: string;
  state?: string;
  country?: string;
  industry?: string;
  status: string;
}

interface Campaign {
  id: string;
  name: string;
}

export default function SourcingPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [selectedEmail, setSelectedEmail] = useState<{subject: string, full_body: string} | null>(null);

  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<string>>(new Set());
  const [selectedCampaignId, setSelectedCampaignId] = useState('');

  const [searchQuery, setSearchQuery] = useState('');
  const [titleFilter, setTitleFilter] = useState('');
  const [industryFilter, setIndustryFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');

  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);
  const [filterParams, setFilterParams] = useState({
    q_keywords: '',
    per_page: '10'
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [leadsRes, campaignsRes] = await Promise.all([
        api.get('/leads'),
        api.get('/campaigns')
      ]);
      setLeads(leadsRes.data);
      setCampaigns(campaignsRes.data);
    } catch (err: any) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleGenerateEmail = async (leadId: string) => {
    setGeneratingId(leadId);
    const toastId = toast.loading('AI is writing email...');
    try {
      const res = await api.post(`/generate/email/${leadId}`, {
        campaign_goal: 'Introduce GoMarg AI Sales automation platform and book a 15 min demo'
      });
      setSelectedEmail(res.data);
      toast.success('Email generated successfully!', { id: toastId });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to generate email', { id: toastId });
    } finally {
      setGeneratingId(null);
    }
  };

  const handleGetLeads = async (e: React.FormEvent) => {
    e.preventDefault();
    setSyncing(true);
    setIsFilterModalOpen(false);
    const toastId = toast.loading('Fetching contacts from Apollo...');
    
    try {
      const res = await api.post('/sourcing/apollo', {
        page: 1,
        per_page: parseInt(filterParams.per_page),
        q_keywords: filterParams.q_keywords || undefined
      });
      toast.success(`Successfully imported contacts!`, { id: toastId });
      await fetchData(); // refresh the table
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to sync leads', { id: toastId });
    } finally {
      setSyncing(false);
    }
  };

  const filteredLeads = leads.filter(lead => {
    const matchesSearch = !searchQuery || 
      `${lead.first_name} ${lead.last_name} ${lead.email} ${lead.company}`.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTitle = !titleFilter || (lead.job_title && lead.job_title.toLowerCase().includes(titleFilter.toLowerCase()));
    const matchesIndustry = !industryFilter || (lead.industry && lead.industry.toLowerCase().includes(industryFilter.toLowerCase()));
    const matchesLocation = !locationFilter || 
      `${lead.city || ''} ${lead.state || ''} ${lead.country || ''}`.toLowerCase().includes(locationFilter.toLowerCase());
    return matchesSearch && matchesTitle && matchesIndustry && matchesLocation;
  });

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedLeadIds(new Set(filteredLeads.map(l => l.id)));
    } else {
      setSelectedLeadIds(new Set());
    }
  };

  const handleSelectLead = (leadId: string) => {
    const newSet = new Set(selectedLeadIds);
    if (newSet.has(leadId)) {
      newSet.delete(leadId);
    } else {
      newSet.add(leadId);
    }
    setSelectedLeadIds(newSet);
  };

  const handleAddToCampaign = async () => {
    if (!selectedCampaignId || selectedLeadIds.size === 0) return;
    const toastId = toast.loading('Adding leads to campaign...');
    try {
      await api.post(`/campaigns/${selectedCampaignId}/leads`, {
        lead_ids: Array.from(selectedLeadIds)
      });
      toast.success('Leads added to campaign successfully!', { id: toastId });
      setSelectedLeadIds(new Set()); // Clear selection
    } catch (err: any) {
      toast.error('Failed to add leads to campaign', { id: toastId });
    }
  };

  return (
    <div className="animate-in">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Lead Sourcing</h1>
          <p className="text-muted-foreground">Search and import your saved contacts from Apollo.</p>
        </div>
        
        <button
          onClick={() => setIsFilterModalOpen(true)}
          disabled={syncing}
          className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-medium flex items-center gap-2 transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50"
        >
          <RefreshCw className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Fetching...' : 'Get More Leads'}
        </button>
      </div>

      <div className="glass rounded-2xl overflow-hidden border border-white/5">
        <div className="p-4 border-b border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between bg-secondary/20 gap-4">
          <div className="flex flex-wrap items-center gap-4 w-full">
            <div className="relative w-64">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input 
                type="text" 
                placeholder="Search name, email, company..." 
                className="w-full bg-black/20 border border-white/10 rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <input
              type="text"
              placeholder="Title (e.g. Director)..."
              className="w-48 bg-black/20 border border-white/10 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
              value={titleFilter}
              onChange={(e) => setTitleFilter(e.target.value)}
            />
            <input
              type="text"
              placeholder="Industry..."
              className="w-48 bg-black/20 border border-white/10 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
              value={industryFilter}
              onChange={(e) => setIndustryFilter(e.target.value)}
            />
            <input
              type="text"
              placeholder="Location..."
              className="w-48 bg-black/20 border border-white/10 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500/50"
              value={locationFilter}
              onChange={(e) => setLocationFilter(e.target.value)}
            />
            <div className="text-sm text-muted-foreground whitespace-nowrap ml-auto">
              {filteredLeads.length} / {leads.length} leads
            </div>
          </div>

          {selectedLeadIds.size > 0 && (
            <div className="flex items-center gap-2 animate-in slide-in-from-right-4 fade-in">
              <span className="text-sm font-medium mr-2">{selectedLeadIds.size} selected</span>
              <select 
                className="bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50"
                value={selectedCampaignId}
                onChange={(e) => setSelectedCampaignId(e.target.value)}
              >
                <option value="">Select a Campaign...</option>
                {campaigns.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <button 
                onClick={handleAddToCampaign}
                disabled={!selectedCampaignId}
                className="bg-white/10 hover:bg-white/20 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                <CheckSquare className="w-4 h-4" /> Add
              </button>
            </div>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-secondary/10">
                <th className="p-4 w-12 text-center">
                  <input 
                    type="checkbox" 
                    className="rounded border-white/20 bg-black/50"
                    onChange={handleSelectAll}
                    checked={filteredLeads.length > 0 && selectedLeadIds.size === filteredLeads.length}
                  />
                </th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Name</th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Title</th>
                <th className="p-4 text-sm font-medium text-muted-foreground whitespace-nowrap">Company & Industry</th>
                <th className="p-4 text-sm font-medium text-muted-foreground whitespace-nowrap">Contact & Location</th>
                <th className="p-4 text-sm font-medium text-muted-foreground">Status</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-muted-foreground">
                    Loading leads...
                  </td>
                </tr>
              ) : filteredLeads.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-12 text-center">
                    <p className="text-lg font-medium mb-2">No leads found</p>
                    <p className="text-muted-foreground mb-4">Try adjusting your filters or fetch more contacts from Apollo.</p>
                  </td>
                </tr>
              ) : (
                filteredLeads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-white/5 transition-colors">
                    <td className="p-4 text-center">
                      <input 
                        type="checkbox" 
                        className="rounded border-white/20 bg-black/50"
                        checked={selectedLeadIds.has(lead.id)}
                        onChange={() => handleSelectLead(lead.id)}
                      />
                    </td>
                    <td className="p-4">
                      <p className="font-medium">{lead.first_name} {lead.last_name}</p>
                      <p className="text-sm text-muted-foreground">{lead.email}</p>
                    </td>
                    <td className="p-4 text-sm">{lead.job_title}</td>
                    <td className="p-4 text-sm">
                      <p className="font-medium">{lead.company}</p>
                      {lead.industry && <p className="text-xs text-muted-foreground mt-0.5">{lead.industry}</p>}
                    </td>
                    <td className="p-4 text-sm">
                      {lead.phone_number ? (
                        <p className="font-medium text-blue-400">{lead.phone_number}</p>
                      ) : (
                        <p className="text-muted-foreground italic text-xs">No Phone</p>
                      )}
                      {(lead.city || lead.country) && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {lead.city}{lead.city && lead.country ? ', ' : ''}{lead.country}
                        </p>
                      )}
                    </td>
                    <td className="p-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-2">
                        {lead.status}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      <button
                        onClick={() => handleGenerateEmail(lead.id)}
                        disabled={generatingId === lead.id}
                        className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all shadow-lg shadow-purple-500/20 disabled:opacity-50"
                      >
                        {generatingId === lead.id ? 'Generating...' : 'Generate AI Email'}
                      </button>
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
                  {selectedEmail.full_body}
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

      {/* Sourcing Filter Modal */}
      {isFilterModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass w-full max-w-md p-6 rounded-2xl border border-white/10 animate-in">
            <h2 className="text-2xl font-bold mb-4">Fetch More Leads</h2>
            <p className="text-sm text-muted-foreground mb-6">Search your saved Apollo contacts to import them into GoMarg.</p>
            <form onSubmit={handleGetLeads}>
              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium mb-2">Search Keywords (Optional)</label>
                  <input 
                    type="text" 
                    placeholder="e.g. CEO, Software, Apple"
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500/50"
                    value={filterParams.q_keywords}
                    onChange={(e) => setFilterParams({...filterParams, q_keywords: e.target.value})}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Searches name, title, company within your saved contacts.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Number of Leads to Fetch</label>
                  <select
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500/50"
                    value={filterParams.per_page}
                    onChange={(e) => setFilterParams({...filterParams, per_page: e.target.value})}
                  >
                    <option value="10">10 Leads</option>
                    <option value="25">25 Leads</option>
                    <option value="50">50 Leads</option>
                    <option value="100">100 Leads</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={() => setIsFilterModalOpen(false)}
                  className="px-4 py-2 rounded-lg hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-all"
                >
                  Import Leads
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

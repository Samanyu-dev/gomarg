'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import toast from 'react-hot-toast';
import { RefreshCw, Search, CheckSquare, Sparkles, X } from 'lucide-react';

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
  const [selectedEmail, setSelectedEmail] = useState<{ subject: string, full_body: string } | null>(null);

  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<string>>(new Set());
  const [selectedCampaignId, setSelectedCampaignId] = useState('');

  const [searchQuery, setSearchQuery] = useState('');
  const [titleFilter, setTitleFilter] = useState('');
  const [industryFilter, setIndustryFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');

  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);

  // ── New: 3-field Apollo search params ──
  const [filterParams, setFilterParams] = useState({
    role: '',
    sector: '',
    company: '',
    per_page: '10'
  });

  // ── New: Email customization modal state ──
  const [isEmailCustomModalOpen, setIsEmailCustomModalOpen] = useState(false);
  const [emailCustomLeadId, setEmailCustomLeadId] = useState<string | null>(null);
  const [emailCustomParams, setEmailCustomParams] = useState({
    campaign_goal: 'Introduce our product and book a 15 min demo',
    tone: 'professional',
    writing_style: 'concise',
    cta_type: 'reply_question',
    sender_name: '',
    sender_company: '',
    custom_instructions: ''
  });

  const [manualLead, setManualLead] = useState({
    first_name: '',
    last_name: '',
    email: '',
    company: '',
    job_title: ''
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

  // ── Open customization modal for a lead ──
  const openEmailCustomModal = (leadId: string) => {
    setEmailCustomLeadId(leadId);
    setIsEmailCustomModalOpen(true);
  };

  // ── Generate email with customization ──
  const handleGenerateEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailCustomLeadId) return;

    setIsEmailCustomModalOpen(false);
    setGeneratingId(emailCustomLeadId);
    const toastId = toast.loading('AI is writing a personalised email...');

    try {
      const payload: any = {
        campaign_goal: emailCustomParams.campaign_goal,
        tone: emailCustomParams.tone,
        writing_style: emailCustomParams.writing_style,
        cta_type: emailCustomParams.cta_type,
      };
      if (emailCustomParams.sender_name) payload.sender_name = emailCustomParams.sender_name;
      if (emailCustomParams.sender_company) payload.sender_company = emailCustomParams.sender_company;
      if (emailCustomParams.custom_instructions) payload.custom_instructions = emailCustomParams.custom_instructions;

      const res = await api.post(`/generate/email/${emailCustomLeadId}`, payload);
      setSelectedEmail(res.data);
      toast.success('Email generated successfully!', { id: toastId });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to generate email', { id: toastId });
    } finally {
      setGeneratingId(null);
      setEmailCustomLeadId(null);
    }
  };

  // ── Fetch leads from Apollo with 3 structured fields ──
  const handleGetLeads = async (e: React.FormEvent) => {
    e.preventDefault();
    setSyncing(true);
    setIsFilterModalOpen(false);
    const toastId = toast.loading('Fetching contacts from Apollo...');

    try {
      const payload: any = {
        page: 1,
        per_page: parseInt(filterParams.per_page),
      };
      if (filterParams.role) payload.role = filterParams.role;
      if (filterParams.sector) payload.sector = filterParams.sector;
      if (filterParams.company) payload.company = filterParams.company;

      const res = await api.post('/sourcing/apollo', payload);
      toast.success(`Successfully imported ${res.data.leads_imported} contacts!`, { id: toastId });
      await fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to sync leads', { id: toastId });
    } finally {
      setSyncing(false);
    }
  };

  const handleCreateManualLead = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsManualModalOpen(false);
    const toastId = toast.loading('Creating lead...');
    try {
      await api.post('/leads', {
        ...manualLead,
        status: 'new'
      });
      toast.success('Lead created successfully!', { id: toastId });
      setManualLead({ first_name: '', last_name: '', email: '', company: '', job_title: '' });
      await fetchData();
    } catch (err: any) {
      toast.error('Failed to create lead', { id: toastId });
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

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsManualModalOpen(true)}
            className="bg-white/10 hover:bg-white/20 text-white px-6 py-3 rounded-xl font-medium transition-all border border-white/10"
          >
            Add Lead Manually
          </button>
          <button
            onClick={() => setIsFilterModalOpen(true)}
            disabled={syncing}
            className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-medium flex items-center gap-2 transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Fetching...' : 'Get Apollo Leads'}
          </button>
        </div>
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
                        onClick={() => openEmailCustomModal(lead.id)}
                        disabled={generatingId === lead.id}
                        className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all shadow-lg shadow-purple-500/20 disabled:opacity-50 flex items-center gap-1.5 ml-auto"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
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
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-2">Email Preview</label>
                <div className="bg-white p-8 rounded-xl shadow-2xl overflow-y-auto max-h-[60vh] border border-white/10">
                  <div 
                    className="whitespace-normal text-left"
                    dangerouslySetInnerHTML={{ __html: selectedEmail.full_body }}
                  />
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

      {/* ═══════════════════════════════════════════════════
          SOURCING FILTER MODAL — 3 structured fields
          ═══════════════════════════════════════════════════ */}
      {isFilterModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass w-full max-w-lg p-6 rounded-2xl border border-white/10 animate-in">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-2xl font-bold">Fetch Apollo Leads</h2>
              <button onClick={() => setIsFilterModalOpen(false)} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors">
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground mb-6">Search your saved Apollo contacts with targeted filters.</p>
            <form onSubmit={handleGetLeads}>
              <div className="space-y-4 mb-6">
                {/* Role */}
                <div>
                  <label className="block text-sm font-medium mb-2">Role / Job Title</label>
                  <input
                    type="text"
                    placeholder="e.g. Data Engineer, VP Sales, Product Manager"
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500/50 transition-colors"
                    value={filterParams.role}
                    onChange={(e) => setFilterParams({ ...filterParams, role: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Filter contacts by their job title or role.</p>
                </div>
                {/* Sector */}
                <div>
                  <label className="block text-sm font-medium mb-2">Sector / Industry</label>
                  <input
                    type="text"
                    placeholder="e.g. Healthcare, FinTech, SaaS"
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500/50 transition-colors"
                    value={filterParams.sector}
                    onChange={(e) => setFilterParams({ ...filterParams, sector: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Filter by industry or sector keywords.</p>
                </div>
                {/* Company */}
                <div>
                  <label className="block text-sm font-medium mb-2">Company</label>
                  <input
                    type="text"
                    placeholder="e.g. Apple, Google, Optum"
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500/50 transition-colors"
                    value={filterParams.company}
                    onChange={(e) => setFilterParams({ ...filterParams, company: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Filter by specific company name.</p>
                </div>
                {/* Number of leads */}
                <div>
                  <label className="block text-sm font-medium mb-2">Number of Leads to Fetch</label>
                  <select
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500/50 transition-colors"
                    value={filterParams.per_page}
                    onChange={(e) => setFilterParams({ ...filterParams, per_page: e.target.value })}
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
                  className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-medium transition-all shadow-lg shadow-blue-500/20"
                >
                  Import Leads
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════
          EMAIL CUSTOMIZATION MODAL — tone, style, CTA
          ═══════════════════════════════════════════════════ */}
      {isEmailCustomModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass w-full max-w-lg p-6 rounded-2xl border border-white/10 animate-in max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-2xl font-bold flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-400" /> Customise AI Email
              </h2>
              <button onClick={() => setIsEmailCustomModalOpen(false)} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors">
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground mb-6">Fine-tune how the AI writes this email. The more context you give, the better the output.</p>
            <form onSubmit={handleGenerateEmail}>
              <div className="space-y-4 mb-6">
                {/* Campaign Goal */}
                <div>
                  <label className="block text-sm font-medium mb-2">Campaign Goal</label>
                  <input
                    type="text"
                    placeholder="e.g. Book a 15-min product demo"
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-purple-500/50 transition-colors"
                    value={emailCustomParams.campaign_goal}
                    onChange={(e) => setEmailCustomParams({ ...emailCustomParams, campaign_goal: e.target.value })}
                  />
                </div>

                {/* Tone + Writing Style — side by side */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Tone</label>
                    <select
                      className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-purple-500/50 transition-colors"
                      value={emailCustomParams.tone}
                      onChange={(e) => setEmailCustomParams({ ...emailCustomParams, tone: e.target.value })}
                    >
                      <option value="professional">Professional</option>
                      <option value="casual">Casual</option>
                      <option value="bold">Bold</option>
                      <option value="friendly">Friendly</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Writing Style</label>
                    <select
                      className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-purple-500/50 transition-colors"
                      value={emailCustomParams.writing_style}
                      onChange={(e) => setEmailCustomParams({ ...emailCustomParams, writing_style: e.target.value })}
                    >
                      <option value="concise">Concise</option>
                      <option value="storytelling">Storytelling</option>
                      <option value="data-driven">Data-Driven</option>
                    </select>
                  </div>
                </div>

                {/* CTA Type */}
                <div>
                  <label className="block text-sm font-medium mb-2">Call to Action</label>
                  <select
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-purple-500/50 transition-colors"
                    value={emailCustomParams.cta_type}
                    onChange={(e) => setEmailCustomParams({ ...emailCustomParams, cta_type: e.target.value })}
                  >
                    <option value="reply_question">Ask a Question (easy reply)</option>
                    <option value="book_meeting">Book a Meeting</option>
                    <option value="visit_link">Visit a Link / Resource</option>
                  </select>
                </div>

                {/* Sender Name + Company — side by side */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Your Name <span className="text-muted-foreground text-xs">(optional)</span></label>
                    <input
                      type="text"
                      placeholder="e.g. Samanyu"
                      className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-purple-500/50 transition-colors"
                      value={emailCustomParams.sender_name}
                      onChange={(e) => setEmailCustomParams({ ...emailCustomParams, sender_name: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Your Company <span className="text-muted-foreground text-xs">(optional)</span></label>
                    <input
                      type="text"
                      placeholder="e.g. GoMarg"
                      className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-purple-500/50 transition-colors"
                      value={emailCustomParams.sender_company}
                      onChange={(e) => setEmailCustomParams({ ...emailCustomParams, sender_company: e.target.value })}
                    />
                  </div>
                </div>

                {/* Custom Instructions */}
                <div>
                  <label className="block text-sm font-medium mb-2">Custom Instructions <span className="text-muted-foreground text-xs">(optional)</span></label>
                  <textarea
                    rows={3}
                    placeholder="e.g. Mention our recent Series A funding, don't use emojis, keep it under 50 words..."
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-purple-500/50 transition-colors resize-none"
                    value={emailCustomParams.custom_instructions}
                    onChange={(e) => setEmailCustomParams({ ...emailCustomParams, custom_instructions: e.target.value })}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsEmailCustomModalOpen(false)}
                  className="px-4 py-2 rounded-lg hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded-lg font-medium transition-all shadow-lg shadow-purple-500/20 flex items-center gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  Generate Email
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Lead Modal */}
      {isManualModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass w-full max-w-md p-6 rounded-2xl border border-white/10 animate-in">
            <h2 className="text-2xl font-bold mb-4">Add Test Lead</h2>
            <p className="text-sm text-muted-foreground mb-6">Create a manual lead (e.g. your own email) to test campaign automations.</p>
            <form onSubmit={handleCreateManualLead}>
              <div className="space-y-4 mb-6">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">First Name</label>
                    <input
                      required
                      type="text"
                      className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500/50"
                      value={manualLead.first_name}
                      onChange={(e) => setManualLead({ ...manualLead, first_name: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Last Name</label>
                    <input
                      required
                      type="text"
                      className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500/50"
                      value={manualLead.last_name}
                      onChange={(e) => setManualLead({ ...manualLead, last_name: e.target.value })}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Email Address</label>
                  <input
                    required
                    type="email"
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500/50"
                    value={manualLead.email}
                    onChange={(e) => setManualLead({ ...manualLead, email: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Company</label>
                  <input
                    type="text"
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500/50"
                    value={manualLead.company}
                    onChange={(e) => setManualLead({ ...manualLead, company: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Job Title</label>
                  <input
                    type="text"
                    className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500/50"
                    value={manualLead.job_title}
                    onChange={(e) => setManualLead({ ...manualLead, job_title: e.target.value })}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsManualModalOpen(false)}
                  className="px-4 py-2 rounded-lg hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-all"
                >
                  Create Lead
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import toast from 'react-hot-toast';
import Link from 'next/link';
import { Plus, Megaphone, ArrowRight } from 'lucide-react';

interface Campaign {
  id: string;
  name: string;
  status: string;
  created_at: string;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newCampaignName, setNewCampaignName] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchCampaigns = async () => {
    setLoading(true);
    try {
      const res = await api.get('/campaigns');
      setCampaigns(res.data);
    } catch (err) {
      toast.error('Failed to load campaigns');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCampaignName) return;
    setCreating(true);
    try {
      await api.post('/campaigns', {
        name: newCampaignName,
        status: 'draft',
        settings: {},
        steps: []
      });
      toast.success('Campaign created!');
      setIsModalOpen(false);
      setNewCampaignName('');
      fetchCampaigns();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create campaign');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="animate-in relative">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Campaigns</h1>
          <p className="text-muted-foreground">Manage your AI email outreach campaigns.</p>
        </div>
        
        <button
          onClick={() => setIsModalOpen(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-medium flex items-center gap-2 transition-all shadow-lg shadow-blue-500/20"
        >
          <Plus className="w-5 h-5" />
          Create Campaign
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          <div className="col-span-full p-12 text-center text-muted-foreground">Loading campaigns...</div>
        ) : campaigns.length === 0 ? (
          <div className="col-span-full glass p-12 text-center rounded-2xl border border-white/5">
            <Megaphone className="w-12 h-12 text-blue-500/50 mx-auto mb-4" />
            <p className="text-lg font-medium mb-2">No campaigns yet</p>
            <p className="text-muted-foreground mb-4">Create your first campaign to start generating AI emails.</p>
          </div>
        ) : (
          campaigns.map((camp) => (
            <Link 
              href={`/dashboard/campaigns/${camp.id}`} 
              key={camp.id}
              className="glass p-6 rounded-2xl border border-white/5 hover:border-blue-500/30 transition-all duration-300 group block"
            >
              <div className="flex justify-between items-start mb-4">
                <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400">
                  <Megaphone className="w-6 h-6" />
                </div>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-secondary text-muted-foreground border border-white/10">
                  {camp.status}
                </span>
              </div>
              <h3 className="text-xl font-bold mb-1 truncate">{camp.name}</h3>
              <p className="text-sm text-muted-foreground mb-4">Created {new Date(camp.created_at).toLocaleDateString()}</p>
              
              <div className="flex items-center text-blue-400 text-sm font-medium group-hover:translate-x-1 transition-transform">
                Manage Campaign <ArrowRight className="w-4 h-4 ml-1" />
              </div>
            </Link>
          ))
        )}
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass w-full max-w-md p-6 rounded-2xl border border-white/10 animate-in">
            <h2 className="text-2xl font-bold mb-4">New Campaign</h2>
            <form onSubmit={handleCreateCampaign}>
              <div className="mb-6">
                <label className="block text-sm font-medium mb-2">Campaign Name</label>
                <input 
                  type="text" 
                  autoFocus
                  required
                  placeholder="e.g. Q3 Director Outreach"
                  className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500/50"
                  value={newCampaignName}
                  onChange={(e) => setNewCampaignName(e.target.value)}
                />
              </div>
              <div className="flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={creating || !newCampaignName}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-all disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { StatsGrid, CampaignTable } from '../components';
import { useSSE } from '../hooks/useSSE';
import { api } from '../api/client';

interface Lead {
  lead_id: string;
  name: string;
  phone: string;
  score: number;
  category: string;
  campaign_id: string;
}

interface AnalyticsData {
  total_leads: number;
  hot: number;
  warm: number;
  cold: number;
  in_progress: number;
  completed: number;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { connected } = useSSE();

  const { data: campaignsData } = useQuery<{ success: boolean; data: { campaign_id: string; name: string; status: string; created_at: string; stats?: Record<string, number> }[] }>({
    queryKey: ['campaigns'],
    queryFn: () => api.get('/api/campaigns'),
    refetchInterval: 3000,
  });

  const { data: analyticsData } = useQuery<{ success: boolean; data: AnalyticsData }>({
    queryKey: ['analytics-summary'],
    queryFn: () => api.get('/api/analytics/summary'),
    refetchInterval: 3000,
  });

  const { data: leadsData } = useQuery<{ success: boolean; data: Lead[] }>({
    queryKey: ['top-leads'],
    queryFn: () => api.get('/api/leads?sort=score&limit=5'),
    refetchInterval: 3000,
  });

  const campaigns = campaignsData?.data ?? [];
  const analytics = analyticsData?.data;
  const topLeads = leadsData?.data ?? [];

  const stats = {
    total: analytics?.total_leads ?? 0,
    hot: analytics?.hot ?? 0,
    warm: analytics?.warm ?? 0,
    cold: analytics?.cold ?? 0,
    in_progress: analytics?.in_progress ?? 0,
    completed: analytics?.completed ?? 0,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <span className={`flex items-center gap-1.5 text-xs font-medium ${connected ? 'text-green-600' : 'text-gray-400'}`}>
          <span className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`} />
          {connected ? 'Live' : 'Connecting...'}
        </span>
      </div>

      <StatsGrid stats={stats} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Recent Campaigns</h2>
          <CampaignTable
            campaigns={campaigns.slice(0, 5)}
            onView={(id) => navigate(`/campaigns/${id}`)}
          />
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Top Leads</h2>
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm divide-y divide-gray-50">
            {topLeads.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-gray-400">No leads yet.</p>
            ) : (
              topLeads.map((lead) => (
                <button
                  key={lead.lead_id}
                  onClick={() => navigate(`/leads/${lead.lead_id}`)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-900">{lead.name}</p>
                    <p className="text-xs text-gray-400">{lead.phone}</p>
                  </div>
                  <span className="text-sm font-bold text-blue-600">{lead.score}</span>
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

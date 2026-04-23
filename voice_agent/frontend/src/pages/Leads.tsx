import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { LeadScoreBar, SentimentBadge } from '../components';
import { useCampaigns } from '../hooks/useCampaign';
import { api } from '../api/client';

interface Lead {
  lead_id: string;
  name: string;
  phone: string;
  score: number;
  category: string;
  sentiment?: string;
  campaign_id: string;
}

const CATEGORIES = ['All', 'Hot', 'Warm', 'Cold', 'Not_Interested'];

export default function Leads() {
  const navigate = useNavigate();
  const [campaignFilter, setCampaignFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [minScore, setMinScore] = useState(0);
  const [maxScore, setMaxScore] = useState(100);

  const { data: campaignsData } = useCampaigns();
  const campaigns = campaignsData?.data ?? [];

  const params = new URLSearchParams();
  if (campaignFilter) params.set('campaign_id', campaignFilter);
  if (categoryFilter !== 'All') params.set('category', categoryFilter);
  params.set('min_score', String(minScore));
  params.set('max_score', String(maxScore));

  const { data: leadsData, isLoading } = useQuery<{ success: boolean; data: Lead[] }>({
    queryKey: ['leads', campaignFilter, categoryFilter, minScore, maxScore],
    queryFn: () => api.get(`/api/leads?${params.toString()}`),
    refetchInterval: 5000,
  });

  const leads = leadsData?.data ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Leads</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">Campaign</label>
          <select
            value={campaignFilter}
            onChange={(e) => setCampaignFilter(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Campaigns</option>
            {campaigns.map((c) => (
              <option key={c.campaign_id} value={c.campaign_id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">Category</label>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c === 'Not_Interested' ? 'Not Interested' : c}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">Min Score</label>
          <input
            type="number"
            min={0}
            max={100}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-20 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">Max Score</label>
          <input
            type="number"
            min={0}
            max={100}
            value={maxScore}
            onChange={(e) => setMaxScore(Number(e.target.value))}
            className="w-20 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <p className="text-sm text-gray-400">Loading leads...</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-100">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Phone</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Score</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Category</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Sentiment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {leads.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">No leads match the filters.</td>
                  </tr>
                ) : (
                  leads.map((lead) => (
                    <tr
                      key={lead.lead_id}
                      onClick={() => navigate(`/leads/${lead.lead_id}`)}
                      className="cursor-pointer hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{lead.name}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">{lead.phone}</td>
                      <td className="px-4 py-3 w-32">
                        <LeadScoreBar score={lead.score} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 capitalize">{lead.category}</td>
                      <td className="px-4 py-3">
                        {lead.sentiment ? (
                          <SentimentBadge sentiment={lead.sentiment} />
                        ) : (
                          <span className="text-xs text-gray-300">—</span>
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
    </div>
  );
}

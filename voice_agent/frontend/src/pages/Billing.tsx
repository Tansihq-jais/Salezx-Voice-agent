import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { api } from '../api/client';

interface BillingSummary {
  total_calls: number;
  total_minutes: number;
  total_cost: number;
  rate_per_min: number;
}

interface BillingTier {
  name: string;
  rate_per_min: number;
  next_tier_info: string | null;
}

interface CampaignRow {
  campaign_id: string;
  campaign_name: string;
  calls: number;
  total_minutes: number;
  total_cost: number;
}

interface DailyRow {
  date: string;
  calls: number;
  cost: number;
}

interface BillingData {
  month: string;
  summary: BillingSummary;
  tier: BillingTier;
  byCampaign: CampaignRow[];
  daily: DailyRow[];
  availableMonths: string[];
}

export default function Billing() {
  const [selectedMonth, setSelectedMonth] = useState('');

  const { data, isLoading } = useQuery<{ success: boolean; data: BillingData }>({
    queryKey: ['billing', selectedMonth],
    queryFn: () => api.get(`/api/billing${selectedMonth ? `?month=${selectedMonth}` : ''}`),
  });

  const billing = data?.data;

  if (isLoading) return <p className="text-sm text-gray-400">Loading billing...</p>;

  const summary = billing?.summary;
  const tier = billing?.tier;
  const byCampaign = billing?.byCampaign ?? [];
  const daily = billing?.daily ?? [];
  const availableMonths = billing?.availableMonths ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
        {availableMonths.length > 0 && (
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Current Month</option>
            {availableMonths.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Total Calls</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">{summary?.total_calls ?? 0}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Total Minutes</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">{summary?.total_minutes ?? 0}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Rate / Min</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">₹{summary?.rate_per_min ?? 10}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Total Cost</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">₹{(summary?.total_cost ?? 0).toFixed(2)}</p>
        </div>
      </div>

      {/* Tier info */}
      {tier && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap gap-8">
              <div>
                <p className="text-xs text-indigo-400">Current Plan</p>
                <p className="text-lg font-bold text-indigo-800">{tier.name}</p>
              </div>
              <div>
                <p className="text-xs text-indigo-400">Rate</p>
                <p className="text-lg font-bold text-indigo-800">₹{tier.rate_per_min}/min</p>
              </div>
              <div>
                <p className="text-xs text-indigo-400">Tiers</p>
                <p className="text-sm text-indigo-700">
                  &lt;5k calls → ₹10 · &lt;10k → ₹8 · 10k+ → ₹6.4
                </p>
              </div>
            </div>
            {tier.next_tier_info && (
              <p className="rounded-lg bg-indigo-100 px-3 py-1.5 text-xs font-medium text-indigo-700">
                💡 {tier.next_tier_info}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Daily cost chart */}
      {daily.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">Daily Cost (₹)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={daily} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ fontSize: 12 }}
                formatter={(v: number) => [`₹${v.toFixed(2)}`, 'Cost']}
              />
              <Bar dataKey="cost" fill="#6366f1" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-campaign breakdown */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Per-Campaign Breakdown</h2>
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-100">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Campaign</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">Calls</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">Minutes</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {byCampaign.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-400">
                      No billing data for this period.
                    </td>
                  </tr>
                ) : (
                  byCampaign.map((row) => (
                    <tr key={row.campaign_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{row.campaign_name}</td>
                      <td className="px-4 py-3 text-right text-sm text-gray-600">{row.calls}</td>
                      <td className="px-4 py-3 text-right text-sm text-gray-600">{row.total_minutes}</td>
                      <td className="px-4 py-3 text-right text-sm font-medium text-gray-900">
                        ₹{row.total_cost.toFixed(2)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              {byCampaign.length > 0 && (
                <tfoot className="bg-gray-50">
                  <tr>
                    <td className="px-4 py-3 text-sm font-semibold text-gray-700">Total</td>
                    <td className="px-4 py-3 text-right text-sm font-semibold text-gray-700">
                      {byCampaign.reduce((s, r) => s + r.calls, 0)}
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-semibold text-gray-700">
                      {byCampaign.reduce((s, r) => s + r.total_minutes, 0).toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-semibold text-gray-700">
                      ₹{byCampaign.reduce((s, r) => s + r.total_cost, 0).toFixed(2)}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

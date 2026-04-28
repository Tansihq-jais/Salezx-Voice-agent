import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
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

interface DailyRow {
  date: string;
  calls: number;
  cost: number;
}

interface CampaignRow {
  campaign_id: string;
  campaign_name: string;
  calls: number;
  total_minutes: number;
  total_cost: number;
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
  const [leadsSlider, setLeadsSlider] = useState(100);
  const [avgDuration, setAvgDuration] = useState(2);
  const [showMore, setShowMore] = useState(false);
  const [selectedMonth, setSelectedMonth] = useState('');

  const { data, isLoading } = useQuery<{ success: boolean; data: BillingData }>({
    queryKey: ['billing', selectedMonth],
    queryFn: () => api.get(`/api/billing${selectedMonth ? `?month=${selectedMonth}` : ''}`),
    refetchInterval: 10000,
  });

  const { data: estimateData } = useQuery<{ success: boolean; data: { total_cost: number; rate_per_min: number; tier: string } }>({
    queryKey: ['billing-estimate', leadsSlider, avgDuration],
    queryFn: () =>
      api.post('/api/billing/estimate', { num_contacts: leadsSlider, avg_duration_min: avgDuration }),
    enabled: leadsSlider > 0,
  });

  const billing = data?.data;
  const summary = billing?.summary;
  const tier = billing?.tier;
  const daily = billing?.daily ?? [];
  const byCampaign = billing?.byCampaign ?? [];
  const availableMonths = billing?.availableMonths ?? [];

  const chartData = daily.map((d) => ({ label: d.date, value: d.cost }));
  const estimatedCost = estimateData?.data?.total_cost ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Billing &amp; Subscription</h1>
          <p className="mt-1 text-sm text-gray-500">Manage your enterprise plan, usage limits, and payment history.</p>
        </div>
        <div className="flex items-center gap-2">
          {availableMonths.length > 0 && (
            <select
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#C84B0C]/30 focus:border-[#C84B0C]"
            >
              <option value="">Current Month</option>
              {availableMonths.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          )}
          <button className="flex items-center gap-2 rounded-lg bg-[#C84B0C] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#A83A08] transition-colors shadow-sm">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="18 15 12 9 6 15" /></svg>
            Upgrade Plan
          </button>
        </div>
      </div>

      {/* Summary stat cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="rounded-xl bg-white border border-gray-200 p-5 shadow-sm">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Total Calls</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{summary?.total_calls ?? 0}</p>
        </div>
        <div className="rounded-xl bg-white border border-gray-200 p-5 shadow-sm">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Total Minutes</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{summary?.total_minutes?.toFixed(1) ?? '0'}</p>
        </div>
        <div className="rounded-xl bg-white border border-gray-200 p-5 shadow-sm">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Rate / Min</p>
          <p className="mt-2 text-3xl font-bold text-[#C84B0C]">₹{summary?.rate_per_min ?? '—'}</p>
        </div>
        <div className="rounded-xl bg-white border border-gray-200 p-5 shadow-sm">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Total Cost</p>
          <p className="mt-2 text-3xl font-bold text-[#C84B0C]">₹{summary?.total_cost?.toFixed(2) ?? '0.00'}</p>
        </div>
      </div>

      {/* Plan card + Daily chart */}
      <div className="rounded-xl bg-white border border-gray-200 shadow-sm overflow-hidden">
        <div className="grid grid-cols-5">
          {/* Plan info */}
          <div className="col-span-2 p-6 border-r border-gray-100">
            {tier ? (
              <>
                <span className="inline-block rounded-full border border-[#C84B0C] px-3 py-0.5 text-[10px] font-bold text-[#C84B0C] uppercase tracking-widest mb-4">
                  {tier.name}
                </span>
                <p className="text-2xl font-bold text-[#C84B0C]">
                  ₹{tier.rate_per_min}
                  <span className="text-sm font-normal text-gray-500"> /min</span>
                </p>
                <p className="mt-3 text-sm text-gray-600 leading-relaxed">
                  {tier.next_tier_info
                    ? `💡 ${tier.next_tier_info}`
                    : 'You are on the best available rate.'}
                </p>
                <div className="mt-6 pt-4 border-t border-gray-100">
                  <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Billing Period</p>
                  <p className="mt-1 text-sm font-semibold text-gray-700">{billing?.month ?? '—'}</p>
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-400">{isLoading ? 'Loading...' : 'No plan data.'}</p>
            )}
          </div>

          {/* Daily cost chart */}
          <div className="col-span-3 p-6">
            <h2 className="text-sm font-semibold text-gray-800 mb-4">Daily Cost (₹)</h2>
            {isLoading ? (
              <div className="h-40 flex items-center justify-center text-sm text-gray-400">Loading...</div>
            ) : chartData.length === 0 ? (
              <div className="h-40 flex items-center justify-center text-sm text-gray-400">No data for this period.</div>
            ) : (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -28 }} barSize={14}>
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: '#9CA3AF' }}
                    axisLine={false}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #E5E7EB' }}
                    cursor={{ fill: '#F9FAFB' }}
                    formatter={(v: number) => [`₹${v.toFixed(2)}`, 'Cost']}
                  />
                  <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={i === chartData.length - 1 ? '#C84B0C' : '#FDDCCC'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Cost Estimator + Per-Campaign Breakdown */}
      <div className="grid grid-cols-5 gap-4">
        {/* Cost Estimator — 3 cols */}
        <div className="col-span-3 rounded-xl bg-white border border-gray-200 shadow-sm p-6">
          <h2 className="text-sm font-semibold text-gray-800 mb-5">Cost Estimator</h2>

          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Number of Contacts</p>
              <p className="text-sm font-bold text-[#C84B0C]">{leadsSlider.toLocaleString()}</p>
            </div>
            <input
              type="range"
              min={10}
              max={10000}
              step={10}
              value={leadsSlider}
              onChange={(e) => setLeadsSlider(Number(e.target.value))}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, #C84B0C ${(leadsSlider / 10000) * 100}%, #FDE8D8 ${(leadsSlider / 10000) * 100}%)`,
              }}
            />
          </div>

          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Avg Call Duration (min)</p>
              <p className="text-sm font-bold text-[#C84B0C]">{avgDuration}</p>
            </div>
            <input
              type="range"
              min={1}
              max={15}
              step={0.5}
              value={avgDuration}
              onChange={(e) => setAvgDuration(Number(e.target.value))}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, #C84B0C ${(avgDuration / 15) * 100}%, #FDE8D8 ${(avgDuration / 15) * 100}%)`,
              }}
            />
          </div>

          <div className="rounded-lg bg-gray-50 border border-gray-100 px-4 py-3 flex items-center justify-between">
            <p className="text-sm text-gray-600">Estimated Cost</p>
            <p className="text-sm font-bold text-[#C84B0C]">
              {estimatedCost > 0 ? `₹${estimatedCost.toFixed(2)}` : '—'}
            </p>
          </div>
          {estimateData?.data?.tier && (
            <p className="mt-2 text-xs text-gray-400">
              Rate: ₹{estimateData.data.rate_per_min}/min ({estimateData.data.tier} tier)
            </p>
          )}
        </div>

        {/* Per-Campaign Breakdown — 2 cols */}
        <div className="col-span-2 rounded-xl bg-white border border-gray-200 shadow-sm p-6 overflow-auto">
          <h2 className="text-sm font-semibold text-gray-800 mb-4">By Campaign</h2>
          {byCampaign.length === 0 ? (
            <p className="text-sm text-gray-400">{isLoading ? 'Loading...' : 'No campaign data.'}</p>
          ) : (
            <div className="space-y-3">
              {byCampaign.map((row) => (
                <div key={row.campaign_id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div>
                    <p className="text-xs font-semibold text-gray-800 truncate max-w-[120px]">{row.campaign_name}</p>
                    <p className="text-[10px] text-gray-400">{row.calls} calls · {row.total_minutes.toFixed(1)} min</p>
                  </div>
                  <p className="text-sm font-bold text-[#C84B0C]">₹{row.total_cost.toFixed(2)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Billing History — from byCampaign monthly data */}
      <div className="rounded-xl bg-white border border-gray-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-800">Monthly Summary</h2>
          <button className="flex items-center gap-1.5 text-xs font-medium text-[#C84B0C] hover:underline">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
            Export All (.CSV)
          </button>
        </div>

        <table className="min-w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Campaign</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">Calls</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">Minutes</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {isLoading ? (
              <tr><td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-400">Loading...</td></tr>
            ) : byCampaign.length === 0 ? (
              <tr><td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-400">No billing data for this period.</td></tr>
            ) : (
              (showMore ? byCampaign : byCampaign.slice(0, 5)).map((row) => (
                <tr key={row.campaign_id} className="hover:bg-gray-50/60 transition-colors">
                  <td className="px-6 py-4 text-sm font-medium text-gray-800">{row.campaign_name}</td>
                  <td className="px-4 py-4 text-right text-sm text-gray-600">{row.calls}</td>
                  <td className="px-4 py-4 text-right text-sm text-gray-600">{row.total_minutes.toFixed(1)}</td>
                  <td className="px-6 py-4 text-right text-sm font-bold text-[#C84B0C]">₹{row.total_cost.toFixed(2)}</td>
                </tr>
              ))
            )}
          </tbody>
          {byCampaign.length > 0 && (
            <tfoot className="bg-gray-50/50">
              <tr>
                <td className="px-6 py-3 text-sm font-semibold text-gray-700">Total</td>
                <td className="px-4 py-3 text-right text-sm font-semibold text-gray-700">
                  {byCampaign.reduce((s, r) => s + r.calls, 0)}
                </td>
                <td className="px-4 py-3 text-right text-sm font-semibold text-gray-700">
                  {byCampaign.reduce((s, r) => s + r.total_minutes, 0).toFixed(1)}
                </td>
                <td className="px-6 py-3 text-right text-sm font-semibold text-[#C84B0C]">
                  ₹{byCampaign.reduce((s, r) => s + r.total_cost, 0).toFixed(2)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>

        {byCampaign.length > 5 && (
          <div className="border-t border-gray-100 px-6 py-3 text-center">
            <button
              onClick={() => setShowMore((v) => !v)}
              className="flex items-center gap-1.5 mx-auto text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors"
            >
              {showMore ? 'Show Less' : `Load More (${byCampaign.length - 5} more)`}
              <svg
                width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className={`transition-transform ${showMore ? 'rotate-180' : ''}`}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

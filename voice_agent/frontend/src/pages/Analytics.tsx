import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { FunnelChart } from '../components';
import { api } from '../api/client';

interface AnalyticsData {
  funnel: { stage: string; count: number }[];
  sentiment_distribution: { sentiment: string; count: number }[];
  intent_breakdown: { intent: string; count: number }[];
  top_topics: { topic: string; count: number }[];
}

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#22c55e',
  neutral: '#94a3b8',
  negative: '#ef4444',
};

const INTENT_COLORS = ['#6366f1', '#f97316', '#3b82f6', '#a855f7', '#ec4899', '#14b8a6'];

export default function Analytics() {
  const { data, isLoading } = useQuery<{ success: boolean; data: AnalyticsData }>({
    queryKey: ['analytics'],
    queryFn: () => api.get('/api/analytics'),
    refetchInterval: 5000,
  });

  const analytics = data?.data;

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading analytics...</p>;
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Funnel */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">Lead Funnel</h2>
          <FunnelChart data={analytics?.funnel ?? []} />
        </div>

        {/* Sentiment Distribution */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">Sentiment Distribution</h2>
          {(analytics?.sentiment_distribution ?? []).length === 0 ? (
            <p className="text-sm text-gray-400">No data available.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={analytics?.sentiment_distribution ?? []} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                <XAxis dataKey="sentiment" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip contentStyle={{ fontSize: 12 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {(analytics?.sentiment_distribution ?? []).map((entry) => (
                    <Cell key={entry.sentiment} fill={SENTIMENT_COLORS[entry.sentiment.toLowerCase()] ?? '#94a3b8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Intent Breakdown */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">Intent Breakdown</h2>
          {(analytics?.intent_breakdown ?? []).length === 0 ? (
            <p className="text-sm text-gray-400">No data available.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={analytics?.intent_breakdown ?? []}
                  dataKey="count"
                  nameKey="intent"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ intent, percent }) => `${intent} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {(analytics?.intent_breakdown ?? []).map((entry, i) => (
                    <Cell key={entry.intent} fill={INTENT_COLORS[i % INTENT_COLORS.length]} />
                  ))}
                </Pie>
                <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
                <Tooltip contentStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Top Topics */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">Top Topics</h2>
          {(analytics?.top_topics ?? []).length === 0 ? (
            <p className="text-sm text-gray-400">No topics available.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {(analytics?.top_topics ?? []).map((t) => {
                const size = Math.min(24, Math.max(12, 12 + t.count));
                return (
                  <span
                    key={t.topic}
                    className="rounded-full bg-indigo-50 px-3 py-1 font-medium text-indigo-700"
                    style={{ fontSize: size }}
                  >
                    {t.topic}
                    <span className="ml-1 text-xs text-indigo-400">({t.count})</span>
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

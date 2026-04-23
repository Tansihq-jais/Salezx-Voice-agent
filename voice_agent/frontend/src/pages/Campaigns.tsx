import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CampaignTable, FileUploadZone } from '../components';
import { useCampaigns } from '../hooks/useCampaign';
import { api } from '../api/client';

interface CreateCampaignPayload {
  name: string;
  description?: string;
}

export default function Campaigns() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading } = useCampaigns();
  const campaigns = data?.data ?? [];

  const [showModal, setShowModal] = useState(false);
  const [campaignName, setCampaignName] = useState('');
  const [description, setDescription] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: async (payload: CreateCampaignPayload) => {
      const campaign = await api.post<{ success: boolean; data: { campaign_id: string } }>(
        '/api/campaigns',
        payload
      );
      if (uploadedFile) {
        const formData = new FormData();
        formData.append('file', uploadedFile);
        await fetch('/campaign/upload', {
          method: 'POST',
          body: formData,
          headers: { 'X-API-Key': localStorage.getItem('voice_agent_api_key') || '' },
        });
      }
      return campaign;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      setShowModal(false);
      setCampaignName('');
      setDescription('');
      setUploadedFile(null);
      setCreateError(null);
    },
    onError: (err: Error) => setCreateError(err.message),
  });

  async function handleFileUpload(file: File) {
    setUploadedFile(file);
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!campaignName.trim()) return;
    createMutation.mutate({ name: campaignName.trim(), description: description.trim() || undefined });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Campaigns</h1>
        <button
          onClick={() => setShowModal(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          + New Campaign
        </button>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading campaigns...</p>
      ) : (
        <CampaignTable
          campaigns={campaigns}
          onView={(id) => navigate(`/campaigns/${id}`)}
        />
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">New Campaign</h2>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600"
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Campaign Name *</label>
                <input
                  type="text"
                  value={campaignName}
                  onChange={(e) => setCampaignName(e.target.value)}
                  required
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Q1 Outreach"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Optional description"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Upload Leads (optional)</label>
                <FileUploadZone onUpload={handleFileUpload} />
                {uploadedFile && (
                  <p className="mt-1 text-xs text-green-600">✓ {uploadedFile.name} ready to upload</p>
                )}
              </div>

              {createError && (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{createError}</p>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

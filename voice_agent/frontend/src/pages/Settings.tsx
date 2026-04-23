import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

// ── Gemini Live voice catalogue ───────────────────────────────────────────────
const GEMINI_VOICES: { name: string; tone: string }[] = [
  { name: 'Puck',           tone: 'Upbeat' },
  { name: 'Aoede',          tone: 'Breezy' },
  { name: 'Kore',           tone: 'Firm' },
  { name: 'Charon',         tone: 'Informative' },
  { name: 'Fenrir',         tone: 'Excitable' },
  { name: 'Zephyr',         tone: 'Bright' },
  { name: 'Orus',           tone: 'Firm' },
  { name: 'Autonoe',        tone: 'Bright' },
  { name: 'Umbriel',        tone: 'Easy-going' },
  { name: 'Erinome',        tone: 'Clear' },
  { name: 'Laomedeia',      tone: 'Upbeat' },
  { name: 'Schedar',        tone: 'Even' },
  { name: 'Achird',         tone: 'Friendly' },
  { name: 'Sadachbia',      tone: 'Lively' },
  { name: 'Enceladus',      tone: 'Breathy' },
  { name: 'Algieba',        tone: 'Smooth' },
  { name: 'Algenib',        tone: 'Gravelly' },
  { name: 'Achernar',       tone: 'Soft' },
  { name: 'Gacrux',         tone: 'Mature' },
  { name: 'Zubenelgenubi',  tone: 'Casual' },
  { name: 'Sadaltager',     tone: 'Knowledgeable' },
  { name: 'Leda',           tone: 'Youthful' },
  { name: 'Callirrhoe',     tone: 'Easy-going' },
  { name: 'Iapetus',        tone: 'Clear' },
  { name: 'Despina',        tone: 'Smooth' },
  { name: 'Rasalgethi',     tone: 'Informative' },
  { name: 'Alnilam',        tone: 'Firm' },
  { name: 'Pulcherrima',    tone: 'Forward' },
  { name: 'Vindemiatrix',   tone: 'Gentle' },
  { name: 'Sulafat',        tone: 'Warm' },
];

// ── Supported languages ───────────────────────────────────────────────────────
const LANGUAGES: { code: string; label: string }[] = [
  { code: 'en-IN', label: 'English (India)' },
  { code: 'hi-IN', label: 'Hindi (India)' },
  { code: 'en-US', label: 'English (US)' },
  { code: 'mr-IN', label: 'Marathi' },
  { code: 'ta-IN', label: 'Tamil' },
  { code: 'te-IN', label: 'Telugu' },
  { code: 'bn-BD', label: 'Bengali' },
  { code: 'ar-EG', label: 'Arabic (Egyptian)' },
  { code: 'de-DE', label: 'German' },
  { code: 'es-US', label: 'Spanish (US)' },
  { code: 'fr-FR', label: 'French' },
  { code: 'id-ID', label: 'Indonesian' },
  { code: 'it-IT', label: 'Italian' },
  { code: 'ja-JP', label: 'Japanese' },
  { code: 'ko-KR', label: 'Korean' },
  { code: 'pt-BR', label: 'Portuguese (Brazil)' },
  { code: 'ru-RU', label: 'Russian' },
  { code: 'nl-NL', label: 'Dutch' },
  { code: 'pl-PL', label: 'Polish' },
  { code: 'th-TH', label: 'Thai' },
  { code: 'tr-TR', label: 'Turkish' },
  { code: 'vi-VN', label: 'Vietnamese' },
];

interface SettingsData {
  agent_name: string;
  company_name: string;
  product_name: string;
  agent_language: string;
  gemini_voice: string;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">{title}</h2>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-600">{label}</label>
      {children}
    </div>
  );
}

const INPUT = 'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500';

export default function Settings() {
  const queryClient = useQueryClient();

  const [agentName,      setAgentName]      = useState('');
  const [companyName,    setCompanyName]    = useState('');
  const [productName,    setProductName]    = useState('');
  const [agentLanguage,  setAgentLanguage]  = useState('en-IN');
  const [geminiVoice,    setGeminiVoice]    = useState('Aoede');
  const [saved,          setSaved]          = useState(false);

  const { data, isLoading } = useQuery<{ success: boolean; data: SettingsData }>({
    queryKey: ['settings'],
    queryFn: () => api.get('/api/settings'),
  });

  // Populate form once data arrives
  useEffect(() => {
    if (data?.data) {
      const d = data.data;
      setAgentName(d.agent_name ?? '');
      setCompanyName(d.company_name ?? '');
      setProductName(d.product_name ?? '');
      setAgentLanguage(d.agent_language ?? 'en-IN');
      setGeminiVoice(d.gemini_voice ?? 'Aoede');
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put('/api/settings', {
        agent_name:     agentName,
        company_name:   companyName,
        product_name:   productName,
        agent_language: agentLanguage,
        gemini_voice:   geminiVoice,
      }),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  if (isLoading) return <p className="text-sm text-gray-400">Loading settings...</p>;

  const selectedVoiceInfo = GEMINI_VOICES.find((v) => v.name === geminiVoice);

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {/* ── Voice Agent ─────────────────────────────────────────────────── */}
      <Section title="Voice Agent">
        <div className="space-y-4">
          <Field label="Gemini Voice">
            <div className="space-y-2">
              <select
                value={geminiVoice}
                onChange={(e) => setGeminiVoice(e.target.value)}
                className={INPUT}
              >
                {GEMINI_VOICES.map((v) => (
                  <option key={v.name} value={v.name}>
                    {v.name} — {v.tone}
                  </option>
                ))}
              </select>
              {selectedVoiceInfo && (
                <p className="text-xs text-gray-400">
                  Tone: <span className="font-medium text-gray-600">{selectedVoiceInfo.tone}</span>
                  {' · '}
                  <a
                    href="https://cloud.google.com/text-to-speech/docs/chirp3-hd"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline"
                  >
                    Preview voices ↗
                  </a>
                </p>
              )}
            </div>
          </Field>

          <Field label="Response Language">
            <select
              value={agentLanguage}
              onChange={(e) => setAgentLanguage(e.target.value)}
              className={INPUT}
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </Field>
        </div>
      </Section>

      {/* ── Agent Persona ────────────────────────────────────────────────── */}
      <Section title="Agent Persona">
        <div className="space-y-4">
          <Field label="Agent Name">
            <input
              type="text"
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              className={INPUT}
              placeholder="e.g. Priya"
            />
          </Field>
          <Field label="Company Name">
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className={INPUT}
              placeholder="e.g. TechVision Solutions"
            />
          </Field>
          <Field label="Product / Service Name">
            <input
              type="text"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              className={INPUT}
              placeholder="e.g. CloudPro CRM"
            />
          </Field>
        </div>
      </Section>

      {/* ── Save ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {saveMutation.isPending ? 'Saving…' : 'Save Settings'}
        </button>
        {saved && (
          <span className="text-sm text-green-600">✓ Settings saved — active for new calls</span>
        )}
        {saveMutation.isError && (
          <span className="text-sm text-red-600">Failed to save. Try again.</span>
        )}
      </div>
    </div>
  );
}

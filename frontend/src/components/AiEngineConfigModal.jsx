import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';

export default function AiEngineConfigModal({ isOpen, onClose, onConfigSaved, isAr }) {
  const [config, setConfig] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState('groq');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [analyzerModel, setAnalyzerModel] = useState('');
  const [suggestionsModel, setSuggestionsModel] = useState('');
  const [timeoutSeconds, setTimeoutSeconds] = useState(2.5);

  const [liveModels, setLiveModels] = useState([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [modelsFetchNotice, setModelsFetchNotice] = useState('');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Fetch current config on open
  useEffect(() => {
    if (!isOpen) return;

    setLoading(true);
    setTestResult(null);
    setSaveSuccess(false);

    fetch(`${API_BASE}/api/v1/config/llm`)
      .then((res) => res.json())
      .then((data) => {
        setConfig(data);
        const prov = data.provider || 'groq';
        setSelectedProvider(prov);
        setBaseUrl(data.base_url || '');
        setApiKey(data.api_key_set ? data.api_key_masked : '');
        setAnalyzerModel(data.analyzer_model || 'qwen/qwen3.8-27b');
        setSuggestionsModel(data.suggestions_model || 'qwen/qwen3.8-27b');
        setTimeoutSeconds(data.timeout_seconds || 2.5);
        setLoading(false);

        // Fetch live models for current provider
        fetchLiveModels(prov, data.base_url, data.api_key_set ? data.api_key_masked : '');
      })
      .catch((err) => {
        console.error('Failed to load LLM config:', err);
        setLoading(false);
      });
  }, [isOpen]);

  const fetchLiveModels = async (prov = selectedProvider, bUrl = baseUrl, key = apiKey) => {
    setFetchingModels(true);
    setModelsFetchNotice('');
    try {
      const q = new URLSearchParams({
        provider: prov || '',
        base_url: bUrl || '',
        api_key: key || '',
      });
      const res = await fetch(`${API_BASE}/api/v1/config/llm/models?${q.toString()}`);
      if (res.ok) {
        const data = await res.json();
        if (data.models && data.models.length > 0) {
          setLiveModels(data.models);
          setModelsFetchNotice(data.message || `Loaded ${data.models.length} live models`);
        }
      }
    } catch (e) {
      console.warn('Could not fetch live models:', e);
    } finally {
      setFetchingModels(false);
    }
  };

  // When changing provider tab, auto-fill defaults and fetch live models
  const handleSelectProvider = (provKey) => {
    setSelectedProvider(provKey);
    setTestResult(null);
    setSaveSuccess(false);

    const preset = config?.presets?.[provKey];
    if (preset) {
      const newUrl = preset.default_base_url || '';
      const newAnalyzer = preset.default_analyzer_model || 'qwen/qwen3.8-27b';
      const newSuggestions = preset.default_suggestions_model || 'qwen/qwen3.8-27b';
      setBaseUrl(newUrl);
      setAnalyzerModel(newAnalyzer);
      setSuggestionsModel(newSuggestions);

      const targetKey = provKey === config?.provider ? (config?.api_key_set ? config.api_key_masked : '') : '';
      setApiKey(targetKey);

      // Query live models from newly selected provider
      fetchLiveModels(provKey, newUrl, targetKey);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/config/llm/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          base_url: baseUrl,
          api_key: apiKey,
          model: analyzerModel,
        }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (err) {
      setTestResult({
        success: false,
        message: 'Network error connecting to backend test endpoint',
        error: String(err),
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);

    try {
      const payload = {
        provider: selectedProvider,
        base_url: baseUrl,
        api_key: apiKey,
        analyzer_model: analyzerModel,
        suggestions_model: suggestionsModel,
        timeout_seconds: parseFloat(timeoutSeconds) || 2.5,
      };

      const res = await fetch(`${API_BASE}/api/v1/config/llm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`Failed to save: ${res.statusText}`);
      }

      const updated = await res.json();
      setConfig(updated);
      setSaveSuccess(true);
      if (onConfigSaved) onConfigSaved(updated);

      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      alert(`Error saving configuration: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const currentPreset = config?.presets?.[selectedProvider] || {};
  // Use live models if fetched; otherwise fallback to presets
  const displayModels = liveModels.length > 0 ? liveModels : (currentPreset.recommended_models || []);

  return (
    <div className="ai-modal-backdrop" onClick={onClose}>
      <div
        className="ai-modal-container"
        onClick={(e) => e.stopPropagation()}
        dir={isAr ? 'rtl' : 'ltr'}
      >
        {/* Modal Header */}
        <div className="ai-modal-header">
          <div className="ai-modal-title-group">
            <div className="ai-modal-icon-badge">⚡</div>
            <div>
              <h2 className="ai-modal-title">
                {isAr ? 'إعدادات محرك ونماذج الذكاء الاصطناعي' : 'AI Engine & Model Configuration'}
              </h2>
              <p className="ai-modal-subtitle">
                {isAr
                  ? 'جلب النماذج الحية من Groq و Ollama واختيارها ديناميكياً'
                  : 'Live model discovery from Groq, Ollama, and OpenAI — no hardcoding'}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="ai-modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="ai-modal-loading">
            <div className="ai-spinner" />
            <p>{isAr ? 'جاري تحميل الإعدادات...' : 'Loading AI configuration...'}</p>
          </div>
        ) : (
          <form onSubmit={handleSave} className="ai-modal-form">
            {/* Active Status Ribbon */}
            <div className="ai-status-ribbon">
              <span className="ai-ribbon-label">
                {isAr ? 'النموذج النشط حالياً:' : 'Currently Active Engine:'}
              </span>
              <span className="ai-ribbon-badge">
                <span className="ai-dot-pulse" />
                {config?.provider?.toUpperCase()} • {config?.analyzer_model}
              </span>
            </div>

            {/* Provider Selector Tabs */}
            <div className="ai-provider-tabs">
              {[
                { key: 'groq', icon: '⚡', label: 'Groq Cloud', tag: 'Fastest (LPU)' },
                { key: 'ollama', icon: '🦙', label: 'Ollama', tag: '100% Local' },
                { key: 'openai', icon: '🧠', label: 'OpenAI', tag: 'GPT-4o' },
                { key: 'vllm', icon: '⚙️', label: 'vLLM / Spec', tag: 'Self-Hosted' },
              ].map((p) => (
                <button
                  key={p.key}
                  type="button"
                  className={`ai-provider-card ${selectedProvider === p.key ? 'active' : ''}`}
                  onClick={() => handleSelectProvider(p.key)}
                >
                  <div className="ai-card-top">
                    <span className="ai-card-icon">{p.icon}</span>
                    <span className="ai-card-tag">{p.tag}</span>
                  </div>
                  <div className="ai-card-name">{p.label}</div>
                </button>
              ))}
            </div>

            {/* Configuration Form Inputs */}
            <div className="ai-form-grid">
              {/* Endpoint Base URL */}
              <div className="ai-field-group">
                <label className="ai-field-label">
                  {isAr ? 'عنوان الخادم الأساسي (Base URL)' : 'API Base URL'}
                </label>
                <input
                  type="text"
                  className="ai-input"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="e.g. https://api.groq.com/openai/v1 or http://localhost:11434/v1"
                  required
                />
              </div>

              {/* API Key */}
              <div className="ai-field-group">
                <label className="ai-field-label">
                  {isAr ? 'مفتاح الواجهة البرمجية (API Key)' : 'API Key'}
                  {currentPreset.requires_api_key === false && (
                    <span className="ai-tag-optional"> (Optional for Ollama)</span>
                  )}
                </label>
                <div className="ai-input-with-action">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    className="ai-input"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={
                      currentPreset.requires_api_key
                        ? selectedProvider === 'groq'
                          ? 'gsk_...'
                          : 'sk-...'
                        : 'Not required for local Ollama'
                    }
                  />
                  <button
                    type="button"
                    className="ai-input-action-btn"
                    onClick={() => setShowApiKey(!showApiKey)}
                  >
                    {showApiKey ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>

              {/* Analyzer Model (Stage 4) & Dynamic Live Models */}
              <div className="ai-field-group">
                <div className="ai-label-with-refresh">
                  <label className="ai-field-label">
                    {isAr ? 'نموذج التحقق (Stage 4 Validation Model)' : 'Stage 4 Validation Model'}
                  </label>
                  <button
                    type="button"
                    className="ai-refresh-models-btn"
                    onClick={() => fetchLiveModels(selectedProvider, baseUrl, apiKey)}
                    disabled={fetchingModels}
                    title="Fetch live models directly from provider API"
                  >
                    {fetchingModels ? 'Fetching...' : `🔄 ${isAr ? 'جلب النماذج الحية' : 'Fetch Live Models'}`}
                  </button>
                </div>

                {/* Dynamic Live Model Dropdown */}
                {displayModels.length > 0 && (
                  <select
                    className="ai-input ai-select-input"
                    value={displayModels.some((m) => m.id === analyzerModel) ? analyzerModel : 'custom'}
                    onChange={(e) => {
                      if (e.target.value !== 'custom') {
                        setAnalyzerModel(e.target.value);
                        if (!suggestionsModel || displayModels.some((dm) => dm.id === suggestionsModel)) {
                          setSuggestionsModel(e.target.value);
                        }
                      }
                    }}
                  >
                    {displayModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.id} {m.id.includes('qwen3.8-27b') ? '⭐ (Primary)' : ''}
                      </option>
                    ))}
                    <option value="custom">✏️ {isAr ? 'إدخال معرف مخصص يدوي...' : 'Custom / Enter manually below...'}</option>
                  </select>
                )}

                <input
                  type="text"
                  className="ai-input"
                  value={analyzerModel}
                  onChange={(e) => setAnalyzerModel(e.target.value)}
                  placeholder="e.g. qwen/qwen3.8-27b or qwen2.5vl:7b"
                  required
                />

                {/* Dynamic Live Model Quick-Pick Pills (Top 2-4 models) */}
                {displayModels.length > 0 && (
                  <div className="ai-quick-models">
                    <span className="ai-quick-title">
                      {liveModels.length > 0 ? (
                        <span className="ai-live-badge">🟢 {isAr ? 'نماذج حية من المزود:' : 'Live Provider Models (Quick Select):'}</span>
                      ) : (
                        <span>{isAr ? 'نماذج مقترحة:' : 'Quick Select:'}</span>
                      )}
                    </span>
                    {displayModels.slice(0, 4).map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        className={`ai-quick-btn ${analyzerModel === m.id ? 'active' : ''}`}
                        onClick={() => {
                          setAnalyzerModel(m.id);
                          if (!suggestionsModel || displayModels.some((dm) => dm.id === suggestionsModel)) {
                            setSuggestionsModel(m.id);
                          }
                        }}
                      >
                        {m.id}
                      </button>
                    ))}
                  </div>
                )}

                {modelsFetchNotice && (
                  <span className="ai-models-notice">{modelsFetchNotice}</span>
                )}
              </div>

              {/* Suggestions Model (Stage 6) */}
              <div className="ai-field-group">
                <label className="ai-field-label">
                  {isAr ? 'نموذج اقتراح الأسماء (Stage 6 Suggestions)' : 'Stage 6 Suggestions Model'}
                </label>
                {displayModels.length > 0 && (
                  <select
                    className="ai-input ai-select-input"
                    value={displayModels.some((m) => m.id === suggestionsModel) ? suggestionsModel : 'custom'}
                    onChange={(e) => {
                      if (e.target.value !== 'custom') {
                        setSuggestionsModel(e.target.value);
                      }
                    }}
                  >
                    {displayModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.id} {m.id.includes('qwen3.8-27b') ? '⭐ (Primary)' : ''}
                      </option>
                    ))}
                    <option value="custom">✏️ {isAr ? 'إدخال معرف مخصص يدوي...' : 'Custom / Enter manually below...'}</option>
                  </select>
                )}
                <input
                  type="text"
                  className="ai-input"
                  value={suggestionsModel}
                  onChange={(e) => setSuggestionsModel(e.target.value)}
                  placeholder="e.g. qwen/qwen3.8-27b or qwen2.5vl:7b"
                  required
                />
              </div>

              {/* Timeout Seconds */}
              <div className="ai-field-group half-width">
                <label className="ai-field-label">
                  {isAr ? 'مهلة الطلب بالثواني (Timeout)' : 'Timeout (Seconds)'}
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="1"
                  max="60"
                  className="ai-input"
                  value={timeoutSeconds}
                  onChange={(e) => setTimeoutSeconds(e.target.value)}
                />
                <span className="ai-field-hint">Spec SLA budget: 2.5s</span>
              </div>
            </div>

            {/* Test Connection Banner */}
            {testResult && (
              <div className={`ai-test-result ${testResult.success ? 'success' : 'error'}`}>
                <div className="ai-test-icon">{testResult.success ? '✅' : '❌'}</div>
                <div className="ai-test-content">
                  <div className="ai-test-msg">{testResult.message}</div>
                  {testResult.latency_ms && (
                    <div className="ai-test-latency">Latency: {testResult.latency_ms} ms</div>
                  )}
                  {testResult.error && (
                    <div className="ai-test-error">{testResult.error}</div>
                  )}
                  {testResult.reply && (
                    <div className="ai-test-reply">Model output: "{testResult.reply}"</div>
                  )}
                </div>
              </div>
            )}

            {saveSuccess && (
              <div className="ai-test-result success">
                <div className="ai-test-icon">✨</div>
                <div className="ai-test-content">
                  <div className="ai-test-msg">
                    {isAr ? 'تم حفظ وتفعيل النموذج بنجاح!' : 'Configuration updated and applied live!'}
                  </div>
                </div>
              </div>
            )}

            {/* Modal Actions */}
            <div className="ai-modal-footer">
              <button
                type="button"
                className="ai-btn-test"
                onClick={handleTestConnection}
                disabled={testing || saving}
              >
                {testing ? (
                  <>
                    <span className="ai-mini-spinner" /> Testing...
                  </>
                ) : (
                  <>⚡ {isAr ? 'اختبار الاتصال' : 'Test Connection'}</>
                )}
              </button>

              <div className="ai-footer-right">
                <button
                  type="button"
                  className="ai-btn-cancel"
                  onClick={onClose}
                  disabled={saving}
                >
                  {isAr ? 'إلغاء' : 'Cancel'}
                </button>
                <button
                  type="submit"
                  className="ai-btn-save"
                  disabled={saving || testing}
                >
                  {saving ? (
                    <>
                      <span className="ai-mini-spinner" /> Saving...
                    </>
                  ) : (
                    <>✓ {isAr ? 'تطبيق وحفظ الإعدادات' : 'Apply & Save Live'}</>
                  )}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

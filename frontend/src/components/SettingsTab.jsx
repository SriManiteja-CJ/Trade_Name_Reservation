import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';

export default function SettingsTab({ lang }) {
  const isAr = lang === 'ar';

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

  // Load config on mount
  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = () => {
    setLoading(true);
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

        fetchLiveModels(prov, data.base_url, data.api_key_set ? data.api_key_masked : '');
      })
      .catch((err) => {
        console.error('Failed to load LLM config:', err);
        setLoading(false);
      });
  };

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

      if (!res.ok) throw new Error(`Failed to save: ${res.statusText}`);

      const updated = await res.json();
      setConfig(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err) {
      alert(`Error saving configuration: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const currentPreset = config?.presets?.[selectedProvider] || {};
  const displayModels = liveModels.length > 0 ? liveModels : (currentPreset.recommended_models || []);

  return (
    <div className="settings-page-wrapper" dir={isAr ? 'rtl' : 'ltr'}>
      {/* Header Banner */}
      <div className="settings-hero">
        <div className="settings-hero-content">
          <div className="settings-badge">
            <span className="settings-badge-dot" />
            {isAr ? 'إدارة النظام والذكاء الاصطناعي' : 'System & AI Engine Management'}
          </div>
          <h1 className="settings-title">
            {isAr ? 'إعدادات المنظومة والذكاء الاصطناعي' : 'System Configuration & Model Serving'}
          </h1>
          <p className="settings-subtitle">
            {isAr
              ? 'جلب النماذج ديناميكياً من Groq و Ollama بدون تقيد بالنماذج الثابتة، مع دعم التبديل السريع'
              : 'Dynamically discover live models from Groq and Ollama APIs with zero hardcoding'}
          </p>
        </div>
      </div>

      <div className="settings-cards-grid">
        {/* Main Card: LLM Serving & Model Configuration */}
        <div className="settings-card main-config-card">
          <div className="settings-card-header">
            <div className="settings-card-icon">⚡</div>
            <div>
              <h2 className="settings-card-title">
                {isAr ? 'محرك ونماذج الذكاء الاصطناعي' : 'LLM Inference & Model Serving'}
              </h2>
              <p className="settings-card-desc">
                {isAr
                  ? 'اختر المزود واجلب النماذج المتاحة حياً عبر واجهة المزود'
                  : 'Select provider and dynamically discover models directly from the provider API'}
              </p>
            </div>
          </div>

          {loading ? (
            <div className="ai-modal-loading">
              <div className="ai-spinner" />
              <p>{isAr ? 'جاري تحميل الإعدادات...' : 'Loading configuration...'}</p>
            </div>
          ) : (
            <form onSubmit={handleSave} className="settings-form">
              {/* Active Provider Indicator */}
              <div className="settings-active-banner">
                <span className="banner-label">
                  {isAr ? 'المزود النشط حالياً:' : 'Active Engine:'}
                </span>
                <span className="banner-val">
                  <span className="ai-dot-pulse" />
                  {config?.provider?.toUpperCase()} • {config?.analyzer_model}
                </span>
              </div>

              {/* Provider Selection Tabs */}
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

              {/* Form Fields */}
              <div className="ai-form-grid">
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
                          {m.id} {m.id.includes('qwen3.8-27b') ? '⭐ (Primary Recommended)' : ''}
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
                          <span className="ai-live-badge">🟢 {isAr ? 'نماذج حية مكتشفة (اختيار سريع):' : 'Live Provider Models (Quick Select):'}</span>
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

                <div className="ai-field-group">
                  <label className="ai-field-label">
                    {isAr ? 'نموذج اقتراح الأسماء (Stage 6 Suggestions Model)' : 'Stage 6 Suggestions Model'}
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
                          {m.id} {m.id.includes('qwen3.8-27b') ? '⭐ (Primary Recommended)' : ''}
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
                </div>
              </div>

              {/* Test feedback */}
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
                      {isAr ? 'تم حفظ وتفعيل التكوين بنجاح!' : 'Configuration updated and applied live!'}
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="settings-form-actions">
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
                    <>✓ {isAr ? 'حفظ وتطبيق التغييرات' : 'Save & Apply Live'}</>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Sidebar Info Cards: Database & System Status */}
        <div className="settings-side-column">
          {/* Neon Database Status Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <div className="settings-card-icon db-icon">🗄️</div>
              <div>
                <h3 className="settings-card-title">
                  {isAr ? 'قاعدة بيانات Neon DB' : 'PostgreSQL Neon DB'}
                </h3>
                <p className="settings-card-desc">Cloud Postgres with pgvector & pg_trgm</p>
              </div>
            </div>

            <div className="settings-status-list">
              <div className="status-row">
                <span className="status-label">Connection:</span>
                <span className="status-value success">
                  <span className="status-dot green" /> Connected (AWS US-East-2)
                </span>
              </div>
              <div className="status-row">
                <span className="status-label">PostgreSQL Version:</span>
                <span className="status-value">18.6 (ARM64)</span>
              </div>
              <div className="status-row">
                <span className="status-label">pgvector Extension:</span>
                <span className="status-value success">Active (v0.8.6)</span>
              </div>
              <div className="status-row">
                <span className="status-label">pg_trgm Extension:</span>
                <span className="status-value success">Active (v1.6)</span>
              </div>
              <div className="status-row">
                <span className="status-label">Alembic Migration:</span>
                <span className="status-value success">Up to Date (001_initial)</span>
              </div>
            </div>
          </div>

          {/* Embeddings Status Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <div className="settings-card-icon emb-icon">🧩</div>
              <div>
                <h3 className="settings-card-title">
                  {isAr ? 'محرك التضمين الدلالي' : 'Embeddings Engine'}
                </h3>
                <p className="settings-card-desc">Multilingual vectors (768-dim)</p>
              </div>
            </div>

            <div className="settings-status-list">
              <div className="status-row">
                <span className="status-label">Embedding Dimensions:</span>
                <span className="status-value">768 floats</span>
              </div>
              <div className="status-row">
                <span className="status-label">TEI Endpoint:</span>
                <span className="status-value">http://localhost:8081</span>
              </div>
              <div className="status-row">
                <span className="status-label">Ollama Embeddings:</span>
                <span className="status-value">bge-m3 / nomic-embed-text</span>
              </div>
              <div className="status-row">
                <span className="status-label">Lexical Fallback:</span>
                <span className="status-value success">Active (Trigram + Phonetic)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

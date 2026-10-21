import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';

const CATEGORIES = [
  { value: 'prohibited', label: 'Prohibited (محظور)' },
  { value: 'profanity', label: 'Profanity (بذيء)' },
  { value: 'unfriendly', label: 'Unfriendly / Hostile (غير لائق)' },
  { value: 'special', label: 'Special / Sovereign (خاص / سيادي)' },
  { value: 'divine_name', label: 'Divine / Allah Names (أسماء الجلالة)' },
  { value: 'location', label: 'Location / Sovereign Geo (جغرافي)' },
  { value: 'family_name', label: 'Family / Tribal Names (عائلي / قبلي)' },
];

export default function LexiconTab({ lang }) {
  const isAr = lang === 'ar';

  // Proposals State
  const [proposals, setProposals] = useState([]);
  const [loadingProposals, setLoadingProposals] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(null);

  // Variant Generator State
  const [term, setTerm] = useState('');
  const [category, setCategory] = useState('prohibited');
  const [termLang, setTermLang] = useState('ar');
  const [generatedVariants, setGeneratedVariants] = useState([]);
  const [genLoading, setGenLoading] = useState(false);

  // Direct Entry State
  const [directSeverity, setDirectSeverity] = useState('block');
  const [savingEntry, setSavingEntry] = useState(false);

  // Fetch Pending Proposals
  const fetchProposals = async () => {
    setLoadingProposals(true);
    try {
      const resp = await fetch(`${API_BASE}/Admin/Lexicon/Proposals`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setProposals(data.proposals || []);
    } catch (err) {
      console.error('Failed to fetch proposals:', err);
    } finally {
      setLoadingProposals(false);
    }
  };

  useEffect(() => {
    fetchProposals();
  }, []);

  // Handle Approve / Reject
  const handleAction = async (proposalId, action) => {
    setActionInProgress(proposalId);
    try {
      const resp = await fetch(`${API_BASE}/Admin/Lexicon/Proposals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposal_id: proposalId,
          action: action,
          reviewer_id: 'admin_officer_uaq',
        }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${resp.status}`);
      }

      await fetchProposals();
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  // Generate Variants via Stage ⑨ LLM (E7)
  const handleGenerateVariants = async (e) => {
    e?.preventDefault();
    if (!term.trim()) return;

    setGenLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/Admin/Lexicon/ProposeVariants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          term: term.trim(),
          category: category,
          lang: termLang,
        }),
      });

      if (!resp.ok) {
        throw new Error(`Variant generation failed: ${resp.status}`);
      }

      const data = await resp.json();
      setGeneratedVariants(data.variants || []);
    } catch (err) {
      alert(`Variant generation error: ${err.message}`);
    } finally {
      setGenLoading(false);
    }
  };

  // Save Entry directly
  const handleSaveEntry = async () => {
    if (!term.trim()) return;
    setSavingEntry(true);
    try {
      const resp = await fetch(`${API_BASE}/Admin/Lexicon/Entries`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          term: term.trim(),
          category: category,
          lang: termLang,
          severity: directSeverity,
          variants: generatedVariants,
          auto_propose_variants: false,
          approved_by: 'admin_officer_uaq',
        }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${resp.status}`);
      }

      alert(isAr ? 'تمت إضافة المصطلح بنجاح إلى المعجم' : 'Term added successfully to Lexicon!');
      setTerm('');
      setGeneratedVariants([]);
      fetchProposals();
    } catch (err) {
      alert(`Save error: ${err.message}`);
    } finally {
      setSavingEntry(false);
    }
  };

  return (
    <div className="tab-pane active" id="tab-lexicon">
      <div className="grid-2col">
        {/* Left Column: AI Variant Proposer & Creator */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">
                <span>🤖</span>
                <span>{isAr ? 'توليد أشكال التحايل والتهجئة الذكي' : 'AI Evasion & Variant Generator'}</span>
              </h2>
              <span className="badge badge-gold">{isAr ? 'توليد ذكي' : 'AI Generator'}</span>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '16px' }}>
              {isAr
                ? 'استخدام نموذج الذكاء الاصطناعي لتوليد أشكال التحايل الصوتي، الحروف الإنجليزية المعربة (Arabizi)، والأخطاء الإملائية الشائعة مع إلزامية المراجعة البشرية.'
                : 'Generates phonetic, typo, and Arabizi evasion variants for restricted terms. Requires human governance before inclusion.'}
            </p>

            <form onSubmit={handleGenerateVariants}>
              <div className="form-group">
                <label className="form-label">{isAr ? 'المصطلح الأساسي:' : 'Base Compliance Term:'}</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder={termLang === 'ar' ? 'مثال: كازينو، قمار، بيرة...' : 'e.g. Casino, Gamble, Vodka...'}
                  value={term}
                  onChange={(e) => setTerm(e.target.value)}
                />
              </div>

              <div className="form-row" style={{ marginTop: '12px' }}>
                <div className="form-group">
                  <label className="form-label">{isAr ? 'الفئة الرقابية:' : 'Restricted Category:'}</label>
                  <select
                    className="form-input"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">{isAr ? 'اللغة:' : 'Language:'}</label>
                  <select
                    className="form-input"
                    value={termLang}
                    onChange={(e) => setTermLang(e.target.value)}
                  >
                    <option value="ar">العربية (Arabic)</option>
                    <option value="en">الإنجليزية (English)</option>
                  </select>
                </div>
              </div>

              <div className="form-row" style={{ marginTop: '12px' }}>
                <div className="form-group">
                  <label className="form-label">{isAr ? 'درجة الخطورة:' : 'Severity Action:'}</label>
                  <select
                    className="form-input"
                    value={directSeverity}
                    onChange={(e) => setDirectSeverity(e.target.value)}
                  >
                    <option value="block">حظر قاطع (Block / Hard Stop)</option>
                    <option value="human_review">مراجعة بشرية (Human Review)</option>
                    <option value="warn">تحذير تنبيهي (Warning)</option>
                  </select>
                </div>

                <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end' }}>
                  <button
                    type="submit"
                    className="btn btn-secondary"
                    style={{ width: '100%' }}
                    disabled={genLoading || !term.trim()}
                  >
                    {genLoading ? (isAr ? 'جاري التوليد...' : 'Generating...') : (isAr ? '✨ توليد المقترحات' : '✨ Propose Variants')}
                  </button>
                </div>
              </div>
            </form>

            {/* Generated Variants Display */}
            {generatedVariants.length > 0 && (
              <div style={{ marginTop: '20px', padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <h4 style={{ margin: 0, fontSize: '0.9rem', color: 'var(--gold-primary)' }}>
                    {isAr ? `الأشكال المولدة (${generatedVariants.length}):` : `Generated Variants (${generatedVariants.length}):`}
                  </h4>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                  {generatedVariants.map((v, i) => (
                    <span
                      key={i}
                      style={{
                        padding: '4px 8px',
                        background: 'rgba(217, 119, 6, 0.15)',
                        border: '1px solid rgba(217, 119, 6, 0.3)',
                        borderRadius: '4px',
                        fontSize: '0.8rem',
                        color: '#fef3c7',
                      }}
                    >
                      {v}
                    </span>
                  ))}
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                  onClick={handleSaveEntry}
                  disabled={savingEntry}
                >
                  {savingEntry ? (isAr ? 'جاري الحفظ...' : 'Saving...') : (isAr ? '💾 اعتماد وإضافة للمعجم' : '💾 Save Directly to Lexicon')}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Pending Proposals Queue */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="card" style={{ height: '100%' }}>
            <div className="card-header">
              <h2 className="card-title">
                <span>🛡️</span>
                <span>{isAr ? 'قائمة المقترحات المعلقة بانتظار الاعتماد' : 'Human Approval Queue'}</span>
              </h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-warning">
                  {proposals.length} {isAr ? 'معلق' : 'Pending'}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                  onClick={fetchProposals}
                >
                  🔄
                </button>
              </div>
            </div>

            {loadingProposals && (
              <div className="empty-state">
                <span className="empty-icon">⏳</span>
                <p>{isAr ? 'جاري تحميل قائمة المقترحات...' : 'Fetching pending proposals...'}</p>
              </div>
            )}

            {!loadingProposals && proposals.length === 0 && (
              <div className="empty-state">
                <span className="empty-icon">✅</span>
                <p>
                  {isAr
                    ? 'لا توجد مقترحات معلقة حالياً. جميع المصطلحات معتمدة ومحدثة في المعجم.'
                    : 'No pending proposals. All compliance terms are reviewed and approved.'}
                </p>
              </div>
            )}

            {!loadingProposals && proposals.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {proposals.map((prop) => {
                  const isProcessing = actionInProgress === prop.id;
                  const variantsList = prop.variants || [];
                  return (
                    <div
                      key={prop.id}
                      style={{
                        padding: '14px',
                        background: 'rgba(255, 255, 255, 0.03)',
                        borderRadius: 'var(--radius)',
                        border: '1px solid var(--border-color)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '10px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span className="badge badge-info">ID #{prop.id}</span>
                          <span className="badge badge-danger">{prop.category}</span>
                          <span className="badge badge-gold">{prop.lang?.toUpperCase()}</span>
                        </div>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          Severity: {prop.severity}
                        </span>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{prop.term}</div>
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                            Normalized: {prop.normalized_term}
                          </div>
                        </div>

                        {/* Approval Action Buttons */}
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            type="button"
                            className="btn btn-primary"
                            style={{ padding: '6px 14px', fontSize: '0.85rem' }}
                            disabled={isProcessing}
                            onClick={() => handleAction(prop.id, 'approve')}
                          >
                            {isProcessing ? '...' : (isAr ? 'قبول' : 'Approve')}
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger"
                            style={{ padding: '6px 14px', fontSize: '0.85rem' }}
                            disabled={isProcessing}
                            onClick={() => handleAction(prop.id, 'reject')}
                          >
                            {isProcessing ? '...' : (isAr ? 'رفض' : 'Reject')}
                          </button>
                        </div>
                      </div>

                      {variantsList.length > 0 && (
                        <div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                            {isAr ? 'الأشكال المقترحة للتحايل:' : 'Evasion Variants:'}
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                            {variantsList.map((v, i) => (
                              <span
                                key={i}
                                style={{
                                  fontSize: '0.75rem',
                                  padding: '2px 6px',
                                  background: 'rgba(255, 255, 255, 0.05)',
                                  borderRadius: '3px',
                                  color: 'var(--text-secondary)',
                                }}
                              >
                                {v}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

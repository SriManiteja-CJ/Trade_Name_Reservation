import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';

export default function ReviewerCopilotTab({ lang, activeRequestId }) {
  const isAr = lang === 'ar';

  const [searchId, setSearchId] = useState(activeRequestId || '');
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [decisionSuccess, setDecisionSuccess] = useState(null);
  const [commentsEn, setCommentsEn] = useState('');
  const [commentsAr, setCommentsAr] = useState('');

  // Update searchId if activeRequestId changes from validation tab
  useEffect(() => {
    if (activeRequestId) {
      setSearchId(activeRequestId);
      fetchBrief(activeRequestId);
    }
  }, [activeRequestId]);

  const fetchBrief = async (reqId) => {
    const idToFetch = reqId || searchId;
    if (!idToFetch.trim()) return;

    setLoading(true);
    setDecisionSuccess(null);
    try {
      const resp = await fetch(`${API_BASE}/TradeName/ReviewerBrief/${encodeURIComponent(idToFetch.trim())}`);
      if (resp.status === 404) {
        alert(isAr ? 'لم يتم العثور على ملف ملخص المراجع لهذا المعرف' : 'Reviewer brief for this request ID was not found.');
        setBrief(null);
        return;
      }
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setBrief(data);
      setCommentsEn(data.draft_admin_comments_en || '');
      setCommentsAr(data.draft_admin_comments_ar || '');
    } catch (err) {
      alert(`Error loading brief: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (decision) => {
    if (!brief) return;
    setActionLoading(true);
    setDecisionSuccess(null);
    try {
      const resp = await fetch(`${API_BASE}/TradeName/ReviewerDecision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_id: brief.request_id,
          decision: decision,
          reviewer_id: 'officer_uaq_copilot',
          comments_en: commentsEn,
          comments_ar: commentsAr,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${resp.status}`);
      }

      setDecisionSuccess(decision);
      setBrief({ ...brief, reviewer_decision: decision });
    } catch (err) {
      alert(`Decision recording failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="tab-pane active" id="tab-copilot">
      {/* Top Search Bar for Request ID */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <h2 className="card-title">
            <span>🤖</span>
            <span>{isAr ? 'مساعد المراجع الذكي (Reviewer Copilot)' : 'AI Reviewer Copilot & Governance Dossier'}</span>
          </h2>
          <span className="badge badge-gold">{isAr ? 'نظام التحليل الذكي' : 'AI Analysis Engine'}</span>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '16px' }}>
          {isAr
            ? 'توليد وتدقيق ملف دراسة الاسم التجاري للمراجع الحكومي، مع شروحات المخاطر الثنائية ومسودات القرارات الإدارية.'
            : 'Prepares officer-facing intelligence brief with multi-tier risk analysis, draft administrative remarks, and closed-loop feedback.'}
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            fetchBrief(searchId);
          }}
          style={{ display: 'flex', gap: '12px', alignItems: 'center' }}
        >
          <input
            type="text"
            className="form-input"
            style={{ flex: 1 }}
            placeholder={isAr ? 'أدخل معرف الطلب (مثال: req-001 أو من عملية الفحص)...' : 'Enter Request ID (e.g. req-001 or from validation)...'}
            value={searchId}
            onChange={(e) => setSearchId(e.target.value)}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !searchId.trim()}
          >
            {loading ? (isAr ? 'جاري التحميل...' : 'Loading...') : (isAr ? '📑 استدعاء الملف' : '📑 Load Dossier')}
          </button>
        </form>
      </div>

      {!brief && !loading && (
        <div className="empty-state">
          <span className="empty-icon">📁</span>
          <p>
            {isAr
              ? 'أدخل معرف الطلب أعلاه لعرض ملف المراجع، أو قم بإجراء فحص في تبويب الفحص والضغط على "عرض في المساعد".'
              : 'Enter a Request ID above or validate a trade name to inspect the AI intelligence dossier.'}
          </p>
        </div>
      )}

      {brief && (
        <div className="grid-2col">
          {/* Left Column: Risk Flags, Similarity & Fit */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Recommendation & Overview Card */}
            <div className="card">
              <div className="card-header">
                <div>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Request ID: <strong>{brief.request_id}</strong>
                  </span>
                  <h3 style={{ margin: '4px 0 0 0' }}>
                    {isAr ? 'توصية الذكاء الاصطناعي' : 'AI Recommendation'}
                  </h3>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <span
                    className={`badge ${
                      brief.recommendation === 'approve'
                        ? 'badge-success'
                        : brief.recommendation === 'reject'
                        ? 'badge-danger'
                        : 'badge-warning'
                    }`}
                    style={{ fontSize: '0.85rem', padding: '6px 12px' }}
                  >
                    {brief.recommendation?.toUpperCase()}
                  </span>
                  {brief.reviewer_decision && (
                    <span className="badge badge-info" style={{ fontSize: '0.85rem', padding: '6px 12px' }}>
                      Status: {brief.reviewer_decision}
                    </span>
                  )}
                </div>
              </div>

              {brief.generated_on && (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
                  Generated on: {brief.generated_on}
                </div>
              )}

              {/* Activity Fit Verdict */}
              {brief.activity_fit_verdict && (
                <div
                  style={{
                    padding: '12px',
                    borderRadius: 'var(--radius)',
                    background: brief.activity_fit_verdict.is_fit ? 'rgba(52, 211, 153, 0.08)' : 'rgba(244, 63, 94, 0.08)',
                    border: `1px solid ${brief.activity_fit_verdict.is_fit ? 'rgba(52, 211, 153, 0.25)' : 'rgba(244, 63, 94, 0.25)'}`,
                    marginBottom: '14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>{isAr ? 'توافق النشاط الاقتصادي:' : 'Economic Activity Fit:'}</strong>
                    <span className={`badge ${brief.activity_fit_verdict.is_fit ? 'badge-success' : 'badge-danger'}`}>
                      {brief.activity_fit_verdict.is_fit ? 'Compatible' : 'Mismatch'}
                    </span>
                  </div>
                  <p style={{ margin: '6px 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    {isAr ? brief.activity_fit_verdict.reason_ar : brief.activity_fit_verdict.reason_en}
                  </p>
                </div>
              )}
            </div>

            {/* Compliance Flags */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">{isAr ? 'مؤشرات الامتثال والمخاطر' : 'Compliance & Risk Indicators'}</h3>
                <span className="badge badge-info">{brief.flags?.length || 0} Flags</span>
              </div>

              {(!brief.flags || brief.flags.length === 0) ? (
                <p style={{ color: '#34d399', margin: 0, fontSize: '0.9rem' }}>
                  ✅ {isAr ? 'لا توجد مخالفات قانونية أو لفظية مسجلة.' : 'No compliance violations or lexical flags triggered.'}
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {brief.flags.map((f, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '10px 12px',
                        borderRadius: 'var(--radius)',
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid var(--border-color)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span className="badge badge-danger">{f.code || 'FLAG'}</span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{f.stage}</span>
                      </div>
                      <p style={{ margin: '6px 0 2px 0', fontSize: '0.85rem' }} className="rtl">
                        {f.reason_ar}
                      </p>
                      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {f.reason_en}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Top Similar Registered Names */}
            {brief.top_similar && brief.top_similar.length > 0 && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">{isAr ? 'أعلى الأسماء المشابهة المسجلة' : 'Top Similar Registered Names'}</h3>
                  <span className="badge badge-warning">{brief.top_similar.length} Found</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {brief.top_similar.map((s, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '10px 12px',
                        background: 'rgba(255, 255, 255, 0.02)',
                        borderRadius: 'var(--radius)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600 }}>{s.normalized_ar}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{s.normalized_en}</div>
                      </div>
                      <span className="badge badge-warning">
                        {Math.round((s.similarity_score || 0) * 100)}% Sim
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Draft Comments & Decision Actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">{isAr ? 'مسودة الملاحظات الإدارية (AI Draft)' : 'Draft Administrative Comments'}</h3>
                <span className="badge badge-gold">{isAr ? 'ثنائي اللغة' : 'Bilingual Draft'}</span>
              </div>

              <div className="form-group" style={{ marginBottom: '16px' }}>
                <label className="form-label">{isAr ? 'الملاحظة الإدارية (بالعربية):' : 'Official Notice (Arabic):'}</label>
                <textarea
                  className="form-input rtl"
                  rows={4}
                  value={commentsAr}
                  onChange={(e) => setCommentsAr(e.target.value)}
                  placeholder="الملاحظات الموجهة للمتعامل بالعربية..."
                />
              </div>

              <div className="form-group" style={{ marginBottom: '16px' }}>
                <label className="form-label">{isAr ? 'الملاحظة الإدارية (بالإنجليزية):' : 'Official Notice (English):'}</label>
                <textarea
                  className="form-input"
                  rows={4}
                  value={commentsEn}
                  onChange={(e) => setCommentsEn(e.target.value)}
                  placeholder="Official comments for the applicant in English..."
                />
              </div>

              <hr style={{ borderColor: 'var(--border-color)', margin: '20px 0' }} />

              <h3 style={{ fontSize: '1rem', marginBottom: '12px', color: 'var(--gold-primary)' }}>
                {isAr ? 'اتخاذ القرار الإداري النهائي' : 'Record Officer Final Decision'}
              </h3>

              {decisionSuccess && (
                <div
                  style={{
                    padding: '12px',
                    borderRadius: 'var(--radius)',
                    background: 'rgba(52, 211, 153, 0.15)',
                    border: '1px solid rgba(52, 211, 153, 0.4)',
                    color: '#34d399',
                    marginBottom: '16px',
                    fontSize: '0.9rem',
                  }}
                >
                  ✅ {isAr ? `تم تسجيل القرار بنجاح: [${decisionSuccess}]` : `Decision logged to audit database: [${decisionSuccess}]`}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={actionLoading}
                  onClick={() => handleDecision('approve')}
                >
                  {isAr ? '✅ اعتماد الاسم' : '✅ Approve Name'}
                </button>

                <button
                  type="button"
                  className="btn btn-danger"
                  disabled={actionLoading}
                  onClick={() => handleDecision('reject')}
                >
                  {isAr ? '🚫 رفض الطلب' : '🚫 Reject Name'}
                </button>

                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={actionLoading}
                  onClick={() => handleDecision('return')}
                >
                  {isAr ? '↩️ إعادة للتعديل' : '↩️ Return for Correction'}
                </button>

                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ borderColor: '#a855f7', color: '#c084fc' }}
                  disabled={actionLoading}
                  onClick={() => handleDecision('ssp_committee')}
                >
                  {isAr ? '🏛️ إحالة للجنة الخاصة' : '🏛️ SSP Committee'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

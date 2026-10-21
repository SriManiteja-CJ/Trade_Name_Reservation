import React, { useState } from 'react';
import HeroBanner from './HeroBanner';
import { API_BASE } from '../config';

const PRESETS = [
  {
    label: "Al Noor (Compliant)",
    nameAr: "مخبز النور الحديث",
    nameEn: "Al Noor Modern Bakery",
    op: "new",
    legal: "LLC",
    cat: 1,
  },
  {
    label: "Casino (Hard Block)",
    nameAr: "كازينو الخليج",
    nameEn: "Gulf Casino",
    op: "new",
    legal: "LLC",
    cat: 1,
  },
  {
    label: "Outside UAQ Branch",
    nameAr: "مطعم الصقر",
    nameEn: "Falcon Restaurant",
    op: "branch",
    legal: "Branch",
    outsideUaq: true,
  },
  {
    label: "Legal Form Amend",
    nameAr: "شركة الأمل للتجارة",
    nameEn: "Al Amal Trading Co",
    op: "legal_form_amend",
    oldLegal: "LLC",
    newLegal: "PJSC",
    prevAr: "شركة الأمل للتجارة",
    prevEn: "Al Amal Trading Co",
  },
  {
    label: "Speed Cars (Duplicate Check)",
    nameAr: "السرعة للسيارات",
    nameEn: "Speed Cars",
    op: "new",
    legal: "LLC",
  },
];

export default function ValidationTab({ lang, channel, onValidationComplete, onNavigateCopilot }) {
  const isAr = lang === 'ar';

  const [requestId, setRequestId] = useState(`UAQ-REQ-2026-${Math.floor(1000 + Math.random() * 9000)}`);
  const [nameAr, setNameAr] = useState("مخبز الأمل للحلويات");
  const [nameEn, setNameEn] = useState("Hope Bakery & Sweets");
  const [opType, setOpType] = useState("new");
  const [legalForm, setLegalForm] = useState("LLC");
  const [activityCategory, setActivityCategory] = useState("1");
  const [excludeId, setExcludeId] = useState("");
  const [isOutsideUaq, setIsOutsideUaq] = useState(false);
  const [oldLegalForm, setOldLegalForm] = useState("");
  const [newLegalForm, setNewLegalForm] = useState("");
  const [prevNameAr, setPrevNameAr] = useState("");
  const [prevNameEn, setPrevNameEn] = useState("");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [translitResult, setTranslitResult] = useState(null);
  const [catResult, setCatResult] = useState(null);

  const applyPreset = (p) => {
    setNameAr(p.nameAr || "");
    setNameEn(p.nameEn || "");
    setOpType(p.op || "new");
    setLegalForm(p.legal || "LLC");
    if (p.cat) setActivityCategory(String(p.cat));
    setIsOutsideUaq(Boolean(p.outsideUaq));
    setOldLegalForm(p.oldLegal || "");
    setNewLegalForm(p.newLegal || "");
    setPrevNameAr(p.prevAr || "");
    setPrevNameEn(p.prevEn || "");
    setResult(null);
    setTranslitResult(null);
    setCatResult(null);
  };

  const handleValidate = async (e) => {
    e.preventDefault();
    setLoading(true);

    const payload = {
      RequestId: requestId.trim(),
      NameAr: nameAr.trim(),
      NameEn: nameEn.trim(),
      OperationType: opType,
      LegalForm: legalForm.trim() || null,
      ActivityCategoryId: parseInt(activityCategory) || null,
      TradeNameId: parseInt(excludeId) || null,
      IsOutsideUAQ: isOutsideUaq,
      OldLegalForm: oldLegalForm.trim() || null,
      NewLegalForm: newLegalForm.trim() || null,
      PreviousNameAr: prevNameAr.trim() || null,
      PreviousNameEn: prevNameEn.trim() || null,
      Channel: channel,
    };

    try {
      const resp = await fetch(`${API_BASE}/TradeName/ValidateWithSuggestion`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept-Language': lang,
          'X-Channel': channel,
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${resp.status}`);
      }

      const data = await resp.json();
      setResult(data);
      if (onValidationComplete) onValidationComplete(requestId);
    } catch (err) {
      alert(`Validation error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const checkTransliteration = async () => {
    try {
      const resp = await fetch(`${API_BASE}/TradeName/CheckTransliteration`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Channel': channel },
        body: JSON.stringify({ NameAr: nameAr, NameEn: nameEn }),
      });
      const data = await resp.json();
      setTranslitResult(data);
    } catch (err) {
      alert(`Transliteration check failed: ${err.message}`);
    }
  };

  const suggestCategory = async () => {
    try {
      const resp = await fetch(`${API_BASE}/TradeName/SuggestCategory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Channel': channel },
        body: JSON.stringify({ NameAr: nameAr, NameEn: nameEn }),
      });
      const data = await resp.json();
      setCatResult(data);
    } catch (err) {
      alert(`Category suggestion failed: ${err.message}`);
    }
  };

  return (
    <div className="compliance-tab-container" dir={isAr ? 'rtl' : 'ltr'}>
      <HeroBanner
        isAr={isAr}
        title={isAr ? 'الامتثال وفحص بوابات الرقابة' : 'Compliance & Governance Inspection'}
        breadcrumbs={[
          isAr ? 'الخدمات الذكية' : 'Smart Services',
          isAr ? 'الامتثال والرقابة' : 'Compliance & Risk Controls'
        ]}
      />
      <div className="grid-layout">
      {/* Left Column: Form & Presets */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">{isAr ? 'فحص وصياغة الاسم التجاري' : 'Trade Name Validation Form'}</h2>
            <div className="card-sub">{isAr ? 'الفحص عبر البوابات القطعية ومحرك الذكاء الاصطناعي (المراحل ١-٦)' : 'Strict deterministic gate checks + AI analyzer (Stages ①–⑥)'}</div>
          </div>
          <span className="badge badge-info">{isAr ? 'مباشر' : 'Live'}</span>
        </div>

        {/* Preset Chips */}
        <div className="preset-chips">
          {PRESETS.map((p, i) => (
            <button
              key={i}
              type="button"
              className="preset-chip"
              onClick={() => applyPreset(p)}
            >
              {p.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleValidate} className="form-grid">
          <div className="form-group full-width">
            <label>{isAr ? 'رقم طلب المعاملة' : 'Application Request ID'}</label>
            <input
              type="text"
              className="input-control"
              value={requestId}
              onChange={(e) => setRequestId(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>{isAr ? 'الاسم التجاري بالعربية' : 'Arabic Trade Name'}</label>
            <input
              type="text"
              className="input-control input-ar"
              value={nameAr}
              onChange={(e) => setNameAr(e.target.value)}
              dir="rtl"
              required
            />
          </div>

          <div className="form-group">
            <label>{isAr ? 'الاسم التجاري بالإنجليزية' : 'English Trade Name'}</label>
            <input
              type="text"
              className="input-control"
              value={nameEn}
              onChange={(e) => setNameEn(e.target.value)}
              required
            />
          </div>

          {/* Quick Helper Actions */}
          <div className="full-width" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-sm btn-outline"
              onClick={checkTransliteration}
              style={{ color: '#38bdf8', borderColor: 'rgba(56, 189, 248, 0.4)' }}
            >
              🔍 {isAr ? 'فحص المطابقة الصوتية' : 'Quick Translit Check'}
            </button>
            <button
              type="button"
              className="btn btn-sm btn-outline"
              onClick={suggestCategory}
              style={{ color: '#fbbf24', borderColor: 'rgba(251, 191, 36, 0.4)' }}
            >
              🏷️ {isAr ? 'اقتراح النشاط التجاري' : 'Auto-Suggest Category'}
            </button>
          </div>

          {/* Translit Banner */}
          {translitResult && (
            <div className="full-width" style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '10px', borderRadius: '6px', border: '1px solid rgba(56, 189, 248, 0.3)', fontSize: '12px' }}>
              <strong>{isAr ? 'نتيجة فحص التعريب:' : 'Transliteration Verdict:'}</strong> {translitResult.consistent ? '✅ متطابق (Consistent)' : '⚠️ غير متطابق (Inconsistent)'} • {isAr ? 'نسبة الثقة:' : 'Confidence:'} {Math.round(translitResult.confidence * 100)}%
            </div>
          )}

          {/* Category Banner */}
          {catResult && (
            <div className="full-width" style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '10px', borderRadius: '6px', border: '1px solid rgba(251, 191, 36, 0.3)', fontSize: '12px' }}>
              <strong>{isAr ? 'النشاط المقترح:' : 'Suggested Activity Category:'}</strong> <span style={{ color: '#fbbf24', fontWeight: 700 }}>{catResult.suggested_category_code}</span> • {isAr ? catResult.reason_ar : catResult.reason_en}
            </div>
          )}

          <div className="form-group">
            <label>{isAr ? 'نوع المعاملة' : 'Operation Type'}</label>
            <select
              className="input-control"
              value={opType}
              onChange={(e) => setOpType(e.target.value)}
            >
              <option value="new">New Registration (حجز جديد)</option>
              <option value="edit">Edit Trade Name (تعديل اسم)</option>
              <option value="renew">Renewal (تجديد رخصة)</option>
              <option value="branch">Branch Office (فرع رخصة)</option>
              <option value="legal_form_amend">Legal Form Amendment (تعديل الشكل القانوني)</option>
            </select>
          </div>

          <div className="form-group">
            <label>{isAr ? 'الشكل القانوني' : 'Legal Form'}</label>
            <input
              type="text"
              className="input-control"
              value={legalForm}
              onChange={(e) => setLegalForm(e.target.value)}
              placeholder="e.g. LLC, PJSC"
            />
          </div>

          <div className="form-group">
            <label>{isAr ? 'رمز النشاط الاقتصادي' : 'Activity Category ID'}</label>
            <input
              type="number"
              className="input-control"
              value={activityCategory}
              onChange={(e) => setActivityCategory(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label>{isAr ? 'استثناء معرف الاسم الحالي' : 'Exclude Current Record ID'}</label>
            <input
              type="number"
              className="input-control"
              value={excludeId}
              onChange={(e) => setExcludeId(e.target.value)}
              placeholder="e.g. 104"
            />
          </div>

          {/* Branch Outside UAQ Checkbox */}
          <div className="form-group full-width">
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px' }}>
              <input
                type="checkbox"
                checked={isOutsideUaq}
                onChange={(e) => setIsOutsideUaq(e.target.checked)}
              />
              <span>{isAr ? 'فرع خارج أم القيوين (تطبيق لاحقة "فرع أم القيوين" تلقائياً)' : 'Branch outside UAQ (Applies suffix "Umm Al Quwain Branch")'}</span>
            </label>
          </div>

          {/* Amendment specific inputs */}
          {opType === 'legal_form_amend' && (
            <div className="full-width form-grid" style={{ background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px' }}>
              <div className="form-group">
                <label>{isAr ? 'الشكل القانوني السابق' : 'Old Legal Form'}</label>
                <input type="text" className="input-control" value={oldLegalForm} onChange={(e) => setOldLegalForm(e.target.value)} placeholder="e.g. LLC" />
              </div>
              <div className="form-group">
                <label>{isAr ? 'الشكل القانوني الجديد' : 'New Legal Form'}</label>
                <input type="text" className="input-control" value={newLegalForm} onChange={(e) => setNewLegalForm(e.target.value)} placeholder="e.g. PJSC" />
              </div>
            </div>
          )}

          <div className="form-actions full-width" style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
            <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex: 1 }}>
              {loading ? (isAr ? 'جاري الفحص...' : 'Validating...') : (isAr ? 'فحص الاسم التجاري (Validate)' : 'Validate Trade Name')}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setNameAr("");
                setNameEn("");
                setResult(null);
                setTranslitResult(null);
                setCatResult(null);
              }}
            >
              {isAr ? 'مسح' : 'Clear'}
            </button>
          </div>
        </form>
      </div>

      {/* Right Column: Results & Suggestions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Outcome Card */}
        <div className="card">
          <div className="outcome-header">
            <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: 600 }}>
              {isAr ? 'قرار الفحص:' : 'Validation Decision:'}
            </span>
            {result ? (
              <span className={`outcome-badge badge-${result.decision.toLowerCase()}`}>
                {result.decision}
              </span>
            ) : (
              <span className="outcome-badge" style={{ background: 'rgba(148, 163, 184, 0.15)', color: '#94a3b8' }}>
                {isAr ? 'جاهز للفحص' : 'READY TO VALIDATE'}
              </span>
            )}
          </div>

          {result && onNavigateCopilot && (
            <div style={{ marginTop: '12px', marginBottom: '8px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ width: '100%', borderColor: 'var(--gold-primary)', color: 'var(--gold-primary)', fontSize: '0.85rem' }}
                onClick={() => onNavigateCopilot(requestId)}
              >
                {isAr ? '🤖 فتح ملف الطلب في مساعد المراجع (Copilot)' : '🤖 Open Dossier in Reviewer Copilot'}
              </button>
            </div>
          )}

          {result ? (
            <div>
              {result.decision === 'OK' && (
                <p style={{ color: '#34d399', fontWeight: 600 }}>
                  ✓ {isAr ? 'الاسم التجاري يستوفي جميع الشروط المحددة ولا يتعارض مع الأسماء المحجوزة.' : 'Trade name satisfies all deterministic rules and active registry criteria.'}
                </p>
              )}
              {result.decision === 'NEEDS_REVIEW' && (
                <p style={{ color: '#fbbf24', fontWeight: 600 }}>
                  ⚠ {isAr ? 'يتطلب مراجعة من قبل موظف الدائرة أو لجنة التدقيق الخاصة (SSP).' : 'Flagged for human reviewer inspection (e.g. location name, ambiguity).'}
                </p>
              )}
              {result.decision === 'BLOCKED' && (
                <p style={{ color: '#fb7185', fontWeight: 600 }}>
                  ✕ {isAr ? 'تم رفض الاسم لوجود تعارض قطعي أو كلمة محظورة.' : 'Hard gate rejection: exact duplicate in active registry or prohibited term.'}
                </p>
              )}
            </div>
          ) : (
            <p style={{ color: 'var(--text-subtle)', fontSize: '0.85rem' }}>
              {isAr ? 'يرجى إدخال اسم تجاري أو اختيار أحد النماذج لفحص الاسم عبر البوابات القطعية ومحرك الذكاء الاصطناعي.' : 'Submit a trade name or choose a preset to inspect deterministic gate checks and pipeline behavior.'}
            </p>
          )}
        </div>

        {/* Bilingual Flags & Reasons */}
        {result && result.reasons && result.reasons.length > 0 && (
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '10px' }}>
              {isAr ? 'الأسباب والملاحظات (Flags & Fixes)' : 'Flags & Fix Recommendations'}
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {result.reasons.map((r, i) => (
                <div key={i} style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '10px', borderRadius: '6px', borderLeft: `3px solid ${r.severity === 'block' ? '#f43f5e' : '#fbbf24'}` }}>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#fff' }}>
                    [{r.severity.toUpperCase()}] {r.category}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {isAr ? r.reason_ar : r.reason_en}
                  </div>
                  {(r.fix_en || r.fix_ar) && (
                    <div style={{ fontSize: '0.75rem', color: '#38bdf8', marginTop: '4px' }}>
                      💡 {isAr ? r.fix_ar : r.fix_en}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AI & Deterministic Suggestions */}
        {result && result.suggestions && result.suggestions.length > 0 && (
          <div className="card">
            <div className="card-header" style={{ marginBottom: '8px' }}>
              <h3 className="card-title" style={{ color: '#38bdf8' }}>
                ✨ {isAr ? 'الأسماء البديلة المقترحة' : 'AI Trade Name Suggestions'}
              </h3>
              <span className="badge badge-info">{isAr ? 'اقتراحات ذكية' : 'Smart Suggestions'}</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px' }}>
              {isAr ? 'أسماء مميزة وغير محجوزة. اضغط "استخدام الاسم" لتطبيقه مباشرة.' : 'Distinct, unreserved alternatives. Click "Use Name" to apply.'}
            </p>
            <div className="suggestions-grid">
              {result.suggestions.map((s, i) => (
                <div key={i} className="suggestion-item-card">
                  <div>
                    <div className="suggestion-name-en">{s.name_en}</div>
                    <div className="suggestion-name-ar">{s.name_ar}</div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline"
                    style={{ borderColor: 'rgba(56, 189, 248, 0.4)', color: '#38bdf8' }}
                    onClick={() => {
                      setNameAr(s.name_ar);
                      setNameEn(s.name_en);
                    }}
                  >
                    {isAr ? 'استخدام' : 'Use Name'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Standard API Inspector */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">{isAr ? 'عقد استجابة النظام الأساسي' : 'Standard DED API Response Contract'}</h3>
            <span className="badge badge-info">{isAr ? 'توافق كامل' : 'Full Compatibility'}</span>
          </div>
          <div className="legacy-grid">
            <div className="legacy-item">
              <span className="legacy-key">Prohibted:</span>
              <span className={`legacy-val ${result?.Prohibted ? 'true' : 'false'}`}>{String(result?.Prohibted ?? false)}</span>
            </div>
            <div className="legacy-item">
              <span className="legacy-key">Profanity:</span>
              <span className={`legacy-val ${result?.Profanity ? 'true' : 'false'}`}>{String(result?.Profanity ?? false)}</span>
            </div>
            <div className="legacy-item">
              <span className="legacy-key">Unfriendly:</span>
              <span className={`legacy-val ${result?.Unfriendly ? 'true' : 'false'}`}>{String(result?.Unfriendly ?? false)}</span>
            </div>
            <div className="legacy-item">
              <span className="legacy-key">Special:</span>
              <span className={`legacy-val ${result?.Special ? 'true' : 'false'}`}>{String(result?.Special ?? false)}</span>
            </div>
            <div className="legacy-item">
              <span className="legacy-key">AllahNames:</span>
              <span className={`legacy-val ${result?.AllahNames ? 'true' : 'false'}`}>{String(result?.AllahNames ?? false)}</span>
            </div>
            <div className="legacy-item">
              <span className="legacy-key">LocationNames:</span>
              <span className={`legacy-val ${result?.LocationNames ? 'true' : 'false'}`}>{String(result?.LocationNames ?? false)}</span>
            </div>
            <div className="legacy-item">
              <span className="legacy-key">FamilyNames:</span>
              <span className={`legacy-val ${result?.FamilyNames ? 'true' : 'false'}`}>{String(result?.FamilyNames ?? false)}</span>
            </div>
            <div className="legacy-item">
              <span className="legacy-key">Similarity:</span>
              <span className="legacy-val">{result?.Similarity ?? 0.0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);
}

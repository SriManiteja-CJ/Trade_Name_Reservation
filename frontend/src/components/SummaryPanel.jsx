import React from 'react';

export default function SummaryPanel({
  isAr,
  mode = 'initial', // 'initial' (Screens 2 & 6) vs 'summary' (Screens 3, 4, 5)
  reservationType = 'new', // 'new' vs 'branch'
  selectedName,
  legalForm = 'Limited Liability Company',
  selectedActivity,
  parentLicenseNo = '123456',
  onSubmitPay,
  onSaveDraft,
  onPayLater,
}) {
  if (mode === 'initial') {
    return (
      <aside className="figma-summary-card initial-card" aria-label="Service Details">
        <div className="initial-description-text">
          {isAr
            ? 'رخصة لتشجيع مواطني دولة الإمارات والمقيمين (في إمارة أم القيوين) على ممارسة الأعمال من المنزل وعبر الإنترنت (وسائل التواصل الاجتماعي).'
            : 'A license to encourage UAE nationals & residents (in Umm Al Quwain) to conduct business from home and online (social media).'}
        </div>

        <div className="initial-beneficiary-section">
          <h4 className="beneficiary-heading">
            {isAr ? 'المستفيدون:' : 'Beneficiary:'}
          </h4>
          <div className="beneficiary-item">
            {isAr ? 'مواطنو الدولة (18 سنة فما فوق)' : 'UAE Nationals (18 and above)'}
          </div>
          <div className="beneficiary-item">
            {isAr ? 'المقيمون بالدولة (21 سنة فما فوق)' : 'UAE Residents (21 and above)'}
          </div>
        </div>

        <div className="initial-cost-section">
          <h4 className="cost-heading">
            {isAr ? 'تكلفة الخدمة' : 'Service Cost'}
          </h4>
          <div className="cost-row">
            <span className="cost-duration">{isAr ? 'سنة واحدة' : '1 Year'}</span>
            <span className="cost-amount">AED 1000</span>
          </div>
        </div>
      </aside>
    );
  }

  // Summary State (Screens 3, 4, 5)
  const isBranch = reservationType === 'branch';

  return (
    <aside className="figma-summary-card" aria-label="Summary">
      <h3 className="summary-heading">
        {isAr ? 'الملخص' : 'Summary'}
      </h3>

      {/* Summary Field Items */}
      <div className="summary-field-group">
        <div className="summary-field-label">
          {isAr ? 'النوع :' : 'Type :'}
        </div>
        <div className="summary-field-value">
          {isBranch
            ? (isAr ? 'فرع لرخصة خارج أم القيوين' : 'Branch of a licence outside UAQ')
            : (isAr ? 'رخصة جديدة داخل أم القيوين' : 'New License inside UAQ')}
        </div>
      </div>

      {isBranch && (
        <div className="summary-field-group">
          <div className="summary-field-label">
            {isAr ? 'الرخصة الأم' : 'Parent licence'}
          </div>
          <div className="summary-field-value">
            {isAr ? `مسترجعة · [${parentLicenseNo}] · دبي` : `Fetched · [${parentLicenseNo}] · Dubai`}
          </div>
        </div>
      )}

      <div className="summary-field-group">
        <div className="summary-field-label">
          {isAr ? 'الشكل القانوني' : 'Legal Form'}
        </div>
        <div className="summary-field-value">
          {isBranch
            ? (isAr ? 'فرع شركة مسجلة في إمارة أخرى' : 'Branch of company registered in other emirates')
            : (legalForm || (isAr ? 'غير محدد' : 'Not Selected'))}
        </div>
      </div>

      <div className="summary-field-group">
        <div className="summary-field-label">
          {isAr ? 'الأنشطة' : 'Activities'}
        </div>
        <div className="summary-field-value">
          {selectedActivity || (isAr ? 'غير محدد' : 'Not Selected')}
        </div>
      </div>

      {!isBranch && (
        <div className="summary-field-group">
          <div className="summary-field-label">
            {isAr ? 'الاسم المختار' : 'Select Name'}
          </div>
          <div className="summary-field-value">
            {selectedName || (isAr ? 'لم يتم التحقق بعد' : 'Not Validated yet')}
          </div>
        </div>
      )}

      <div className="summary-divider" />

      {/* Fees Breakdown */}
      <div className="summary-fees-section">
        <h4 className="fees-heading">
          {isAr ? 'الرسوم' : 'Fees'}
        </h4>

        <div className="fee-line-item">
          <span>{isAr ? 'رخصة إبداع (سنة واحدة)' : 'Ibdaa licence (1 year)'}</span>
          <span className="fee-val">AED 1000</span>
        </div>
        <div className="fee-line-item">
          <span>{isAr ? 'رسوم الخدمات الإلكترونية' : 'Electronic service fee'}</span>
          <span className="fee-val">{isAr ? 'رسوم' : 'Fee'}</span>
        </div>
        <div className="fee-line-item">
          <span>{isAr ? 'رسوم الدفع الإلكتروني' : 'Electronic payment fee'}</span>
          <span className="fee-val">{isAr ? 'رسوم' : 'Fee'}</span>
        </div>
        <div className="fee-line-item">
          <span>{isAr ? 'رسوم أخرى' : 'Other fees'}</span>
          <span className="fee-val">{isAr ? 'رسوم' : 'Fee'}</span>
        </div>
      </div>

      <div className="summary-divider" />

      {/* Total Fee */}
      <div className="summary-total-row">
        <span>{isAr ? 'إجمالي الرسوم' : 'Total Fee'}</span>
        <span className="total-amount">AED 1000</span>
      </div>

      {/* Action Buttons Stack */}
      <div className="summary-action-buttons">
        <button
          type="button"
          className="btn-submit-pay"
          onClick={onSubmitPay}
        >
          {isAr ? 'إرسال ودفع' : 'Submit & Pay'}
        </button>

        <button
          type="button"
          className="btn-save-draft"
          onClick={onSaveDraft}
        >
          {isAr ? 'حفظ كمسودة' : 'Save Draft'}
        </button>

        <button
          type="button"
          className="btn-pay-later"
          onClick={onPayLater}
        >
          {isAr ? 'الدفع لاحقاً' : 'Pay Later'}
        </button>
      </div>
    </aside>
  );
}

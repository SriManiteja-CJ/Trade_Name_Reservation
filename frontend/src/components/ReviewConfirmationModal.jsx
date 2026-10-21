import React from 'react';

export default function ReviewConfirmationModal({
  isAr,
  onClose,
  onConfirm,
  formData,
  loading,
}) {
  return (
    <div className="figma-modal-overlay" role="dialog" aria-modal="true">
      <div className="figma-modal-dialog" style={{ maxWidth: '620px' }}>
        <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
          ×
        </button>

        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f2952', marginBottom: '6px' }}>
          {isAr ? 'مراجعة وتأكيد حجز الاسم التجاري' : 'Application Review & Confirmation'}
        </h2>
        <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '20px' }}>
          {isAr
            ? 'يرجى مراجعة تفاصيل الطلب بدقة قبل الاعتماد النهائي وإصدار إشعار الحجز الرسمي.'
            : 'Please review the license and trade name details before submitting your formal reservation.'}
        </p>

        {/* 2-Column Summary Grid */}
        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '20px' }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>{isAr ? 'الاسم التجاري (بالعربية):' : 'Trade Name (Arabic):'}</div>
            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0f2952' }} className="rtl">{formData.nameAr || '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>{isAr ? 'الاسم التجاري (بالإنجليزية):' : 'Trade Name (English):'}</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#1e293b' }}>{formData.nameEn || '—'}</div>
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>{isAr ? 'الشكل القانوني:' : 'Legal Form:'}</div>
            <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#334155' }}>{formData.legalForm || 'LLC'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>{isAr ? 'فئة النشاط الاقتصادي:' : 'Activity Category:'}</div>
            <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#334155' }}>{formData.activityCategory || 'COMM_001'}</div>
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>{isAr ? 'الإمارة:' : 'Emirate:'}</div>
            <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#334155' }}>{isAr ? 'أم القيوين' : 'Umm Al Quwain'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>{isAr ? 'نوع الفرع:' : 'Branch Status:'}</div>
            <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#334155' }}>
              {formData.isOutsideUaq ? (isAr ? 'فرع خارج الإمارة' : 'Outside UAQ Branch') : (isAr ? 'رئيسي / داخل الإمارة' : 'Main / Inside UAQ')}
            </div>
          </div>

          <div style={{ gridColumn: 'span 2', borderTop: '1px solid #e2e8f0', paddingTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 700, color: '#0f2952', fontSize: '0.95rem' }}>{isAr ? 'إجمالي الرسوم المقدرة:' : 'Total Estimated Fee:'}</span>
            <span style={{ fontWeight: 800, color: '#0f2952', fontSize: '1.15rem' }}>AED 750</span>
          </div>
        </div>

        {/* Buttons Row */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button
            type="button"
            className="btn-figma-secondary"
            onClick={onClose}
            disabled={loading}
          >
            {isAr ? 'إلغاء' : 'Cancel'}
          </button>
          <button
            type="button"
            className="btn-figma-primary"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? (isAr ? 'جاري التأكيد...' : 'Confirming...') : (isAr ? 'تأكيد الحجز النهائي' : 'Confirm Reservation')}
          </button>
        </div>
      </div>
    </div>
  );
}

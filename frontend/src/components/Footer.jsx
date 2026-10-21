import React from 'react';

export default function Footer({ lang }) {
  const isAr = lang === 'ar';

  return (
    <footer
      style={{
        marginTop: 'auto',
        borderTop: '1px solid var(--border-color)',
        background: 'rgba(11, 15, 25, 0.95)',
        backdropFilter: 'blur(12px)',
        padding: '30px 0',
        fontSize: '0.85rem',
        color: 'var(--text-muted)',
      }}
    >
      <div className="container" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--gold-primary)', fontSize: '0.95rem' }}>
              {isAr ? 'حكومة أم القيوين • دائرة التنمية الاقتصادية' : 'Government of Umm Al Quwain • Department of Economic Development'}
            </div>
            <div style={{ marginTop: '4px' }}>
              {isAr
                ? 'نظام الذكاء الاصطناعي لتدقيق الأسماء التجارية واقتراح البدائل المتوافقة'
                : 'Next-Generation Trade Name Intelligence & Compliance Service'}
            </div>
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderTop: '1px solid rgba(255,255,255,0.05)',
            paddingTop: '12px',
            flexWrap: 'wrap',
            gap: '8px',
            fontSize: '0.78rem',
          }}
        >
          <div>
            {isAr
              ? 'متوافق مع القانون الاتحادي رقم (37) لسنة 1992 وقانون العلامات التجارية الاتحادي رقم (36) لسنة 2021.'
              : 'Governed under UAE Federal Law No. 37 of 1992 & Federal Decree-Law No. 36 of 2021 on Trademarks.'}
          </div>
          <div>
            {isAr ? 'نظام الاستعلام والرقابة على الأسماء التجارية • أم القيوين' : 'Official Trade Name Intelligence & Governance Platform'}
          </div>
        </div>
      </div>
    </footer>
  );
}

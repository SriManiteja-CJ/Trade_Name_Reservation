import React, { useState } from 'react';

const CATALOG_ITEMS = [
  { id: 1, ar: "مخبز النور الحديث", en: "Al Noor Modern Bakery", category: "Commercial", tag: "Bakery & Sweets" },
  { id: 2, ar: "الصقر لتجارة المعدات", en: "Falcon Equipment Trading", category: "Commercial", tag: "General Trading" },
  { id: 3, ar: "الأمل للاستشارات التقنية", en: "Al Amal Tech Advisory", category: "Professional", tag: "IT & Advisory" },
  { id: 4, ar: "الخليج للمقاولات العامة", en: "Gulf General Contracting", category: "Industrial", tag: "Construction" },
  { id: 5, ar: "الريادة لخدمات الأعمال", en: "Al Reyada Business Services", category: "Professional", tag: "Consultancy" },
  { id: 6, ar: "الأفق للصناعات الغذائية", en: "Horizon Food Industries", category: "Industrial", tag: "Food Packaging" },
];

export default function SuggestionsCatalogModal({ isAr, onClose, onSelectName }) {
  const [activeTab, setActiveTab] = useState('select');
  const [activeCategory, setActiveCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');

  const categories = ['All', 'Commercial', 'Professional', 'Industrial'];

  const filteredItems = CATALOG_ITEMS.filter((item) => {
    const matchesCat = activeCategory === 'All' || item.category === activeCategory;
    const matchesQuery =
      !searchQuery.trim() ||
      item.ar.includes(searchQuery) ||
      item.en.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesQuery;
  });

  return (
    <div className="figma-modal-overlay" role="dialog" aria-modal="true">
      <div className="figma-modal-dialog" style={{ maxWidth: '680px' }}>
        <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
          ×
        </button>

        {/* Top Segmented Tab Pill */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', background: '#f1f5f9', padding: '4px', borderRadius: '8px' }}>
          <button
            type="button"
            style={{
              flex: 1,
              padding: '8px 16px',
              border: 'none',
              borderRadius: '6px',
              background: activeTab === 'select' ? '#0f2952' : 'transparent',
              color: activeTab === 'select' ? '#ffffff' : '#64748b',
              fontWeight: 600,
              fontSize: '0.88rem',
              cursor: 'pointer',
            }}
            onClick={() => setActiveTab('select')}
          >
            {isAr ? 'اختيار اسم تجاري معتمد' : 'Select Trade Name'}
          </button>
          <button
            type="button"
            style={{
              flex: 1,
              padding: '8px 16px',
              border: 'none',
              borderRadius: '6px',
              background: activeTab === 'upload' ? '#0f2952' : 'transparent',
              color: activeTab === 'upload' ? '#ffffff' : '#64748b',
              fontWeight: 600,
              fontSize: '0.88rem',
              cursor: 'pointer',
            }}
            onClick={() => setActiveTab('upload')}
          >
            {isAr ? 'إرفاق وثيقة موافقة خاصة' : 'Upload Special Approval'}
          </button>
        </div>

        {activeTab === 'select' ? (
          <div>
            {/* Search Input */}
            <div style={{ marginBottom: '16px' }}>
              <input
                type="text"
                className="figma-input"
                placeholder={isAr ? 'بحث في قائمة الأسماء المقترحة...' : 'Search suggested trade names or keywords...'}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Category Filter Pills */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '18px', flexWrap: 'wrap' }}>
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  style={{
                    padding: '6px 14px',
                    borderRadius: '20px',
                    border: activeCategory === cat ? '1.5px solid #0f2952' : '1px solid #cbd5e1',
                    background: activeCategory === cat ? '#0f2952' : '#ffffff',
                    color: activeCategory === cat ? '#ffffff' : '#475569',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                  onClick={() => setActiveCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Grid of Selectable Name Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {filteredItems.map((item) => (
                <div
                  key={item.id}
                  style={{
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '12px 14px',
                    background: '#ffffff',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.72rem', color: '#0284c7', background: '#f0f9ff', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                      {item.tag}
                    </span>
                    <button
                      type="button"
                      style={{
                        padding: '4px 10px',
                        background: '#0f2952',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                      onClick={() => onSelectName(item.ar, item.en)}
                    >
                      {isAr ? 'اختيار' : 'Select'}
                    </button>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: '0.98rem', color: '#0f2952' }} className="rtl">
                    {item.ar}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#64748b' }}>
                    {item.en}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ padding: '30px', textAlign: 'center', border: '2px dashed #cbd5e1', borderRadius: '8px' }}>
            <span style={{ fontSize: '2.5rem' }}>📄</span>
            <p style={{ marginTop: '10px', fontSize: '0.9rem', color: '#64748b' }}>
              {isAr
                ? 'يرجى سحب وإفلات موافقة الجهة المعنية (الأسماء السيادية أو الاستثناءات القانونية).'
                : 'Upload special authority approval document (e.g. Sovereign approval or SSP waiver).'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

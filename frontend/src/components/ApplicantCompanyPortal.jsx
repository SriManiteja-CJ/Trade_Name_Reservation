import React, { useState } from 'react';

export default function ApplicantCompanyPortal({ onSelectService, isAr }) {
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Filter service items by search and tab
  const filterService = (title, tag) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      if (!title.toLowerCase().includes(q)) return false;
    }
    if (activeTab === 'all') return true;
    if (activeTab === 'inquiries' && tag === 'inquiries') return true;
    if (activeTab === 'new-license' && tag === 'new-license') return true;
    if (activeTab === 'others' && tag === 'others') return true;
    return true;
  };

  return (
    <div className="portal-page-container">
      {/* Underlying Dashboard Stage (Visible behind modal matching Figma reference) */}
      <div className="dashboard-background-stage">
        {/* Top Dark Hero Card */}
        <div className="dashboard-hero-card">
          <div className="hero-text-col">
            <span className="hero-badge">
              {isAr ? 'الخدمات الذكية لدائرة التنمية الاقتصادية' : 'DED Smart Services'}
            </span>
            <h1 className="hero-welcome-title">
              {isAr ? 'مرحباً بك، محمد كمران' : 'Welcome to DED Smart Services'}
            </h1>
            <div className="applicant-details-card">
              <div className="applicant-detail-item">
                <span className="detail-lbl">{isAr ? 'المتقدم:' : 'Applicant:'}</span>
                <span className="detail-val">Mohammed Kamran</span>
              </div>
              <div className="applicant-detail-item">
                <span className="detail-lbl">{isAr ? 'رقم الهاتف:' : 'Mobile:'}</span>
                <span className="detail-val">+971561234567</span>
              </div>
              <div className="applicant-detail-item">
                <span className="detail-lbl">{isAr ? 'البريد الإلكتروني:' : 'Email:'}</span>
                <span className="detail-val">MohammedKamran@gmail.com</span>
              </div>
            </div>
          </div>

          <div className="hero-avatar-col">
            <img
              src="/assets/user-avatar.png"
              alt="Applicant Profile"
              className="dashboard-hero-avatar"
            />
          </div>
        </div>

        {/* Dashboard Quick Stats Row */}
        <div className="dashboard-stats-row">
          <div className="dash-stat-box">
            <div className="stat-label">{isAr ? 'الرخص الفعالة' : 'Active Licenses'}</div>
            <div className="stat-big-num">2</div>
            <div className="stat-meta">{isAr ? 'أم القيوين' : 'UAQ Mainland'}</div>
          </div>
          <div className="dash-stat-box">
            <div className="stat-label">{isAr ? 'الطلبات المنجزة' : 'Total Requests'}</div>
            <div className="stat-big-num">18</div>
            <div className="stat-meta">{isAr ? 'خلال 12 شهر' : 'Last 12 months'}</div>
          </div>
          <div className="dash-stat-box">
            <div className="stat-label">{isAr ? 'معدل الامتثال' : 'Compliance Rate'}</div>
            <div className="stat-big-num green-text">99%</div>
            <div className="stat-meta">{isAr ? 'معايير الدائرة' : 'DED Standard'}</div>
          </div>
          <div className="dash-stat-box action-box">
            <button
              type="button"
              className="btn-open-catalogue-banner"
              onClick={() => setIsModalOpen(true)}
            >
              <span className="plus-icon">⊕</span>
              {isAr ? 'فتح دليل الخدمات' : 'Open Service Catalogue'}
            </button>
          </div>
        </div>
      </div>

      {/* Modal / Dialog Overlay (Figma Prototype Screen 0) */}
      {isModalOpen && (
        <div className="portal-modal-backdrop" onClick={() => setIsModalOpen(false)}>
          <div
            className="service-catalogue-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="catalogue-title"
          >
            {/* Modal Close Button */}
            <button
              type="button"
              className="catalogue-modal-close"
              onClick={() => setIsModalOpen(false)}
              title={isAr ? 'إغلاق' : 'Close'}
              aria-label="Close dialogue"
            >
              ✕
            </button>

            {/* Top Header Stats Banner (New / General vs Existing License) */}
            <div className="catalogue-banner-row">
              <div
                className={`catalogue-stat-card primary ${activeTab === 'new-license' ? 'highlight-active' : ''}`}
                onClick={() => setActiveTab('new-license')}
              >
                <div className="stat-icon-title">
                  <div className="stat-bubble-icon">⊕</div>
                  <div>
                    <div className="stat-title">
                      {isAr ? 'جديد / عام' : 'New / General'}
                    </div>
                    <div className="stat-desc">
                      {isAr ? 'استفسارات، رخص جديدة، شكاوى' : 'Inquiries, new licenses, complaints'}
                    </div>
                  </div>
                </div>
                <div className="stat-count">10</div>
              </div>

              <div
                className="catalogue-stat-card secondary"
                onClick={() => setActiveTab('inquiries')}
              >
                <div className="stat-icon-title">
                  <div className="stat-bubble-icon doc">📄</div>
                  <div>
                    <div className="stat-title">
                      {isAr ? 'رخصة حالية' : 'Existing license'}
                    </div>
                    <div className="stat-desc">
                      {isAr ? 'تجديد، تعديل، عقود، حالة' : 'Renew, amend, contracts, status'}
                    </div>
                  </div>
                </div>
                <div className="stat-count">22</div>
              </div>
            </div>

            {/* Search Bar */}
            <div className="catalogue-search-bar">
              <span className="search-icon">🔍</span>
              <input
                id="catalogue-search-input"
                type="text"
                className="search-input"
                placeholder={isAr ? 'ابحث عن خدمة باللغة الإنجليزية أو العربية' : 'Search service in english or arabic'}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  className="clear-search-btn"
                  onClick={() => setSearchQuery('')}
                >
                  ✕
                </button>
              )}
            </div>

            {/* Filter Pills */}
            <div className="catalogue-filter-pills">
              <button
                type="button"
                className={`filter-pill ${activeTab === 'all' ? 'active' : ''}`}
                onClick={() => setActiveTab('all')}
              >
                {isAr ? 'الكل' : 'All'} <span className="pill-badge">10</span>
              </button>
              <button
                type="button"
                className={`filter-pill ${activeTab === 'inquiries' ? 'active' : ''}`}
                onClick={() => setActiveTab('inquiries')}
              >
                {isAr ? 'استفسارات' : 'Inquiries'} <span className="pill-badge">10</span>
              </button>
              <button
                type="button"
                className={`filter-pill ${activeTab === 'new-license' ? 'active' : ''}`}
                onClick={() => setActiveTab('new-license')}
              >
                {isAr ? 'رخصة جديدة' : 'New License'} <span className="pill-badge">6</span>
              </button>
              <button
                type="button"
                className={`filter-pill ${activeTab === 'others' ? 'active' : ''}`}
                onClick={() => setActiveTab('others')}
              >
                {isAr ? 'أخرى' : 'Others'} <span className="pill-badge">2</span>
              </button>
            </div>

            {/* Scrollable Body Content */}
            <div className="catalogue-scroll-content">
              {/* Most Used Services Section */}
              <div className="catalogue-section">
                <h4 className="section-header">
                  {isAr ? 'الخدمات الأكثر استخداماً' : 'Most Used Services'}
                </h4>
                <div className="services-grid-4">
                  <div
                    className="service-quick-card"
                    onClick={() => onSelectService('reservation')}
                  >
                    {isAr ? 'الموافقة المبدئية' : 'Initial Approval'}
                  </div>
                  <div
                    className="service-quick-card highlight"
                    onClick={() => onSelectService('reservation')}
                  >
                    {isAr ? 'حجز الاسم التجاري' : 'Trade Name Reservation'}
                  </div>
                  <div
                    className="service-quick-card"
                    onClick={() => onSelectService('reservation')}
                  >
                    {isAr ? 'الرخصة الفورية' : 'Instant License'}
                  </div>
                  <div
                    className="service-quick-card"
                    onClick={() => onSelectService('search')}
                  >
                    {isAr ? 'الاستعلام عن رخصة' : 'License Inquiry'}
                  </div>
                </div>
              </div>

              {/* Inquiries Section */}
              {(activeTab === 'all' || activeTab === 'inquiries') && (
                <div className="catalogue-section">
                  <h4 className="section-header">
                    {isAr ? 'استفسارات' : 'Inquiries'}
                  </h4>
                  <p className="section-sub">
                    {isAr ? 'لا تشترط وجود رخصة' : 'No license needed'}
                  </p>
                  <div className="services-grid-3">
                    {filterService('Legal Type Inquiries', 'inquiries') && (
                      <div className="service-detail-card" onClick={() => onSelectService('reservation')}>
                        <div className="service-name">
                          {isAr ? 'استفسارات الشكل القانوني' : 'Legal Type Inquiries'}
                        </div>
                        <div className="service-caption">
                          {isAr ? 'الأشكال القانونية المسموح بها ومتطلباتها' : 'Allowed legal forms and their requirements'}
                        </div>
                        <div className="service-tag-pill">
                          {isAr ? 'طلبات جديدة' : 'New requests'}
                        </div>
                      </div>
                    )}

                    {filterService('Activity inquiries', 'inquiries') && (
                      <div className="service-detail-card" onClick={() => onSelectService('search')}>
                        <div className="service-name">
                          {isAr ? 'استفسارات الأنشطة الاقتصادية' : 'Activity inquiries'}
                        </div>
                        <div className="service-caption">
                          {isAr ? 'بحث الأنشطة والموافقات والرسوم المقررة' : 'Search activities, approvals and fees'}
                        </div>
                        <div className="service-tag-pill">
                          {isAr ? 'طلبات جديدة' : 'New requests'}
                        </div>
                      </div>
                    )}

                    {filterService('License inquiry', 'inquiries') && (
                      <div className="service-detail-card" onClick={() => onSelectService('search')}>
                        <div className="service-name">
                          {isAr ? 'الاستعلام عن رخصة' : 'License inquiry'}
                        </div>
                        <div className="service-caption">
                          {isAr ? 'الاطلاع على تفاصيل أي رخصة وحالتها' : "Look up any license's details and status"}
                        </div>
                        <div className="service-tag-pill">
                          {isAr ? 'طلبات جديدة' : 'New requests'}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* New License Section */}
              {(activeTab === 'all' || activeTab === 'new-license') && (
                <div className="catalogue-section">
                  <h4 className="section-header">
                    {isAr ? 'رخصة جديدة' : 'New License'}
                  </h4>
                  <p className="section-sub">
                    {isAr ? 'لا تشترط وجود رخصة سابقة' : 'No license needed'}
                  </p>
                  <div className="services-grid-3">
                    {filterService('Reserve trade name', 'new-license') && (
                      <div
                        className="service-detail-card clickable highlight-card"
                        onClick={() => onSelectService('reservation')}
                      >
                        <div className="service-name">
                          {isAr ? 'حجز اسم تجاري' : 'Reserve trade name'}
                        </div>
                        <div className="service-caption">
                          {isAr ? 'فحص وحجز الاسم التجاري بالذكاء الاصطناعي' : 'Check and reserve a trade name'}
                        </div>
                        <div className="service-tag-pill highlight-pill">
                          {isAr ? 'طلبات جديدة' : 'New requests'}
                        </div>
                      </div>
                    )}

                    {filterService('Initial approval', 'new-license') && (
                      <div className="service-detail-card" onClick={() => onSelectService('reservation')}>
                        <div className="service-name">
                          {isAr ? 'الموافقة المبدئية' : 'Initial approval'}
                        </div>
                        <div className="service-caption">
                          {isAr ? 'بدء طلب إصدار رخصة تجارية جديدة' : 'Start a new license application'}
                        </div>
                        <div className="service-tag-pill">
                          {isAr ? 'طلبات جديدة' : 'New requests'}
                        </div>
                      </div>
                    )}

                    {filterService('License issuance', 'new-license') && (
                      <div className="service-detail-card" onClick={() => onSelectService('reservation')}>
                        <div className="service-name">
                          {isAr ? 'إصدار الرخصة' : 'License issuance'}
                        </div>
                        <div className="service-caption">
                          {isAr ? 'إصدار الرخصة بعد الحصول على الموافقة المبدئية' : 'Issue a license after initial approval'}
                        </div>
                        <div className="service-tag-pill">
                          {isAr ? 'طلبات جديدة' : 'New requests'}
                        </div>
                      </div>
                    )}

                    {filterService('Instant license', 'new-license') && (
                      <div className="service-detail-card" onClick={() => onSelectService('reservation')}>
                        <div className="service-name">
                          {isAr ? 'الرخصة الفورية' : 'Instant license'}
                        </div>
                        <div className="service-caption">
                          {isAr ? 'رخصة خلال دقائق للأنشطة المؤهلة' : 'Same-day license for eligible activities'}
                        </div>
                        <div className="service-tag-pill">
                          {isAr ? 'طلبات جديدة' : 'New requests'}
                        </div>
                      </div>
                    )}

                    {filterService('Ibdaa license', 'new-license') && (
                      <div className="service-detail-card" onClick={() => onSelectService('reservation')}>
                        <div className="service-name">
                          {isAr ? 'رخصة إبداع' : 'Ibdaa license'}
                        </div>
                        <div className="service-caption">
                          {isAr ? 'رخصة ممارسة الأعمال من المنزل وتحت برنامج إبداع' : 'License under the Ibdaa programme'}
                        </div>
                        <div className="service-tag-pill">
                          {isAr ? 'طلبات جديدة' : 'New requests'}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

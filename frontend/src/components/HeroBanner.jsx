import React from 'react';

export default function HeroBanner({ isAr, title, breadcrumbs }) {
  const defaultBreadcrumb = isAr
    ? 'خدمات الدائرة الذكية - دليل الخدمات'
    : 'DED Smart Services - Service Catalogue';

  const defaultTitle = isAr ? 'حجز اسم تجاري' : 'Trade Name Reservation';

  return (
    <div className="figma-hero-banner">
      <div className="banner-content-left">
        <div className="banner-breadcrumbs">
          {breadcrumbs ? breadcrumbs.join(' / ') : defaultBreadcrumb}
        </div>
        <h1 className="banner-title">
          {title || defaultTitle}
        </h1>
      </div>
      <div className="banner-bg-image-overlay" aria-hidden="true" />
    </div>
  );
}

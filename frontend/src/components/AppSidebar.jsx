import React from 'react';

export default function AppSidebar({
  activeNav,
  setActiveNav,
  isAr,
  isCollapsed = false,
  onToggleCollapse,
}) {
  const navItems = [
    {
      key: 'portal',
      labelEn: 'Applicant & Search',
      labelAr: 'المتقدمون والبحث',
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="2" y="2" width="6.5" height="6.5" rx="2" fill="currentColor" />
          <rect x="11.5" y="2" width="6.5" height="6.5" rx="2" fill="currentColor" />
          <rect x="2" y="11.5" width="6.5" height="6.5" rx="2" fill="currentColor" />
          <rect x="11.5" y="11.5" width="6.5" height="6.5" rx="2" fill="currentColor" />
        </svg>
      ),
    },
    {
      key: 'reservation',
      labelEn: 'Trade Name',
      labelAr: 'الأسماء التجارية',
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M2 3.5C2 2.67 2.67 2 3.5 2H9V9H2V3.5Z" fill="currentColor" />
          <path d="M11 2H16.5C17.33 2 18 2.67 18 3.5V9H11V2Z" fill="currentColor" />
          <path d="M2 11H9V18H3.5C2.67 18 2 17.33 2 16.5V11Z" fill="currentColor" />
          <path d="M11 11H18V16.5C18 17.33 17.33 18 16.5 18H11V11Z" fill="currentColor" />
        </svg>
      ),
    },
    {
      key: 'work',
      labelEn: 'Work Management',
      labelAr: 'إدارة العمل',
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="2" y="3" width="16" height="14" rx="2" stroke="currentColor" strokeWidth="1.8" />
          <path d="M7 3V1M13 3V1M2 8H18" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      ),
    },
    {
      key: 'copilot',
      labelEn: 'Reviewer Copilot',
      labelAr: 'مساعد المراجع',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M12 2L4 5.5V11C4 16.2 7.4 20.9 12 22C16.6 20.9 20 16.2 20 11V5.5L12 2Z"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M9 11.5L11 13.5L15 9.5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ),
    },
    {
      key: 'search',
      labelEn: 'Registry Search',
      labelAr: 'بحث السجل التجاري',
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="2" />
          <path d="M13.5 13.5L17.5 17.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      key: 'lexicon',
      labelEn: 'Administration',
      labelAr: 'الإدارة والمعجم',
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4 3H16C16.5523 3 17 3.44772 17 4V16C17 16.5523 16.5523 17 16 17H4C3.44772 17 3 16.5523 3 16V4C3 3.44772 3.44772 3 4 3Z" stroke="currentColor" strokeWidth="1.8" />
          <path d="M3 7H17M7 17V7" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      ),
    },
    {
      key: 'compliance',
      labelEn: 'Compliance',
      labelAr: 'الامتثال والرقابة',
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="2" />
          <path d="M10 6V10L12.5 12.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      key: 'settings',
      labelEn: 'Settings',
      labelAr: 'الإعدادات',
      icon: (
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            fillRule="evenodd"
            clipRule="evenodd"
            d="M9.05 1.5H10.95L11.4 3.75C11.95 3.98 12.46 4.28 12.92 4.64L15.08 3.84L16.42 5.5L14.98 7.23C15.12 7.78 15.19 8.36 15.19 8.95C15.19 9.54 15.12 10.12 14.98 10.67L16.42 12.4L15.08 14.06L12.92 13.26C12.46 13.62 11.95 13.92 11.4 14.15L10.95 16.4H9.05L8.6 14.15C8.05 13.92 7.54 13.62 7.08 13.26L4.92 14.06L3.58 12.4L5.02 10.67C4.88 10.12 4.81 9.54 4.81 8.95C4.81 8.36 4.88 7.78 5.02 7.23L3.58 5.5L4.92 3.84L7.08 4.64C7.54 4.28 8.05 3.98 8.6 3.75L9.05 1.5ZM10 12C11.66 12 13 10.66 13 9C13 7.34 11.66 6 10 6C8.34 6 7 7.34 7 9C7 10.66 8.34 12 10 12Z"
            fill="currentColor"
          />
        </svg>
      ),
    },
  ];

  return (
    <aside
      className={`figma-sidebar ${isCollapsed ? 'collapsed' : ''}`}
      aria-label="Portal Navigation"
    >
      {/* Top Hamburger / Collapse Toggle Button */}
      <button
        type="button"
        className="sidebar-icon-btn toggle-collapse-btn"
        title={
          isCollapsed
            ? isAr ? 'توسيع القائمة' : 'Expand navigation'
            : isAr ? 'طي القائمة' : 'Collapse navigation'
        }
        aria-label={
          isCollapsed
            ? isAr ? 'توسيع القائمة' : 'Expand navigation'
            : isAr ? 'طي القائمة' : 'Collapse navigation'
        }
        onClick={onToggleCollapse}
      >
        <svg width="22" height="16" viewBox="0 0 22 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <line y1="1" x2="22" y2="1" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
          <line y1="8" x2="22" y2="8" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
          <line y1="15" x2="22" y2="15" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>

      {/* Main Nav Items with Horizontal Icon + Text Layout matching Reference Designs */}
      <nav className="sidebar-nav-list">
        {navItems.map((item) => {
          const isActive = activeNav === item.key || 
            (item.key === 'work' && activeNav === 'work') ||
            (item.key === 'compliance' && activeNav === 'compliance');
          const itemLabel = isAr ? item.labelAr : item.labelEn;
          return (
            <button
              key={item.key}
              type="button"
              className={`sidebar-nav-btn ${isActive ? 'active-highlight' : ''}`}
              onClick={() => {
                if (item.key === 'work') {
                  setActiveNav('reservation');
                } else {
                  setActiveNav(item.key);
                }
              }}
              title={itemLabel}
              aria-label={itemLabel}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className="sidebar-nav-icon">{item.icon}</span>
              {!isCollapsed && (
                <span className="sidebar-nav-label">
                  {itemLabel}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

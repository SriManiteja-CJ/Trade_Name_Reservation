import React, { useState, useEffect } from 'react';
import AppSidebar from './components/AppSidebar';
import AppHeader from './components/AppHeader';
import TradeNameReservationFlow from './components/TradeNameReservationFlow';
import ApplicantCompanyPortal from './components/ApplicantCompanyPortal';
import RegistrySearchTab from './components/RegistrySearchTab';
import LexiconTab from './components/LexiconTab';
import ReviewerCopilotTab from './components/ReviewerCopilotTab';
import SettingsTab from './components/SettingsTab';
import ValidationTab from './components/ValidationTab';
import WorkManagementTab from './components/WorkManagementTab';
import { API_BASE } from './config';

export default function App() {
  const [lang, setLang] = useState('en');
  const [activeNav, setActiveNav] = useState('portal'); // 'portal' (Default: Applicant & Company Search) | 'reservation' | 'settings' | 'copilot'
  const [activeRequestId, setActiveRequestId] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const isAr = lang === 'ar';

  // Synchronize RTL/LTR document attributes
  useEffect(() => {
    document.documentElement.dir = isAr ? 'rtl' : 'ltr';
    document.documentElement.lang = lang;
  }, [lang, isAr]);

  const handleNavigateToCopilot = (reqId) => {
    if (reqId) setActiveRequestId(reqId);
    setActiveNav('copilot');
  };

  return (
    <div className={`figma-app-shell ${isSidebarCollapsed ? 'sidebar-is-collapsed' : ''}`}>
      {/* Dark Navy Left Sidebar */}
      <AppSidebar
        activeNav={activeNav}
        setActiveNav={setActiveNav}
        isAr={isAr}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
      />

      {/* Main Presentation Area */}
      <div className={`figma-main-container ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        {/* Top Header with Official DED Logo & Profile */}
        <AppHeader
          lang={lang}
          setLang={setLang}
          activeNav={activeNav}
          onOpenSettings={() => setActiveNav('settings')}
        />

        {/* Page Content Body */}
        <main className="figma-page-body">
          {activeNav === 'portal' && (
            <ApplicantCompanyPortal
              isAr={isAr}
              onSelectService={(srv) => setActiveNav(srv)}
            />
          )}

          {activeNav === 'reservation' && (
            <TradeNameReservationFlow
              isAr={isAr}
              onNavigateToCopilot={handleNavigateToCopilot}
            />
          )}

          {activeNav === 'work' && (
            <WorkManagementTab
              lang={lang}
              onNavigateCopilot={handleNavigateToCopilot}
            />
          )}

          {activeNav === 'search' && (
            <RegistrySearchTab
              lang={lang}
              channel="portal"
            />
          )}

          {activeNav === 'lexicon' && (
            <LexiconTab
              lang={lang}
            />
          )}

          {activeNav === 'copilot' && (
            <ReviewerCopilotTab
              lang={lang}
              activeRequestId={activeRequestId}
            />
          )}

          {activeNav === 'compliance' && (
            <ValidationTab
              lang={lang}
              channel="portal"
              onNavigateCopilot={handleNavigateToCopilot}
            />
          )}

          {activeNav === 'settings' && (
            <SettingsTab
              lang={lang}
            />
          )}
        </main>
      </div>
    </div>
  );
}

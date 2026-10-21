import React, { useState, useEffect } from 'react';
import AiEngineConfigModal from './AiEngineConfigModal';
import { API_BASE } from '../config';

export default function AppHeader({ lang, setLang, activeNav, onOpenSettings }) {
  const isAr = lang === 'ar';
  const isPortalUser = activeNav === 'portal';
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [aiEngineInfo, setAiEngineInfo] = useState({
    provider: 'groq',
    model: 'qwen/qwen3.8-27b',
  });

  // Fetch active LLM engine state on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/config/llm`)
      .then((res) => res.json())
      .then((data) => {
        if (data && data.provider) {
          setAiEngineInfo({
            provider: data.provider,
            model: data.analyzer_model || 'qwen/qwen3.8-27b',
          });
        }
      })
      .catch(() => {});
  }, []);

  const handleConfigSaved = (updated) => {
    if (updated) {
      setAiEngineInfo({
        provider: updated.provider,
        model: updated.analyzer_model || 'default',
      });
    }
  };

  const handleOpenSettings = () => {
    if (onOpenSettings) {
      onOpenSettings();
    } else {
      setIsConfigOpen(true);
    }
  };

  return (
    <header className="figma-top-header">
      {/* Official DED Umm Al Quwain Logo */}
      <div className="header-brand-wrap">
        <img
          src="/assets/ded-logo.png"
          alt="Government of Umm Al Quwain - Department of Economic Development"
          className="header-brand-logo"
        />
      </div>

      {/* Header Actions Matching Approved Figma Screens */}
      <div className="header-actions">
        {/* Clean Settings Gear Icon Button */}
        <button
          type="button"
          className="header-settings-icon-btn"
          onClick={handleOpenSettings}
          title={
            isAr
              ? `إعدادات الذكاء الاصطناعي (${aiEngineInfo.provider.toUpperCase()} • ${aiEngineInfo.model})`
              : `AI Engine Settings (${aiEngineInfo.provider.toUpperCase()} • ${aiEngineInfo.model})`
          }
          aria-label="Settings"
        >
          <svg width="19" height="19" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M9.05 1.5H10.95L11.4 3.75C11.95 3.98 12.46 4.28 12.92 4.64L15.08 3.84L16.42 5.5L14.98 7.23C15.12 7.78 15.19 8.36 15.19 8.95C15.19 9.54 15.12 10.12 14.98 10.67L16.42 12.4L15.08 14.06L12.92 13.26C12.46 13.62 11.95 13.92 11.4 14.15L10.95 16.4H9.05L8.6 14.15C8.05 13.92 7.54 13.62 7.08 13.26L4.92 14.06L3.58 12.4L5.02 10.67C4.88 10.12 4.81 9.54 4.81 8.95C4.81 8.36 4.88 7.78 5.02 7.23L3.58 5.5L4.92 3.84L7.08 4.64C7.54 4.28 8.05 3.98 8.6 3.75L9.05 1.5ZM10 12C11.66 12 13 10.66 13 9C13 7.34 11.66 6 10 6C8.34 6 7 7.34 7 9C7 10.66 8.34 12 10 12Z"
              fill="currentColor"
            />
          </svg>
          <span className="settings-active-dot" />
        </button>

        {/* Arabic Language Toggle Pill Button */}
        <button
          type="button"
          className="header-lang-btn"
          onClick={() => setLang(isAr ? 'en' : 'ar')}
          title={isAr ? 'Switch to English' : 'التحويل إلى العربية'}
          aria-label="Toggle Arabic Language"
        >
          ع
        </button>

        {/* User Profile Pill */}
        <div className="header-user-pill">
          <div className="header-user-name">
            <span className="user-name-first">
              {isPortalUser ? 'Mohammed' : 'Abdullah'}
            </span>
            <span className="user-name-last">
              {isPortalUser ? 'Kamran' : 'Muhammed'}
            </span>
          </div>
          <img
            src={isPortalUser ? '/assets/avatar-kamran.png' : '/assets/avatar-abdullah.png'}
            alt="User Avatar"
            className="header-user-avatar-img"
          />
        </div>
      </div>

      {/* AI Engine & Model Configuration Modal */}
      <AiEngineConfigModal
        isOpen={isConfigOpen}
        onClose={() => setIsConfigOpen(false)}
        onConfigSaved={handleConfigSaved}
        isAr={isAr}
      />
    </header>
  );
}

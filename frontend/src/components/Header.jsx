import React from 'react';

export default function Header({ lang, setLang, channel, setChannel, backendConnected, analyzerFlag }) {
  const isAr = lang === 'ar';

  return (
    <header className="app-header">
      <div className="container header-inner">
        <div className="brand-section">
          <div className="ded-emblem" aria-label="DED Emblem">🏛️</div>
          <div className="title-group">
            <h1>{isAr ? 'منظومة فحص الأسماء التجارية الذكية' : 'Trade Name Intelligence Service'}</h1>
            <p>{isAr ? 'دائرة التنمية الاقتصادية • أم القيوين' : 'Department of Economic Development • Umm Al Quwain'}</p>
          </div>
        </div>

        <div className="header-controls">
          {/* Backend Status Dot */}
          <div 
            className="system-status-pill"
            style={{
              borderColor: backendConnected ? 'rgba(52, 211, 153, 0.4)' : 'rgba(244, 63, 94, 0.4)',
              color: backendConnected ? '#34d399' : '#fb7185',
            }}
          >
            <span 
              className="status-dot" 
              style={{ 
                backgroundColor: backendConnected ? '#34d399' : '#f43f5e',
                boxShadow: backendConnected ? '0 0 8px #34d399' : '0 0 8px #f43f5e'
              }}
            />
            <span>
              {backendConnected 
                ? (isAr ? `متصل (:8000) [AI: ${analyzerFlag}]` : `Backend Active (:8000) [AI: ${analyzerFlag}]`)
                : (isAr ? 'الخادم غير متصل' : 'Backend Offline (:8000)')}
            </span>
          </div>

          {/* Channel Selector */}
          <div className="channel-toggle">
            <span className="channel-label">{isAr ? 'القناة:' : 'Channel:'}</span>
            <button
              type="button"
              className={`channel-btn ${channel === 'online' ? 'active' : ''}`}
              onClick={() => setChannel('online')}
            >
              {isAr ? 'أونلاين' : 'Online'}
            </button>
            <button
              type="button"
              className={`channel-btn ${channel === 'walkin' ? 'active' : ''}`}
              onClick={() => setChannel('walkin')}
            >
              {isAr ? 'حضوري' : 'Walk-in'}
            </button>
          </div>

          {/* Language Switch */}
          <button
            type="button"
            className="lang-switch-btn"
            onClick={() => setLang(isAr ? 'en' : 'ar')}
            title="Switch Language"
          >
            <span>🌐</span>
            <span>{isAr ? 'English' : 'العربية'}</span>
          </button>
        </div>
      </div>
    </header>
  );
}

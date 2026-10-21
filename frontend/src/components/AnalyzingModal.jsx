import React from 'react';

export default function AnalyzingModal({ isAr, title, onClose }) {
  const modalTitle = title || (isAr ? 'جاري تحليل نشاطك التجاري...' : 'Analyzing your business...');

  return (
    <div className="figma-modal-overlay" role="dialog" aria-modal="true">
      <div className="analyzing-modal-box">
        {onClose && (
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        )}

        <h3 className="analyzing-title">{modalTitle}</h3>

        {/* AI Sparkles Cluster from approved Figma screens */}
        <div className="sparkles-container">
          <img
            src="/assets/ai-sparkles-exact.png"
            alt="AI Sparkles"
            className="ai-sparkles-img"
          />
        </div>
      </div>
    </div>
  );
}

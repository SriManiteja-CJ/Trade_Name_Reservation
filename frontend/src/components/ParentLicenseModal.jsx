import React, { useState } from 'react';

export default function ParentLicenseModal({ isAr, onClose, onSave, initialData }) {
  const [formData, setFormData] = useState({
    licenceNumber: initialData?.licenceNumber || '',
    issuingEmirate: initialData?.issuingEmirate || 'Dubai',
    tradeNameEn: initialData?.tradeNameEn || '',
    tradeNameAr: initialData?.tradeNameAr || '',
    legalType: initialData?.legalType || 'Limited liability company',
    licenceType: initialData?.licenceType || 'Commercial',
    issuanceDate: initialData?.issuanceDate || '',
    expiryDate: initialData?.expiryDate || '',
    nationality: initialData?.nationality || 'UAE National',
    contact: initialData?.contact || '',
    email: initialData?.email || '',
    address: initialData?.address || '',
    licenseActivity: initialData?.licenseActivity || '',
  });

  const [categories, setCategories] = useState(initialData?.categories || ['5630001 Cafe', '5630001 Restaurant']);
  const [newCat, setNewCat] = useState('');

  const handleAddCategory = () => {
    if (newCat.trim()) {
      setCategories([...categories, newCat.trim()]);
      setNewCat('');
    }
  };

  return (
    <div className="figma-modal-overlay" role="dialog" aria-modal="true">
      <div className="parent-license-modal-box">
        <button
          type="button"
          className="modal-close-btn"
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>

        <div className="modal-header-section">
          <h2 className="modal-title">Parent License Details</h2>
          <p className="modal-subtitle">
            Licence outside UAQ · fill in from your licence copy
          </p>
        </div>

        <div className="modal-form-grid">
          {/* Row 1 */}
          <div className="figma-field-group">
            <label className="field-lbl">Licence number</label>
            <input
              type="text"
              className="field-input"
              value={formData.licenceNumber}
              onChange={(e) => setFormData({ ...formData, licenceNumber: e.target.value })}
            />
          </div>

          <div className="figma-field-group">
            <label className="field-lbl">Issuing emirate</label>
            <input
              type="text"
              className="field-input"
              value={formData.issuingEmirate}
              onChange={(e) => setFormData({ ...formData, issuingEmirate: e.target.value })}
            />
          </div>

          {/* Row 2 */}
          <div className="figma-field-group">
            <label className="field-lbl">Trade Name (English)</label>
            <input
              type="text"
              className="field-input"
              value={formData.tradeNameEn}
              onChange={(e) => setFormData({ ...formData, tradeNameEn: e.target.value })}
            />
          </div>

          <div className="figma-field-group">
            <label className="field-lbl">Trade Name (Arabic)</label>
            <input
              type="text"
              className="field-input"
              value={formData.tradeNameAr}
              onChange={(e) => setFormData({ ...formData, tradeNameAr: e.target.value })}
            />
          </div>

          {/* Row 3 */}
          <div className="figma-field-group">
            <label className="field-lbl">Legal type</label>
            <input
              type="text"
              className="field-input"
              value={formData.legalType}
              onChange={(e) => setFormData({ ...formData, legalType: e.target.value })}
            />
          </div>

          <div className="figma-field-group">
            <label className="field-lbl">Licence type</label>
            <input
              type="text"
              className="field-input"
              value={formData.licenceType}
              onChange={(e) => setFormData({ ...formData, licenceType: e.target.value })}
            />
          </div>

          {/* Row 4 */}
          <div className="figma-field-group">
            <label className="field-lbl">Issuance date</label>
            <input
              type="text"
              className="field-input"
              value={formData.issuanceDate}
              onChange={(e) => setFormData({ ...formData, issuanceDate: e.target.value })}
            />
          </div>

          <div className="figma-field-group">
            <label className="field-lbl">Expiry date</label>
            <input
              type="text"
              className="field-input"
              value={formData.expiryDate}
              onChange={(e) => setFormData({ ...formData, expiryDate: e.target.value })}
            />
          </div>

          {/* Row 5 */}
          <div className="figma-field-group">
            <label className="field-lbl">Nationality</label>
            <input
              type="text"
              className="field-input"
              value={formData.nationality}
              onChange={(e) => setFormData({ ...formData, nationality: e.target.value })}
            />
          </div>

          <div className="figma-field-group">
            <label className="field-lbl">Contact</label>
            <input
              type="text"
              className="field-input"
              value={formData.contact}
              onChange={(e) => setFormData({ ...formData, contact: e.target.value })}
            />
          </div>

          {/* Row 6 */}
          <div className="figma-field-group">
            <label className="field-lbl">Email ID</label>
            <input
              type="text"
              className="field-input"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
          </div>

          <div className="figma-field-group">
            <label className="field-lbl">Address</label>
            <input
              type="text"
              className="field-input"
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
            />
          </div>
        </div>

        {/* Upload License copy */}
        <div style={{ marginTop: '16px' }}>
          <label className="field-lbl">Upload License copy</label>
          <div className="license-upload-dropzone">
            <span>Upload from device or Drag</span>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
        </div>

        {/* License Activity */}
        <div style={{ marginTop: '20px' }}>
          <label className="field-lbl">License Activity</label>
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              className="field-input"
              value={formData.licenseActivity}
              onChange={(e) => setFormData({ ...formData, licenseActivity: e.target.value })}
            />
            <span style={{ position: 'absolute', right: '14px', top: '12px', color: '#94a3b8' }}>🔍</span>
          </div>
        </div>

        {/* Activity Categorys */}
        <div style={{ marginTop: '18px' }}>
          <label className="field-lbl">Activity Categorys</label>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
            <input
              type="text"
              className="field-input"
              placeholder="Cafe"
              value={newCat}
              onChange={(e) => setNewCat(e.target.value)}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn-add-activity"
              onClick={handleAddCategory}
            >
              Add Activity
            </button>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            {categories.map((c, i) => (
              <span key={i} className="activity-chip-tag">
                {c}
              </span>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="modal-actions-row">
          <button
            type="button"
            className="btn-modal-cancel"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-modal-save"
            onClick={() => onSave(formData)}
          >
            Save License Details
          </button>
        </div>
      </div>
    </div>
  );
}

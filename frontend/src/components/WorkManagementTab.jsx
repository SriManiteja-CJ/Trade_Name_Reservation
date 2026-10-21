import React, { useState } from 'react';

export default function WorkManagementTab({ lang, onNavigateCopilot }) {
  const isAr = lang === 'ar';

  const [filterStatus, setFilterStatus] = useState('all'); // all | pending | clarify | approved | rejected
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTask, setSelectedTask] = useState(null);

  // Sample production-grade work management queue items for UAQ DED Officers
  const [tasks, setTasks] = useState([
    {
      id: 'UAQ-TRN-2026-0814',
      nameAr: 'شركة الصقر للخدمات اللوجستية ذ.م.م',
      nameEn: 'Falcon Logistics Services LLC',
      applicantName: 'محمد راشد المعلا',
      applicantId: '784-1985-1234567-1',
      category: 'النقل والخدمات اللوجستية (Logistics)',
      categoryId: 6,
      legalForm: 'Limited Liability Company',
      submittedAt: '2026-10-12 08:30 AM',
      slaHours: 2.5,
      status: 'pending',
      aiVerdict: 'NEEDS_REVIEW',
      aiRiskScore: 68,
      aiFlagDescAr: 'اشتباه تشابه صوتي مع اسم مقيد "الصقر لنقل البضائع"',
      aiFlagDescEn: 'Potential phonetic similarity with "Falcon Cargo Transport"',
    },
    {
      id: 'UAQ-TRN-2026-0819',
      nameAr: 'مطعم ومقهى نبع الخير',
      nameEn: 'Nabaa Al Khair Restaurant & Cafe',
      applicantName: 'فاطمة سلطان الشامسي',
      applicantId: '784-1992-7654321-2',
      category: 'المطاعم والضيافة (Food & Hospitality)',
      categoryId: 4,
      legalForm: 'Sole Proprietorship',
      submittedAt: '2026-10-12 09:15 AM',
      slaHours: 3.8,
      status: 'pending',
      aiVerdict: 'OK',
      aiRiskScore: 12,
      aiFlagDescAr: 'اسم لائق ومتاح ومطابق للضوابط بنسبة 100%',
      aiFlagDescEn: 'Fully compliant, distinctive, no lexicon conflicts',
    },
    {
      id: 'UAQ-TRN-2026-0802',
      nameAr: 'مؤسسة المعلا لتجارة المواد الغذائية',
      nameEn: 'Al Mualla Food Trading Establishment',
      applicantName: 'عبدالله حميد المنصوري',
      applicantId: '784-1988-9988776-3',
      category: 'التجارة العامة (General Trading)',
      categoryId: 1,
      legalForm: 'Sole Proprietorship',
      submittedAt: '2026-10-12 07:45 AM',
      slaHours: 0.8,
      status: 'clarify',
      aiVerdict: 'BLOCKED',
      aiRiskScore: 95,
      aiFlagDescAr: 'يتضمن لقباً أسرياً سيادياً "المعلا" يتطلب موافقة الديوان الأميري',
      aiFlagDescEn: 'Contains protected royal family name "Al Mualla" requiring Amiri Diwan approval',
    },
    {
      id: 'UAQ-TRN-2026-0798',
      nameAr: 'مركز الأفق للابتكار التكنولوجي',
      nameEn: 'Horizon Tech Innovation Center',
      applicantName: 'عمر خالد السويدي',
      applicantId: '784-1990-4455667-4',
      category: 'التكنولوجيا والاتصالات (IT & Tech)',
      categoryId: 7,
      legalForm: 'Limited Liability Company',
      submittedAt: '2026-10-11 04:20 PM',
      slaHours: 0,
      status: 'approved',
      aiVerdict: 'OK',
      aiRiskScore: 8,
      aiFlagDescAr: 'تم الاعتماد وإصدار شهادة الحجز الإلكترونية',
      aiFlagDescEn: 'Approved and digital reservation certificate issued',
    },
    {
      id: 'UAQ-TRN-2026-0775',
      nameAr: 'كازينو الخليج للمشروبات والترفيه',
      nameEn: 'Gulf Casino Beverages & Entertainment',
      applicantName: 'جون سميث (مفوض)',
      applicantId: '784-1980-3322114-9',
      category: 'الترفيه والفعاليات (Entertainment)',
      categoryId: 9,
      legalForm: 'Limited Liability Company',
      submittedAt: '2026-10-11 02:10 PM',
      slaHours: 0,
      status: 'rejected',
      aiVerdict: 'BLOCKED',
      aiRiskScore: 100,
      aiFlagDescAr: 'مرفوض قطعياً لاشتماله على أنشطة ومصطلحات مخالفة للنظام العام',
      aiFlagDescEn: 'Strictly prohibited: contains illegal gambling term "Casino"',
    },
  ]);

  const handleStatusUpdate = (taskId, newStatus) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t))
    );
    if (selectedTask?.id === taskId) {
      setSelectedTask((prev) => ({ ...prev, status: newStatus }));
    }
  };

  const filteredTasks = tasks.filter((t) => {
    if (filterStatus !== 'all' && t.status !== filterStatus) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = t.id.toLowerCase().includes(q);
      const matchEn = t.nameEn.toLowerCase().includes(q);
      const matchAr = t.nameAr.includes(searchQuery.trim());
      const matchApplicant = t.applicantName.includes(searchQuery.trim());
      return matchId || matchEn || matchAr || matchApplicant;
    }
    return true;
  });

  const countPending = tasks.filter((t) => t.status === 'pending').length;
  const countClarify = tasks.filter((t) => t.status === 'clarify').length;
  const countApproved = tasks.filter((t) => t.status === 'approved').length;

  return (
    <div className="tab-pane active" id="tab-work-management">
      <div className="work-management-container">
        {/* Page Title & KPI Scorecard Header */}
        <div className="work-header-section">
          <div>
            <h1 className="work-page-title">
              {isAr ? 'إدارة العمل والمعاملات اليومية' : 'Work Management & Task Center'}
            </h1>
            <p className="work-page-subtitle">
              {isAr
                ? 'لوحة المراجعة الموحدة لموظفي ومراجعي دائرة التنمية الاقتصادية بأم القيوين لمتابعة وفحص طلبات حجز الأسماء التجارية.'
                : 'Centralized queue management for DED Umm Al Quwain trade name reservation requests, SLA tracking, and examiner approvals.'}
            </p>
          </div>

          <div className="work-kpi-row">
            <div className="work-kpi-card">
              <span className="kpi-label">{isAr ? 'إجمالي المعاملات' : 'Total Queue'}</span>
              <span className="kpi-value">{tasks.length}</span>
            </div>
            <div className="work-kpi-card warning">
              <span className="kpi-label">{isAr ? 'قيد المراجعة' : 'Pending Review'}</span>
              <span className="kpi-value text-amber">{countPending}</span>
            </div>
            <div className="work-kpi-card info">
              <span className="kpi-label">{isAr ? 'طلب استيضاح' : 'Clarifications'}</span>
              <span className="kpi-value text-blue">{countClarify}</span>
            </div>
            <div className="work-kpi-card success">
              <span className="kpi-label">{isAr ? 'معتمد اليوم' : 'Approved Today'}</span>
              <span className="kpi-value text-green">{countApproved}</span>
            </div>
            <div className="work-kpi-card highlight">
              <span className="kpi-label">{isAr ? 'الالتزام بـ SLA' : 'SLA Compliance'}</span>
              <span className="kpi-value text-gold">98.4%</span>
            </div>
          </div>
        </div>

        {/* Filters and Search Toolbar */}
        <div className="work-toolbar-card">
          <div className="work-tabs-group">
            <button
              type="button"
              className={`work-tab-btn ${filterStatus === 'all' ? 'active' : ''}`}
              onClick={() => setFilterStatus('all')}
            >
              {isAr ? 'جميع المعاملات' : 'All Tasks'} ({tasks.length})
            </button>
            <button
              type="button"
              className={`work-tab-btn ${filterStatus === 'pending' ? 'active' : ''}`}
              onClick={() => setFilterStatus('pending')}
            >
              {isAr ? 'قيد المراجعة' : 'Pending'} ({countPending})
            </button>
            <button
              type="button"
              className={`work-tab-btn ${filterStatus === 'clarify' ? 'active' : ''}`}
              onClick={() => setFilterStatus('clarify')}
            >
              {isAr ? 'طلب استيضاح' : 'Clarifications'} ({countClarify})
            </button>
            <button
              type="button"
              className={`work-tab-btn ${filterStatus === 'approved' ? 'active' : ''}`}
              onClick={() => setFilterStatus('approved')}
            >
              {isAr ? 'المعتمدة' : 'Approved'} ({countApproved})
            </button>
            <button
              type="button"
              className={`work-tab-btn ${filterStatus === 'rejected' ? 'active' : ''}`}
              onClick={() => setFilterStatus('rejected')}
            >
              {isAr ? 'المرفوضة' : 'Rejected'} ({tasks.filter((t) => t.status === 'rejected').length})
            </button>
          </div>

          <div className="work-search-box">
            <input
              type="text"
              className="form-input work-search-input"
              placeholder={isAr ? 'بحث برقم المعاملة، الاسم التجاري، أو مقدم الطلب...' : 'Search by Ref No, Trade Name, or Applicant...'}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className="btn-clear-search"
                onClick={() => setSearchQuery('')}
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Task Items Table Grid */}
        <div className="work-table-card">
          <div className="table-responsive">
            <table className="work-data-table">
              <thead>
                <tr>
                  <th>{isAr ? 'رقم المعاملة' : 'Application Ref'}</th>
                  <th>{isAr ? 'الاسم التجاري المقترح' : 'Proposed Trade Name'}</th>
                  <th>{isAr ? 'مقدم الطلب' : 'Applicant'}</th>
                  <th>{isAr ? 'النشاط والشكل' : 'Category & Form'}</th>
                  <th>{isAr ? 'الفحص الذكي' : 'AI Analysis'}</th>
                  <th>{isAr ? 'اتفاقية الخدمة (SLA)' : 'SLA Status'}</th>
                  <th>{isAr ? 'الحالة' : 'Status'}</th>
                  <th style={{ textAlign: 'center' }}>{isAr ? 'الإجراءات' : 'Actions'}</th>
                </tr>
              </thead>
              <tbody>
                {filteredTasks.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '40px' }}>
                      <div className="empty-state">
                        <span className="empty-icon">📂</span>
                        <p>{isAr ? 'لا توجد معاملات مطابقة لمعايير البحث الحالية.' : 'No tasks match your filter criteria.'}</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredTasks.map((t) => {
                    const isPending = t.status === 'pending';
                    const isClarify = t.status === 'clarify';
                    const isApproved = t.status === 'approved';
                    const isRejected = t.status === 'rejected';

                    return (
                      <tr key={t.id} className={`work-row ${selectedTask?.id === t.id ? 'selected' : ''}`}>
                        <td className="font-mono font-semibold text-gold">{t.id}</td>
                        <td>
                          <div className="trade-name-cell">
                            <span className="name-ar font-arabic">{t.nameAr}</span>
                            <span className="name-en text-muted">{t.nameEn}</span>
                          </div>
                        </td>
                        <td>
                          <div className="applicant-cell">
                            <span className="applicant-name">{t.applicantName}</span>
                            <span className="applicant-id text-muted font-mono">{t.applicantId}</span>
                          </div>
                        </td>
                        <td>
                          <div className="category-cell">
                            <span className="badge badge-info">{t.category}</span>
                            <span className="legal-form text-muted">{t.legalForm}</span>
                          </div>
                        </td>
                        <td>
                          <div className="ai-verdict-cell">
                            {t.aiVerdict === 'OK' && (
                              <span className="badge badge-success">
                                ✓ {isAr ? 'متاح' : 'Clear (0 Risk)'}
                              </span>
                            )}
                            {t.aiVerdict === 'NEEDS_REVIEW' && (
                              <span className="badge badge-warning">
                                ⚠️ {isAr ? 'مراجعة' : 'Review Needed'}
                              </span>
                            )}
                            {t.aiVerdict === 'BLOCKED' && (
                              <span className="badge badge-danger">
                                ⛔ {isAr ? 'مخالف' : 'Blocked'}
                              </span>
                            )}
                            <span className="ai-tooltip-hint" title={isAr ? t.aiFlagDescAr : t.aiFlagDescEn}>
                              {isAr ? t.aiFlagDescAr : t.aiFlagDescEn}
                            </span>
                          </div>
                        </td>
                        <td>
                          {t.slaHours > 0 ? (
                            <span className={`sla-badge ${t.slaHours <= 1.0 ? 'urgent' : 'normal'}`}>
                              ⏱ {t.slaHours} {isAr ? 'ساعات متبقية' : 'hrs left'}
                            </span>
                          ) : (
                            <span className="sla-badge done">✓ {isAr ? 'مكتمل' : 'Completed'}</span>
                          )}
                        </td>
                        <td>
                          {isPending && <span className="status-pill pending">{isAr ? 'قيد المراجعة' : 'Pending'}</span>}
                          {isClarify && <span className="status-pill clarify">{isAr ? 'طلب استيضاح' : 'Clarification'}</span>}
                          {isApproved && <span className="status-pill approved">{isAr ? 'معتمد' : 'Approved'}</span>}
                          {isRejected && <span className="status-pill rejected">{isAr ? 'مرفوض' : 'Rejected'}</span>}
                        </td>
                        <td>
                          <div className="action-buttons-cell">
                            <button
                              type="button"
                              className="btn-action-primary"
                              title={isAr ? 'فتح في مساعد المراجع الذكي' : 'Open in Reviewer Copilot'}
                              onClick={() => onNavigateCopilot && onNavigateCopilot(t.id)}
                            >
                              🛡️ {isAr ? 'المراجع الذكي' : 'Copilot'}
                            </button>
                            {isPending && (
                              <>
                                <button
                                  type="button"
                                  className="btn-action-approve"
                                  title={isAr ? 'اعتماد سريع' : 'Fast Approve'}
                                  onClick={() => handleStatusUpdate(t.id, 'approved')}
                                >
                                  ✓
                                </button>
                                <button
                                  type="button"
                                  className="btn-action-clarify"
                                  title={isAr ? 'طلب استيضاح' : 'Request Clarification'}
                                  onClick={() => handleStatusUpdate(t.id, 'clarify')}
                                >
                                  💬
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

"""
pipeline/activity_catalogue.py
Official UAE / DED Umm Al Quwain Business Activity Catalogue.

Defines the 10 official business activity categories and their approved
representative activity types according to national economic activity classifications.
Used for deterministic validation of AI recommendations.
"""
from typing import Any, Optional


OFFICIAL_ACTIVITY_CATALOGUE = [
    {
        "category_id": 1,
        "code": "COMM_001",
        "name_en": "Commercial & Trading",
        "name_ar": "التجارة والأعمال التجارية",
        "representative_activities": [
            "General trading",
            "Import/export",
            "Wholesale trade",
            "Retail trade",
            "Foodstuff & Beverage Trading",
            "Online retail",
            "E-Commerce portal operations",
        ],
        "isic_codes": [
            {"code": "46900", "name_en": "Non-specialised wholesale trade", "name_ar": "تجارة الجملة غير المتخصصة"},
            {"code": "46901", "name_en": "General Import and Export", "name_ar": "الاستيراد والتصدير العام"},
            {"code": "47190", "name_en": "Other retail sale in non-specialised stores", "name_ar": "تجارة التجزئة في المتاجر غير المتخصصة"},
            {"code": "47910", "name_en": "Retail sale via mail order houses or via Internet", "name_ar": "البيع بالتجزئة عن طريق الإنترنت"},
        ]
    },
    {
        "category_id": 2,
        "code": "SERV_002",
        "name_en": "Consulting & Professional Services",
        "name_ar": "الاستشارات والخدمات المهنية",
        "representative_activities": [
            "Management consultancy",
            "Business consultancy",
            "Professional advisory services",
            "Corporate Services & Auditing",
        ],
        "isic_codes": [
            {"code": "70200", "name_en": "Management consultancy activities", "name_ar": "أنشطة الاستشارات الإدارية"},
            {"code": "70201", "name_en": "Business consultancy and strategic advisory", "name_ar": "استشارات الأعمال والتخطيط الاستراتيجي"},
            {"code": "74900", "name_en": "Other professional, scientific and technical activities", "name_ar": "أنشطة مهنية وعلمية وتقنية أخرى"},
        ]
    },
    {
        "category_id": 3,
        "code": "TECH_003",
        "name_en": "IT & Technology",
        "name_ar": "تكنولوجيا المعلومات والتقنية",
        "representative_activities": [
            "Software development",
            "IT consultancy",
            "Technology services",
            "Cloud computing & Data hosting",
            "Artificial Intelligence & Cyber Security",
        ],
        "isic_codes": [
            {"code": "62010", "name_en": "Computer programming activities", "name_ar": "أنشطة البرمجة الحاسوبية"},
            {"code": "62020", "name_en": "Computer consultancy and facilities management", "name_ar": "استشارات الحاسوب وإدارة المرافق"},
            {"code": "62090", "name_en": "Other information technology and computer service activities", "name_ar": "أنشطة خدمات تكنولوجيا المعلومات الأخرى"},
            {"code": "63110", "name_en": "Data processing, hosting and related activities", "name_ar": "معالجة البيانات واستضافتها والأنشطة المتصلة بها"},
        ]
    },
    {
        "category_id": 4,
        "code": "REST_004",
        "name_en": "Restaurants, Cafes & Food Services",
        "name_ar": "المطاعم والمقاهي وخدمات الأغذية",
        "representative_activities": [
            "Cafe and Restaurant",
            "Restaurant",
            "Cafe",
            "Fast Food Restaurant",
            "Bakery and Sweets",
            "Cafe and Restaurant Operations",
            "Foodstuff Catering & Lounge",
        ],
        "isic_codes": [
            {"code": "56100", "name_en": "Restaurants and mobile food service activities", "name_ar": "أنشطة المطاعم والمقاهي المتنقلة والثابتة"},
            {"code": "56300", "name_en": "Beverage serving activities (Cafes & Juice bars)", "name_ar": "أنشطة تقديم المشروبات والمقاهي"},
            {"code": "10710", "name_en": "Manufacture of bakery products", "name_ar": "صنع منتجات المخابز والحلويات"},
        ]
    },
    {
        "category_id": 5,
        "code": "MKTG_005",
        "name_en": "Digital Marketing & Advertising",
        "name_ar": "التسويق الرقمي والدعاية والإعلان",
        "representative_activities": [
            "Digital marketing",
            "Advertising services",
            "Marketing consultancy",
            "Public Relations & Media Buying",
        ],
        "isic_codes": [
            {"code": "73100", "name_en": "Advertising agency activities", "name_ar": "أنشطة وكالات الدعاية والإعلان"},
            {"code": "73101", "name_en": "Digital marketing & online ad campaign management", "name_ar": "إدارة الحملات الإعلانية والتسويق الرقمي"},
            {"code": "73200", "name_en": "Market research and public opinion polling", "name_ar": "بحوث التسويق واستطلاعات الرأي العام"},
        ]
    },
    {
        "category_id": 6,
        "code": "MDIA_006",
        "name_en": "Media & Creative",
        "name_ar": "الإعلام والخدمات الإبداعية",
        "representative_activities": [
            "Content creation",
            "Media production",
            "Creative services",
            "Graphic Design & Photography",
        ],
        "isic_codes": [
            {"code": "59110", "name_en": "Motion picture, video and television programme production", "name_ar": "إنتاج الأفلام السينمائية والفيديوهات والبرامج"},
            {"code": "74100", "name_en": "Specialised design and creative activities", "name_ar": "أنشطة التصميم المتخصص والإبداعي"},
            {"code": "74200", "name_en": "Photographic activities and digital visual production", "name_ar": "أنشطة التصوير الفوتوغرافي والإنتاج المرئي"},
        ]
    },
    {
        "category_id": 7,
        "code": "INDU_007",
        "name_en": "Industrial & Manufacturing",
        "name_ar": "الصناعة والإنتاج والتصنيع",
        "representative_activities": [
            "Manufacturing",
            "Processing",
            "Production",
            "Assembly",
        ],
        "isic_codes": [
            {"code": "10800", "name_en": "Manufacture of prepared foods and goods", "name_ar": "صناعة وتجهيز المنتجات والمواد الغذائية"},
            {"code": "25990", "name_en": "Manufacture of other fabricated products", "name_ar": "صناعة المنتجات المعدنية والمصنوعات"},
            {"code": "28290", "name_en": "Mechanical and equipment assembly", "name_ar": "تجميع وتصنيع الآلات والمعدات"},
        ]
    },
    {
        "category_id": 8,
        "code": "LOGS_008",
        "name_en": "Logistics & Warehousing",
        "name_ar": "الخدمات اللوجستية والتخزين",
        "representative_activities": [
            "Storage",
            "Distribution",
            "Logistics services",
            "Courier & Delivery Services",
        ],
        "isic_codes": [
            {"code": "52100", "name_en": "Warehousing and storage", "name_ar": "التخزين والمستودعات"},
            {"code": "52290", "name_en": "Other transportation support and logistics activities", "name_ar": "خدمات الدعم اللوجستي والنقل والشحن"},
            {"code": "53200", "name_en": "Courier and last-mile delivery activities", "name_ar": "خدمات التوصيل والطرود البريدية"},
        ]
    },
    {
        "category_id": 9,
        "code": "EDUC_009",
        "name_en": "Education & Training",
        "name_ar": "التعليم والتدريب",
        "representative_activities": [
            "Professional training",
            "Tutoring",
            "Educational services",
            "Corporate Training & Workshops",
        ],
        "isic_codes": [
            {"code": "85490", "name_en": "Other education n.e.c., vocational and professional training", "name_ar": "التعليم والتدريب المهني والتقني"},
            {"code": "85590", "name_en": "Academic tutoring and supplementary education", "name_ar": "الدروس الخصوصية والتعليم التكميلي"},
            {"code": "85600", "name_en": "Educational support and advisory services", "name_ar": "خدمات الدعم والاستشارات التعليمية"},
        ]
    },
    {
        "category_id": 10,
        "code": "FREE_010",
        "name_en": "Freelance & Independent Services",
        "name_ar": "العمل الحر والخدمات المستقلة",
        "representative_activities": [
            "Digital services",
            "Technical services",
            "Creative services",
            "Professional freelance activities",
        ],
        "isic_codes": [
            {"code": "62092", "name_en": "Freelance digital and web technology services", "name_ar": "خدمات التقنية والويب المستقلة"},
            {"code": "74902", "name_en": "Independent advisory, copywriting and translation", "name_ar": "الخدمات المهنية والترجمة والكتابة الحرة"},
            {"code": "90000", "name_en": "Creative, artistic and freelance media services", "name_ar": "أنشطة الفنون والإبداع المستقلة"},
        ]
    },
]


def get_all_categories() -> list[dict[str, Any]]:
    """Return all 10 official business activity categories."""
    return OFFICIAL_ACTIVITY_CATALOGUE


def get_category_by_code(code: str) -> Optional[dict[str, Any]]:
    """Find category entry by its official code (e.g. 'COMM_001')."""
    clean = (code or "").upper().strip()
    for cat in OFFICIAL_ACTIVITY_CATALOGUE:
        if cat["code"] == clean:
            return cat
    return None


def get_category_by_id(cat_id: int) -> Optional[dict[str, Any]]:
    """Find category entry by integer ID."""
    for cat in OFFICIAL_ACTIVITY_CATALOGUE:
        if cat["category_id"] == cat_id:
            return cat
    return None


def find_category_by_keyword(query: str) -> Optional[dict[str, Any]]:
    """Fuzzy / keyword lookup across categories and activities."""
    q = (query or "").lower().strip()
    if not q:
        return None
    for cat in OFFICIAL_ACTIVITY_CATALOGUE:
        if q in cat["name_en"].lower() or q in cat["name_ar"].lower():
            return cat
        for act in cat["representative_activities"]:
            if q in act.lower():
                return cat
    return None


def validate_activity_record(category_code: str, activity_name: str) -> tuple[bool, Optional[str]]:
    """
    Deterministic validation: checks if the activity belongs to the official catalogue.
    Returns (is_valid, standardized_activity_name).
    """
    cat = get_category_by_code(category_code)
    if not cat:
        return False, None
    act_lower = (activity_name or "").lower().strip()
    for rep in cat["representative_activities"]:
        if act_lower in rep.lower() or rep.lower() in act_lower:
            return True, rep
    return False, None

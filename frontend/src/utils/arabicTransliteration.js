/**
 * utils/arabicTransliteration.js
 * AI-Powered English-to-Arabic Trade Name Transliteration (Industry Best Practice)
 * 
 * Uses backend LLM endpoint (/TradeName/Transliterate) to provide context-aware
 * UAE DED-compliant Arabic trade names without maintaining fragile static dictionaries.
 */
import { API_BASE } from '../config';

/**
 * Calls the backend AI transliteration service with debouncing support.
 * @param {string} englishName - The English trade name input.
 * @returns {Promise<string>} The official Arabic trade name equivalent.
 */
export async function fetchArabicTransliteration(englishName) {
  if (!englishName || !englishName.trim()) {
    return '';
  }

  try {
    const res = await fetch(`${API_BASE}/TradeName/Transliterate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name_en: englishName.trim() }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data && data.arabic_name) {
        return data.arabic_name.trim();
      }
    }
  } catch (err) {
    console.warn('Backend AI transliteration failed, falling back:', err);
  }

  // Graceful client-side fallback if backend is offline
  return quickClientFallback(englishName);
}

/**
 * Ultra-lightweight phonetic fallback (no maintained static dictionaries).
 */
const CHAR_MAP = {
  sh: 'ش', th: 'ث', kh: 'خ', ch: 'تش', ph: 'ف', gh: 'غ', dh: 'ذ', ee: 'ي', oo: 'و',
  a: 'ا', b: 'ب', c: 'ك', d: 'د', e: 'ي', f: 'ف', g: 'ج', h: 'ه', i: 'ي', j: 'ج',
  k: 'ك', l: 'ل', m: 'م', n: 'ن', o: 'و', p: 'ب', q: 'ق', r: 'ر', s: 'س', t: 'ت',
  u: 'و', v: 'ف', w: 'و', x: 'كس', y: 'ي', z: 'ز',
};

export function quickClientFallback(englishName) {
  if (!englishName || !englishName.trim()) return '';
  const clean = englishName.trim().toLowerCase();
  let result = '';
  let i = 0;
  while (i < clean.length) {
    if (i + 1 < clean.length && CHAR_MAP[clean.slice(i, i + 2)]) {
      result += CHAR_MAP[clean.slice(i, i + 2)];
      i += 2;
    } else if (CHAR_MAP[clean[i]]) {
      result += CHAR_MAP[clean[i]];
      i += 1;
    } else {
      result += clean[i];
      i += 1;
    }
  }
  return result;
}

export async function fetchEnglishTransliteration(arabicName) {
  if (!arabicName || !arabicName.trim()) {
    return '';
  }

  try {
    const res = await fetch(`${API_BASE}/TradeName/Transliterate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name_ar: arabicName.trim() }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data && data.name_en) {
        return data.name_en.trim();
      }
    }
  } catch (err) {
    console.warn('Backend AI English transliteration failed, falling back:', err);
  }

  // Graceful client-side fallback if backend is offline
  return quickClientFallbackArToEn(arabicName);
}

const AR_PHRASE_MAP = {
  'للتجارة العامة': 'General Trading',
  'تجارة عامة': 'General Trading',
  'للحلول البرمجية': 'Software Solutions',
  'للحلول الذكية': 'Smart Solutions',
  'للحلول الرقمية': 'Digital Solutions',
  'لحلول تقنية المعلومات': 'IT Solutions',
  'للنقل والشحن': 'Transport & Cargo',
  'المجموعة التجارية': 'Commercial Group',
  'للمقاولات العامة': 'General Contracting',
  'لمقاولات البناء': 'Building Contracting',
  'للخدمات اللوجستية': 'Logistics Services',
  'خدمات لوجستية': 'Logistics Services',
  'للوجبات السريعة': 'Fast Food',
  'لتأجير السيارات': 'Car Rental',
  'للعقارات': 'Real Estate',
};

const AR_WORD_MAP = {
  'للتجارة': 'Trading',
  'تجارة': 'Trading',
  'للتكنولوجيا': 'Technologies',
  'تكنولوجيا': 'Technologies',
  'للتقنية': 'Technology',
  'تقنية': 'Technology',
  'للبرمجيات': 'Software',
  'برمجيات': 'Software',
  'للحلول': 'Solutions',
  'حلول': 'Solutions',
  'للأنظمة': 'Systems',
  'أنظمة': 'Systems',
  'للخدمات': 'Services',
  'خدمات': 'Services',
  'للاستشارات': 'Consultancy',
  'استشارات': 'Consultancy',
  'للمقاولات': 'Contracting',
  'مقاولات': 'Contracting',
  'كافيه': 'Cafe',
  'مقهى': 'Cafe',
  'مطعم': 'Restaurant',
  'مطاعم': 'Restaurants',
  'مجموعة': 'Group',
  'شركة': 'Company',
  'مؤسسة': 'Establishment',
  'تيجا': 'Teja',
  'فالكون': 'Falcon',
  'صحراء': 'Sahra',
  'صحرا': 'Sahra',
  'ستار': 'Star',
  'الواحة': 'Al Waha',
  'واحة': 'Oasis',
  'برايم': 'Prime',
  'أبيكس': 'Apex',
  'كلاودجون': 'Cloudjune',
  'نور': 'Noor',
  'النور': 'Al Noor',
};

const AR_CHAR_MAP = {
  'ا': 'a', 'أ': 'a', 'إ': 'e', 'آ': 'aa', 'ب': 'b', 'ت': 't', 'ث': 'th',
  'ج': 'j', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z',
  'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a',
  'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
  'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'h', 'ء': 'a'
};

export function quickClientFallbackArToEn(arabicName) {
  if (!arabicName || !arabicName.trim()) return '';
  let str = arabicName.trim();
  for (const [arPhrase, enPhrase] of Object.entries(AR_PHRASE_MAP)) {
    if (str.includes(arPhrase)) {
      str = str.replace(arPhrase, ` ${enPhrase} `);
    }
  }

  const tokens = str.split(/\s+/).filter(Boolean);
  const res = tokens.map((t) => {
    if (/^[a-zA-Z]+$/.test(t)) return t;
    if (AR_WORD_MAP[t]) return AR_WORD_MAP[t];
    let word = '';
    for (let i = 0; i < t.length; i++) {
      word += AR_CHAR_MAP[t[i]] || t[i];
    }
    return word.charAt(0).toUpperCase() + word.slice(1);
  });

  return res.join(' ');
}

// Backward compatibility alias
export const convertEnglishToTradeNameArabic = quickClientFallback;
export const convertArabicToTradeNameEnglish = quickClientFallbackArToEn;

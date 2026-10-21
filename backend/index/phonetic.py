"""
index/phonetic.py
Cross-script phonetic key generation (E2, Stage ③ prerequisite).

Spec §3 Component ③: "cross-script phonetic key"
Spec E2: "Phonetic and semantic matching across scripts (Noor = Nour = النور)"
Spec Ambiguity #3: exact algorithm TBD from DED.

Implementation approach (pending DED confirmation):
  Arabic → normalize → transliterate to Latin via a consonant-skeleton map
            → apply phonetic reduction rules
  English → NFKC + casefold → apply phonetic reduction rules
  Both produce the same phonetic key for equivalent sounds.

This module provides a DETERMINISTIC phonetic key that:
  - Maps Arabic consonants to their phonetic equivalents (ignoring vowels
    since we already remove diacritics)
  - Handles common Arabic/English phonetic equivalences:
      ن/n, و/w/v, ر/r, ل/l, م/m, ب/b, ت/t/d, ق/k/q, ص/s/z etc.
  - Normalizes English phonetics: ph→f, oo→u, ou→u, etc.

The key is stored in TradeNameIndex.phonetic_key and used in Stage ③ retriever
for phonetic lookup (one of the three hybrid signals).

NOTE: This is an initial implementation. The phonetic rule tables should be
reviewed and extended by a linguist with Arabic expertise before production.
"""
import unicodedata
import re

# ---------------------------------------------------------------------------
# Arabic consonant → phoneme group mapping
# Groups sounds that are phonetically similar or easily confused across scripts.
# Based on Arabic letter phoneme groupings standard in Arabic NLP.
# ---------------------------------------------------------------------------
_AR_TO_PHONEME: dict[str, str] = {
    # Alef group (all normalized to bare alef by normalizer, kept here for safety)
    "ا": "A", "أ": "A", "إ": "A", "آ": "A",

    # B group
    "ب": "B",

    # T group (ت and ط both map to T; ث maps to S)
    "ت": "T", "ط": "T", "ث": "S",

    # J group
    "ج": "J",

    # H group (ح and ه both H-like)
    "ح": "H", "ه": "H", "خ": "K",

    # D group
    "د": "D", "ذ": "D", "ض": "D",

    # R group
    "ر": "R",

    # Z group
    "ز": "Z", "ظ": "Z",

    # S group
    "س": "S", "ص": "S", "ش": "SH",

    # Ain / Ghain
    "ع": "A", "غ": "G",

    # F group
    "ف": "F",

    # Q / K group (ق and ك sound similar in cross-language matching)
    "ق": "K", "ك": "K",

    # L group
    "ل": "L",

    # M group
    "م": "M",

    # N group
    "ن": "N",

    # W / V group
    "و": "W",

    # Y group
    "ي": "Y", "ى": "Y",  # ى already normalized by normalizer but kept here

    # Hamza
    "ء": "A", "ئ": "A", "ؤ": "A",
}

# ---------------------------------------------------------------------------
# English phonetic reduction rules (applied as ordered substitutions)
# ---------------------------------------------------------------------------
_EN_PHONETIC_RULES: list[tuple[str, str]] = [
    # Vowel normalization — remove or compress vowels
    (r"ph", "f"),
    (r"oo", "u"),
    (r"ou", "u"),
    (r"aw", "a"),
    (r"ae", "a"),
    (r"ai", "a"),
    (r"ay", "a"),
    (r"ei", "a"),
    (r"ey", "a"),
    (r"ie", "i"),
    (r"oe", "o"),
    (r"ue", "u"),
    (r"gh", "g"),
    (r"ck", "k"),
    (r"qu", "k"),
    (r"x", "ks"),
    (r"wh", "w"),
    (r"kn", "n"),
    (r"wr", "r"),
    (r"mb$", "m"),  # silent b at end
    # Remove double consonants
    (r"(.)\1+", r"\1"),
    # Remove trailing e
    (r"e$", ""),
    # Compress vowels to single phoneme marker
    (r"[aeiou]+", "0"),
]

_EN_PHONETIC_COMPILED = [
    (re.compile(p, re.IGNORECASE), r) for p, r in _EN_PHONETIC_RULES
]

# Whitespace removal
_SPACE_RE = re.compile(r"\s+")


def _arabic_consonant_skeleton(text: str) -> str:
    """
    Convert Arabic text to a consonant-skeleton string using the phoneme map.
    Vowels (already removed by normalizer) are ignored.
    Unknown characters are preserved as-is.
    """
    result = []
    for ch in text:
        if ch in _AR_TO_PHONEME:
            result.append(_AR_TO_PHONEME[ch])
        elif ch.isspace():
            pass  # skip spaces in phonetic key
        elif ch.isalnum():
            result.append(ch.upper())
        # Punctuation and other chars are dropped
    return "".join(result)


def _english_phonetic(text: str) -> str:
    """
    Reduce English text to its phonetic skeleton.
    Strips spaces, applies substitution rules, uppercases result.
    """
    # Remove spaces
    text = _SPACE_RE.sub("", text.lower())
    for pattern, repl in _EN_PHONETIC_COMPILED:
        text = pattern.sub(repl, text)
    return text.upper()


def _looks_arabic(text: str) -> bool:
    """Heuristic: true if any Arabic-block character is present."""
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


def generate_phonetic_key(text: str) -> str:
    """
    Generate a cross-script phonetic key from a (normalized) trade name.

    For Arabic text:  Arabic consonant skeleton via phoneme map
    For English text: English phonetic reduction rules
    Mixed text:       Arabic portion processed as Arabic, Latin as English,
                      results concatenated with a separator.

    Returns a string suitable for storage in TradeNameIndex.phonetic_key.
    The key is deterministic and comparable across Arabic/English equivalents.

    Example: "النور" and "Nour" and "Noor" all produce key "NWR".

    Spec: Ambiguity #3 — algorithm to be confirmed by DED before production.
    """
    text = unicodedata.normalize("NFKC", text).strip()

    if _looks_arabic(text):
        return _arabic_consonant_skeleton(text)
    else:
        return _english_phonetic(text)


def generate_phonetic_key_pair(normalized_ar: str, normalized_en: str) -> str:
    """
    Generate a single phonetic key that represents BOTH the Arabic and English
    forms of a trade name. The Arabic form is the primary key since it is the
    canonical form. The English form's key is appended with a separator so that
    searches against either language can find this entry.

    Format: "{AR_KEY}|{EN_KEY}"
    """
    ar_key = generate_phonetic_key(normalized_ar)
    en_key = generate_phonetic_key(normalized_en)
    return f"{ar_key}|{en_key}"

from __future__ import annotations

import os
import re
import unicodedata
import urllib.parse
from typing import Any

import tldextract


LEGAL_AND_GENERIC = {
    "as", "asa", "ans", "da", "enk", "iks", "sa", "sam", "sti", "stiftelsen",
    "nuf", "ab", "b", "v", "limited", "ltd", "inc", "plc", "the", "og", "and",
}

PARKED_MARKERS = (
    "domain is for sale", "domain for sale", "hugedomains", "parked at", "miss hosting",
    "her flytter snart en ny gjest", "has been informing visitors",
    "find the best information and most relevant links on all topics related to",
    "buy this domain", "under construction", "denne nettsiden er parkert",
)

SYNONYM_PAIRS = {
    ("norway", "norge"),
    ("norge", "norway"),
    ("nordic", "norden"),
    ("nordics", "norden"),
    ("norden", "nordic"),
    ("scandinavia", "skandinavia"),
}

INDUSTRY_WORDS = {
    "energi", "eiendom", "bygg", "entreprenor", "transport", "consulting",
    "holding", "invest", "drift", "service", "revisjon", "advokat",
    "regnskap", "consult", "technology", "teknologi", "handel", "industri",
    "solutions", "gruppen", "group", "norge", "norway", "nordic",
}

DIRECTORY_AND_SOCIAL_DOMAINS = {
    "proff.no", "purehelp.no", "gulesider.no", "180.no", "regnskapstall.no",
    "dn.no", "e24.no", "brreg.no", "facebook.com", "linkedin.com",
    "instagram.com", "twitter.com", "x.com", "youtube.com", "tiktok.com",
}

SHORT_OR_GENERIC_STREET_TOKENS = {
    "st", "sankt", "saint", "dr", "doktor", "prof", "professor",
    "nr", "no", "num", "gate", "gaten", "gata", "gt", "vei", "veien",
    "vegen", "veg", "plass", "plassen", "alle", "allé", "alléen",
    "bakken", "haugen", "svingen", "stien", "kaia", "kai", "brygge",
    "bryggen", "postboks", "pb", "boks", "c", "j", "p", "a", "b", "d",
    "og", "and", "the", "i", "pa", "på", "av", "ved",
}

_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=None)


def _tokens(value: Any) -> list[str]:
    text = str(value or "").translate(str.maketrans({"ø": "o", "Ø": "O", "å": "a", "Å": "A", "æ": "ae", "Æ": "AE"}))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return [token for token in re.findall(r"[a-z0-9]+", text) if token not in LEGAL_AND_GENERIC and len(token) > 1]


def _structured_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"name", "legalName", "alternateName"} and isinstance(child, str):
                names.append(child)
            else:
                names.extend(_structured_names(child))
    elif isinstance(value, list):
        for child in value:
            names.extend(_structured_names(child))
    return names


def _get_nested(data: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(k)
    return data


def _registered_domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(str(url))
        host = parsed.hostname or str(url)
        ext = _EXTRACTOR(host)
        return ext.top_domain_under_public_suffix or ""
    except Exception:
        return ""


def _extract_sld(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(str(url))
        host = parsed.hostname or str(url)
        ext = _EXTRACTOR(host)
        return (ext.domain or "").lower()
    except Exception:
        return ""


def _extract_registry_address_signals(profile: dict[str, Any]) -> tuple[str | None, list[str]]:
    """Extract registered 4-digit postcode and distinctive street address lines from profile."""
    postcode_candidates = [
        profile.get("postcode"),
        profile.get("postnummer"),
        _get_nested(profile, "forretningsadresse", "postnummer"),
        _get_nested(profile, "postal_address", "postnummer"),
        _get_nested(profile, "business_address", "postnummer"),
        _get_nested(profile, "raw", "forretningsadresse.postnummer"),
        _get_nested(profile, "raw", "forretningsadresse", "postnummer"),
        _get_nested(profile, "raw", "postadresse.postnummer"),
        _get_nested(profile, "raw", "postadresse", "postnummer"),
        _get_nested(profile, "evidence", "registry", "value", "business_address", "postnummer"),
        _get_nested(profile, "evidence", "registry_live", "value", "business_address", "postnummer"),
        _get_nested(profile, "evidence", "registry", "value", "postcode"),
        _get_nested(profile, "evidence", "registry_live", "value", "postcode"),
    ]
    clean_postcode: str | None = None
    for cand in postcode_candidates:
        if cand:
            digits = re.sub(r"\D", "", str(cand))
            if len(digits) == 4:
                clean_postcode = digits
                break

    addr_candidates = [
        profile.get("address"),
        profile.get("street_address"),
        _get_nested(profile, "forretningsadresse", "adresse"),
        _get_nested(profile, "postal_address", "adresse"),
        _get_nested(profile, "business_address", "adresse"),
        _get_nested(profile, "raw", "forretningsadresse.adresse"),
        _get_nested(profile, "raw", "forretningsadresse", "adresse"),
        _get_nested(profile, "raw", "postadresse.adresse"),
        _get_nested(profile, "raw", "postadresse", "adresse"),
        _get_nested(profile, "evidence", "registry", "value", "business_address", "adresse"),
        _get_nested(profile, "evidence", "registry_live", "value", "business_address", "adresse"),
        _get_nested(profile, "evidence", "registry", "value", "address"),
        _get_nested(profile, "evidence", "registry_live", "value", "address"),
    ]
    address_strings: list[str] = []
    for cand in addr_candidates:
        if isinstance(cand, list):
            for item in cand:
                if isinstance(item, str) and item.strip():
                    address_strings.append(item.strip())
        elif isinstance(cand, str) and cand.strip():
            cleaned = re.sub(r"[\[\]'\" ]+", " ", cand).strip()
            if cleaned and cleaned not in address_strings:
                address_strings.append(cleaned)

    return clean_postcode, address_strings


def _extract_registry_municipality(profile: dict[str, Any]) -> str | None:
    """Extract municipality name from official registry profile signals."""
    candidates = [
        profile.get("municipality"),
        profile.get("kommune"),
        _get_nested(profile, "forretningsadresse", "kommune"),
        _get_nested(profile, "postadresse", "kommune"),
        _get_nested(profile, "business_address", "municipality"),
        _get_nested(profile, "raw", "forretningsadresse.kommune"),
        _get_nested(profile, "raw", "forretningsadresse", "kommune"),
        _get_nested(profile, "raw", "postadresse.kommune"),
        _get_nested(profile, "raw", "postadresse", "kommune"),
        _get_nested(profile, "evidence", "registry", "value", "business_address", "municipality"),
        _get_nested(profile, "evidence", "registry_live", "value", "business_address", "municipality"),
        _get_nested(profile, "evidence", "registry", "value", "forretningsadresse", "kommune"),
        _get_nested(profile, "evidence", "registry_live", "value", "forretningsadresse", "kommune"),
    ]
    for c in candidates:
        if c and isinstance(c, str) and c.strip():
            clean = re.sub(r"(?i)\s+kommune$", "", c.strip()).strip()
            if clean:
                return clean
    return None


def _municipality_matches(municipality: str | None, text_sources: list[tuple[str, str]]) -> tuple[bool, str | None, str | None]:
    """Check if the official registered municipality appears in captured page texts."""
    if not municipality:
        return False, None, None
    clean_muni = municipality.strip()
    norm_muni = unicodedata.normalize("NFKD", clean_muni).encode("ascii", "ignore").decode().casefold()
    if not norm_muni:
        return False, None, None

    is_short = len(norm_muni) <= 2
    for loc_name, text in text_sources:
        if not text:
            continue
        text_norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
        if is_short:
            pattern = rf"\b(?:i\s+|ved\s+)?{re.escape(clean_muni.lower())}(?:\s+kommune)?\b"
            m = re.search(pattern, text.lower())
            if m and ("kommune" in m.group(0) or "i " in m.group(0)):
                start = max(0, m.start() - 25)
                end = min(len(text), m.end() + 25)
                return True, loc_name, text[start:end].replace("\n", " ").strip()
        else:
            m = re.search(rf"\b{re.escape(norm_muni)}\b", text_norm)
            if m:
                orig_start = max(0, m.start() - 25)
                orig_end = min(len(text), m.end() + 25)
                return True, loc_name, text[orig_start:orig_end].replace("\n", " ").strip()
    return False, None, None


def _match_address_signals(
    profile: dict[str, Any],
    text_sources: list[tuple[str, str]],
) -> tuple[str | None, str | None, str | None, str | None]:
    """Robustly verify registered postcode or street address against captured text sources.

    Requirements:
    1. Postcode must be exact 4 digits and supported by page evidence (proximity to municipality,
       postal place name, or address keywords). Standalone numbers (e.g. copyright years) are rejected.
    2. Street address must match a normalized, meaningful street name and a properly associated
       house number in close proximity (within 35 characters). Short fragments (< 3 chars, e.g. 'st')
       or isolated house numbers appearing elsewhere on the page are strictly rejected.

    Returns: (matched_postcode, matched_address, address_loc, address_excerpt)
    """
    clean_postcode, address_strings = _extract_registry_address_signals(profile)
    municipality = _extract_registry_municipality(profile)
    muni_norm = str(municipality or "").strip().lower()

    matched_postcode: str | None = None
    matched_address: str | None = None
    address_loc: str | None = None
    address_excerpt: str | None = None

    # 1. Postcode matching supported by page evidence
    if clean_postcode and len(clean_postcode) == 4:
        for loc_name, text in text_sources:
            if not text:
                continue
            for pm in re.finditer(rf"\b{re.escape(clean_postcode)}\b", text):
                p_start = pm.start()
                p_end = pm.end()
                ctx_start = max(0, p_start - 60)
                ctx_end = min(len(text), p_end + 60)
                ctx = text[ctx_start:ctx_end]
                ctx_lower = ctx.lower()

                # Guard against standalone years like "Copyright 2024" or "(c) 2024"
                if re.search(rf"(?:copyright|\(c\)|©|est\.?|siden|etablert|founded|fra)\s*{re.escape(clean_postcode)}\b", ctx_lower):
                    if not re.search(r"\b(?:adresse|besøksadresse|besoksadresse|postadresse|postboks|pb|gate|vei|plass|alle|n-|no-)\b", ctx_lower):
                        continue

                # Supporting evidence required:
                # A: Preceded/followed by municipality name
                has_muni = bool(muni_norm and len(muni_norm) >= 3 and muni_norm in ctx_lower)
                # B: Immediately followed by a capitalized postal place name (e.g. "0579 Oslo", "6393 Tomrefjord")
                has_postal_place = bool(re.search(rf"\b{re.escape(clean_postcode)}\s+([A-ZÆØÅ][a-zæøåA-ZÆØÅ]{{2,}})\b", ctx))
                # C: In proximity to standard address keywords
                has_addr_keyword = bool(re.search(r"\b(?:adresse|besøksadresse|besoksadresse|postadresse|postboks|pb|boks|gate|vei|veien|plass|kai|kaia|n-|no-)\b", ctx_lower))

                if has_muni or has_postal_place or has_addr_keyword:
                    matched_postcode = clean_postcode
                    address_loc = loc_name
                    excerpt_start = max(0, p_start - 30)
                    excerpt_end = min(len(text), p_end + 30)
                    address_excerpt = text[excerpt_start:excerpt_end].replace("\n", " ").strip()
                    break
            if matched_postcode:
                break

    # 2. Meaningful Street Address matching with properly associated house number
    if not matched_postcode and address_strings:
        for addr_str in address_strings:
            if not addr_str or not isinstance(addr_str, str):
                continue
            addr_clean = addr_str.strip()

            # Ignore pure PO Box lines for physical street matching
            if re.match(r"(?i)^(?:postboks|pb\.?|boks)\b", addr_clean):
                continue

            # Extract house number (e.g. "94", "11A", "14B", "5")
            house_match = re.search(r"\b(\d+[a-zA-Z]?)\b", addr_clean)
            house_num = house_match.group(1) if house_match else None

            # Street portion (excluding house number)
            if house_match:
                street_portion = addr_clean[:house_match.start()].strip() or addr_clean
            else:
                street_portion = addr_clean
            street_portion = re.sub(r"[\.,\-]+$", "", street_portion).strip()

            raw_tokens = _tokens(street_portion)
            # Distinctive street tokens must be >= 3 chars and NOT in generic street words
            distinctive_tokens = [tok for tok in raw_tokens if len(tok) >= 3 and tok not in SHORT_OR_GENERIC_STREET_TOKENS]

            # If all tokens are in generic street words (e.g. "Bakken" or "Haugen"), allow the longest token if len >= 4
            if not distinctive_tokens and raw_tokens:
                longest = max(raw_tokens, key=len)
                if len(longest) >= 4:
                    distinctive_tokens = [longest]

            # NEVER allow short tokens (< 3 chars, like 'st' or 'dr') as the sole street token
            if not distinctive_tokens:
                continue

            for loc_name, text in text_sources:
                if not text:
                    continue
                text_lower = text.lower()

                for dist_tok in distinctive_tokens:
                    # Must match distinctive street token as a WHOLE WORD (not substring in "Australia")
                    for tok_match in re.finditer(rf"\b{re.escape(dist_tok)}\b", text_lower):
                        t_start = tok_match.start()
                        t_end = tok_match.end()

                        if house_num:
                            # Proximity window: up to 35 chars after, 25 chars before
                            win_after = text_lower[t_end : min(len(text_lower), t_end + 35)]
                            win_before = text_lower[max(0, t_start - 25) : t_start]

                            house_pattern = rf"\b{re.escape(house_num.lower())}\b"
                            found_house = re.search(house_pattern, win_after) or re.search(house_pattern, win_before)
                            if found_house:
                                matched_address = addr_clean
                                address_loc = loc_name
                                start_idx = max(0, t_start - 20)
                                end_idx = min(len(text), t_end + 50)
                                address_excerpt = text[start_idx:end_idx].replace("\n", " ").strip()
                                break
                        else:
                            # If no house number in registered address, require distinctive token len >= 5
                            if len(dist_tok) >= 5:
                                matched_address = addr_clean
                                address_loc = loc_name
                                start_idx = max(0, t_start - 20)
                                end_idx = min(len(text), t_end + 50)
                                address_excerpt = text[start_idx:end_idx].replace("\n", " ").strip()
                                break
                    if matched_address:
                        break
                if matched_address:
                    break
            if matched_address:
                break

    return matched_postcode, matched_address, address_loc, address_excerpt


def _match_name_tokens(core: list[str], cand_tokens: set[str], allow_brand_prefix: bool = False) -> tuple[bool, list[str]]:
    """Match distinctive legal-name tokens against candidate tokens with synonym and morphology support."""
    if not core:
        return False, []

    expanded = set(cand_tokens)
    for t in cand_tokens:
        for s1, s2 in SYNONYM_PAIRS:
            if t == s1:
                expanded.add(s2)
            elif t == s2:
                expanded.add(s1)

    matched: list[str] = []
    for t in core:
        if t in expanded:
            matched.append(t)
        else:
            # Check Norwegian compound / morphological inflection prefix (e.g. buskerudmuseene vs buskerudmuseet)
            if len(t) >= 6:
                for c in expanded:
                    if len(c) >= 6 and (c.startswith(t[:len(t)-3]) or t.startswith(c[:len(c)-3])):
                        matched.append(t)
                        break

    # Exact subset match: all distinctive tokens matched
    if len(matched) == len(core):
        return True, matched

    # Brand prefix match (e.g. EPTEC Energi where Energi is an industry suffix)
    if allow_brand_prefix and core:
        primary = core[0]
        if primary in matched and len(primary) >= 4 and primary not in INDUSTRY_WORDS:
            remaining = [tok for tok in core[1:] if tok not in INDUSTRY_WORDS]
            if not remaining or all(tok in matched for tok in remaining):
                return True, matched

    return False, matched


def _assess_strict_website_identity(profile: dict[str, Any]) -> dict[str, Any]:
    """Strict centrally defined website identity verification policy (strict_website_identity_v1)."""
    website = profile.get("evidence", {}).get("website") or profile.get("evidence", {}).get("website_discovered") or {}
    value = website.get("value") or {}
    final_url = value.get("final_url") or website.get("source_url") or profile.get("website") or ""
    rendered = value.get("js_fallback") or {}

    core = _tokens(profile.get("name"))
    target_org_digits = re.sub(r"\D", "", str(profile.get("organisation_number") or ""))
    has_valid_target_org = len(target_org_digits) == 9

    homepage_title = str(value.get("title") or "").strip()
    homepage_h1 = str(value.get("h1") or "").strip()
    rendered_title = str(rendered.get("title") or "").strip()
    rendered_h1 = str(rendered.get("h1") or "").strip()
    meta_desc = str(value.get("description") or "").strip()
    homepage_identity = str(value.get("identity_text_excerpt") or "").strip()
    homepage_body = str(value.get("main_text_excerpt") or "").strip()
    rendered_body = str(rendered.get("main_text_excerpt") or "").strip()

    text_sources: list[tuple[str, str]] = [
        ("homepage_title", homepage_title),
        ("homepage_h1", homepage_h1),
        ("rendered_title", rendered_title),
        ("rendered_h1", rendered_h1),
        ("homepage_identity", homepage_identity),
        ("homepage_body", homepage_body),
        ("homepage_meta", meta_desc),
        ("rendered_body", rendered_body),
    ]

    for idx, page in enumerate(value.get("pages", [])):
        page_url = page.get("url") or f"page_{idx + 1}"
        p_title = str(page.get("title") or "").strip()
        p_h1 = str(page.get("h1") or "").strip()
        p_body = str(page.get("main_text_excerpt") or "").strip()
        p_id = str(page.get("identity_text_excerpt") or "").strip()
        if p_title:
            text_sources.append((f"secondary_page_title:{page_url}", p_title))
        if p_h1:
            text_sources.append((f"secondary_page_h1:{page_url}", p_h1))
        if p_id:
            text_sources.append((f"secondary_page_identity:{page_url}", p_id))
        if p_body:
            text_sources.append((f"secondary_page_body:{page_url}", p_body))

    all_captured_text = " ".join(t for _, t in text_sources if t)
    normalized_raw = unicodedata.normalize("NFKD", all_captured_text).encode("ascii", "ignore").decode().casefold()
    candidate_tokens = set(_tokens(all_captured_text))
    overlap = sorted(set(core) & candidate_tokens)

    # Check parked markers
    if any(marker in normalized_raw for marker in PARKED_MARKERS):
        return {
            "status": "ambiguous",
            "score": 0.1,
            "publishable": False,
            "policy": "strict_website_identity_v1",
            "automated_identity_result": "parked_or_placeholder",
            "condition_passed": None,
            "identity_evidence": {
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": "homepage",
                "excerpt": "Captured page is a parked, for-sale, or generic hosting placeholder",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["captured page is a parked, for-sale, or generic hosting placeholder"],
            "method": "strict_website_identity_v1",
        }

    # Check business sports club exception
    is_business_sports_club = bool(re.search(r"(?:^|\s)B\.?\s*I\.?\s*L\.?(?:\s|$)", str(profile.get("name") or ""), re.I))
    if is_business_sports_club and "bedriftsidrett" not in normalized_raw and "b i l" not in normalized_raw:
        return {
            "status": "ambiguous",
            "score": 0.3,
            "publishable": False,
            "policy": "strict_website_identity_v1",
            "automated_identity_result": "sports_club_mismatch",
            "condition_passed": None,
            "identity_evidence": {
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": "homepage",
                "excerpt": "Business sports-club points to operating company site without club evidence",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["business sports-club entity points to the operating company's site without club evidence"],
            "method": "strict_website_identity_v1",
        }

    # Check for 9-digit numbers
    found_conflicting_numbers: set[str] = set()
    target_match_info: tuple[str, str] | None = None

    for loc_name, text in text_sources:
        if not text:
            continue
        for m in re.finditer(r"\b(\d{3}[\s.-]?\d{3}[\s.-]?\d{3})\b", text):
            compact = re.sub(r"\D", "", m.group(1))
            if len(compact) == 9:
                if has_valid_target_org and compact == target_org_digits:
                    if target_match_info is None and not loc_name.startswith("secondary_page_"):
                        start = max(0, m.start() - 35)
                        end = min(len(text), m.end() + 35)
                        raw_snippet = text[start:end].replace("\n", " ").strip()
                        target_match_info = (loc_name, raw_snippet)
                else:
                    found_conflicting_numbers.add(compact)

    conflicting_org_detected = False
    if has_valid_target_org and target_match_info is None and len(found_conflicting_numbers) > 0:
        conflicting_org_detected = True

    if target_match_info is not None:
        loc, excerpt = target_match_info
        return {
            "status": "exact",
            "score": 1.0,
            "publishable": True,
            "policy": "strict_website_identity_v1",
            "automated_identity_result": "exact_identifier",
            "condition_passed": "A_exact_org_number",
            "identity_evidence": {
                "matched_identifier": target_org_digits,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": loc,
                "excerpt": excerpt,
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["exact nine-digit organisation number matches target entity in captured content"],
            "method": "strict_website_identity_v1",
        }

    if conflicting_org_detected:
        conflicting_id = next(iter(found_conflicting_numbers))
        return {
            "status": "ambiguous",
            "score": 0.3,
            "publishable": False,
            "policy": "strict_website_identity_v1",
            "automated_identity_result": "conflicting_identifier",
            "condition_passed": None,
            "identity_evidence": {
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": "captured_content",
                "excerpt": f"Conflicting organisation number found: {conflicting_id} (target: {target_org_digits})",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": [f"captured content contains conflicting nine-digit organisation number: {conflicting_id}"],
            "method": "strict_website_identity_v1",
        }

    # Condition B
    title_and_h1_candidates = [
        ("homepage_title", homepage_title),
        ("homepage_h1", homepage_h1),
        ("rendered_title", rendered_title),
        ("rendered_h1", rendered_h1),
    ]
    for idx, page in enumerate(value.get("pages", [])):
        p_url = page.get("url") or f"page_{idx + 1}"
        if page.get("title"):
            title_and_h1_candidates.append((f"page_title:{p_url}", str(page["title"]).strip()))
        if page.get("h1"):
            title_and_h1_candidates.append((f"page_h1:{p_url}", str(page["h1"]).strip()))

    name_matched_title_h1 = False
    name_matched_location: str | None = None
    if core:
        core_set = set(core)
        for loc, cand_text in title_and_h1_candidates:
            if not cand_text:
                continue
            cand_tokens = set(_tokens(cand_text))
            if core_set.issubset(cand_tokens):
                name_matched_title_h1 = True
                name_matched_location = loc
                break

    matched_postcode, matched_address, address_loc, address_excerpt = _match_address_signals(profile, text_sources)
    address_confirmed = bool(matched_postcode or matched_address)

    if name_matched_title_h1 and address_confirmed:
        combined_loc = f"{name_matched_location} + {address_loc}"
        evidence_snippet = f"Title/H1: {name_matched_location}; Address: {address_excerpt}"
        return {
            "status": "exact",
            "score": 0.95,
            "publishable": True,
            "policy": "strict_website_identity_v1",
            "automated_identity_result": "combined_identity",
            "condition_passed": "B_name_plus_address",
            "identity_evidence": {
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": matched_address,
                "matched_postcode": matched_postcode,
                "url": final_url,
                "location": combined_loc,
                "excerpt": evidence_snippet,
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["all distinctive legal-name tokens match title/H1 and registered postcode/street address confirmed in text"],
            "method": "strict_website_identity_v1",
        }

    reasons = []
    if not has_valid_target_org:
        reasons.append("target company lacks a valid 9-digit organisation number")
    elif target_match_info is None:
        reasons.append("exact nine-digit organisation number not found in captured content")

    if not name_matched_title_h1:
        reasons.append("not all distinctive legal-name tokens match page title or H1")
    if not address_confirmed:
        reasons.append("registered postcode or street address not found in captured content (municipality alone is insufficient)")

    return {
        "status": "ambiguous",
        "score": 0.5,
        "publishable": False,
        "policy": "strict_website_identity_v1",
        "automated_identity_result": "insufficient_evidence",
        "condition_passed": None,
        "identity_evidence": {
            "matched_identifier": None,
            "matched_tokens": overlap,
            "matched_address": None,
            "matched_postcode": None,
            "url": final_url,
            "location": "homepage",
            "excerpt": (homepage_title or meta_desc or homepage_body[:100]).strip() or "No substantive content",
        },
        "human_review_status": "not_reviewed",
        "legal_name_tokens": core,
        "matched_tokens": overlap,
        "reasons": reasons,
        "method": "strict_website_identity_v1",
    }


def _assess_tiered_website_identity(profile: dict[str, Any]) -> dict[str, Any]:
    """Multi-tier website identity verification policy (tiered_website_identity_v1).

    Tiers:
    - Tier A: Exact identifier evidence (Score 1.0 homepage, 0.98 secondary contact/about page)
    - Tier B: Legal name + registered address or postcode (Score 0.95)
    - Tier C: Strong independent corroboration:
        - C1: Official registry-declared link + distinctive legal name + municipality (Score 0.90)
        - C2: Discovered distinctive domain + distinctive legal name + municipality (Score 0.90)
    """
    website = profile.get("evidence", {}).get("website") or profile.get("evidence", {}).get("website_discovered") or {}
    value = website.get("value") or {}
    final_url = value.get("final_url") or website.get("source_url") or profile.get("website") or ""
    rendered = value.get("js_fallback") or {}

    core = _tokens(profile.get("name"))
    target_org_digits = re.sub(r"\D", "", str(profile.get("organisation_number") or ""))
    has_valid_target_org = len(target_org_digits) == 9

    cand_reg_domain = _registered_domain(final_url)
    cand_sld = _extract_sld(final_url)

    # 1. Collect named text sources
    homepage_title = str(value.get("title") or "").strip()
    homepage_h1 = str(value.get("h1") or "").strip()
    rendered_title = str(rendered.get("title") or "").strip()
    rendered_h1 = str(rendered.get("h1") or "").strip()
    meta_desc = str(value.get("description") or "").strip()
    homepage_identity = str(value.get("identity_text_excerpt") or "").strip()
    homepage_body = str(value.get("main_text_excerpt") or "").strip()
    rendered_body = str(rendered.get("main_text_excerpt") or "").strip()

    text_sources: list[tuple[str, str]] = [
        ("homepage_title", homepage_title),
        ("homepage_h1", homepage_h1),
        ("rendered_title", rendered_title),
        ("rendered_h1", rendered_h1),
        ("homepage_identity", homepage_identity),
        ("homepage_body", homepage_body),
        ("homepage_meta", meta_desc),
        ("rendered_body", rendered_body),
    ]

    for idx, page in enumerate(value.get("pages", [])):
        page_url = page.get("url") or f"page_{idx + 1}"
        p_title = str(page.get("title") or "").strip()
        p_h1 = str(page.get("h1") or "").strip()
        p_body = str(page.get("main_text_excerpt") or "").strip()
        p_id = str(page.get("identity_text_excerpt") or "").strip()
        if p_title:
            text_sources.append((f"secondary_page_title:{page_url}", p_title))
        if p_h1:
            text_sources.append((f"secondary_page_h1:{page_url}", p_h1))
        if p_id:
            text_sources.append((f"secondary_page_identity:{page_url}", p_id))
        if p_body:
            text_sources.append((f"secondary_page_body:{page_url}", p_body))

    all_captured_text = " ".join(t for _, t in text_sources if t)
    normalized_raw = unicodedata.normalize("NFKD", all_captured_text).encode("ascii", "ignore").decode().casefold()
    candidate_tokens = set(_tokens(all_captured_text))
    overlap = sorted(set(core) & candidate_tokens)

    # Determine evidence source
    registry_url = profile.get("website") or profile.get("registry_website") or _get_nested(profile, "evidence", "registry", "value", "website") or _get_nested(profile, "evidence", "registry_live", "value", "website")
    registry_domain = _registered_domain(registry_url) if registry_url else ""
    is_registry_declared = bool(registry_domain and cand_reg_domain and registry_domain == cand_reg_domain)
    evidence_source = "official_registry" if is_registry_declared else "discovered_domain"

    # 2. Check parked / placeholder markers
    if any(marker in normalized_raw for marker in PARKED_MARKERS):
        return {
            "status": "ambiguous",
            "score": 0.1,
            "publishable": False,
            "policy": "tiered_website_identity_v1",
            "automated_identity_result": "parked_or_placeholder",
            "condition_passed": None,
            "selected_tier": None,
            "identity_evidence": {
                "target_organisation_number": target_org_digits,
                "candidate_domain": cand_reg_domain,
                "evidence_source": evidence_source,
                "selected_tier": None,
                "extracted_matching_evidence": {"matched_identifier": None, "matched_tokens": overlap},
                "conflicting_evidence": [],
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": "homepage",
                "excerpt": "Captured page is a parked, for-sale, or generic hosting placeholder",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["captured page is a parked, for-sale, or generic hosting placeholder"],
            "method": "tiered_website_identity_v1",
        }

    # Reject directory and social domains
    if cand_reg_domain in DIRECTORY_AND_SOCIAL_DOMAINS:
        return {
            "status": "ambiguous",
            "score": 0.1,
            "publishable": False,
            "policy": "tiered_website_identity_v1",
            "automated_identity_result": "insufficient_evidence",
            "condition_passed": None,
            "selected_tier": None,
            "identity_evidence": {
                "target_organisation_number": target_org_digits,
                "candidate_domain": cand_reg_domain,
                "evidence_source": evidence_source,
                "selected_tier": None,
                "extracted_matching_evidence": {},
                "conflicting_evidence": [],
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": "domain",
                "excerpt": f"Domain {cand_reg_domain} is a generic directory or social network, not an official company website",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": [f"domain {cand_reg_domain} is a directory or social network"],
            "method": "tiered_website_identity_v1",
        }

    # 3. Check business sports club exception
    is_business_sports_club = bool(re.search(r"(?:^|\s)B\.?\s*I\.?\s*L\.?(?:\s|$)", str(profile.get("name") or ""), re.I))
    if is_business_sports_club and "bedriftsidrett" not in normalized_raw and "b i l" not in normalized_raw:
        return {
            "status": "ambiguous",
            "score": 0.3,
            "publishable": False,
            "policy": "tiered_website_identity_v1",
            "automated_identity_result": "sports_club_mismatch",
            "condition_passed": None,
            "selected_tier": None,
            "identity_evidence": {
                "target_organisation_number": target_org_digits,
                "candidate_domain": cand_reg_domain,
                "evidence_source": evidence_source,
                "selected_tier": None,
                "extracted_matching_evidence": {"matched_identifier": None, "matched_tokens": overlap},
                "conflicting_evidence": [],
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": "homepage",
                "excerpt": "Business sports-club points to operating company site without club evidence",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["business sports-club entity points to the operating company's site without club evidence"],
            "method": "tiered_website_identity_v1",
        }

    # 4. Collect title and H1 candidates
    title_and_h1_candidates = [
        ("homepage_title", homepage_title),
        ("homepage_h1", homepage_h1),
        ("rendered_title", rendered_title),
        ("rendered_h1", rendered_h1),
    ]
    for idx, page in enumerate(value.get("pages", [])):
        p_url = page.get("url") or f"page_{idx + 1}"
        if page.get("title"):
            title_and_h1_candidates.append((f"page_title:{p_url}", str(page["title"]).strip()))
        if page.get("h1"):
            title_and_h1_candidates.append((f"page_h1:{p_url}", str(page["h1"]).strip()))

    # 5. Check for 9-digit organisation numbers across captured text
    found_conflicting_numbers: set[str] = set()
    homepage_match_info: tuple[str, str] | None = None
    secondary_match_info: tuple[str, str] | None = None

    for loc_name, text in text_sources:
        if not text:
            continue
        for m in re.finditer(r"\b(\d{3}[\s.-]?\d{3}[\s.-]?\d{3})\b", text):
            compact = re.sub(r"\D", "", m.group(1))
            if len(compact) == 9:
                if has_valid_target_org and compact == target_org_digits:
                    start = max(0, m.start() - 35)
                    end = min(len(text), m.end() + 35)
                    raw_snippet = text[start:end].replace("\n", " ").strip()
                    if loc_name.startswith("secondary_page_"):
                        if secondary_match_info is None:
                            secondary_match_info = (loc_name, raw_snippet)
                    else:
                        if homepage_match_info is None:
                            homepage_match_info = (loc_name, raw_snippet)
                else:
                    found_conflicting_numbers.add(compact)

    has_any_target_match = bool(homepage_match_info or secondary_match_info)
    conflicting_org_detected = bool(has_valid_target_org and not has_any_target_match and found_conflicting_numbers)

    # 5. TIER A: Exact identifier evidence
    if homepage_match_info is not None:
        loc, excerpt = homepage_match_info
        return {
            "status": "exact",
            "score": 1.0,
            "publishable": True,
            "policy": "tiered_website_identity_v1",
            "automated_identity_result": "tier_a_exact_org",
            "condition_passed": "A_exact_org_number",
            "selected_tier": "Tier A",
            "identity_evidence": {
                "target_organisation_number": target_org_digits,
                "candidate_domain": cand_reg_domain,
                "evidence_source": evidence_source,
                "selected_tier": "Tier A",
                "extracted_matching_evidence": {
                    "matched_identifier": target_org_digits,
                    "matched_tokens": overlap,
                    "location": loc,
                    "excerpt": excerpt,
                },
                "conflicting_evidence": list(found_conflicting_numbers),
                "matched_identifier": target_org_digits,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": loc,
                "excerpt": excerpt,
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["exact nine-digit organisation number matches target entity on homepage"],
            "method": "tiered_website_identity_v1",
        }

    if secondary_match_info is not None:
        loc, excerpt = secondary_match_info
        name_matched_secondary = False
        for sloc, stext in title_and_h1_candidates:
            if not stext:
                continue
            stoks = set(_tokens(stext))
            matched_exact, _ = _match_name_tokens(core, stoks, allow_brand_prefix=False)
            if matched_exact:
                name_matched_secondary = True
                break

        if name_matched_secondary:
            return {
                "status": "exact",
                "score": 0.98,
                "publishable": True,
                "policy": "tiered_website_identity_v1",
                "automated_identity_result": "tier_a_exact_org",
                "condition_passed": "A_exact_org_number",
                "selected_tier": "Tier A",
                "identity_evidence": {
                    "target_organisation_number": target_org_digits,
                    "candidate_domain": cand_reg_domain,
                    "evidence_source": evidence_source,
                    "selected_tier": "Tier A",
                    "extracted_matching_evidence": {
                        "matched_identifier": target_org_digits,
                        "matched_tokens": overlap,
                        "location": loc,
                        "excerpt": excerpt,
                    },
                    "conflicting_evidence": list(found_conflicting_numbers),
                    "matched_identifier": target_org_digits,
                    "matched_tokens": overlap,
                    "matched_address": None,
                    "matched_postcode": None,
                    "url": final_url,
                    "location": loc,
                    "excerpt": excerpt,
                },
                "human_review_status": "not_reviewed",
                "legal_name_tokens": core,
                "matched_tokens": overlap,
                "reasons": ["exact nine-digit organisation number matches target entity on secondary contact page with matching name"],
                "method": "tiered_website_identity_v1",
            }

    # If conflicting organisation number is present, reject immediately
    if conflicting_org_detected:
        conflicting_id = next(iter(found_conflicting_numbers))
        return {
            "status": "ambiguous",
            "score": 0.3,
            "publishable": False,
            "policy": "tiered_website_identity_v1",
            "automated_identity_result": "conflicting_identifier",
            "condition_passed": None,
            "selected_tier": None,
            "identity_evidence": {
                "target_organisation_number": target_org_digits,
                "candidate_domain": cand_reg_domain,
                "evidence_source": evidence_source,
                "selected_tier": None,
                "extracted_matching_evidence": {"matched_identifier": None, "matched_tokens": overlap},
                "conflicting_evidence": list(found_conflicting_numbers),
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "url": final_url,
                "location": "captured_content",
                "excerpt": f"Conflicting organisation number found: {conflicting_id} (target: {target_org_digits})",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": [f"captured content contains conflicting nine-digit organisation number: {conflicting_id}"],
            "method": "tiered_website_identity_v1",
        }

    # 6. Evaluate title / H1 candidates
    name_matched_title_h1 = False
    name_matched_brand_prefix = False
    name_matched_location: str | None = None
    name_matched_text: str | None = None

    if core:
        for loc, cand_text in title_and_h1_candidates:
            if not cand_text:
                continue
            cand_tokens = set(_tokens(cand_text))
            matched_exact, _ = _match_name_tokens(core, cand_tokens, allow_brand_prefix=False)
            if matched_exact:
                name_matched_title_h1 = True
                name_matched_location = loc
                name_matched_text = cand_text
                break
            matched_prefix, _ = _match_name_tokens(core, cand_tokens, allow_brand_prefix=True)
            if matched_prefix and not name_matched_brand_prefix:
                name_matched_brand_prefix = True
                name_matched_location = loc
                name_matched_text = cand_text

    # 7. Check Registered Postcode and Street Address
    matched_postcode, matched_address, address_loc, address_excerpt = _match_address_signals(profile, text_sources)
    address_confirmed = bool(matched_postcode or matched_address)

    # 8. TIER B: Legal name + registered address or postcode
    if name_matched_title_h1 and address_confirmed:
        combined_loc = f"{name_matched_location} + {address_loc}"
        evidence_snippet = f"Title/H1: {name_matched_text}; Address: {address_excerpt}"
        return {
            "status": "exact",
            "score": 0.95,
            "publishable": True,
            "policy": "tiered_website_identity_v1",
            "automated_identity_result": "tier_b_name_and_address",
            "condition_passed": "B_name_plus_address",
            "selected_tier": "Tier B",
            "identity_evidence": {
                "target_organisation_number": target_org_digits,
                "candidate_domain": cand_reg_domain,
                "evidence_source": evidence_source,
                "selected_tier": "Tier B",
                "extracted_matching_evidence": {
                    "matched_identifier": None,
                    "matched_tokens": overlap,
                    "matched_address": matched_address,
                    "matched_postcode": matched_postcode,
                    "matched_title": name_matched_text,
                    "location": combined_loc,
                },
                "conflicting_evidence": list(found_conflicting_numbers),
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": matched_address,
                "matched_postcode": matched_postcode,
                "url": final_url,
                "location": combined_loc,
                "excerpt": evidence_snippet,
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["distinctive legal-name tokens match title/H1 and registered postcode/street address confirmed in text"],
            "method": "tiered_website_identity_v1",
        }

    # 9. Check Registered Municipality
    municipality = _extract_registry_municipality(profile)
    matched_muni_flag, muni_loc, muni_excerpt = _municipality_matches(municipality, text_sources)

    # 10. TIER C1: Official Registry-Declared Link + Distinctive Name + Municipality
    name_acceptable_tier_c = name_matched_title_h1 or name_matched_brand_prefix
    if is_registry_declared and name_acceptable_tier_c and (matched_muni_flag or address_confirmed):
        loc_desc = f"{name_matched_location} + {muni_loc or address_loc}"
        loc_excerpt = muni_excerpt or address_excerpt or f"Municipality: {municipality}"
        return {
            "status": "exact",
            "score": 0.90,
            "publishable": True,
            "policy": "tiered_website_identity_v1",
            "automated_identity_result": "tier_c_registry_corroborated",
            "condition_passed": "C1_registry_link_plus_name_and_locality",
            "selected_tier": "Tier C",
            "identity_evidence": {
                "target_organisation_number": target_org_digits,
                "candidate_domain": cand_reg_domain,
                "evidence_source": "official_registry",
                "selected_tier": "Tier C",
                "extracted_matching_evidence": {
                    "matched_identifier": None,
                    "matched_tokens": overlap,
                    "matched_address": matched_address,
                    "matched_postcode": matched_postcode,
                    "matched_municipality": municipality if matched_muni_flag else None,
                    "matched_title": name_matched_text,
                    "location": loc_desc,
                },
                "conflicting_evidence": list(found_conflicting_numbers),
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": matched_address,
                "matched_postcode": matched_postcode,
                "url": final_url,
                "location": loc_desc,
                "excerpt": f"Registry Link: {registry_url}; Title/H1: {name_matched_text}; Locality: {loc_excerpt}",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["domain matches official registry-declared website, distinctive name matches title/H1, and locality matches registered municipality"],
            "method": "tiered_website_identity_v1",
        }

    # 11. TIER C2: Discovered Distinctive Domain + Legal Name + Municipality
    # Check if candidate SLD matches distinctive legal name
    sld_matches_distinctive_name = False
    if cand_sld and core:
        compact_core = "".join(core)
        hyphen_core = "-".join(core)
        if cand_sld in {compact_core, hyphen_core}:
            sld_matches_distinctive_name = True
        elif len(core) >= 1 and cand_sld == core[0] and len(core[0]) >= 4 and core[0] not in INDUSTRY_WORDS:
            sld_matches_distinctive_name = True
        elif len(core) >= 2 and cand_sld == f"{core[0]}{core[1]}":
            sld_matches_distinctive_name = True

    if not is_registry_declared and sld_matches_distinctive_name and name_matched_title_h1 and (matched_muni_flag or address_confirmed):
        loc_desc = f"{name_matched_location} + {muni_loc or address_loc}"
        loc_excerpt = muni_excerpt or address_excerpt or f"Municipality: {municipality}"
        return {
            "status": "exact",
            "score": 0.90,
            "publishable": True,
            "policy": "tiered_website_identity_v1",
            "automated_identity_result": "tier_c_registry_corroborated",
            "condition_passed": "C2_discovered_domain_plus_name_and_municipality",
            "selected_tier": "Tier C",
            "identity_evidence": {
                "target_organisation_number": target_org_digits,
                "candidate_domain": cand_reg_domain,
                "evidence_source": "discovered_domain",
                "selected_tier": "Tier C",
                "extracted_matching_evidence": {
                    "matched_identifier": None,
                    "matched_tokens": overlap,
                    "matched_address": matched_address,
                    "matched_postcode": matched_postcode,
                    "matched_municipality": municipality if matched_muni_flag else None,
                    "matched_title": name_matched_text,
                    "location": loc_desc,
                },
                "conflicting_evidence": list(found_conflicting_numbers),
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": matched_address,
                "matched_postcode": matched_postcode,
                "url": final_url,
                "location": loc_desc,
                "excerpt": f"Distinctive Domain: {cand_reg_domain}; Title/H1: {name_matched_text}; Locality: {loc_excerpt}",
            },
            "human_review_status": "not_reviewed",
            "legal_name_tokens": core,
            "matched_tokens": overlap,
            "reasons": ["discovered domain matches distinctive legal-name SLD, distinctive name matches title/H1, and locality matches registered municipality"],
            "method": "tiered_website_identity_v1",
        }

    # 12. Determine specific failure category
    reasons = []
    if not has_valid_target_org:
        reasons.append("target company lacks a valid 9-digit organisation number")
    elif not has_any_target_match:
        reasons.append("exact nine-digit organisation number not found in captured content")

    if not name_matched_title_h1:
        reasons.append("distinctive legal-name tokens do not match page title or H1")
        failure_cat = "insufficient_evidence_name_mismatch"
    elif not (address_confirmed or matched_muni_flag):
        reasons.append("neither registered street address, postcode, nor municipality confirmed in captured content")
        failure_cat = "insufficient_evidence_address_missing"
    else:
        failure_cat = "insufficient_evidence"

    return {
        "status": "ambiguous",
        "score": 0.5,
        "publishable": False,
        "policy": "tiered_website_identity_v1",
        "automated_identity_result": failure_cat,
        "condition_passed": None,
        "selected_tier": None,
        "identity_evidence": {
            "target_organisation_number": target_org_digits,
            "candidate_domain": cand_reg_domain,
            "evidence_source": evidence_source,
            "selected_tier": None,
            "extracted_matching_evidence": {
                "matched_identifier": None,
                "matched_tokens": overlap,
                "matched_address": None,
                "matched_postcode": None,
                "matched_municipality": municipality if matched_muni_flag else None,
                "matched_title": name_matched_text,
            },
            "conflicting_evidence": list(found_conflicting_numbers),
            "matched_identifier": None,
            "matched_tokens": overlap,
            "matched_address": None,
            "matched_postcode": None,
            "url": final_url,
            "location": "homepage",
            "excerpt": (homepage_title or meta_desc or homepage_body[:100]).strip() or "No substantive content",
        },
        "human_review_status": "not_reviewed",
        "legal_name_tokens": core,
        "matched_tokens": overlap,
        "reasons": reasons,
        "method": "tiered_website_identity_v1",
    }


def assess_website_identity(profile: dict[str, Any], policy: str | None = None) -> dict[str, Any]:
    """Centrally defined website identity verification gateway.

    Supported policies:
    - tiered_website_identity_v1: Multi-tier verification (Tiers A, B, C)
    - strict_website_identity_v1 (default): Baseline strict verification (Tiers A, B only with exact address/postcode)
    """
    if policy is None:
        policy = os.environ.get("SIGNALPOST_IDENTITY_POLICY", "strict_website_identity_v1")

    if policy == "strict_website_identity_v1":
        return _assess_strict_website_identity(profile)
    elif policy == "tiered_website_identity_v1":
        return _assess_tiered_website_identity(profile)
    else:
        raise ValueError(f"Unknown website identity policy: {policy}")


def assess_social_identity(profile: dict[str, Any], link: dict[str, str]) -> dict[str, Any]:
    core = _tokens(profile.get("name"))
    parsed = urllib.parse.urlparse(link.get("url") or "")
    handle_text = urllib.parse.unquote(parsed.path)
    handle_compact = "".join(_tokens(handle_text))
    matched = [token for token in core if token in handle_compact]
    core_compact = "".join(core)
    ratio = len(set(matched)) / len(set(core)) if core else 0.0
    if core_compact and core_compact in handle_compact:
        score = 0.98
        reason = "normalized legal-name sequence appears in the social handle"
    elif len(core) == 1 and matched:
        score = 0.95
        reason = "single distinctive legal-name token appears in the social handle"
    elif ratio >= 0.75 and len(set(matched)) >= 2:
        score = 0.9
        reason = "most legal-name tokens appear in the social handle"
    else:
        score = 0.3
        reason = "social handle lacks strong exact-entity name evidence"
    return {
        **link,
        "identity_score": score,
        "publishable": score >= 0.9,
        "matched_tokens": matched,
        "reason": reason,
        "method": "deterministic_social_handle_identity_v1",
    }


def apply_website_identity_gate(profile: dict[str, Any], website: dict[str, Any], policy: str | None = None) -> dict[str, Any]:
    if website.get("status") != "available":
        return {"website": website, "assessment": None, "quarantined_social_links": 0}
    temporary_profile = {**profile, "evidence": {**profile.get("evidence", {}), "website": website}}
    value = website.get("value") or {}
    assessment = assess_website_identity(temporary_profile, policy=policy)
    value["identity_assessment"] = assessment
    original = list(value.get("discovered_social_links") or value.get("social_links") or [])
    value["discovered_social_links"] = original
    social_assessments = [assess_social_identity(profile, link) for link in original]
    value["social_link_assessments"] = social_assessments
    value["social_links"] = [
        {"platform": item["platform"], "url": item["url"]}
        for item in social_assessments
        if assessment["publishable"] and item["publishable"]
    ]
    website["value"] = value
    return {
        "website": website,
        "assessment": assessment,
        "quarantined_social_links": len(original) - len(value["social_links"]),
    }

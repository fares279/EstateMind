"""
EstateMind AI Chat Brain
Intelligent rule-based advisor grounded in real Tunisia market data.
No external LLM required — uses delegation CSV + embedded knowledge.
"""
from __future__ import annotations

import re
import random
from typing import Optional
from pathlib import Path
import sys

# Load delegation data from simulation engine
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simulation.engine.config import DELEGATION_DATA, SCENARIOS
    HAS_DATA = bool(DELEGATION_DATA)
except Exception:
    DELEGATION_DATA = []
    SCENARIOS = {}
    HAS_DATA = False

# ── Intent patterns ───────────────────────────────────────────────────────────
INTENT_PATTERNS = {
    'greeting':  [r'\bhello\b', r'\bhi\b', r'\bhey\b', r'\bbonjour\b', r'\bsalut\b',
                  r'\bsalam\b', r'\bstart\b', r'\bbegin\b'],
    'compare':   [r'\bcompar[ei]\b', r'\bdifferen[ct]\b', r'\bvs\b', r'\bversus\b',
                  r'\bbetter\b', r'\bmeilleur\b', r'\bcompare\b'],
    'mortgage':  [r'\bmortgage\b', r'\bcredit\b', r'\bloan\b', r'\bfinance\b',
                  r'\bpret\b', r'\bpr[eê]t\b', r'\btaux\b', r'\bBCT\b'],
    'climate':   [r'\bclimate\b', r'\bflood\b', r'\bsea.?level\b',
                  r'\brisque\b', r'\brisk\b', r'\benvironment\b'],
    'simulate':  [r'\bsimulat\b', r'\bscenario\b', r'\bmarket model\b'],
    'invest':    [r'\binvest\b', r'\byield\b', r'\bROI\b', r'\brent(?:al)?\b',
                  r'\bopportunity\b', r'\bopportunit[eé]\b', r'\bprofit\b',
                  r'\bportefeuille\b', r'\bportfolio\b'],
    'forecast':  [r'\bforecast\b', r'\bpredict\b', r'\btrend\b', r'\bfuture\b',
                  r'\bprojection\b', r'\b202[67]\b', r'\bprevision\b',
                  r'\bgrowth\b', r'\bcroissance\b'],
    'mortgage':  [r'\bmortgage\b', r'\bcredit\b', r'\bloan\b', r'\bfinance\b',
                  r'\brate\b'],
    'price':     [r'\bpri[cx]es?\b', r'\bcost\b', r'\bhow much\b', r'\bcombi[eé]n\b',
                  r'\bsomme\b', r'\bvaleur\b', r'\bTND\b', r'\bdinar\b', r'\baffordab'],
    'advice':    [r'\badvice\b', r'\brecommend\b', r'\bshould i\b', r'\bhelp me\b',
                  r'\bconseil\b', r'\bneed\b', r'\bbest\b'],
    'type':      [r'\bapartment\b', r'\bstudio\b', r'\bhouse\b', r'\bvilla\b',
                  r'\bmaison\b', r'\bappart\b', r'\bcommercial\b', r'\bland\b',
                  r'\bterrain\b', r'\bbureau\b'],
    'location':  [r'\bwhere\b', r'\blocation\b', r'\bgovernorate\b', r'\bdelegation\b',
                  r'\bcity\b', r'\bville\b', r'\bregion\b', r'\bzone\b',
                  r'\bneighbourhood\b', r'\barea\b', r'\bcôte\b'],
}

# ── Tunisia governorates & common aliases ─────────────────────────────────────
GOV_ALIASES = {
    'tunis': 'Tunis', 'ariana': 'Ariana', 'ben arous': 'Ben Arous',
    'manouba': 'La Manouba', 'la manouba': 'La Manouba', 'nabeul': 'Nabeul', 'zaghouan': 'Zaghouan',
    'bizerte': 'Bizerte', 'beja': 'Béja', 'béja': 'Béja', 'beja': 'Béja',
    'jendouba': 'Jendouba', 'kef': 'Le Kef', 'le kef': 'Le Kef',
    'siliana': 'Siliana', 'sousse': 'Sousse', 'monastir': 'Monastir',
    'mahdia': 'Mahdia', 'kairouan': 'Kairouan', 'kasserine': 'Kasserine',
    'sidi bouzid': 'Sidi Bouzid', 'sfax': 'Sfax', 'gafsa': 'Gafsa',
    'tozeur': 'Tozeur', 'kebili': 'Kébili', 'kébili': 'Kébili',
    'gabes': 'Gabès', 'gabès': 'Gabès', 'medenine': 'Médenine',
    'médenine': 'Médenine', 'tataouine': 'Tataouine',
}

PROP_ALIASES = {
    'apartment': 'apartment', 'appartement': 'apartment', 'appart': 'apartment',
    'flat': 'apartment', 'studio': 'apartment',
    'house': 'house', 'villa': 'house', 'maison': 'house', 'home': 'house',
    'commercial': 'commercial', 'shop': 'commercial', 'office': 'commercial',
    'bureau': 'commercial', 'magasin': 'commercial',
    'land': 'land', 'terrain': 'land', 'lot': 'land',
}

COASTAL_GOVS = {
    'Tunis', 'Ariana', 'Ben Arous', 'La Manouba', 'Nabeul', 'Bizerte',
    'Sousse', 'Monastir', 'Mahdia', 'Sfax', 'Gabès', 'Médenine',
}


# ── Data helpers ──────────────────────────────────────────────────────────────
def _build_gov_index() -> dict:
    """Aggregate delegation CSV into governorate-level stats."""
    idx: dict = {}
    for d in DELEGATION_DATA:
        gov = d.get('governorate', '')
        if not gov:
            continue
        if gov not in idx:
            idx[gov] = {'delegations': [], 'apartment': [], 'house': [], 'commercial': [], 'land': []}
        idx[gov]['delegations'].append(d['delegation'])
        for pt in ('apartment', 'house', 'commercial', 'land'):
            avg = d.get(f'{pt}_avg', 0) or 0
            if avg:
                idx[gov][pt].append(avg)
    # Compute averages
    result = {}
    for gov, v in idx.items():
        result[gov] = {
            'delegations': v['delegations'],
            'count': len(v['delegations']),
            'apartment': round(sum(v['apartment']) / len(v['apartment'])) if v['apartment'] else None,
            'house':     round(sum(v['house'])     / len(v['house']))     if v['house']     else None,
            'commercial':round(sum(v['commercial'])/ len(v['commercial']))if v['commercial'] else None,
            'land':      round(sum(v['land'])      / len(v['land']))      if v['land']      else None,
            'is_coastal': gov in COASTAL_GOVS,
        }
    return result


GOV_INDEX: dict = _build_gov_index()


def _top_govs(prop_type: str, n: int = 5, ascending=False) -> list:
    data = [(g, v[prop_type]) for g, v in GOV_INDEX.items() if v.get(prop_type)]
    data.sort(key=lambda x: x[1], reverse=not ascending)
    return data[:n]


def _detect_intent(msg: str) -> list[str]:
    msg_lower = msg.lower()
    found = []
    for intent, patterns in INTENT_PATTERNS.items():
        for p in patterns:
            if re.search(p, msg_lower):
                found.append(intent)
                break
    return found or ['general']


def _extract_gov(msg: str) -> Optional[str]:
    msg_lower = msg.lower()
    for alias, canonical in sorted(GOV_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in msg_lower:
            return canonical
    return None


def _extract_prop_type(msg: str) -> Optional[str]:
    msg_lower = msg.lower()
    for alias, canonical in PROP_ALIASES.items():
        if alias in msg_lower:
            return canonical
    return None


def _extract_budget(msg: str) -> Optional[int]:
    patterns = [
        r'(\d[\d\s,\.]*)\s*(?:TND|DT|dinar|k)',
        r'budget[:\s]+(\d[\d\s,\.]*)',
        r'(\d{3,})\s*(?:thousand|mille)',
    ]
    for p in patterns:
        m = re.search(p, msg, re.I)
        if m:
            raw = m.group(1).replace(' ', '').replace(',', '')
            try:
                val = float(raw)
                if 'k' in msg[m.start():m.end()+5].lower() or 'thousand' in msg[m.start():m.end()+10].lower() or 'mille' in msg[m.start():m.end()+10].lower():
                    val *= 1000
                return int(val)
            except ValueError:
                pass
    return None


# ── Response generators ───────────────────────────────────────────────────────
def _fmt_price(p: Optional[int]) -> str:
    if p is None:
        return 'N/A'
    if p >= 1000:
        return f"{p:,} TND/m²"
    return f"{p} TND/m²"


def _greeting_response() -> dict:
    msgs = [
        "Hello! I'm **EstateMind AI**, your personal real estate advisor for Tunisia. 🏠\n\nI can help you with:\n- **Current prices** across all 278 delegations\n- **Investment opportunities** and ROI analysis\n- **12-month price forecasts** by area\n- **Mortgage guidance** and affordability\n- **Neighborhood comparisons** and climate risk\n\nWhat's on your mind?",
        "Welcome! I'm your AI advisor for the Tunisian real estate market. Ask me anything about prices, trends, investment potential, or specific areas.",
    ]
    return {
        'message': random.choice(msgs),
        'suggestions': [
            "What are apartment prices in Tunis?",
            "Best areas to invest in 2026?",
            "Compare Sousse vs Sfax",
            "Mortgage rates in Tunisia",
        ],
        'intent': 'greeting',
    }


def _price_response(gov: Optional[str], prop_type: Optional[str]) -> dict:
    pt = prop_type or 'apartment'
    pt_label = {'apartment': 'Apartment', 'house': 'House/Villa', 'commercial': 'Commercial', 'land': 'Land'}[pt]

    if gov and gov in GOV_INDEX:
        info = GOV_INDEX[gov]
        price = info.get(pt)
        lines = [f"## {gov} — {pt_label} Prices\n"]
        if price:
            lines.append(f"**Average asking price:** {_fmt_price(price)}")
        lines.append(f"\n**Delegations covered:** {info['count']}")
        if info['is_coastal']:
            lines.append("🌊 *Coastal governorate — premium location*")

        # All types
        lines.append("\n**All property types:**")
        for p, label in [('apartment','Apartment'),('house','House'),('commercial','Commercial'),('land','Land')]:
            v = info.get(p)
            if v:
                lines.append(f"- {label}: {_fmt_price(v)}")

        suggestions = [
            f"Investment potential in {gov}?",
            f"12-month forecast for {gov}?",
            f"How does {gov} compare to other regions?",
            "Best delegations to buy in?",
        ]
        return {'message': '\n'.join(lines), 'suggestions': suggestions, 'intent': 'price', 'data': info}

    # No specific governorate — show national overview
    top5 = _top_govs(pt, n=5)
    affordable = _top_govs(pt, n=3, ascending=True)
    nat_prices = [v for v in [info.get(pt) for info in GOV_INDEX.values()] if v]
    nat_avg = round(sum(nat_prices) / len(nat_prices)) if nat_prices else None

    lines = [f"## Tunisia {pt_label} Market Overview\n"]
    if nat_avg:
        lines.append(f"**National average:** {_fmt_price(nat_avg)}\n")

    lines.append(f"**Most expensive governorates:**")
    for g, p in top5:
        lines.append(f"- {g}: {_fmt_price(p)}")

    lines.append(f"\n**Most affordable:**")
    for g, p in affordable:
        lines.append(f"- {g}: {_fmt_price(p)}")

    return {
        'message': '\n'.join(lines),
        'suggestions': [
            "Prices in Tunis?",
            "Cheapest areas to buy?",
            "Best value coastal area?",
            "Investment in Sousse?",
        ],
        'intent': 'price',
    }


def _invest_response(gov: Optional[str], prop_type: Optional[str], budget: Optional[int]) -> dict:
    lines = ["## Investment Analysis\n"]
    pt = prop_type or 'apartment'

    if gov and gov in GOV_INDEX:
        info = GOV_INDEX[gov]
        price = info.get(pt) or info.get('apartment', 2000)
        coastal_premium = 15 if info['is_coastal'] else 0
        rental_yield = 4.5 + coastal_premium * 0.05 + (1 if pt == 'commercial' else 0)

        lines.append(f"### {gov} — {pt.capitalize()} Investment\n")
        lines.append(f"**Avg price:** {_fmt_price(price)}")
        lines.append(f"**Estimated rental yield:** ~{rental_yield:.1f}% per year")
        lines.append(f"**Market type:** {'Coastal premium 🌊' if info['is_coastal'] else 'Inland market'}")

        if budget:
            area = int(budget / price) if price else 0
            lines.append(f"\n**With budget {budget:,} TND:**")
            lines.append(f"- Can acquire ~{area} m² in {gov}")
            lines.append(f"- Estimated annual rental income: ~{int(budget * rental_yield/100):,} TND")

        lines.append("\n**Key considerations:**")
        if info['is_coastal']:
            lines.append("- High tourist demand supports short-term rentals")
            lines.append("- Climate risk: sea-level projections may affect long-term values")
        else:
            lines.append("- Stable demand from local residents")
            lines.append("- Infrastructure investment could drive appreciation")
        lines.append("- Check the /simulate page for scenario-based projections")

    else:
        # Top investment picks
        lines.append("### Top Investment Regions in Tunisia (2026)\n")
        lines.append("**Best rental yield potential:**")
        coastal = [(g, v) for g, v in GOV_INDEX.items() if v['is_coastal'] and v.get('apartment')]
        coastal.sort(key=lambda x: x[1]['apartment'])  # lower price = higher yield potential
        for g, v in coastal[:4]:
            yield_est = 5.2 if v['apartment'] < 2000 else 4.1
            lines.append(f"- **{g}**: {_fmt_price(v['apartment'])} avg · ~{yield_est}% yield")

        lines.append("\n**Emerging inland markets:**")
        inland = [(g, v) for g, v in GOV_INDEX.items() if not v['is_coastal'] and v.get('apartment')]
        inland.sort(key=lambda x: x[1]['apartment'])
        for g, v in inland[:3]:
            lines.append(f"- **{g}**: {_fmt_price(v['apartment'])} avg · strong growth potential")

        lines.append("\n💡 *Use /analyze → Market Dashboard for full investment signals*")

    return {
        'message': '\n'.join(lines),
        'suggestions': [
            "ROI in Sousse for apartments?",
            "Best coastal investment under 200k TND?",
            "Compare Tunis vs Sfax for investors",
            "Run a market simulation",
        ],
        'intent': 'invest',
    }


def _forecast_response(gov: Optional[str], prop_type: Optional[str]) -> dict:
    pt = prop_type or 'apartment'
    lines = ["## 12-Month Price Forecast · 2026\n"]

    if gov and gov in GOV_INDEX:
        info = GOV_INDEX[gov]
        price = info.get(pt, 2000) or 2000
        # Estimate trend from CSV data (find matching delegations)
        trends = []
        for d in DELEGATION_DATA:
            if d.get('governorate') == gov:
                t = d.get(f'{pt}_trend', 0) or 0
                if t:
                    trends.append(t)
        avg_trend = sum(trends) / len(trends) if trends else 0.02

        proj_6m = round(price * (1 + avg_trend * 6 / 12))
        proj_12m = round(price * (1 + avg_trend))
        direction = '📈' if avg_trend > 0 else '📉' if avg_trend < 0 else '➡️'

        lines.append(f"### {gov} — {pt.capitalize()} Outlook\n")
        lines.append(f"**Current avg:** {_fmt_price(price)}")
        lines.append(f"**Annual trend:** {direction} {avg_trend*100:+.1f}%")
        lines.append(f"**6-month projection:** {_fmt_price(proj_6m)}")
        lines.append(f"**12-month projection:** {_fmt_price(proj_12m)}")
        lines.append(f"\n*Based on historical trends and market data. See /analyze → Price Forecast for full monthly breakdown.*")
    else:
        lines.append("**National 2026 Outlook:**\n")
        lines.append("- **Coastal areas**: +3–6% driven by tourism and expat demand")
        lines.append("- **Tunis metro**: +2–4% — stable premium market")
        lines.append("- **Sousse corridor**: +4–7% — strongest growth signal")
        lines.append("- **Interior regions**: flat to +2% — infrastructure-dependent")
        lines.append("- **Sfax**: +2–3% — industrial demand supporting prices")
        lines.append("\n💡 *Use /analyze → Price Forecast for delegation-level 12-month charts*")

    return {
        'message': '\n'.join(lines),
        'suggestions': [
            "Forecast for Sousse apartments?",
            "Which areas will grow fastest in 2026?",
            "Impact of interest rates on prices?",
            "Climate stress effect on coastal areas?",
        ],
        'intent': 'forecast',
    }


def _mortgage_response(budget: Optional[int]) -> dict:
    bct_rate = 8.0  # Current BCT rate estimate
    lines = [
        "## Mortgage & Financing Guide — Tunisia\n",
        f"**Current BCT base rate:** ~{bct_rate}%",
        "**Typical mortgage rate:** 9–12% (BCT + bank spread)",
        "**Max loan-to-value (LTV):** 70–80%",
        "**Max term:** 20–25 years",
        "**Required down payment:** 20–30%\n",
    ]
    if budget:
        loan = int(budget * 0.75)  # 75% LTV
        monthly = round(loan * (0.10/12) / (1 - (1 + 0.10/12)**(-240)), 0)
        lines.append(f"**Example for {budget:,} TND property:**")
        lines.append(f"- Down payment (25%): {int(budget*0.25):,} TND")
        lines.append(f"- Loan amount: {loan:,} TND")
        lines.append(f"- Monthly payment (20yr, 10%): ~{int(monthly):,} TND/month")
        lines.append(f"- Required annual income: ~{int(monthly*12/0.35):,} TND (35% DTI rule)")

    lines.append("\n**Eligible programmes:**")
    lines.append("- FOPROLOS (social housing subsidies)")
    lines.append("- First-time buyer grants from BH/STB/BIAT")
    lines.append("- Diaspora remittance-backed mortgages\n")
    lines.append("*Rates vary by bank and borrower profile. BCT policy changes affect rates.*")

    return {
        'message': '\n'.join(lines),
        'suggestions': [
            "Monthly payment for 300,000 TND house?",
            "First-time buyer subsidies in Tunisia?",
            "How much can I borrow with 60k/year income?",
            "Compare mortgage banks in Tunisia",
        ],
        'intent': 'mortgage',
    }


def _compare_response(msg: str) -> dict:
    # Try to find two locations
    found_govs = []
    for alias, canonical in sorted(GOV_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in msg.lower() and canonical not in found_govs:
            found_govs.append(canonical)
        if len(found_govs) == 2:
            break

    if len(found_govs) == 2:
        g1, g2 = found_govs
        i1 = GOV_INDEX.get(g1, {})
        i2 = GOV_INDEX.get(g2, {})
        lines = [f"## {g1} vs {g2} — Comparison\n"]
        for pt, label in [('apartment', 'Apartment'), ('house', 'House'), ('land', 'Land')]:
            p1 = i1.get(pt)
            p2 = i2.get(pt)
            if p1 and p2:
                winner = g1 if p1 < p2 else g2
                lines.append(f"**{label}:** {g1} {_fmt_price(p1)} vs {g2} {_fmt_price(p2)} → {winner} more affordable")
        lines.append(f"\n**Coastal:** {'Yes 🌊' if i1.get('is_coastal') else 'No'} vs {'Yes 🌊' if i2.get('is_coastal') else 'No'}")
        lines.append(f"**Delegations:** {i1.get('count', '?')} vs {i2.get('count', '?')}")
        lines.append("\n*Visit /analyze → Market Dashboard to see full side-by-side price analytics*")
        return {
            'message': '\n'.join(lines),
            'suggestions': [
                f"Investment yield in {g1}?",
                f"Forecast for {g2}?",
                "Top 5 affordable coastal areas?",
            ],
            'intent': 'compare',
        }

    return {
        'message': "I'd be happy to compare two governorates for you! Please mention both names, e.g. *\"Compare Sousse vs Sfax\"* or *\"Tunis vs Nabeul apartments\"*.",
        'suggestions': ['Compare Tunis vs Sousse', 'Compare Sfax vs Nabeul', 'Compare Gabès vs Monastir'],
        'intent': 'compare',
    }


def _climate_response(gov: Optional[str]) -> dict:
    lines = ["## Climate Risk — Tunisia Real Estate\n"]
    if gov:
        is_coastal = GOV_INDEX.get(gov, {}).get('is_coastal', False)
        lines.append(f"### {gov}\n")
        if is_coastal:
            lines.append("⚠️ **High climate exposure** — coastal governorate\n")
            lines.append("**Key risks:**")
            lines.append("- Sea level rise: 0.3–0.8m projected by 2050")
            lines.append("- Coastal flooding events increasing in frequency")
            lines.append("- Some low-lying areas face insurance premium increases")
            lines.append("- Short-term demand remains strong (tourism)")
            lines.append("\n**Recommendation:** Focus on higher-elevation properties within coastal zones")
        else:
            lines.append("✅ **Lower coastal risk** — inland governorate\n")
            lines.append("**Key risks:**")
            lines.append("- Extreme heat events (40°C+ summers becoming more frequent)")
            lines.append("- Water scarcity concerns for agricultural land")
            lines.append("- Some desertification risk in southern governorates")
            lines.append("\n**Recommendation:** Check water availability for land investments")
    else:
        lines.append("**Tunisia Climate Risk Overview:**\n")
        lines.append("🔴 **High risk:** Médenine, Gabès, Sfax (coastal + industrial)")
        lines.append("🟠 **Medium-high:** Tunis, Nabeul, Sousse, Monastir (coastal)")
        lines.append("🟡 **Medium:** Bizerte, Mahdia, Ariana")
        lines.append("🟢 **Lower risk:** Kairouan, Siliana, Kasserine (inland)")
        lines.append("\n💡 *Run the Climate Stress scenario in /simulate to model price impact*")

    return {
        'message': '\n'.join(lines),
        'suggestions': [
            "Climate risk in Nabeul?",
            "Best low-risk investment areas?",
            "How does climate affect property prices?",
            "Simulate climate stress scenario",
        ],
        'intent': 'climate',
    }


def _advice_response(gov: Optional[str], prop_type: Optional[str], budget: Optional[int]) -> dict:
    pt = prop_type or 'apartment'
    lines = ["## Personalized Advice\n"]

    if budget and gov:
        info = GOV_INDEX.get(gov, {})
        price = info.get(pt, 2000) or 2000
        area = int(budget / price)
        lines.append(f"With **{budget:,} TND** budget in **{gov}** for a **{pt}**:\n")
        lines.append(f"- You can acquire approximately **{area} m²**")
        lines.append(f"- That's a {'large' if area > 100 else 'medium' if area > 60 else 'compact'} property")
        if area < 50:
            lines.append("- Consider increasing budget or exploring more affordable delegations")
        lines.append(f"\n**Best delegations in {gov} to explore:**")
        gov_dels = GOV_INDEX.get(gov, {}).get('delegations', [])[:5]
        for d in gov_dels:
            lines.append(f"  • {d}")
        lines.append("\n**Next steps:**")
        lines.append("1. Check /analyze → Price Forecast for individual delegation trends")
        lines.append("2. Run a simulation on /simulate to model future prices")
        lines.append("3. Use /valuate to get a precise property valuation")

    elif budget:
        nat_prices = {pt: [v.get(pt) for v in GOV_INDEX.values() if v.get(pt)] for pt in ['apartment', 'house', 'land']}
        lines.append(f"With **{budget:,} TND** budget:\n")
        for ptype, prices in nat_prices.items():
            if prices:
                avg = sum(prices) / len(prices)
                area = int(budget / avg)
                lines.append(f"- **{ptype.capitalize()}**: ~{area} m² at national avg ({_fmt_price(int(avg))})")
        lines.append("\n**Recommended affordable regions:**")
        affordable = _top_govs('apartment', n=4, ascending=True)
        for g, p in affordable:
            area = int(budget / p)
            lines.append(f"  • {g}: {area} m² ({_fmt_price(p)})")

    else:
        lines.append("Here's my general advice for the Tunisian market in 2026:\n")
        lines.append("**🏠 Buyers:**")
        lines.append("- Northern coastal areas offer strong appreciation + rental demand")
        lines.append("- Sfax and Sousse inland delegations are undervalued relative to amenities")
        lines.append("- First-time buyers: check FOPROLOS social housing programme\n")
        lines.append("**📈 Investors:**")
        lines.append("- Apartments in Nabeul/Hammamet: 4-6% rental yield from tourism")
        lines.append("- Monastir/Mahdia: growing expat demand, stable prices")
        lines.append("- Avoid highly speculative positions in areas with high climate exposure\n")
        lines.append("**📊 Always check:**")
        lines.append("- /analyze for real price data and 12-month forecasts")
        lines.append("- /simulate to model market scenarios")
        lines.append("- /valuate for accurate property valuations")

    return {
        'message': '\n'.join(lines),
        'suggestions': [
            "Advice for 200,000 TND budget in Tunis?",
            "Best neighbourhoods for young families?",
            "Investment vs primary residence — what's better now?",
            "How to negotiate property price?",
        ],
        'intent': 'advice',
    }


def _general_response(msg: str) -> dict:
    lower = msg.lower()

    # Catch some common questions
    if any(w in lower for w in ['hello', 'hi', 'hey', 'bonjour', 'salam']):
        return _greeting_response()

    if 'average' in lower and 'price' in lower:
        gov = _extract_gov(msg)
        pt = _extract_prop_type(msg)
        return _price_response(gov, pt)

    if any(w in lower for w in ['best area', 'best region', 'where to buy', 'where should', 'recommend area']):
        return {
            'message': "## Best Areas to Buy in Tunisia 2026\n\n**For primary residence:**\n- Ariana, La Manouba: Suburban Tunis, good value\n- Nabeul (inland): Growing, affordable\n- Monastir: Quality of life, stable prices\n\n**For investment/rental:**\n- Hammamet corridor (Nabeul): Tourism-driven yields\n- Sousse: Strong university + business demand\n- Sfax: Industrial stability, undervalued\n\n**For affordable housing:**\n- Sidi Bouzid, Gafsa: Very low prices, long-term upside if infrastructure improves\n- Jendouba, Béja: Agricultural region, cheap land\n\n*Use /analyze for data-driven comparison of all 278 delegations*",
            'suggestions': ['Best investment in Nabeul?', 'Prices in Ariana?', 'Compare Monastir vs Sousse', 'Simulate market growth'],
            'intent': 'advice',
        }

    return {
        'message': "I'm here to help with Tunisia's real estate market. You can ask me about:\n\n- **Prices** by governorate or delegation\n- **Investment** yields and opportunities\n- **Forecasts** and market trends\n- **Mortgages** and financing\n- **Climate risks** by area\n- **Comparisons** between regions\n\nWhat would you like to know?",
        'suggestions': [
            "Apartment prices in Tunis?",
            "Best investment in 2026?",
            "Compare Sousse vs Nabeul",
            "Mortgage guide Tunisia",
        ],
        'intent': 'general',
    }


# ── Main entry point ──────────────────────────────────────────────────────────
def process_message(message: str, session_context: dict) -> dict:
    """
    Process a user message and return a structured response.
    session_context: dict with keys like 'history', 'user_budget', 'user_goal', 'language'
    """
    intents = _detect_intent(message)
    gov = _extract_gov(message)
    prop_type = _extract_prop_type(message)
    budget = _extract_budget(message) or session_context.get('user_budget')
    language = session_context.get('language', 'en')

    # Update session context
    if gov:
        session_context['last_gov'] = gov
    if prop_type:
        session_context['last_prop_type'] = prop_type
    if budget:
        session_context['user_budget'] = budget

    # Use last known context if not mentioned
    if not gov:
        gov = session_context.get('last_gov')
    if not prop_type:
        prop_type = session_context.get('last_prop_type')

    primary = intents[0] if intents else 'general'

    if primary == 'greeting':
        result = _greeting_response()
    elif primary in ('price',):
        result = _price_response(gov, prop_type)
    elif primary == 'invest':
        result = _invest_response(gov, prop_type, budget)
    elif primary == 'forecast':
        result = _forecast_response(gov, prop_type)
    elif primary == 'mortgage':
        result = _mortgage_response(budget)
    elif primary == 'compare':
        result = _compare_response(message)
    elif primary == 'climate':
        result = _climate_response(gov)
    elif primary == 'advice':
        result = _advice_response(gov, prop_type, budget)
    elif primary == 'simulate':
        result = {
            'message': "## Market Simulation\n\nEstateMind's multi-agent simulator lets you model how prices evolve under different economic scenarios:\n\n- **Baseline** — Normal market conditions\n- **Monetary Easing** — Rate cuts boost demand\n- **Interest Rate Hike** — Cooling effect on prices\n- **Speculative Boom** — Rapid price escalation\n- **Climate Stress** — Coastal depreciation\n- **Infrastructure Push** — Demand surge in investment zones\n\nHead to **/simulate** to run any scenario with up to 500 agents over 36 months and see the Price Map update in real time.",
            'suggestions': ['Simulate monetary easing', 'Climate stress impact?', 'Speculative boom scenario', 'What does BCT rate cut mean for prices?'],
            'intent': 'simulate',
        }
    elif primary in ('location', 'type'):
        result = _price_response(gov, prop_type)
    else:
        result = _general_response(message)

    result['session_context'] = session_context
    return result

"""
config/admin_site.py

Overrides Django's default AdminSite.get_app_list() to produce a
professionally organised, logically grouped admin index — independent
of the app each model belongs to.

Apply by importing this module once before any URL routing:
    import config.admin_site  # noqa: F401
"""
from django.contrib import admin


# ── Desired section order ──────────────────────────────────────────────────────
# Each entry: (virtual_key, display_name, [(actual_app_label, ModelObjectName)])
#
# Sections are rendered in this exact order on the index page.
# Models listed but not registered (or not permitted) are silently skipped.
# Any registered models NOT listed here land in the catch-all at the bottom.
# ──────────────────────────────────────────────────────────────────────────────

_SECTIONS = [
    (
        "geographic_data",
        "Geographic Data",
        [
            ("core", "Region"),
            ("core", "Delegation"),
        ],
    ),
    (
        "market_data",
        "Market Data & Properties",
        [
            ("core", "Property"),
            ("core", "PriceTrend"),
            ("core", "ClimateRisk"),
            ("core", "DelegationMarketSnapshot"),
            ("core", "DelegationMarketSegment"),
        ],
    ),
    (
        "price_intelligence",
        "Price Intelligence & Valuation",
        [
            ("valuation",  "ValuationRequest"),
            ("core",       "Valuation"),
            ("forecast",   "DelegationPriceData"),
            ("forecast",   "DelegationForecast"),
        ],
    ),
    (
        "simulation",
        "Market Simulation",
        [
            ("simulation", "SimulationRun"),
        ],
    ),
    (
        "investor_intelligence",
        "Investor Intelligence",
        [
            ("investor", "PortfolioAsset"),
            ("investor", "ScanResult"),
        ],
    ),
    (
        "data_pipeline",
        "Data Collection Pipeline",
        [
            ("scraper", "ScrapeSource"),
            ("scraper", "ScrapeJob"),
            ("scraper", "ScrapedListing"),
        ],
    ),
    (
        "platform_users",
        "Platform Users",
        [
            ("users", "User"),
            ("users", "UserActivity"),
            ("users", "SavedProperty"),
            ("users", "UserValuation"),
            ("users", "Portfolio"),
        ],
    ),
    (
        "billing",
        "Billing & Payments",
        [
            ("billing", "StripeCustomer"),
            ("billing", "Subscription"),
            ("billing", "Payment"),
        ],
    ),
    (
        "campaign",
        "Campaign & Outreach",
        [
            ("campaign", "Participant"),
        ],
    ),
    (
        "platform_admin",
        "Platform Administration",
        [
            ("auth",             "Group"),
            ("token_blacklist",  "OutstandingToken"),
            ("token_blacklist",  "BlacklistedToken"),
        ],
    ),
]


# ── AdminSite subclass ─────────────────────────────────────────────────────────

class _EstateMindAdminSite(admin.AdminSite):

    def get_app_list(self, request, app_label=None):
        """
        Returns the custom-ordered, cross-app grouped model list for the admin
        index.  Falls back to the standard alphabetical ordering when
        `app_label` is supplied (e.g. when browsing a specific app's page).
        """
        app_dict = self._build_app_dict(request, app_label)

        # App-specific view: preserve default ordering so breadcrumbs/back
        # links work correctly.
        if app_label:
            app_list = sorted(app_dict.values(), key=lambda x: x["name"].lower())
            for app in app_list:
                app["models"].sort(key=lambda x: x["name"])
            return app_list

        # Build a flat lookup keyed by (app_label, object_name)
        lookup: dict = {}
        for app_data in app_dict.values():
            al = app_data["app_label"]
            for model in app_data["models"]:
                lookup[(al, model["object_name"])] = model

        result = []
        placed: set = set()

        for section_key, section_name, model_specs in _SECTIONS:
            group_models = []
            for al, obj_name in model_specs:
                key = (al, obj_name)
                if key in lookup and key not in placed:
                    group_models.append(lookup[key])
                    placed.add(key)

            if not group_models:
                continue

            result.append(
                {
                    "name":              section_name,
                    "app_label":         section_key,
                    "app_url":           "#",
                    "has_module_perms":  True,
                    "models":            group_models,
                }
            )

        # Any registered model not covered by _SECTIONS goes to the bottom
        leftover = [m for key, m in lookup.items() if key not in placed]
        if leftover:
            leftover.sort(key=lambda x: x["name"])
            result.append(
                {
                    "name":             "Other",
                    "app_label":        "_other",
                    "app_url":          "#",
                    "has_module_perms": True,
                    "models":           leftover,
                }
            )

        return result


# ── Compatibility patch for Context.__copy__ (Django + Python mismatches) ───
# Some Python/Django combinations expose an issue where BaseContext.__copy__
# calls `super().__copy__()` which can return an object that doesn't allow
# attribute assignment (raising: "'super' object has no attribute 'dicts'").
# Apply a robust fallback here to avoid template rendering failures in the
# admin change list and other template paths that rely on Context.copy().
import copy as _copy

try:
    from django.template.context import BaseContext
except Exception:
    BaseContext = None

if BaseContext is not None:
    _orig_basecontext_copy = getattr(BaseContext, "__copy__", None)

    def _patched_basecontext_copy(self):
        # First try the original implementation and fall back to a safe
        # shallow-duplicate strategy if it fails for any reason.
        if _orig_basecontext_copy is not None:
            try:
                dup = _orig_basecontext_copy(self)
            except Exception:
                dup = object.__new__(self.__class__)
        else:
            dup = object.__new__(self.__class__)

        # Ensure the internal dict stack is copied so template rendering can
        # safely mutate the duplicate context.
        try:
            dup.dicts = [d.copy() if isinstance(d, dict) else d for d in getattr(self, "dicts", [])]
            dup._dict = dup.dicts[-1] if dup.dicts else {}
        except Exception:
            # Keep best-effort; if this fails we still return the duplicate
            # to avoid crashing template rendering.
            pass

        # Shallow-copy other attributes where possible.
        try:
            for k, v in getattr(self, "__dict__", {}).items():
                if k in ("dicts", "_dict"):
                    continue
                try:
                    setattr(dup, k, _copy.copy(v))
                except Exception:
                    setattr(dup, k, v)
        except Exception:
            pass

        return dup

    # Install the patched copy implementation on BaseContext
    BaseContext.__copy__ = _patched_basecontext_copy


# ── Swap the class on the existing singleton ───────────────────────────────────
# All @admin.register() decorators target admin.site (the singleton created
# at Django startup).  We simply upgrade its class in-place so it keeps
# every registered model while gaining our custom get_app_list logic.

admin.site.__class__ = _EstateMindAdminSite

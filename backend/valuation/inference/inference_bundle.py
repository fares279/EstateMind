"""Dynamic serving bundles for EstateMind valuation artifacts.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import KNNImputer
from sklearn.neighbors import BallTree

if TYPE_CHECKING:
    from .model_registry import ModelHandle


REFERENCE_DATASET_CANDIDATES = (
    Path("backend/valuation/repo_clone/data/csv/preprocessed/final_listings_preprocessed.csv"),
    Path("frontend/repo_clone/data/csv/preprocessed/final_listings_preprocessed.csv"),
    Path("data/csv/preprocessed/final_listings_preprocessed.csv"),
    Path("data/csv/final_listings_preprocessed.csv"),
)

# trimmed constants (same as upstream)
CATEGORICAL_COLUMNS = ("city", "governorate", "property_type", "transaction_type")
NUMERIC_COLUMNS = (
    "price_tnd",
    "surface_m2",
    "price_per_m2",
    "rooms",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
)


@dataclass
class PredictionResult:
    estimated_price: int
    price_per_m2: int
    prediction_mode: str
    warnings: list[str]
    model_info: dict[str, Any]
    feature_frame: pd.DataFrame | None = None
    uncertainty_reasons: list[str] = field(default_factory=list)
    ood_flags: list[str] = field(default_factory=list)


def _raw_text_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _normalize_text_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = text.replace("_", " ").replace("/", " ")
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text


class _ServingProcessor:
    def __init__(self, reference_df: pd.DataFrame, *, radius_km: float = 1.0, n_geo_clusters: int = 20) -> None:
        self.radius_km = radius_km
        self.n_geo_clusters = n_geo_clusters
        self.reference_df = self._clean(reference_df)
        self.numeric_columns = [col for col in NUMERIC_COLUMNS if col in self.reference_df.columns and self.reference_df[col].notna().any()]
        self.imputer = KNNImputer(n_neighbors=5, weights="distance")
        if self.numeric_columns:
            self.reference_df[self.numeric_columns] = self.imputer.fit_transform(self.reference_df[self.numeric_columns])

        self.categorical_fill: dict[str, str] = {}
        for col in list(CATEGORICAL_COLUMNS) + ["city_governorate"]:
            if col in self.reference_df.columns:
                mode = self.reference_df[col].mode(dropna=True)
                fill_val = str(mode.iat[0]) if not mode.empty else "unknown"
                self.categorical_fill[col] = fill_val
                self.reference_df[col] = self.reference_df[col].fillna(fill_val)

        coords = self.reference_df[["latitude", "longitude"]].apply(pd.to_numeric, errors="coerce")
        valid = coords.notna().all(axis=1)
        coords_valid = coords[valid]
        if len(coords_valid) == 0:
            raise ValueError("Reference dataset does not contain any usable latitude/longitude rows")

        self.kmeans = KMeans(
            n_clusters=min(self.n_geo_clusters, len(coords_valid)),
            random_state=42,
            n_init=10,
        ).fit(coords_valid.values)
        self.tree = BallTree(np.radians(coords_valid.values), metric="haversine")

        self.train_prices = pd.to_numeric(self.reference_df["price_tnd"], errors="coerce").fillna(0.0).to_numpy()
        self.global_price = float(np.nanmean(self.train_prices)) if len(self.train_prices) else 0.0

        ppm2 = self.reference_df["price_tnd"] / self.reference_df["surface_m2"].replace({0: np.nan})
        self.city_governorate_price_m2 = (
            pd.DataFrame({"key": self.reference_df.get("city_governorate"), "ppm2": ppm2})
            .dropna(subset=["key", "ppm2"])
            .assign(key=lambda df: df["key"].map(_normalize_text_key))
            .groupby("key", dropna=True)["ppm2"]
            .median()
            .to_dict()
        )
        self.city_avg_price_m2 = (
            pd.DataFrame({"key": self.reference_df["city"], "ppm2": ppm2})
            .dropna(subset=["key", "ppm2"])
            .assign(key=lambda df: df["key"].map(_normalize_text_key))
            .groupby("key", dropna=True)["ppm2"]
            .median()
            .to_dict()
        )
        self.gov_avg_price_m2 = (
            pd.DataFrame({"key": self.reference_df["governorate"], "ppm2": ppm2})
            .dropna(subset=["key", "ppm2"])
            .assign(key=lambda df: df["key"].map(_normalize_text_key))
            .groupby("key", dropna=True)["ppm2"]
            .median()
            .to_dict()
        )
        self.local_avg_price_m2 = dict(self.city_governorate_price_m2)

        city_geo = (
            self.reference_df.dropna(subset=["city", "latitude", "longitude"])
            .assign(city=lambda df: df["city"].map(_normalize_text_key))
            .groupby("city", dropna=True)[["latitude", "longitude"]]
            .median()
            .reset_index()
        )
        self.city_geo_lookup = {
            str(row["city"]): (float(row["latitude"]), float(row["longitude"]))
            for _, row in city_geo.iterrows()
        }

        gov_geo = (
            self.reference_df.dropna(subset=["governorate", "latitude", "longitude"])
            .assign(governorate=lambda df: df["governorate"].map(_normalize_text_key))
            .groupby("governorate", dropna=True)[["latitude", "longitude"]]
            .median()
            .reset_index()
        )
        self.gov_geo_lookup = {
            str(row["governorate"]): (float(row["latitude"]), float(row["longitude"]))
            for _, row in gov_geo.iterrows()
        }

        self.quantiles: dict[str, tuple[float, float]] = {}
        for col in ("price_tnd", "surface_m2"):
            if col in self.reference_df.columns and self.reference_df[col].notna().any():
                self.quantiles[col] = (
                    float(self.reference_df[col].quantile(0.01)),
                    float(self.reference_df[col].quantile(0.99)),
                )

    @staticmethod
    def _to_num(value: Any) -> float:
        if pd.isna(value):
            return float("nan")
        text = str(value).upper().replace("DT", "").replace("TND", "")
        text = re.sub(r"\s+", "", text).replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group()) if match else float("nan")

    @classmethod
    def _clean(cls, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out.drop(columns=[c for c in ("record_id", "description", "location_raw") if c in out.columns], inplace=True, errors="ignore")
        for col in NUMERIC_COLUMNS:
            if col in out.columns:
                out[col] = out[col].map(cls._to_num)
        for col in CATEGORICAL_COLUMNS:
            if col in out.columns:
                normalized = out[col].map(_normalize_text_key)
                out[col] = normalized.mask(normalized == "", np.nan)
        if "city" in out.columns and "governorate" in out.columns:
            out["city_governorate"] = out["city"].fillna("unknown") + "__" + out["governorate"].fillna("unknown")
        return out

    def _resolve_price_prior(self, frame: pd.DataFrame) -> tuple[float, list[str], list[str]]:
        warnings: list[str] = []
        ood_flags: list[str] = []
        city_key = "" if pd.isna(frame["city"].iat[0]) else str(frame["city"].iat[0]).strip()
        gov_key = "" if pd.isna(frame["governorate"].iat[0]) else str(frame["governorate"].iat[0]).strip()
        exact_key = _normalize_text_key(f"{city_key} {gov_key}") if city_key and gov_key else ""

        if exact_key and exact_key in self.local_avg_price_m2:
            return float(self.local_avg_price_m2[exact_key]), warnings, ood_flags

        if city_key and city_key in self.city_avg_price_m2:
            warnings.append("local_price_prior_fallback_city")
            if gov_key:
                ood_flags.append("local_price_prior_city_governorate_data_coverage")
            else:
                ood_flags.append("local_price_prior_governorate_missing_input")
            return float(self.city_avg_price_m2[city_key]), warnings, ood_flags

        if gov_key and gov_key in self.gov_avg_price_m2:
            warnings.append("local_price_prior_fallback_governorate")
            if city_key:
                ood_flags.append("local_price_prior_city_data_coverage")
            else:
                ood_flags.append("local_price_prior_city_missing_input")
            return float(self.gov_avg_price_m2[gov_key]), warnings, ood_flags

        warnings.append("local_price_prior_fallback_global")
        if city_key and gov_key:
            ood_flags.append("local_price_prior_governorate_data_coverage")
        else:
            ood_flags.append("local_price_prior_missing_input")
        return float(self.global_price), warnings, ood_flags

    def transform_request(self, row: dict[str, Any]) -> tuple[pd.DataFrame, list[str], list[str]]:
        warnings: list[str] = []
        ood_flags: list[str] = []
        raw_city_key = _raw_text_key(row.get("city"))
        raw_gov_key = _raw_text_key(row.get("governorate"))
        frame = pd.DataFrame([row])
        frame = self._clean(frame)

        city_key = "" if pd.isna(frame["city"].iat[0]) else str(frame["city"].iat[0]).strip()
        gov_key = "" if pd.isna(frame["governorate"].iat[0]) else str(frame["governorate"].iat[0]).strip()

        if raw_city_key and raw_city_key != city_key and city_key:
            warnings.append("city_normalization_applied")
        if raw_gov_key and raw_gov_key != gov_key and gov_key:
            warnings.append("governorate_normalization_applied")

        if city_key not in self.city_geo_lookup and frame.get("latitude", pd.Series([np.nan])).isna().iat[0]:
            if not (gov_key and gov_key in self.gov_geo_lookup):
                warnings.append("geo_lookup_missing")
                if city_key:
                    ood_flags.append("unknown_city_data_coverage")
                else:
                    ood_flags.append("unknown_city_missing_input")
        if "surface_m2" in self.quantiles:
            lo, hi = self.quantiles["surface_m2"]
            surface = float(frame["surface_m2"].iat[0]) #type:ignore
            if surface < lo or surface > hi:
                ood_flags.append("surface_out_of_range")

        if "latitude" not in frame.columns:
            frame["latitude"] = np.nan
        if "longitude" not in frame.columns:
            frame["longitude"] = np.nan
        if pd.isna(frame["latitude"].iat[0]) or pd.isna(frame["longitude"].iat[0]):
            coords = self.city_geo_lookup.get(city_key)
            if not coords and gov_key:
                coords = self.gov_geo_lookup.get(gov_key)
            if coords:
                frame.at[0, "latitude"] = coords[0]
                frame.at[0, "longitude"] = coords[1]
            else:
                warnings.append("geo_lookup_missing")

        for col in self.numeric_columns:
            if col not in frame.columns:
                frame[col] = np.nan
        if self.numeric_columns:
            frame[self.numeric_columns] = self.imputer.transform(frame[self.numeric_columns])

        for col, fill_val in self.categorical_fill.items():
            if col in frame.columns:
                frame[col] = frame[col].fillna(fill_val)
            elif col != "city_governorate":
                frame[col] = fill_val

        frame["city_governorate"] = frame["city"].fillna("unknown") + "__" + frame["governorate"].fillna("unknown")
        frame["city_governorate_lookup_key"] = (
            frame["city"].fillna("").astype(str) + " " + frame["governorate"].fillna("").astype(str)
        ).map(_normalize_text_key)
        frame["local_avg_price_m2"] = frame["city_governorate_lookup_key"].map(self.local_avg_price_m2)
        if frame["local_avg_price_m2"].isna().any():
            local_prior, prior_warnings, prior_ood_flags = self._resolve_price_prior(frame)
            frame["local_avg_price_m2"] = frame["local_avg_price_m2"].fillna(local_prior)
            warnings.extend(prior_warnings)
            ood_flags.extend(prior_ood_flags)

        frame["gov_avg_price_m2"] = frame["governorate"].map(self.gov_avg_price_m2)
        if frame["gov_avg_price_m2"].isna().any():
            frame["gov_avg_price_m2"] = frame["gov_avg_price_m2"].fillna(self.gov_avg_price_m2.get(gov_key, self.global_price))
            if gov_key and gov_key not in self.gov_avg_price_m2:
                warnings.append("gov_price_prior_fallback")
                ood_flags.append("governorate_price_prior_data_coverage")

        coords = frame[["latitude", "longitude"]].apply(pd.to_numeric, errors="coerce")
        valid = coords.notna().all(axis=1)
        frame["geo_cluster_id"] = np.nan
        frame["avg_price_1km_radius"] = np.nan
        frame["listings_density_in_area"] = np.nan
        if valid.any():
            values = coords[valid].values
            frame.loc[valid, "geo_cluster_id"] = self.kmeans.predict(values)
            query_rad = np.radians(values)
            neighbors = self.tree.query_radius(query_rad, r=self.radius_km / 6371.0)
            avg_prices: list[float] = []
            densities: list[float] = []
            area = np.pi * (self.radius_km**2)
            for idx in neighbors:
                idx_list = idx.tolist()
                if not idx_list:
                    avg_prices.append(self.global_price)
                    densities.append(0.0)
                else:
                    avg_prices.append(float(np.nanmean(self.train_prices[idx_list])))
                    densities.append(len(idx_list) / area)
            frame.loc[valid, "avg_price_1km_radius"] = avg_prices
            frame.loc[valid, "listings_density_in_area"] = densities
        else:
            warnings.append("spatial_features_missing")

        frame["size_x_local_price"] = frame["surface_m2"] * frame["local_avg_price_m2"]
        return frame, warnings, ood_flags


@dataclass
class InferenceBundle:
    estimator: Any
    model_name: str
    property_scope: str
    reference_rows: int
    feature_columns: list[str]
    processor: Optional[_ServingProcessor]
    source_path: Path
    uses_proxy_price_features: bool = False
    version: str = "estatebundle-v1"

    @classmethod
    def from_handle(cls, handle: "ModelHandle", reference_df: pd.DataFrame | None) -> "InferenceBundle":
        estimator = handle.estimator
        if estimator is None:
            raise ValueError("Estimator must be loaded before bundle creation")
        feature_columns = list(getattr(estimator, "feature_names_", []) or [])
        if not feature_columns:
            raise ValueError("Unsupported artifact: estimator does not expose feature names")
        if handle.model_name.lower() != "catboost":
            raise ValueError("Unsupported artifact: only catboost serving bundles are implemented")

        subset = reference_df.copy() if reference_df is not None else pd.DataFrame()
        if (
            handle.scope == "by_type"
            and handle.property_type
            and handle.property_type.upper() != "ALL"
            and not subset.empty
            and "property_type" in subset.columns
        ):
            mask = subset["property_type"].astype(str).str.strip().str.lower() == handle.property_type.strip().lower()
            typed = subset[mask].copy()
            if not typed.empty:
                subset = typed
        processor: Optional[_ServingProcessor] = None
        try:
            processor = _ServingProcessor(subset) if not subset.empty else None
        except Exception:
            processor = None
        return cls(
            estimator=estimator,
            model_name=handle.model_name,
            property_scope=handle.property_type,
            reference_rows=int(len(subset)),
            feature_columns=feature_columns,
            processor=processor,
            source_path=handle.path,
            uses_proxy_price_features=("price_tnd" in feature_columns or "price_per_m2" in feature_columns),
        )

    def predict(
        self,
        mapped: dict[str, Any],
        market_context: dict[str, Any],
        cv_analysis: dict[str, Any] | None = None,
        text_analysis: dict[str, Any] | None = None,
    ) -> PredictionResult:
        seed_ppm = market_context.get("avg_price_per_m2") or market_context.get("avg_m2") or 1450
        seed_ppm = max(float(seed_ppm or 1450), 1.0)
        proxy_price = float(mapped["surface_m2"]) * seed_ppm
        proxy_rooms = int(mapped.get("bedrooms", 0)) + (1 if str(mapped.get("model_property_type") or mapped.get("property_type", "")).lower() != "terrain" else 0)
        request_row = {
            "transaction_type": str(mapped.get("transaction_type") or "sale"),
            "property_type": str(mapped.get("model_property_type") or mapped["property_type"]),
            "price_tnd": proxy_price,
            "surface_m2": float(mapped["surface_m2"]),
            "price_per_m2": seed_ppm,
            "rooms": float(mapped.get("rooms") or proxy_rooms),
            "bedrooms": float(mapped.get("bedrooms", 0)),
            "bathrooms": float(mapped.get("bathrooms", 0)),
            "governorate": str(mapped["governorate"]),
            "city": str(mapped.get("city") or mapped.get("delegation") or ""),
            "latitude": float(mapped["latitude"]) if mapped.get("latitude") is not None else np.nan,
            "longitude": float(mapped["longitude"]) if mapped.get("longitude") is not None else np.nan,
        }

        # Handle missing processor gracefully
        if self.processor is not None:
            transformed, warnings, ood_flags = self.processor.transform_request(request_row)
        else:
            warnings = ["reference_dataset_missing"]
            ood_flags = ["processor_unavailable"]
            transformed = pd.DataFrame([request_row])
            for col in self.feature_columns:
                if col not in transformed.columns:
                    transformed[col] = np.nan
            
            # Create derived features that processor would normally create
            if "city_governorate" in self.feature_columns and "city_governorate" not in transformed.columns:
                city_col = transformed["city"].fillna("unknown").astype(str) if "city" in transformed.columns else "unknown"
                gov_col = transformed["governorate"].fillna("unknown").astype(str) if "governorate" in transformed.columns else "unknown"
                transformed["city_governorate"] = city_col + "__" + gov_col
            
            # Create market context features with defaults
            if "local_avg_price_m2" in self.feature_columns and "local_avg_price_m2" not in transformed.columns:
                transformed["local_avg_price_m2"] = seed_ppm
            
            if "gov_avg_price_m2" in self.feature_columns and "gov_avg_price_m2" not in transformed.columns:
                transformed["gov_avg_price_m2"] = seed_ppm
            
            if "size_x_local_price" in self.feature_columns and "size_x_local_price" not in transformed.columns:
                transformed["size_x_local_price"] = float(mapped.get("surface_m2", 0)) * seed_ppm

        # Integrate CV and sentiment signals
        cv_signal_multiplier = 1.0
        text_signal_multiplier = 1.0

        if cv_analysis is not None:
            try:
                quality_score = float(cv_analysis.get("quality_score", 0.5))
                coverage_score = float(cv_analysis.get("coverage_score", 0.5))
                cv_confidence = float(cv_analysis.get("confidence", 0.0))
                image_count = int(cv_analysis.get("image_count", 0))

                # CV signal: comprehensive images indicate better property condition
                cv_signal_multiplier = 1.0 + (coverage_score * 0.1) + (quality_score * 0.05)
                cv_signal_multiplier = min(cv_signal_multiplier, 1.2)  # Cap at 20% boost
                if cv_confidence > 0.7:
                    warnings.append("cv_confidence_high")
                if image_count > 0:
                    warnings.append(f"cv_images_analyzed_{image_count}")
            except Exception as e:
                warnings.append(f"cv_signal_error: {str(e)[:50]}")

        if text_analysis is not None:
            try:
                sentiment_score = float(text_analysis.get("sentiment_score", 0.5))
                description_quality = str(text_analysis.get("description_quality", "poor")).lower()

                # Sentiment signal: positive descriptions correlate with buyer appeal
                text_signal_multiplier = 0.95 + (sentiment_score * 0.1)  # Range [0.95, 1.05]
                if description_quality == "good":
                    text_signal_multiplier += 0.05
                    warnings.append("text_quality_good")
                elif description_quality == "poor":
                    text_signal_multiplier -= 0.05
                    ood_flags.append("text_quality_poor")

                text_signal_multiplier = max(0.9, min(text_signal_multiplier, 1.15))
            except Exception as e:
                warnings.append(f"text_signal_error: {str(e)[:50]}")

        missing_columns = [col for col in self.feature_columns if col not in transformed.columns]
        if missing_columns:
            raise ValueError(f"schema mismatch: missing transformed columns {missing_columns}")
        features = transformed[self.feature_columns].copy()
        
        # Get categorical feature indices from model if available
        cat_feature_indices = []
        if hasattr(self.estimator, "get_cat_feature_indices"):
            try:
                cat_feature_indices = list(self.estimator.get_cat_feature_indices())
            except Exception:
                pass
        
        # If no cat_feature_indices, use known categorical feature names
        if not cat_feature_indices:
            categorical_names = {"transaction_type", "property_type", "governorate", "city", "city_governorate"}
            cat_feature_indices = [
                i for i, col in enumerate(self.feature_columns) if col in categorical_names
            ]
        
        # Convert categorical features to proper strings FIRST (before any other handling)
        # This is crucial: fill NaN -> "unknown", then convert to plain string dtype
        for idx in cat_feature_indices:
            if idx < len(self.feature_columns):
                col = self.feature_columns[idx]
                if col in features.columns:
                    # Fill NaN first, then convert to plain string (not StringDtype)
                    features[col] = features[col].fillna("unknown").astype(str)
        
        # Handle NaN in numeric features
        for i, col in enumerate(self.feature_columns):
            if i not in cat_feature_indices and col in features.columns:
                if features[col].isna().any():
                    median_val = features[col].median()
                    features[col] = features[col].fillna(median_val if not pd.isna(median_val) else 0)
        
        pred_log = float(self.estimator.predict(features)[0])
        pred_price = int(round(float(np.expm1(pred_log))))

        # Apply multi-signal adjustment to price
        multi_signal_adjustment = cv_signal_multiplier * text_signal_multiplier
        if multi_signal_adjustment != 1.0:
            pred_price = int(round(pred_price * multi_signal_adjustment))
            warnings.append(f"catboost_signal_adjustment_{multi_signal_adjustment:.2f}")

        pred_ppm = int(round(pred_price / max(float(mapped["surface_m2"]), 1.0)))

        if self.uses_proxy_price_features:
            warnings.append("proxy_price_features_used")

        uncertainty_reasons = []
        if ood_flags:
            uncertainty_reasons.extend([f"ood:{flag}" for flag in ood_flags])
        if warnings:
            uncertainty_reasons.extend(warnings)

        return PredictionResult(
            estimated_price=max(pred_price, 1),
            price_per_m2=max(pred_ppm, 1),
            prediction_mode="catboost_by_type" if self.property_scope != "ALL" else "catboost_global",
            warnings=sorted(set(warnings)),
            model_info={
                "bundle_version": self.version,
                "model_name": self.model_name,
                "property_scope": self.property_scope,
                "source_path": str(self.source_path),
                "reference_rows": self.reference_rows,
                "cv_signals_applied": cv_analysis is not None,
                "text_signals_applied": text_analysis is not None,
            },
            feature_frame=features,
            uncertainty_reasons=sorted(set(uncertainty_reasons)),
            ood_flags=sorted(set(ood_flags)),
        )


def load_reference_dataset(reference_path: str | Path | None = None) -> pd.DataFrame:
    root = Path(__file__).resolve().parents[3]
    if reference_path is not None:
        path = Path(reference_path)
        resolved = path if path.is_absolute() else root / path
        if not resolved.exists():
            raise FileNotFoundError(f"Reference dataset not found: {resolved}")
        return pd.read_csv(resolved)

    for rel_path in REFERENCE_DATASET_CANDIDATES:
        resolved = root / rel_path
        if resolved.exists():
            return pd.read_csv(resolved)
    raise FileNotFoundError("Could not locate a preprocessed listings dataset for serving bundle reconstruction")

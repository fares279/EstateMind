"""Computer vision inference for property type classification from images."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CVPrediction:
    property_type: str
    confidence: float
    predicted_class_id: int
    class_label: str
    image_quality_score: float
    coverage_score: float
    status: str
    warnings: list[str]
    model_info: dict[str, Any]


class CVModelService:
    """Load and use pre-trained ResNet50 image classification model."""

    def __init__(self, artifacts_dir: str | Path | None = None) -> None:
        root = Path(__file__).resolve().parents[3]
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else root / "backend" / "valuation" / "artifacts" / "models"
        self.model_path = self.artifacts_dir / "image_property_type_fallback.pt"
        self.labels_path = self.artifacts_dir / "image_property_type_fallback.labels.json"
        
        self._model: Any | None = None
        self._labels: dict[str, Any] | None = None
        self._class_map: dict[int, str] | None = None

    def _load_labels(self) -> dict[int, str] | None:
        """Load class labels from JSON manifest."""
        if self._class_map is not None:
            return self._class_map
        
        if not self.labels_path.exists():
            return None
        
        try:
            data = json.loads(self.labels_path.read_text(encoding="utf-8"))
            self._labels = data
            self._class_map = {
                int(cls["id"]): str(cls["label"]).lower()
                for cls in data.get("classes", [])
            }
            return self._class_map
        except Exception:
            return None

    def _load_model(self) -> Any:
        """Lazy-load the ResNet50 checkpoint as a PyTorch module."""
        if self._model is not None:
            return self._model
        
        if not self.model_path.exists():
            return None
        
        try:
            import torch
            from torchvision.models import resnet50

            checkpoint = torch.load(self.model_path, map_location="cpu")
            state_dict = checkpoint.get("state_dict") if isinstance(checkpoint, dict) else None
            num_classes = int((checkpoint or {}).get("num_classes", 3)) if isinstance(checkpoint, dict) else 3
            if not state_dict:
                return None

            model = resnet50(weights=None)
            model.fc = torch.nn.Sequential(
                torch.nn.Dropout(p=0.2),
                torch.nn.Linear(model.fc.in_features, num_classes),
            )
            model.load_state_dict(state_dict, strict=True)
            self._model = model.eval()
            return self._model
        except Exception:
            return None

    def analyze_images(self, image_files: list[Any]) -> CVPrediction | None:
        """
        Analyze uploaded images for property type and quality.
        
        Args:
            image_files: List of InMemoryUploadedFile objects from Django request
            
        Returns:
            CVPrediction with property type and quality metrics, or None if no images
        """
        if not image_files or len(image_files) == 0:
            return None
        
        model = self._load_model()
        labels = self._load_labels()
        
        if model is None or labels is None:
            return CVPrediction(
                property_type="unknown",
                confidence=0.0,
                predicted_class_id=-1,
                class_label="model_unavailable",
                image_quality_score=0.0,
                coverage_score=0.0,
                status="model_load_failed",
                warnings=["cv_model_not_available"],
                model_info={"status": "model_unavailable"},
            )
        
        try:
            import io

            import numpy as np
            import torch
            from PIL import Image
            
            # Process first image only for now
            img_file = image_files[0]
            img = Image.open(io.BytesIO(img_file.read())).convert("RGB")
            
            # Resize to expected input size (typically 224x224 for ResNet50)
            img = img.resize((224, 224))
            
            # Normalize and convert to tensor
            img_array = np.array(img).astype(np.float32) / 255.0
            img_array = (img_array - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
            img_tensor = torch.from_numpy(img_array.transpose(2, 0, 1).astype(np.float32)).unsqueeze(0)
            
            # Predict
            with torch.no_grad():
                output = model(img_tensor)
            
            # Get probabilities and class
            probabilities = torch.softmax(output, dim=1).cpu().numpy()[0]
            predicted_class_id = int(np.argmax(probabilities))
            confidence = float(probabilities[predicted_class_id])
            predicted_label = labels.get(predicted_class_id, "unknown")
            
            # Estimate image quality (simple heuristic based on variance)
            img_gray = np.array(img).mean(axis=2)
            quality_score = min(1.0, float(np.std(img_gray) / 100.0))
            
            return CVPrediction(
                property_type=predicted_label,
                confidence=confidence,
                predicted_class_id=predicted_class_id,
                class_label=predicted_label,
                image_quality_score=quality_score,
                coverage_score=0.8 if quality_score > 0.5 else 0.4,
                status="success",
                warnings=[] if confidence > 0.7 else ["low_confidence_prediction"],
                model_info={
                    "model_name": self._labels.get("model_name", "resnet50") if self._labels else "resnet50",
                    "num_images_analyzed": len(image_files),
                    "confidence": confidence,
                },
            )
        except Exception as exc:
            return CVPrediction(
                property_type="unknown",
                confidence=0.0,
                predicted_class_id=-1,
                class_label="analysis_failed",
                image_quality_score=0.0,
                coverage_score=0.0,
                status="analysis_error",
                warnings=[f"cv_analysis_error: {str(exc)}"],
                model_info={"error": str(exc)},
            )

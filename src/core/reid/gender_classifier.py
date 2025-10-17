"""
Gender Classification Module for ReID Enhancement

Classifies person crops as Male/Female/Unknown to improve ReID matching accuracy.
Gender is used as a pre-filter before embedding similarity matching.

Uses OpenCV DNN with lightweight Caffe model for fast CPU inference (~5-10ms).
"""

import numpy as np
import cv2
from typing import Tuple, Optional
import os


class GenderClassifier:
    """
    Lightweight gender classifier using OpenCV DNN.
    
    Uses pre-trained Caffe model (GilLevi Age-Gender) for fast CPU inference.
    Model size: ~44MB, Inference: ~5-10ms per person, Accuracy: ~90%
    """
    
    def __init__(self, confidence_threshold: float = 0.6):
        """
        Initialize gender classifier.
        
        Args:
            confidence_threshold: Minimum confidence to assign gender (0.0-1.0)
        """
        # Allow overriding threshold via environment variable
        try:
            env_thr = os.environ.get("GENDER_CONFIDENCE_THRESHOLD")
            self.confidence_threshold = float(env_thr) if env_thr is not None else confidence_threshold
        except Exception:
            self.confidence_threshold = confidence_threshold
        self.enabled = int(os.environ.get("GENDER_CLASSIFICATION_ENABLED", "1")) == 1
        self.model = None
        
        if self.enabled:
            # Try ONNX model first (more accurate), fallback to Caffe
            model_dir = "/app/models"
            onnx_model = f"{model_dir}/gender_googlenet.onnx"
            prototxt = f"{model_dir}/gender_deploy.prototxt"
            caffemodel = f"{model_dir}/gender_model.caffemodel"
            
            # Priority 1: ONNX GoogleNet (more accurate)
            if os.path.exists(onnx_model):
                try:
                    self.model = cv2.dnn.readNetFromONNX(onnx_model)
                    self.model_type = "ONNX"
                    print(f"🚻 Gender Classification: Enabled (ONNX GoogleNet)")
                    print(f"   Model: GoogleNet ONNX (23MB)")
                    print(f"   Speed: ~8-15ms per person")
                    print(f"   Accuracy: ~95% (improved)")
                    print(f"   Confidence threshold: {confidence_threshold}")
                except Exception as e:
                    print(f"⚠️ ONNX gender model load error: {e}, trying Caffe fallback")
                    self.model = None
            
            # Priority 2: Caffe model (fallback)
            if self.model is None and os.path.exists(prototxt) and os.path.exists(caffemodel):
                try:
                    self.model = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
                    self.model_type = "Caffe"
                    print(f"🚻 Gender Classification: Enabled (OpenCV DNN Caffe)")
                    print(f"   Model: GilLevi Age-Gender (44MB)")
                    print(f"   Speed: ~5-10ms per person")
                    print(f"   Accuracy: ~90%")
                    print(f"   Confidence threshold: {confidence_threshold}")
                except Exception as e:
                    print(f"⚠️ Gender model load error: {e}")
                    self.enabled = False
            
            # Only disable if no model was loaded successfully
            if self.model is None:
                print(f"🚻 Gender Classification: Enabled but no model files found")
                print(f"   Expected ONNX: {onnx_model}")
                print(f"   Expected Caffe: {prototxt}, {caffemodel}")
                print(f"   Falling back to 'unknown' classification")
                self.enabled = False
        else:
            print(f"🚻 Gender Classification: Disabled")
    
    def _enhance_image(self, crop_bgr: np.ndarray) -> np.ndarray:
        """
        Enhance image quality for better gender classification.
        
        Args:
            crop_bgr: Input BGR image
            
        Returns:
            Enhanced BGR image
        """
        try:
            # Convert to LAB color space for better enhancement
            lab = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            # Merge channels back
            enhanced_lab = cv2.merge([l, a, b])
            enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            # Apply slight sharpening
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(enhanced_bgr, -1, kernel)
            
            # Blend original and sharpened (70% sharpened, 30% original)
            enhanced = cv2.addWeighted(sharpened, 0.7, enhanced_bgr, 0.3, 0)
            
            return enhanced
            
        except Exception:
            # Return original if enhancement fails
            return crop_bgr
    
    def classify(self, crop_bgr: np.ndarray) -> Tuple[str, float]:
        """
        Classify gender from person crop using ensemble approach.
        
        Args:
            crop_bgr: Person crop image (BGR format)
            
        Returns:
            Tuple of (gender, confidence) where:
                gender: 'male', 'female', or 'unknown'
                confidence: 0.0 to 1.0
        """
        if not self.enabled or crop_bgr.size == 0:
            return ('unknown', 0.0)
        
        if self.model is None:
            return ('unknown', 0.0)
        
        try:
            # Try multiple approaches for better classification
            results = []
            
            # Approach 1: Original crop
            results.append(self._classify_single_crop(crop_bgr))
            
            # Approach 2: Enhanced crop
            enhanced_crop = self._enhance_image(crop_bgr)
            results.append(self._classify_single_crop(enhanced_crop))
            
            # Approach 3: Flipped crop (horizontal flip for data augmentation)
            flipped_crop = cv2.flip(crop_bgr, 1)
            results.append(self._classify_single_crop(flipped_crop))
            
            # Ensemble voting: take the most confident result
            valid_results = [r for r in results if r[1] > 0.1]  # Filter out very low confidence
            if not valid_results:
                return ('unknown', 0.0)
            
            # Return the result with highest confidence
            best_result = max(valid_results, key=lambda x: x[1])
            return best_result
            
        except Exception as e:
            # Silently return unknown on error (don't spam logs)
            return ('unknown', 0.0)
    
    def _classify_single_crop(self, crop_bgr: np.ndarray) -> Tuple[str, float]:
        """Classify a single crop image."""
        try:
            # Preprocess based on model type
            if hasattr(self, 'model_type') and self.model_type == "ONNX":
                # ONNX GoogleNet expects 224x224 with ImageNet normalization
                # Resize and convert BGR to RGB
                resized = cv2.resize(crop_bgr, (224, 224))
                rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                
                # Normalize to [0,1] then apply ImageNet normalization
                normalized = rgb.astype(np.float32) / 255.0
                mean = np.array([0.485, 0.456, 0.406])
                std = np.array([0.229, 0.224, 0.225])
                normalized = (normalized - mean) / std
                
                # Convert to blob format (1, 3, 224, 224)
                blob = np.transpose(normalized, (2, 0, 1))
                blob = np.expand_dims(blob, axis=0)
            else:
                # Caffe GilLevi model expects 227x227
                blob = cv2.dnn.blobFromImage(
                    crop_bgr,
                    scalefactor=1.0,
                    size=(227, 227),
                    mean=(78.4263377603, 87.7689143744, 114.895847746),
                    swapRB=False
                )
            
            # Run inference
            self.model.setInput(blob)
            preds = self.model.forward()
            
            # Get gender prediction
            # Output: [male_prob, female_prob]
            gender_idx = preds[0].argmax()
            confidence = float(preds[0][gender_idx])
            
            gender = 'male' if gender_idx == 0 else 'female'
            
            # Return unknown if confidence too low
            if confidence < self.confidence_threshold:
                return ('unknown', confidence)
            
            return (gender, confidence)
            
        except Exception as e:
            # Silently return unknown on error (don't spam logs)
            return ('unknown', 0.0)
    
    def should_match(self, gender1: str, gender2: str) -> bool:
        """
        Check if two genders are compatible for ReID matching.
        
        Args:
            gender1: First person's gender
            gender2: Second person's gender
            
        Returns:
            True if genders are compatible for matching
        """
        # Unknown can match with anything
        if gender1 == 'unknown' or gender2 == 'unknown':
            return True
        
        # Same gender can match
        if gender1 == gender2:
            return True
        
        # Different genders cannot match
        return False


class DeepGenderClassifier(GenderClassifier):
    """
    Deep learning-based gender classifier (future enhancement).
    
    Can use models like:
    - FairFace: https://github.com/dchen236/FairFace
    - DeepFace: https://github.com/serengil/deepface
    - Custom trained models on UTKFace, CelebA, etc.
    """
    
    def __init__(self, model_path: Optional[str] = None, confidence_threshold: float = 0.7):
        super().__init__(confidence_threshold)
        self.model = None
        self.model_path = model_path
        
        # TODO: Load actual deep learning model
        # if model_path and os.path.exists(model_path):
        #     self.model = load_gender_model(model_path)
        #     print(f"✅ Loaded gender classification model from {model_path}")
    
    def classify(self, crop_bgr: np.ndarray) -> Tuple[str, float]:
        """Use deep learning model for gender classification"""
        if self.model is None:
            # Fallback to heuristic
            return super().classify(crop_bgr)
        
        # TODO: Implement deep model inference
        # Example:
        # preprocessed = preprocess_for_model(crop_bgr)
        # prediction = self.model.predict(preprocessed)
        # gender = 'male' if prediction > 0.5 else 'female'
        # confidence = max(prediction, 1 - prediction)
        # return (gender, confidence)
        
        return super().classify(crop_bgr)


def create_gender_classifier() -> GenderClassifier:
    """Factory function to create appropriate gender classifier"""
    # Check if deep learning model is available
    model_path = os.environ.get("GENDER_MODEL_PATH", "")
    use_deep = int(os.environ.get("GENDER_USE_DEEP_MODEL", "0")) == 1
    
    if use_deep and model_path:
        return DeepGenderClassifier(model_path)
    else:
        return GenderClassifier()


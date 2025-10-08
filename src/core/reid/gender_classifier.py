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
        self.confidence_threshold = confidence_threshold
        self.enabled = int(os.environ.get("GENDER_CLASSIFICATION_ENABLED", "1")) == 1
        self.model = None
        
        if self.enabled:
            # Load OpenCV DNN gender model
            model_dir = "/app/models"
            prototxt = f"{model_dir}/gender_deploy.prototxt"
            caffemodel = f"{model_dir}/gender_model.caffemodel"
            
            if os.path.exists(prototxt) and os.path.exists(caffemodel):
                try:
                    self.model = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
                    print(f"🚻 Gender Classification: Enabled (OpenCV DNN)")
                    print(f"   Model: GilLevi Age-Gender (44MB)")
                    print(f"   Speed: ~5-10ms per person")
                    print(f"   Confidence threshold: {confidence_threshold}")
                except Exception as e:
                    print(f"⚠️ Gender model load error: {e}")
                    self.enabled = False
            else:
                print(f"🚻 Gender Classification: Enabled but model files not found")
                print(f"   Expected: {prototxt}")
                print(f"   Expected: {caffemodel}")
                print(f"   Falling back to 'unknown' classification")
                self.enabled = False
        else:
            print(f"🚻 Gender Classification: Disabled")
    
    def classify(self, crop_bgr: np.ndarray) -> Tuple[str, float]:
        """
        Classify gender from person crop using OpenCV DNN.
        
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
            # Preprocess for gender model (GilLevi model expects 227x227)
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


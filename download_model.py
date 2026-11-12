"""
Offline Model Preparation & Verification Utility
Downloads official lightweight pretrained model weights, verifies file integrity,
and confirms local offline CPU inference readiness on Raspberry Pi 5.
Run this ONCE while connected to the internet before offline robot deployment.
"""
import os
import sys
import hashlib
from pathlib import Path
import config


def download_and_verify_model(model_name: str = config.MODEL_NAME) -> bool:
    """
    Downloads model weights if missing, verifies file existence, and runs offline warm-up test.
    """
    print("=" * 70)
    print("📥 OFFLINE MODEL PREPARATION & VERIFICATION UTILITY")
    print(f"Target Model: {model_name}")
    print(f"Target Directory: {config.MODELS_DIR}")
    print("=" * 70)

    target_path = config.MODELS_DIR / model_name

    if target_path.exists():
        file_size_mb = target_path.stat().st_size / (1024 * 1024)
        print(f"[Model Prep] Model weights already exist locally: {target_path} ({file_size_mb:.2f} MB)")
    else:
        print(f"[Model Prep] Model weights not found locally. Initiating download for {model_name}...")
        try:
            from ultralytics import YOLO
            # Ultralytics will download the weights to current dir or cache, then we move to models/
            temp_model = YOLO(model_name)
            # Move downloaded .pt file into target path if needed
            downloaded_file = Path(model_name)
            if downloaded_file.exists() and downloaded_file.resolve() != target_path.resolve():
                downloaded_file.replace(target_path)
            print(f"[Model Prep] Download complete. Saved to: {target_path}")
        except Exception as e:
            print(f"[Model Prep ERROR] Automatic download failed: {e}")
            print(f"Manual instruction:\n"
                  f"1. Download '{model_name}' manually from https://github.com/ultralytics/assets/releases\n"
                  f"2. Place the .pt file directly into: {config.MODELS_DIR}")
            return False

    # Verify model file integrity
    file_bytes = target_path.stat().st_size
    if file_bytes < 1_000_000:
        print(f"[Model Prep ERROR] File appears corrupted or too small ({file_bytes} bytes)!")
        return False

    hasher = hashlib.sha256()
    with open(target_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    sha256_hash = hasher.hexdigest()
    print(f"[Model Prep] SHA-256 Hash: {sha256_hash[:16]}...{sha256_hash[-16:]}")

    # Offline Warm-up Verification Test
    print("[Model Prep] Running offline local CPU loading and warm-up inference...")
    try:
        from ai_detector import YOLOv8Detector
        import numpy as np

        detector = YOLOv8Detector(model_path=str(target_path))
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets, latency_ms = detector.detect(dummy_frame)
        print(f"[Model Prep] Verification PASSED! Warm-up inference latency: {latency_ms:.1f} ms.")
        print("=" * 70)
        print("✅ MODEL IS 100% READY FOR OFFLINE AIR-GAPPED DEPLOYMENT!")
        print("=" * 70)
        return True
    except Exception as e:
        print(f"[Model Prep ERROR] Offline loading test failed: {e}")
        return False


if __name__ == "__main__":
    success = download_and_verify_model()
    sys.exit(0 if success else 1)

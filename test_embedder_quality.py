#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app/src')
import numpy as np

print("="*60)
print("Testing Embedder Quality")
print("="*60)

# Test the embedder that's actually being used
from core.reid.facenet_embedder import HybridEmbedder

embedder = HybridEmbedder()
print(f"Embedder type: {type(embedder).__name__}")
print(f"Face enabled: {embedder.face_enabled}")
print(f"Dimension: {embedder.dim}")
print("")

# Create 3 very different test images
test1 = np.full((256, 128, 3), 50, dtype=np.uint8)   # Dark image
test2 = np.full((256, 128, 3), 200, dtype=np.uint8)  # Bright image  
test3 = np.random.randint(0, 255, (256, 128, 3), dtype=np.uint8)  # Random

print("Generating embeddings for 3 different images...")
emb1 = embedder.embed(test1)
emb2 = embedder.embed(test2)
emb3 = embedder.embed(test3)

print(f"Embedding 1: shape={emb1.shape}, norm={np.linalg.norm(emb1):.3f}")
print(f"Embedding 2: shape={emb2.shape}, norm={np.linalg.norm(emb2):.3f}")
print(f"Embedding 3: shape={emb3.shape}, norm={np.linalg.norm(emb3):.3f}")
print("")

# Calculate similarities
def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

sim12 = cosine_sim(emb1, emb2)
sim13 = cosine_sim(emb1, emb3)
sim23 = cosine_sim(emb2, emb3)

print(f"Similarity 1-2: {sim12:.4f}")
print(f"Similarity 1-3: {sim13:.4f}")
print(f"Similarity 2-3: {sim23:.4f}")
print("")

# Diagnosis
print("DIAGNOSIS:")
print("-"*60)
if all(s > 0.99 for s in [sim12, sim13, sim23]):
    print("❌ CRITICAL: All embeddings are IDENTICAL (>0.99 similarity)")
    print("   This means embedder is NOT working!")
    print("   Likely cause: Using fallback/stub embedder")
elif all(s > 0.95 for s in [sim12, sim13, sim23]):
    print("⚠️  WARNING: Embeddings are too similar (>0.95)")
    print("   Embedder may not be discriminative enough")
else:
    print("✅ Embeddings look reasonable (varied similarities)")
    print("   Embedder appears to be working")

print("")
print("="*60)


"""
Voice similarity comparison between my_voice.wav and my_cloned_voice.wav.

Compares voice characteristics (timbre, pitch, spectral shape) — not the words spoken.

Usage:
    python my_voice_comparison_tester.py
    python my_voice_comparison_tester.py --original my_voice.wav --cloned my_cloned_voice.wav
"""

import argparse

import librosa
import numpy as np


def load(path: str, sr: int = 22050) -> tuple[np.ndarray, int]:
    audio, sr = librosa.load(path, sr=sr, mono=True)
    return audio, sr


def mfcc_similarity(a: np.ndarray, b: np.ndarray, sr: int) -> float:
    """Cosine similarity between mean MFCC vectors (captures vocal tract / timbre)."""
    n_mfcc = 20
    mfcc_a = librosa.feature.mfcc(y=a, sr=sr, n_mfcc=n_mfcc)
    mfcc_b = librosa.feature.mfcc(y=b, sr=sr, n_mfcc=n_mfcc)

    # Use mean + std across time for a richer fingerprint
    vec_a = np.concatenate([mfcc_a.mean(axis=1), mfcc_a.std(axis=1)])
    vec_b = np.concatenate([mfcc_b.mean(axis=1), mfcc_b.std(axis=1)])

    return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))


def pitch_similarity(a: np.ndarray, b: np.ndarray, sr: int) -> float:
    """Similarity between mean fundamental frequency (F0) distributions."""
    f0_a = librosa.yin(a, fmin=50, fmax=500, sr=sr)
    f0_b = librosa.yin(b, fmin=50, fmax=500, sr=sr)

    # Filter unvoiced frames (near-zero F0)
    f0_a = f0_a[f0_a > 60]
    f0_b = f0_b[f0_b > 60]

    if len(f0_a) == 0 or len(f0_b) == 0:
        return 0.0

    mean_a, std_a = f0_a.mean(), f0_a.std()
    mean_b, std_b = f0_b.mean(), f0_b.std()

    # Similarity as 1 - normalized difference in mean pitch
    mean_diff = abs(mean_a - mean_b) / max(mean_a, mean_b)
    std_diff = abs(std_a - std_b) / (max(std_a, std_b) + 1e-6)

    return float(1.0 - (0.7 * mean_diff + 0.3 * std_diff))


def spectral_similarity(a: np.ndarray, b: np.ndarray, sr: int) -> float:
    """Cosine similarity of spectral envelope (brightness, resonance)."""
    cent_a = librosa.feature.spectral_centroid(y=a, sr=sr).mean()
    cent_b = librosa.feature.spectral_centroid(y=b, sr=sr).mean()

    rolloff_a = librosa.feature.spectral_rolloff(y=a, sr=sr).mean()
    rolloff_b = librosa.feature.spectral_rolloff(y=b, sr=sr).mean()

    bandwidth_a = librosa.feature.spectral_bandwidth(y=a, sr=sr).mean()
    bandwidth_b = librosa.feature.spectral_bandwidth(y=b, sr=sr).mean()

    vec_a = np.array([cent_a, rolloff_a, bandwidth_a])
    vec_b = np.array([cent_b, rolloff_b, bandwidth_b])

    return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))


def score_label(score: float) -> str:
    if score >= 0.95:
        return "Excellent"
    elif score >= 0.85:
        return "Good"
    elif score >= 0.70:
        return "Fair"
    else:
        return "Poor"


def compare(original_path: str, cloned_path: str) -> None:
    print(f"Loading:  {original_path}")
    original, sr = load(original_path)

    print(f"Loading:  {cloned_path}\n")
    cloned, _ = load(cloned_path, sr=sr)

    print("Analysing voice characteristics...\n")

    mfcc_score   = mfcc_similarity(original, cloned, sr)
    pitch_score  = pitch_similarity(original, cloned, sr)
    spec_score   = spectral_similarity(original, cloned, sr)

    # Weighted overall: MFCC carries most speaker identity info
    overall = 0.60 * mfcc_score + 0.25 * pitch_score + 0.15 * spec_score
    overall = max(0.0, min(1.0, overall))

    print("=" * 45)
    print(f"  {'Metric':<28} {'Score':>7}")
    print("-" * 45)
    print(f"  {'Timbre / Vocal Tract (MFCC)':<28} {mfcc_score * 100:>6.1f}%")
    print(f"  {'Pitch / F0':<28} {pitch_score * 100:>6.1f}%")
    print(f"  {'Spectral Shape':<28} {spec_score * 100:>6.1f}%")
    print("-" * 45)
    print(f"  {'Overall Voice Similarity':<28} {overall * 100:>6.1f}%  {score_label(overall)}")
    print("=" * 45)


def main():
    parser = argparse.ArgumentParser(
        description="Compare voice similarity between two audio files."
    )
    parser.add_argument("--original", type=str, default="my_voice.wav",
                        help="Path to original voice file (default: my_voice.wav)")
    parser.add_argument("--cloned", type=str, default="my_cloned_voice.wav",
                        help="Path to cloned voice file (default: my_cloned_voice.wav)")
    args = parser.parse_args()

    compare(args.original, args.cloned)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Module for converting RGB aerial images into vegetation and water matrices for beaver simulation.

This module processes RGB aerial imagery to extract:
- Vegetation indices (NDVI, VARI)
- Water detection using SAM2 (Segment Anything Model 2)
- Normalized vegetation quality matrices

The processing pipeline handles challenges like shadows, terrain variability,
and water stream detection from RGB channels.
"""

import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import cv2
import os
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, List
from sklearn.preprocessing import MinMaxScaler
from scipy.ndimage import median_filter, binary_opening, binary_closing

# Constants
INVALID_MARKER = -1.0  # Marker for invalid/no-data pixels
WATER_MARKER = -0.5    # Marker for water pixels
EPSILON = 1e-6         # Small value to avoid division by zero
MEDIAN_SIZE = 10       # Kernel size for median filtering to remove outliers


def load_rgb_image(image_path: str, target_size: Optional[Tuple[int, int]] = None) -> Tuple[np.ndarray, Dict]:
    """Load RGB image and extract metadata.
    
    Args:
        image_path: Path to RGB image file
        target_size: Optional (width, height) to resize image
        
    Returns:
        rgb_array: RGB image as numpy array (H, W, 3) with values [0, 255]
        metadata: Dictionary with image information
    """    
    
    # Load image
    img = Image.open(image_path)
    
    # Convert to RGB if needed
    if img.mode != 'RGB':        
        img = img.convert('RGB')
    
    original_size = img.size  # (width, height)
    
    # Resize if requested
    if target_size is not None:        
        img = img.resize(target_size, Image.Resampling.LANCZOS)
    
    # Convert to numpy array
    rgb_array = np.array(img)
    
    metadata = {
        'filename': os.path.basename(image_path),
        'original_size': original_size,
        'processed_size': rgb_array.shape[:2][::-1],  # (width, height)
        'shape': rgb_array.shape,
        'dtype': str(rgb_array.dtype)
    }
    
    print(f"  Image loaded: {rgb_array.shape} (H x W x C)")    
    
    return rgb_array, metadata

def apply_shadow_correction(rgb: np.ndarray, method: str = 'histogram') -> np.ndarray:
    """Correct for shadows in RGB image.
    
    Args:
        rgb: RGB image array (H, W, 3)
        method: 'histogram' or 'clahe'
        
    Returns:
        rgb_corrected: Shadow-corrected RGB image
    """    
    
    if method == 'histogram':
        # Simple histogram equalization per channel
        rgb_corrected = np.zeros_like(rgb)
        for i in range(3):
            rgb_corrected[:, :, i] = cv2.equalizeHist(rgb[:, :, i])
    
    elif method == 'clahe':
        # Contrast Limited Adaptive Histogram Equalization
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        rgb_corrected = np.zeros_like(rgb)
        for i in range(3):
            rgb_corrected[:, :, i] = clahe.apply(rgb[:, :, i])
    
    else:
        raise ValueError(f"Unknown shadow correction method: {method}")
    
    print(f"  Shadow correction applied")
    
    return rgb_corrected


def calculate_ndvi(rgb: np.ndarray, method: str = 'visible') -> np.ndarray:
    """Calculate Normalized Difference Vegetation Index from RGB image.
    
    NDVI traditionally uses Near-Infrared (NIR) and Red bands:
        NDVI = (NIR - Red) / (NIR + Red)
    
    For RGB images without NIR, we use the visible-band approximation:
        NDVI_visible = (Green - Red) / (Green + Red)
    
    Args:
        rgb: RGB image array (H, W, 3) with values [0, 255]
        method: 'visible' for RGB approximation, 'nir' for true NDVI (requires NIR band)
        
    Returns:
        ndvi: NDVI values in range [-1, 1] where:
              > 0.3: Dense vegetation
              0.1-0.3: Sparse vegetation  
              < 0.1: Non-vegetated (water, soil, urban)
              < 0: Water, clouds, snow
    """    
    
    # Extract channels (convert to float to avoid overflow)
    R = rgb[:, :, 0].astype(np.float32)
    G = rgb[:, :, 1].astype(np.float32)
    B = rgb[:, :, 2].astype(np.float32)
    
    if method == 'visible':
        # Visible-band NDVI approximation using Green as proxy for NIR
        numerator = G - R
        denominator = G + R
    else:
        raise ValueError(f"Unknown NDVI method: {method}. Use 'visible'.")
    
    # Avoid division by zero    
    ndvi = np.divide(numerator, denominator + EPSILON, 
                     out=np.zeros_like(numerator), 
                     where=(denominator + EPSILON) != 0)        

    # Apply median filter to remove outliers    
    ndvi_filtered = median_filter(ndvi, size=MEDIAN_SIZE)

    # Rescale NDVI to [-1, 1] using MinMaxScaler from sklearn    
    valid_mask = np.isfinite(ndvi_filtered)
    ndvi_rescaled = np.full_like(ndvi_filtered, np.nan, dtype=np.float32)
    if np.any(valid_mask):
        scaler = MinMaxScaler(feature_range=(-1, 1))
        ndvi_valid = ndvi_filtered[valid_mask].reshape(-1, 1)
        ndvi_scaled = scaler.fit_transform(ndvi_valid).flatten()
        ndvi_rescaled[valid_mask] = ndvi_scaled
        print(f"  NDVI rescaled range: [{ndvi_scaled.min():.3f}, {ndvi_scaled.max():.3f}]")
        print(f"  NDVI rescaled mean: {ndvi_scaled.mean():.3f}")
    return ndvi_rescaled


def calculate_vari(rgb: np.ndarray) -> np.ndarray:
    """Calculate Visible Atmospherically Resistant Index.
    
    VARI is designed to be more robust to atmospheric effects and lighting variations:
        VARI = (Green - Red) / (Green + Red - Blue)
    
    Args:
        rgb: RGB image array (H, W, 3) with values [0, 255]
        
    Returns:
        vari: VARI values typically in range [-1, 1] where:
              Higher values indicate more vegetation
              More resistant to shadows than NDVI
    """    
    
    # Extract channels
    R = rgb[:, :, 0].astype(np.float32)
    G = rgb[:, :, 1].astype(np.float32)
    B = rgb[:, :, 2].astype(np.float32)

    numerator = G - R
    denominator = G + R - B

    # Mask out small denominators to avoid extreme values    
    # vari = np.clip(numerator / denominator, -2, 2)
    vari = numerator / (denominator + EPSILON)  # Add epsilon to avoid division by zero

    # Apply median filter to remove outliers    
    vari_filtered = median_filter(vari, size=MEDIAN_SIZE)

    # Rescale VARI to [-1, 1] using MinMaxScaler from sklearn    
    valid_mask = np.isfinite(vari_filtered)
    vari_rescaled = np.full_like(vari_filtered, np.nan, dtype=np.float32)
    if np.any(valid_mask):
        scaler = MinMaxScaler(feature_range=(-1, 1))
        # Reshape for scaler, scale only valid values
        vari_valid = vari_filtered[valid_mask].reshape(-1, 1)
        vari_scaled = scaler.fit_transform(vari_valid).flatten()
        vari_rescaled[valid_mask] = vari_scaled
        print(f"  VARI rescaled range: [{vari_scaled.min():.3f}, {vari_scaled.max():.3f}]")
        print(f"  VARI rescaled mean: {vari_scaled.mean():.3f}")
    return vari_rescaled


def calculate_excess_green(rgb: np.ndarray) -> np.ndarray:
    """Calculate Excess Green Index (ExG) for vegetation detection.
    
    ExG emphasizes green vegetation and is useful for separating plants from soil:
        ExG = 2*Green - Red - Blue
    
    Args:
        rgb: RGB image array (H, W, 3) with values [0, 255]
        
    Returns:
        exg: Excess Green values (normalized to [0, 1])
    """    
    
    # Normalize RGB to [0, 1]
    rgb_norm = rgb.astype(np.float32) / 255.0
    
    R = rgb_norm[:, :, 0]
    G = rgb_norm[:, :, 1]
    B = rgb_norm[:, :, 2]
    
    exg = 2 * G - R - B

    # Apply median filter to remove outliers    
    exg_filtered = median_filter(exg, size=MEDIAN_SIZE)

    # Rescale ExG to [-1, 1] using MinMaxScaler from sklearn    
    valid_mask = np.isfinite(exg_filtered)
    exg_rescaled = np.full_like(exg_filtered, np.nan, dtype=np.float32)
    if np.any(valid_mask):
        scaler = MinMaxScaler(feature_range=(-1, 1))
        exg_valid = exg_filtered[valid_mask].reshape(-1, 1)
        exg_scaled = scaler.fit_transform(exg_valid).flatten()
        exg_rescaled[valid_mask] = exg_scaled
        print(f"  ExG rescaled range: [{exg_scaled.min():.3f}, {exg_scaled.max():.3f}]")
        print(f"  ExG rescaled mean: {exg_scaled.mean():.3f}")
    return exg_rescaled


def calculate_cwi(rgb: np.ndarray) -> np.ndarray:
    """Calculate Color Water Index (CWI) for direct water detection.
    
    CWI uses the log-ratio of blue to red channels to highlight water's spectral signature.
    Water typically reflects more in the blue spectrum than red, making this index
    particularly effective for water body detection.
    
    Formula:
        CWI = log(Blue / Red)
    
    High positive values indicate water, negative values indicate non-water (vegetation, soil).
    
    Args:
        rgb: RGB image array (H, W, 3) with values [0, 255]
        
    Returns:
        cwi: Color Water Index values (normalized to [-1, 1] range for consistency)
    """    
    
    R = rgb[:, :, 0].astype(np.float32) + EPSILON  # Add epsilon to avoid log(0)
    B = rgb[:, :, 2].astype(np.float32) + EPSILON
    
    # Calculate CWI = log(Blue / Red)
    cwi = np.log(B / R)

    # Apply median filter to remove outliers    
    cwi_filtered = median_filter(cwi, size=MEDIAN_SIZE)

    # Rescale CWI to [-1, 1] using MinMaxScaler from sklearn    
    valid_mask = np.isfinite(cwi_filtered)
    cwi_rescaled = np.full_like(cwi_filtered, np.nan, dtype=np.float32)
    if np.any(valid_mask):
        scaler = MinMaxScaler(feature_range=(-1, 1))
        cwi_valid = cwi_filtered[valid_mask].reshape(-1, 1)
        cwi_scaled = scaler.fit_transform(cwi_valid).flatten()
        cwi_rescaled[valid_mask] = cwi_scaled
        print(f"  CWI rescaled range: [{cwi_scaled.min():.3f}, {cwi_scaled.max():.3f}]")
        print(f"  CWI rescaled mean: {cwi_scaled.mean():.3f}")
    return cwi_rescaled


def detect_water_simple(rgb: np.ndarray, 
                        vegetation_index: np.ndarray,
                        index_name: str = 'NDVI',
                        index_threshold: float = 0.0) -> np.ndarray:
    """Simple water detection using only the vegetation index threshold.
    
    Water is identified based solely on the index value:
    - Low vegetation index values (< threshold) for NDVI/VARI/ExG
    - HIGH CWI values (> threshold) for CWI (inverted logic)
    
    Args:
        rgb: RGB image array (H, W, 3) - not used, kept for API compatibility
        vegetation_index: Vegetation index array (NDVI, VARI, ExG, or CWI)
        index_name: Name of the index for logging ('NDVI', 'VARI', 'ExG', or 'CWI')
        index_threshold: Threshold value for water detection
        
    Returns:
        water_mask: Binary mask where True indicates water
    """    
    
    # Water detection using only index criterion
    # CWI uses inverted logic (high = water), others use low = water
    if index_name.upper() == 'CWI':
        water_mask = vegetation_index > index_threshold
        print(f"  Using {index_name} > {index_threshold:.3f} (CWI: high values = water)")
    else:
        water_mask = vegetation_index < index_threshold
        print(f"  Using {index_name} < {index_threshold:.3f} (vegetation index: low values = water)")
    
    water_pixels = np.sum(water_mask)
    total_pixels = water_mask.size
    
    print(f"  Water pixels detected: {water_pixels:,} ({100*water_pixels/total_pixels:.2f}%)")
    
    return water_mask


def postprocess_water_mask(water_mask: np.ndarray,
                           opening_sizes: List[int] = [],
                           median_sizes: List[int] = [],
                           closing_sizes: List[int] = [],
                           apply_opening: bool = True,
                           apply_median: bool = True,
                           apply_closing: bool = True) -> np.ndarray:
    """Post-process water mask to remove noise and connect water regions.
    
    Applies morphological operations in cascade to clean up water detection:
    1. All openings in sequence: Remove small isolated false positives (erosion + dilation)
    2. All median filters in sequence: Remove salt-and-pepper noise
    3. All morphological closings in sequence: Fill gaps and connect nearby water regions
    
    Strategy: Clean first (opening/median), then connect (closing) for best results.
    Opening is recommended over median for binary masks (more predictable behavior).
    
    Args:
        water_mask: Binary water mask (True = water, False = land)
        opening_sizes: List of opening kernel sizes (erosion then dilation).
                       Applied in cascade. Example: [3, 5] applies 3x3 then 5x5.
                       Removes small isolated false positives without permanently shrinking features.
        median_sizes: List of median filter kernel sizes (must be odd). 
                      Applied in cascade. Example: [5, 11] applies 5x5 then 11x11.
                      Note: For binary masks, opening is usually preferred.
        closing_sizes: List of morphological closing kernel sizes (dilation then erosion).
                       Applied in cascade after opening/median. Example: [7, 11].
                       Fills holes and connects nearby water regions.
        apply_opening: Whether to apply opening operations
        apply_median: Whether to apply median filters
        apply_closing: Whether to apply morphological closings
        
    Returns:
        Processed water mask
    """    
    
    processed_mask = water_mask.copy()
    pixels_before = np.sum(processed_mask)
    
    # Phase 1: Apply all openings in cascade to remove small isolated false positives
    if apply_opening and opening_sizes:
        print(f"  Phase 1: Applying {len(opening_sizes)} opening(s) (erosion + dilation)...")
        for i, opening_size in enumerate(opening_sizes, 1):
            if opening_size > 0:
                structure = np.ones((opening_size, opening_size), dtype=bool)
                processed_mask = binary_opening(processed_mask, structure=structure)
                pixels_after = np.sum(processed_mask)
                removed = pixels_before - pixels_after
                if removed > 0:
                    print(f"    Opening {i} (kernel={opening_size}): Removed {removed:,} noise pixels")
                elif removed < 0:
                    print(f"    Opening {i} (kernel={opening_size}): Added {-removed:,} pixels")
                pixels_before = pixels_after
    
    # Phase 2: Apply all median filters in cascade to remove noise
    if apply_median and median_sizes:
        print(f"  Phase 2: Applying {len(median_sizes)} median filter(s)...")
        for i, median_size in enumerate(median_sizes, 1):
            if median_size > 0:
                processed_mask = median_filter(processed_mask.astype(np.uint8), size=median_size).astype(bool)
                pixels_after = np.sum(processed_mask)
                removed = pixels_before - pixels_after
                if removed > 0:
                    print(f"    Median {i} (kernel={median_size}): Removed {removed:,} outlier pixels")
                elif removed < 0:
                    print(f"    Median {i} (kernel={median_size}): Added {-removed:,} pixels")
                pixels_before = pixels_after
    
    # Phase 3: Apply all morphological closings in cascade to connect regions
    if apply_closing and closing_sizes:
        print(f"  Phase 3: Applying {len(closing_sizes)} morphological closing(s)...")
        for i, closing_size in enumerate(closing_sizes, 1):
            if closing_size > 0:
                structure = np.ones((closing_size, closing_size), dtype=bool)
                closed_mask = binary_closing(processed_mask, structure=structure)
                pixels_after = np.sum(closed_mask)
                added = pixels_after - pixels_before
                if added > 0:
                    print(f"    Closing {i} (kernel={closing_size}): Connected regions, added {added:,} pixels")
                processed_mask = closed_mask
                pixels_before = pixels_after
    
    final_pixels = np.sum(processed_mask)
    original_pixels = np.sum(water_mask)
    change = final_pixels - original_pixels
    change_pct = 100 * change / max(original_pixels, 1)
    
    print(f"  Summary: {original_pixels:,} → {final_pixels:,} pixels ({change_pct:+.1f}%)")
    
    return processed_mask


def apply_water_mask(vegetation_quality: np.ndarray, 
                     water_mask: np.ndarray,
                     water_depth_estimate: Optional[np.ndarray] = None) -> np.ndarray:
    """Apply water mask to vegetation quality matrix.
    
    Args:
        vegetation_quality: Vegetation quality array [0, 1]
        water_mask: Binary water mask
        water_depth_estimate: Optional depth estimate for water [0, 1]
        
    Returns:
        combined_matrix: Combined matrix where:
                        [0, 1]: Land with vegetation quality
                        [-1, 0]: Water (optionally with depth info)
    """    
    
    combined_matrix = vegetation_quality.copy()
    
    if water_depth_estimate is not None:
        # Use depth estimate to set water values in [-1, 0] range
        combined_matrix[water_mask] = -water_depth_estimate[water_mask]
    else:
        # Mark all water as uniform value
        combined_matrix[water_mask] = WATER_MARKER
    
    water_pixels = np.sum(water_mask)
    land_pixels = np.sum(~water_mask)
    total_pixels = combined_matrix.size
    
    print(f"  Land pixels: {land_pixels:,} ({100*land_pixels/total_pixels:.1f}%)")
    print(f"  Water pixels: {water_pixels:,} ({100*water_pixels/total_pixels:.1f}%)")
    
    return combined_matrix


def resize_to_target_resolution(matrix: np.ndarray, 
                                target_shape: Tuple[int, int],
                                method: str = 'bilinear') -> np.ndarray:
    """Resize matrix to target resolution.
    
    Args:
        matrix: Input matrix (H, W)
        target_shape: Target (height, width)
        method: 'bilinear', 'nearest', or 'cubic'
        
    Returns:
        resized_matrix: Resized matrix
    """    
    
    if method == 'bilinear':
        interpolation = cv2.INTER_LINEAR
    elif method == 'nearest':
        interpolation = cv2.INTER_NEAREST
    elif method == 'cubic':
        interpolation = cv2.INTER_CUBIC
    else:
        raise ValueError(f"Unknown interpolation method: {method}")
    
    resized_matrix = cv2.resize(matrix, (target_shape[1], target_shape[0]), 
                                interpolation=interpolation)
    
    print(f"  Resized to {resized_matrix.shape}")
    
    return resized_matrix


def save_rgb_outputs(output_dir: str,
                     combined_matrix: np.ndarray,
                     ndvi: np.ndarray,
                     vari: np.ndarray,
                     water_mask: np.ndarray,
                     metadata: Dict,
                     rgb_original: Optional[np.ndarray] = None) -> None:
    """Save all RGB processing outputs and metadata.
    
    Args:
        output_dir: Directory to save outputs
        combined_matrix: Final combined vegetation/water matrix
        ndvi: NDVI array
        vari: VARI array
        water_mask: Water detection mask
        metadata: Processing metadata dictionary
        rgb_original: Original RGB image (optional, for reference)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Save matrices
    np.save(f"{output_dir}/vegetation_matrix.npy", combined_matrix)
    np.save(f"{output_dir}/ndvi.npy", ndvi)
    np.save(f"{output_dir}/vari.npy", vari)
    np.save(f"{output_dir}/water_mask.npy", water_mask)
    
    if rgb_original is not None:
        np.save(f"{output_dir}/rgb_original.npy", rgb_original)
    
    # Add processing metadata
    metadata['output_files'] = {
        'vegetation_matrix': 'vegetation_matrix.npy',
        'ndvi': 'ndvi.npy',
        'vari': 'vari.npy',
        'water_mask': 'water_mask.npy'
    }
    metadata['matrix_shape'] = list(combined_matrix.shape)
    metadata['value_ranges'] = {
        'land_vegetation': '[0.0, 1.0]',
        'water': '[-1.0, 0.0]',
        'invalid': str(INVALID_MARKER)
    }
    
    # Save metadata
    with open(f"{output_dir}/processing_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✓ Saved to {output_dir}:")

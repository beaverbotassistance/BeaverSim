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
import warnings

# Constants
INVALID_MARKER = -1.0  # Marker for invalid/no-data pixels
WATER_MARKER = -0.5    # Marker for water pixels


def load_rgb_image(image_path: str, target_size: Optional[Tuple[int, int]] = None) -> Tuple[np.ndarray, Dict]:
    """Load RGB image and extract metadata.
    
    Args:
        image_path: Path to RGB image file
        target_size: Optional (width, height) to resize image
        
    Returns:
        rgb_array: RGB image as numpy array (H, W, 3) with values [0, 255]
        metadata: Dictionary with image information
    """
    print(f"Loading RGB image: {image_path}")
    
    # Load image
    img = Image.open(image_path)
    
    # Convert to RGB if needed
    if img.mode != 'RGB':
        print(f"  Converting from {img.mode} to RGB")
        img = img.convert('RGB')
    
    original_size = img.size  # (width, height)
    
    # Resize if requested
    if target_size is not None:
        print(f"  Resizing from {original_size} to {target_size}")
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
    print(f"  Value range: [{rgb_array.min()}, {rgb_array.max()}]")
    
    return rgb_array, metadata


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
    print("Calculating NDVI (Normalized Difference Vegetation Index)...")
    
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
    epsilon = 1e-8
    ndvi = np.divide(numerator, denominator + epsilon, 
                     out=np.zeros_like(numerator), 
                     where=(denominator + epsilon) != 0)
    
    # Clip to valid range [-1, 1]
    ndvi = np.clip(ndvi, -1, 1)
    
    # Calculate statistics
    valid_mask = np.isfinite(ndvi)
    if np.any(valid_mask):
        print(f"  NDVI range: [{ndvi[valid_mask].min():.3f}, {ndvi[valid_mask].max():.3f}]")
        print(f"  NDVI mean: {ndvi[valid_mask].mean():.3f}")
        
        # Vegetation classification
        dense_veg = np.sum(ndvi > 0.3)
        sparse_veg = np.sum((ndvi > 0.1) & (ndvi <= 0.3))
        non_veg = np.sum((ndvi > 0) & (ndvi <= 0.1))
        water_like = np.sum(ndvi < 0)
        total_pixels = ndvi.size
        
        print(f"  Dense vegetation (>0.3): {100*dense_veg/total_pixels:.1f}%")
        print(f"  Sparse vegetation (0.1-0.3): {100*sparse_veg/total_pixels:.1f}%")
        print(f"  Non-vegetated (0-0.1): {100*non_veg/total_pixels:.1f}%")
        print(f"  Water-like (<0): {100*water_like/total_pixels:.1f}%")
    
    return ndvi


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
    print("Calculating VARI (Visible Atmospherically Resistant Index)...")
    
    # Extract channels
    R = rgb[:, :, 0].astype(np.float32)
    G = rgb[:, :, 1].astype(np.float32)
    B = rgb[:, :, 2].astype(np.float32)
    
    numerator = G - R
    denominator = G + R - B
    
    # Avoid division by zero
    epsilon = 1e-8
    vari = np.divide(numerator, denominator + epsilon,
                     out=np.zeros_like(numerator),
                     where=(denominator + epsilon) != 0)
    
    # Clip to reasonable range
    vari = np.clip(vari, -1, 1)
    
    # Calculate statistics
    valid_mask = np.isfinite(vari)
    if np.any(valid_mask):
        print(f"  VARI range: [{vari[valid_mask].min():.3f}, {vari[valid_mask].max():.3f}]")
        print(f"  VARI mean: {vari[valid_mask].mean():.3f}")
        
        # Vegetation classification (similar thresholds as NDVI)
        high_veg = np.sum(vari > 0.3)
        moderate_veg = np.sum((vari > 0.1) & (vari <= 0.3))
        low_veg = np.sum((vari > 0) & (vari <= 0.1))
        non_veg = np.sum(vari < 0)
        total_pixels = vari.size
        
        print(f"  High vegetation (>0.3): {100*high_veg/total_pixels:.1f}%")
        print(f"  Moderate vegetation (0.1-0.3): {100*moderate_veg/total_pixels:.1f}%")
        print(f"  Low vegetation (0-0.1): {100*low_veg/total_pixels:.1f}%")
        print(f"  Non-vegetated (<0): {100*non_veg/total_pixels:.1f}%")
    
    return vari


def calculate_excess_green(rgb: np.ndarray) -> np.ndarray:
    """Calculate Excess Green Index (ExG) for vegetation detection.
    
    ExG emphasizes green vegetation and is useful for separating plants from soil:
        ExG = 2*Green - Red - Blue
    
    Args:
        rgb: RGB image array (H, W, 3) with values [0, 255]
        
    Returns:
        exg: Excess Green values (normalized to [0, 1])
    """
    print("Calculating ExG (Excess Green Index)...")
    
    # Normalize RGB to [0, 1]
    rgb_norm = rgb.astype(np.float32) / 255.0
    
    R = rgb_norm[:, :, 0]
    G = rgb_norm[:, :, 1]
    B = rgb_norm[:, :, 2]
    
    exg = 2 * G - R - B
    
    # Normalize to [-1, 1] range for consistency with NDVI and VARI
    exg_min, exg_max = exg.min(), exg.max()
    if exg_max > exg_min:
        # Map [exg_min, exg_max] to [-1, 1]
        exg = 2 * (exg - exg_min) / (exg_max - exg_min) - 1
    else:
        exg = np.full_like(exg, 0.0)
    
    print(f"  ExG range: [{exg.min():.3f}, {exg.max():.3f}]")
    print(f"  ExG mean: {exg.mean():.3f}")
    
    # Vegetation classification for ExG (now in -1 to 1 scale like NDVI/VARI)
    high_green = np.sum(exg > 0.3)
    moderate_green = np.sum((exg > 0.1) & (exg <= 0.3))
    low_green = np.sum((exg > 0) & (exg <= 0.1))
    minimal_green = np.sum(exg <= 0)
    total_pixels = exg.size
    
    print(f"  High green (>0.3): {100*high_green/total_pixels:.1f}%")
    print(f"  Moderate green (0.1-0.3): {100*moderate_green/total_pixels:.1f}%")
    print(f"  Low green (0-0.1): {100*low_green/total_pixels:.1f}%")
    print(f"  Minimal green (<=0): {100*minimal_green/total_pixels:.1f}%")
    
    return exg


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
    print("Calculating CWI (Color Water Index)...")
    
    R = rgb[:, :, 0].astype(np.float32) + 1e-6  # Add epsilon to avoid log(0)
    B = rgb[:, :, 2].astype(np.float32) + 1e-6
    
    # Calculate CWI = log(Blue / Red)
    cwi = np.log(B / R)
    
    # Normalize to [-1, 1] range for consistency with other indices
    cwi_min, cwi_max = cwi.min(), cwi.max()
    if cwi_max > cwi_min:
        cwi_normalized = 2 * (cwi - cwi_min) / (cwi_max - cwi_min) - 1
    else:
        cwi_normalized = np.full_like(cwi, 0.0)
    
    print(f"  CWI raw range: [{cwi.min():.3f}, {cwi.max():.3f}]")
    print(f"  CWI normalized range: [{cwi_normalized.min():.3f}, {cwi_normalized.max():.3f}]")
    print(f"  CWI normalized mean: {cwi_normalized.mean():.3f}")
    
    # Water classification (high CWI indicates water)
    high_water = np.sum(cwi_normalized > 0.3)
    moderate_water = np.sum((cwi_normalized > 0.1) & (cwi_normalized <= 0.3))
    low_water = np.sum((cwi_normalized > 0) & (cwi_normalized <= 0.1))
    non_water = np.sum(cwi_normalized <= 0)
    total_pixels = cwi_normalized.size
    
    print(f"  Strong water signature (>0.3): {100*high_water/total_pixels:.1f}%")
    print(f"  Moderate water signature (0.1-0.3): {100*moderate_water/total_pixels:.1f}%")
    print(f"  Weak water signature (0-0.1): {100*low_water/total_pixels:.1f}%")
    print(f"  Non-water (<=0): {100*non_water/total_pixels:.1f}%")
    
    return cwi_normalized


def calculate_automatic_water_thresholds(rgb: np.ndarray, 
                                         vegetation_index: np.ndarray,
                                         index_name: str = 'NDVI') -> Dict[str, float]:
    """Automatically calculate water detection threshold using histogram analysis.
    
    Uses Otsu's method to determine optimal threshold for separating water from non-water
    based on the vegetation index distribution.
    
    Args:
        rgb: RGB image array (H, W, 3) - not used, kept for API compatibility
        vegetation_index: Vegetation index array (NDVI, VARI, ExG, or CWI)
        index_name: Name of the index for logging
        
    Returns:
        Dictionary with key: 'index_threshold'
    """
    print(f"Calculating automatic water detection threshold using {index_name}...")
    
    # Index threshold: Use Otsu's method on the vegetation index
    # This finds the optimal separation between vegetation and water
    try:
        from skimage.filters import threshold_otsu
        # Normalize index to 0-255 range for Otsu
        index_normalized = ((vegetation_index + 1) * 127.5).astype(np.uint8)
        otsu_val = threshold_otsu(index_normalized)
        # Convert back to original scale
        index_threshold = float((otsu_val / 127.5) - 1)
    except ImportError:
        # Fallback: use mean - 0.5*std (captures lower tail of distribution)
        index_threshold = float(np.mean(vegetation_index) - 0.5 * np.std(vegetation_index))
    
    print(f"  Calculated threshold:")
    print(f"    {index_name} threshold: {index_threshold:.3f} (Otsu's method)")
    
    return {
        'index_threshold': index_threshold
    }


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
    print(f"Detecting water using {index_name} threshold...")
    
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
    from scipy.ndimage import median_filter, binary_opening, binary_closing
    
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


def detect_water_sam2(rgb: np.ndarray, 
                      checkpoint: Optional[str] = None,
                      model_cfg: str = "sam2_hiera_l.yaml",
                      point_prompts: Optional[List[Tuple[int, int]]] = None,
                      box_prompts: Optional[List[Tuple[int, int, int, int]]] = None,
                      device: str = "cpu") -> np.ndarray:
    """Detect water using SAM2 (Segment Anything Model 2).
    
    SAM2 is a powerful segmentation model that can identify water bodies
    with optional user prompts for guidance.
    
    Args:
        rgb: RGB image array (H, W, 3)
        checkpoint: Path to SAM2 checkpoint file
        model_cfg: SAM2 model configuration
        point_prompts: List of (x, y) points indicating water locations
        box_prompts: List of (x1, y1, x2, y2) boxes containing water
        device: Device to run model on ('cpu' or 'cuda'). Default: 'cpu'
        
    Returns:
        water_mask: Binary mask where True indicates water
    """
    print(f"Detecting water using SAM2 on {device.upper()}...")
    
    try:
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError:
        print("  WARNING: SAM2 not installed. Falling back to simple water detection.")
        print("  Install SAM2: pip install git+https://github.com/facebookresearch/sam2.git")
        return np.zeros(rgb.shape[:2], dtype=bool)
    
    if checkpoint is None:
        print("  WARNING: No SAM2 checkpoint provided. Please download from:")
        print("  https://github.com/facebookresearch/sam2")
        return np.zeros(rgb.shape[:2], dtype=bool)
    
    # Build SAM2 model on specified device
    sam2_model = build_sam2(model_cfg, checkpoint, device=device)
    predictor = SAM2ImagePredictor(sam2_model)
    
    # Set image
    predictor.set_image(rgb)
    
    # Prepare prompts
    input_points = None
    input_labels = None
    input_boxes = None
    
    if point_prompts is not None:
        input_points = np.array(point_prompts)
        input_labels = np.ones(len(point_prompts))  # 1 = foreground (water)
        print(f"  Using {len(point_prompts)} point prompts")
    
    if box_prompts is not None:
        input_boxes = np.array(box_prompts)
        print(f"  Using {len(box_prompts)} box prompts")
    
    # Predict masks
    masks, scores, logits = predictor.predict(
        point_coords=input_points,
        point_labels=input_labels,
        box=input_boxes,
        multimask_output=True
    )
    
    # Select best mask based on score
    best_mask_idx = np.argmax(scores)
    water_mask = masks[best_mask_idx].astype(bool)
    
    water_pixels = np.sum(water_mask)
    total_pixels = water_mask.size
    
    print(f"  Water pixels detected: {water_pixels:,} ({100*water_pixels/total_pixels:.2f}%)")
    print(f"  Confidence score: {scores[best_mask_idx]:.3f}")
    
    return water_mask


def combine_vegetation_indices(ndvi: np.ndarray, 
                                vari: np.ndarray,
                                exg: Optional[np.ndarray] = None,
                                weights: Tuple[float, float, float] = (0.4, 0.3, 0.3)) -> np.ndarray:
    """Combine multiple vegetation indices into a single quality metric.
    
    Args:
        ndvi: NDVI array [-1, 1]
        vari: VARI array [-1, 1]
        exg: Excess Green array [0, 1] (optional)
        weights: (ndvi_weight, vari_weight, exg_weight) - must sum to 1.0
        
    Returns:
        vegetation_quality: Combined vegetation index [0, 1] where:
                           1.0 = optimal vegetation
                           0.0 = no vegetation
    """
    print("Combining vegetation indices...")
    
    # Normalize NDVI and VARI to [0, 1] range
    ndvi_norm = (ndvi + 1) / 2.0  # [-1, 1] -> [0, 1]
    vari_norm = (vari + 1) / 2.0  # [-1, 1] -> [0, 1]
    
    if exg is not None:
        # Weighted combination of all three
        vegetation_quality = (weights[0] * ndvi_norm + 
                            weights[1] * vari_norm + 
                            weights[2] * exg)
    else:
        # Only NDVI and VARI
        w_ndvi = weights[0] / (weights[0] + weights[1])
        w_vari = weights[1] / (weights[0] + weights[1])
        vegetation_quality = w_ndvi * ndvi_norm + w_vari * vari_norm
    
    # Ensure [0, 1] range
    vegetation_quality = np.clip(vegetation_quality, 0, 1)
    
    print(f"  Combined vegetation quality range: [{vegetation_quality.min():.3f}, {vegetation_quality.max():.3f}]")
    print(f"  Mean quality: {vegetation_quality.mean():.3f}")
    
    return vegetation_quality


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
    print("Applying water mask...")
    
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


def apply_shadow_correction(rgb: np.ndarray, method: str = 'histogram') -> np.ndarray:
    """Correct for shadows in RGB image.
    
    Args:
        rgb: RGB image array (H, W, 3)
        method: 'histogram' or 'clahe'
        
    Returns:
        rgb_corrected: Shadow-corrected RGB image
    """
    print(f"Applying shadow correction (method: {method})...")
    
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
    print(f"Resizing from {matrix.shape} to {target_shape}...")
    
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
    print(f"  - vegetation_matrix.npy: {combined_matrix.shape}")
    print(f"  - ndvi.npy: {ndvi.shape}")
    print(f"  - vari.npy: {vari.shape}")
    print(f"  - water_mask.npy: {water_mask.shape}")
    print(f"  - processing_metadata.json")


def visualize_results(rgb: np.ndarray,
                     ndvi: np.ndarray,
                     vari: np.ndarray,
                     water_mask: np.ndarray,
                     combined_matrix: np.ndarray,
                     save_path: Optional[str] = None) -> None:
    """Create comprehensive visualization of processing results.
    
    Args:
        rgb: Original RGB image
        ndvi: NDVI array
        vari: VARI array
        water_mask: Water mask
        combined_matrix: Final combined matrix
        save_path: Optional path to save figure
    """
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # Original RGB
    axes[0, 0].imshow(rgb)
    axes[0, 0].set_title('Original RGB Image', fontsize=14, fontweight='bold')
    axes[0, 0].axis('off')
    
    # NDVI
    im1 = axes[0, 1].imshow(ndvi, cmap='RdYlGn', vmin=-1, vmax=1)
    axes[0, 1].set_title('NDVI (Vegetation Index)', fontsize=14, fontweight='bold')
    axes[0, 1].axis('off')
    plt.colorbar(im1, ax=axes[0, 1], fraction=0.046, pad=0.04)
    
    # VARI
    im2 = axes[0, 2].imshow(vari, cmap='RdYlGn', vmin=-1, vmax=1)
    axes[0, 2].set_title('VARI (Atmospheric Resistant)', fontsize=14, fontweight='bold')
    axes[0, 2].axis('off')
    plt.colorbar(im2, ax=axes[0, 2], fraction=0.046, pad=0.04)
    
    # Water mask
    axes[1, 0].imshow(water_mask, cmap='Blues')
    axes[1, 0].set_title('Water Detection Mask', fontsize=14, fontweight='bold')
    axes[1, 0].axis('off')
    
    # RGB with water overlay
    rgb_overlay = rgb.copy()
    rgb_overlay[water_mask] = [0, 100, 255]  # Blue overlay for water
    axes[1, 1].imshow(rgb_overlay)
    axes[1, 1].set_title('RGB + Water Overlay', fontsize=14, fontweight='bold')
    axes[1, 1].axis('off')
    
    # Final combined matrix
    im3 = axes[1, 2].imshow(combined_matrix, cmap='BrBG', vmin=-1, vmax=1)
    axes[1, 2].set_title('Final Vegetation/Water Matrix', fontsize=14, fontweight='bold')
    axes[1, 2].axis('off')
    cbar = plt.colorbar(im3, ax=axes[1, 2], fraction=0.046, pad=0.04)
    cbar.set_label('Vegetation Quality (Land: 0-1, Water: -1-0)', fontsize=10)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"  Visualization saved to: {save_path}")
    
    plt.show()


def process_rgb_image_complete(image_path: str,
                               output_dir: str,
                               target_size: Optional[Tuple[int, int]] = None,
                               shadow_correction: bool = True,
                               use_sam2: bool = False,
                               sam2_checkpoint: Optional[str] = None,
                               vegetation_weights: Tuple[float, float, float] = (0.4, 0.4, 0.2),
                               visualize: bool = True) -> Dict:
    """Complete RGB image processing pipeline.
    
    Args:
        image_path: Path to input RGB image
        output_dir: Directory to save outputs
        target_size: Optional (width, height) to resize
        shadow_correction: Apply shadow correction
        use_sam2: Use SAM2 for water detection
        sam2_checkpoint: Path to SAM2 checkpoint
        vegetation_weights: (ndvi, vari, exg) weights
        visualize: Show visualization
        
    Returns:
        results: Dictionary with all processing results
    """
    print("="*80)
    print("RGB IMAGE PROCESSING PIPELINE")
    print("="*80)
    
    # Step 1: Load image
    rgb, metadata = load_rgb_image(image_path, target_size)
    rgb_original = rgb.copy()
    
    # Step 2: Shadow correction (optional)
    if shadow_correction:
        rgb = apply_shadow_correction(rgb, method='clahe')
    
    # Step 3: Calculate vegetation indices
    ndvi = calculate_ndvi(rgb, method='visible')
    vari = calculate_vari(rgb)
    exg = calculate_excess_green(rgb)
    
    # Step 4: Detect water
    if use_sam2 and sam2_checkpoint:
        water_mask = detect_water_sam2(rgb, checkpoint=sam2_checkpoint)
    else:
        water_mask = detect_water_simple(rgb, ndvi)
    
    # Step 5: Combine vegetation indices
    vegetation_quality = combine_vegetation_indices(ndvi, vari, exg, 
                                                   weights=vegetation_weights)
    
    # Step 6: Apply water mask
    combined_matrix = apply_water_mask(vegetation_quality, water_mask)
    
    # Step 7: Save outputs
    metadata['processing_parameters'] = {
        'shadow_correction': shadow_correction,
        'use_sam2': use_sam2,
        'vegetation_weights': vegetation_weights,
        'target_size': target_size
    }
    
    save_rgb_outputs(output_dir, combined_matrix, ndvi, vari, water_mask, 
                    metadata, rgb_original)
    
    # Step 8: Visualize (optional)
    if visualize:
        viz_path = f"{output_dir}/visualization.png"
        visualize_results(rgb_original, ndvi, vari, water_mask, combined_matrix, 
                         save_path=viz_path)
    
    # Prepare results
    results = {
        'combined_matrix': combined_matrix,
        'ndvi': ndvi,
        'vari': vari,
        'exg': exg,
        'water_mask': water_mask,
        'vegetation_quality': vegetation_quality,
        'metadata': metadata,
        'output_dir': output_dir
    }
    
    print("\n" + "="*80)
    print("✓ PROCESSING COMPLETE")
    print("="*80)
    
    return results

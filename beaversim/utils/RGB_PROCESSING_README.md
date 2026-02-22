# RGB Aerial Image Processing for Beaver Simulation

This module processes RGB aerial images to extract vegetation quality metrics and water detection for beaver habitat simulation.

## Overview

The RGB processing pipeline analyzes aerial imagery to create normalized matrices representing:
- **Vegetation quality** (0-1 range): Based on NDVI, VARI, and Excess Green indices
- **Water bodies** (-1 to 0 range): Detected using color thresholding or SAM2 segmentation

## Features

- **Vegetation Indices**:
  - NDVI (Normalized Difference Vegetation Index): Traditional vegetation metric
  - VARI (Visible Atmospherically Resistant Index): Shadow/atmospheric resistant
  - ExG (Excess Green Index): Green vegetation emphasis

- **Shadow Correction**: CLAHE-based contrast enhancement for variable lighting

- **Water Detection**:
  - Simple thresholding: Fast, color-based detection
  - SAM2 integration: Advanced segmentation using Meta's Segment Anything Model 2

- **Flexible Output**: Compatible with beaver simulation matrix format

## Quick Start

### Interactive Notebook (Recommended)

```bash
cd beaversim/utils
jupyter notebook rgb_conversion_interactive.ipynb
```

The notebook provides step-by-step processing with visualization for:
- Rumney Marsh example images (Sites A1, A2, B1, B2, B3, C1, C5)
- Custom RGB images

### Python API

```python
from beaversim.utils.rgb_to_matrix import process_rgb_image_complete

# Process an RGB image
results = process_rgb_image_complete(
    image_path='./example_datasets/RUMNEY_MARSH/A2/A2_06132018.PNG',
    output_dir='./output/A2_processed',
    shadow_correction=True,
    use_sam2=False,  # Set True if SAM2 is available
    vegetation_weights=(0.4, 0.4, 0.2),  # (NDVI, VARI, ExG)
    visualize=True
)

# Access results
vegetation_matrix = results['combined_matrix']
ndvi = results['ndvi']
water_mask = results['water_mask']
```

## Installation

### Basic Requirements

```bash
pip install -r requirements.txt
```

Includes:
- numpy
- matplotlib
- opencv-python
- Pillow
- pandas
- scipy
- pyproj

### SAM2 (Optional - for Advanced Water Detection)

SAM2 provides superior water stream detection but requires additional setup:

```bash
# Install SAM2
pip install git+https://github.com/facebookresearch/sam2.git

# Download checkpoint (example for large model)
wget https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt
```

Visit [SAM2 GitHub](https://github.com/facebookresearch/sam2) for more checkpoint options.

## Vegetation Indices Explained

### NDVI (Normalized Difference Vegetation Index)
- **Formula**: `(Green - Red) / (Green + Red)` (RGB approximation)
- **Range**: [-1, 1]
- **Interpretation**:
  - \> 0.3: Dense, healthy vegetation
  - 0.1-0.3: Sparse vegetation
  - < 0.1: Non-vegetated (soil, water, urban)
  - < 0: Water, shadows

### VARI (Visible Atmospherically Resistant Index)
- **Formula**: `(Green - Red) / (Green + Red - Blue)`
- **Advantages**: More resistant to atmospheric effects and shadows
- **Use case**: Aerial imagery with variable lighting conditions

### ExG (Excess Green Index)
- **Formula**: `2*Green - Red - Blue`
- **Purpose**: Emphasizes green vegetation vs soil and water
- **Use case**: Distinguishing vegetation from similar-colored backgrounds

## Water Detection Methods

### Simple Thresholding
Fast, rule-based detection using:
- Blue channel dominance
- Low NDVI values
- Moderate brightness range

**Pros**: Fast, no additional dependencies
**Cons**: Less accurate in complex scenes

### SAM2 (Segment Anything Model 2)
Meta's advanced segmentation model:
- Automatic mask generation
- Optional user prompts (points/boxes)
- Handles complex scenes with shadows

**Pros**: High accuracy, robust to shadows
**Cons**: Requires model download, slower processing

## Output Format

All processing generates:

1. **vegetation_matrix.npy**: Final combined matrix
   - Land: [0, 1] vegetation quality
   - Water: [-1, 0] water bodies

2. **ndvi.npy**: NDVI values [-1, 1]

3. **vari.npy**: VARI values [-1, 1]

4. **water_mask.npy**: Boolean water detection mask

5. **processing_metadata.json**: Processing parameters and metadata

6. **visualization.png**: Multi-panel visualization

## Example Datasets

Located in `example_datasets/RUMNEY_MARSH/`:
- **A1, A2**: Rumney Marsh sites with time series (June-August 2018)
- **B1, B2, B3**: Additional marsh sites
- **C1, C5**: Comparative sites
- Some images include `_annotated.PNG` versions for reference

## Handling Challenges

### Shadows
- Enable `shadow_correction=True` (CLAHE)
- Increase VARI weight in vegetation combination
- Use SAM2 for more robust detection

### Variable Terrain
- Adjust water detection thresholds
- Use multiple vegetation indices
- Consider time-series analysis (multiple dates)

### Low Contrast
- Apply CLAHE shadow correction
- Adjust ExG weight to emphasize green
- Try different interpolation methods

## Advanced Usage

### Custom Vegetation Weights

```python
# Emphasize shadow resistance
weights = (0.2, 0.6, 0.2)  # (NDVI, VARI, ExG)

# Emphasize traditional NDVI
weights = (0.7, 0.2, 0.1)

# Balanced approach
weights = (0.4, 0.4, 0.2)
```

### Manual Water Thresholds

```python
from beaversim.utils.rgb_to_matrix import detect_water_simple

water_mask = detect_water_simple(
    rgb, 
    ndvi,
    blue_threshold=80,      # Lower = more sensitive
    ndvi_threshold=0.1,     # Higher = allow more vegetation
    brightness_max=200      # Adjust for image lighting
)
```

### SAM2 with Prompts

```python
from beaversim.utils.rgb_to_matrix import detect_water_sam2

# Define points on water (x, y coordinates)
water_points = [(100, 150), (200, 300)]

# Or define boxes (x1, y1, x2, y2)
water_boxes = [(50, 50, 150, 200)]

water_mask = detect_water_sam2(
    rgb,
    checkpoint='path/to/sam2_checkpoint.pt',
    point_prompts=water_points,
    box_prompts=water_boxes
)
```

## Integration with Beaver Simulation

The output `vegetation_matrix.npy` is compatible with the beaver simulation framework:

```python
import numpy as np

# Load processed vegetation matrix
vegetation_map = np.load('output/A2_processed/vegetation_matrix.npy')

# Use in simulation
# Land areas (positive values) represent vegetation quality
# Water areas (negative values) represent water bodies
```

## Comparison with DEM Processing

| Feature | DEM (Elevation) | RGB (Imagery) |
|---------|-----------------|---------------|
| **Input** | CSV elevation data | PNG/JPG images |
| **Primary metric** | Elevation (meters) | Vegetation indices |
| **Water detection** | Percentile threshold | Color + NDVI / SAM2 |
| **Resolution** | Resampled to target | Native image resolution |
| **Challenges** | Noisy elevation data | Shadows, variable lighting |
| **Best for** | Terrain analysis | Vegetation assessment |

Both methods produce compatible outputs for the simulation framework.

## Troubleshooting

**Issue**: Water mask is empty
- Lower `blue_threshold` (try 60-80)
- Increase `ndvi_threshold` (try 0.1-0.2)
- Check if image has water bodies

**Issue**: Too much area marked as water
- Increase `blue_threshold` (try 120-150)
- Decrease `ndvi_threshold` (try -0.1 to 0)
- Adjust `brightness_max`

**Issue**: Shadow artifacts
- Enable `shadow_correction=True`
- Increase VARI weight
- Consider using SAM2

**Issue**: SAM2 import error
- Install SAM2: `pip install git+https://github.com/facebookresearch/sam2.git`
- Download model checkpoint
- Verify checkpoint path

## References

- **NDVI**: [Normalized Difference Vegetation Index](https://en.wikipedia.org/wiki/Normalized_difference_vegetation_index)
- **VARI**: Gitelson et al. (2002) - Spectral reflectance for vegetation indices
- **SAM2**: [Meta Segment Anything Model 2](https://github.com/facebookresearch/sam2)
- **CLAHE**: Contrast Limited Adaptive Histogram Equalization

## License

Part of the BeaverSim project. See main repository for license information.

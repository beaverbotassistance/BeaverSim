
# imports
import numpy as np
import random
from scipy.interpolate import CubicSpline
import beaversim.constants as const

# general measure mode
def measure(map: np.ndarray, position: tuple, mode: str, step: int = 1) -> tuple:
    
    if mode is 'full_map':
        measure_positions = 'all'
        measure_values = [map.copy(), map[position[0]][position[1]]]
        return measure_positions, measure_values
    
    # Split exploration_mode into two parts: prefix and suffix
    if len(mode) > 2:
        _prefix = mode[:-3]
        _suffix = int(mode[-3:])
    else:
        _prefix = mode
        _suffix = None            
    
    if _prefix == 'D':
        measure_positions = measure_DN(map, position, N=_suffix, step=step)
    elif _prefix == 'gradient_D':
        measure_positions = measure_DN(map, position, N=_suffix, step=step)
        gradient_matrix, values_matrix = matrix_gradient(map, measure_positions)
        measure_positions, _ = find_monotonic_indices(values_matrix, position)
        measure_positions = np.clip(measure_positions, [0, 0], [map.shape[0] - 1, map.shape[1] - 1])            
    else:
        raise ValueError('Invalid mode')
    
    measure_values = []
    for pos in measure_positions:
        measure_values.append(map[pos[0],pos[1]])
    
    return measure_positions, measure_values
    
# Generalized DN measure
def measure_DN(map: np.ndarray, position: tuple, N: int = 4, step: int = 1) -> list:
    limits = get_map_limits(map)
    neighbourhood = DN_neighbourhood(position, limits, N, step)
    return neighbourhood
    
# Generalized DN neighbourhood
def DN_neighbourhood(position: tuple, limits: np.ndarray, N: int = 4, step: int = 1) -> list:
    
    offset = const.DN_box(side=N+1, step=step)        
    
    neighbourhood = [tuple(np.add(position, o)) for o in offset]
    
    # Ensure all positions in the neighbourhood are within the map limits    
    neighbourhood = [pos for pos in neighbourhood if limits[0][0] <= pos[0] <= limits[0][1] and limits[1][0] <= pos[1] <= limits[1][1]]
    neighbourhood.append(tuple(position)) # ensure the center is included

    return neighbourhood

# get map limits
def get_map_limits(map: np.ndarray) -> np.ndarray:
    return np.array([[0, map.shape[0]-1], [0, map.shape[1]-1]])    

# matrix gradient
def matrix_gradient(matrix: np.ndarray, neighbours: list) -> tuple:
        
    # Determine the bounds of the submatrix
    min_x = min(neighbour[0] for neighbour in neighbours)
    max_x = max(neighbour[0] for neighbour in neighbours)
    min_y = min(neighbour[1] for neighbour in neighbours)
    max_y = max(neighbour[1] for neighbour in neighbours)

    # Create a padded submatrix filled with NaN
    values_matrix_size = max(max_x - min_x + 1, max_y - min_y + 1)
    dd = values_matrix_size // 2
        
    # create the gradient matrix    
    values_matrix = np.full((values_matrix_size,values_matrix_size), np.nan)
    gradient_matrix = np.full((values_matrix_size,values_matrix_size), np.nan)
    center_x, center_y = values_matrix_size // 2, values_matrix_size // 2  # Center of the submatrix corresponds to the position     
    global_center_x, global_center_y = min_x + center_x, min_y + center_y  # Center of the matrix corresponds to the position    
    
    # populate the center of the matrix
    gradient_matrix[center_x, center_y] = 0
    values_matrix[center_x, center_y] = matrix[global_center_x, global_center_y]

    for neighbour in neighbours:
        x, y = neighbour
        if 0 <= x < matrix.shape[0] and 0 <= y < matrix.shape[1]:
            dx, dy = x - global_center_x, y - global_center_y
            if -dd <= dx <= dd and -dd <= dy <= dd:
                values_matrix[center_x + dx, center_y + dy] = matrix[x, y] 
                gradient_matrix[center_x + dx, center_y + dy] = matrix[x, y] - matrix[global_center_x, global_center_y]
    
    return gradient_matrix, values_matrix

# find monotonic indices
def find_monotonic_indices(values_matrix: np.ndarray, center: tuple) -> tuple:
    
    directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    monotonic_indices = []
    monotonic_indices_global = []
    
    dd = values_matrix.shape[0] // 2  

    center_value = values_matrix[dd][dd]
    for dx, dy in directions:
        x, y = dd, dd
        prev_value = center_value
        direction_indices = []

        while True:
            x += dx
            y += dy

            # Check bounds
            if x < 0 or y < 0 or x >= values_matrix.shape[0] or y >= values_matrix.shape[1]:
                break

            current_value = values_matrix[x, y]

            # Stop if NaN or sequence breaks
            if np.isnan(current_value) or (current_value < prev_value and current_value > prev_value):
                break

            # Add to the sequence
            direction_indices.append((x, y))
            prev_value = current_value

        # Add the valid indices for this direction
        if direction_indices:
            monotonic_indices.extend(np.array(direction_indices))

    monotonic_indices.extend(np.array([[dd, dd]]))
    monotonic_indices_global = monotonic_indices + np.array(center) - dd
    monotonic_matrix = np.full(values_matrix.shape, np.nan)
    for idx in monotonic_indices:
        monotonic_matrix[idx[0]][idx[1]] = values_matrix[idx[0]][idx[1]]
        
    return monotonic_indices_global, monotonic_matrix

    


    
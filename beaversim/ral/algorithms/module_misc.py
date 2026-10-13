
# imports
import numpy as np
import beaversim.constants as const

# full map measure: agents observe the whole environment map
def measure(map: np.ndarray, position: tuple) -> tuple:
    return map.copy(), map[position[0]][position[1]]

# Generalized DN neighbourhood
def DN_neighbourhood(position: tuple, limits: np.ndarray, N: int = 4, step: int = 1) -> list:

    offset = const.DN_box(side=N+1, step=step)

    neighbourhood = [tuple(np.add(position, o)) for o in offset]

    # Ensure all positions in the neighbourhood are within the map limits
    neighbourhood = [pos for pos in neighbourhood if (limits[0][0] <= pos[0] <= limits[0][1]) and (limits[1][0] <= pos[1] <= limits[1][1])]
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

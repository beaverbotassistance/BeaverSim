import numpy as np
import beaversim.ral.algorithms.module_misc as module_misc

def exploration_gradient_DN(
    position: tuple[int, int],
    limits: tuple[tuple[int, int], tuple[int, int]],
    local_map: np.ndarray,
    N: int = 4,
    home_base_store: list | None = None,
    eta: float = 1.0,
    step: int = 1,
    *,
    rng: np.random.Generator
) -> tuple[list, list, int]:
    """
    Select next exploration position using gradient-based probabilistic selection (softmax with eta parameter).

    Args:
        position: Current (x, y) position of the agent.
        limits: ((x_min, x_max), (y_min, y_max)) bounds for the map.
        local_map: 2D array of vegetation quality or exploration values.
        N: Neighborhood size for exploration.
        home_base_store: List of home base positions to mask out.
        eta: Softmax temperature parameter (higher = greedier selection).
        step: Step size for neighborhood generation.
        rng: Seeded generator of the calling agent (required for reproducible runs).

    Returns:
        neighbourhood: List of selected next positions.
        [False] * len(neighbourhood): Placeholder for compatibility.
        0: Placeholder for compatibility.
    """
    if home_base_store is None:
        home_base_store = []

    # Zero out home bases in local map
    local_map = local_map.copy()
    for home_base in home_base_store:
        if limits[0][1] >= home_base[0] and limits[1][1] >= home_base[1]:
            local_map[home_base[0]][home_base[1]] = 0

    # Gradient-based mode: probabilistic selection using vegetation gradient
    neighbourhood = module_misc.DN_neighbourhood(position, limits, N, step=step)
    gradient_matrix, _ = module_misc.matrix_gradient(local_map, neighbourhood)

    # Convert matrix indices to direction vectors
    cx, cy = gradient_matrix.shape[0] // 2, gradient_matrix.shape[1] // 2
    directions = np.argwhere(~np.isnan(gradient_matrix))

    # Calculate possible positions and their gradient values
    new_positions: list = []
    gradient_values: list = []
    for i, j in directions:
        dir_vec = [i - cx, j - cy]  # [dx, dy], inverse of matrix_gradient's [cx + dx, cy + dy]
        pos = [position[0] + dir_vec[0], position[1] + dir_vec[1]]
        if pos != list(position):  # Exclude current position
            new_positions.append(pos)
            gradient_values.append(gradient_matrix[i, j])

    try:
        # Filter NaN values
        gradient_values_arr = np.array(gradient_values)
        finite_mask = ~np.isnan(gradient_values_arr)
        finite_values = gradient_values_arr[finite_mask]
        finite_positions = [new_positions[i] for i in range(len(new_positions)) if finite_mask[i]]

        # Softmax selection: higher gradient = higher probability
        scaled = finite_values * eta - np.max(finite_values * eta)
        probs = np.exp(scaled) / np.sum(np.exp(scaled))
        neighbourhood = [finite_positions[rng.choice(len(finite_positions), p=probs)]]

    except (ValueError, IndexError):
        # Fallback: select nearby position
        distances = [np.linalg.norm(np.array(pos) - np.array(position)) for pos in neighbourhood]
        zero_idx = [i for i, d in enumerate(distances) if d == 0.0]
        if zero_idx:
            distances[zero_idx[0]] = np.inf  # Exclude current position
        max_dist = np.max(distances) if distances else 4.0
        valid_idx = [i for i, d in enumerate(distances) if 0 < d <= max_dist]
        neighbourhood = [neighbourhood[rng.choice(valid_idx) if valid_idx else 0]]

    return neighbourhood, [False] * len(neighbourhood), 0
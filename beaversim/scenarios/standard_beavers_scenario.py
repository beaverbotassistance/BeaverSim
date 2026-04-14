from beaversim.ral.backend.base_backend import BaseBackend
from beaversim.ral.environment.environment_beavers_backend import BeaversEnvironmentBackend
from IPython.display import clear_output
from tqdm import tqdm
import os
import glob
from typing import Any, Dict

def standard_beavers_scenario(config: Dict[str, Any]) -> Any:
    """
    Run the standard beavers simulation scenario.

    Args:
        config: Configuration dictionary for simulation parameters.

    Returns:
        Backend: The backend object after simulation.
    """
    # Initialize backend
    Basebackend = BaseBackend()
    Backend = Basebackend.initiate_backend(**config)

    # Number of steps (in hours)
    number_of_steps = int(config.get('simulation').get('number_of_steps')) * 24
    downsampling = int(config.get('simulation').get('downsampling'))
    save_path = config.get('simulation').get('save_path')
    file_name = config.get('simulation').get('file_name')
    max_snapshot_index = number_of_steps // downsampling
    snapshot_index_width = len(str(max_snapshot_index))

    # Initialize agents
    Backend.generate_agents(**config)

    # Clear save folder before starting
    if os.path.isdir(save_path):
        for f in glob.glob(os.path.join(save_path, '*.npy')):
            os.remove(f)

    # Simulation cycle
    for i in range(number_of_steps):
        if i % downsampling == 0:
            Backend.plot_environment_with_heatmap(plot_agents=False)
            save_path_final = get_snapshot_save_path(
                i // downsampling, save_path, file_name, snapshot_index_width)
            Backend.save_environment_map(save_path_final)
            # Backend.plot_simulation_recap()
        Backend.step()
        clear_output(wait=True)

    # Final plots
    Backend.plot_environment_with_heatmap(plot_agents=False)
    Backend.plot_simulation_recap()
    save_path_final = get_snapshot_save_path(
        number_of_steps // downsampling, save_path, file_name, snapshot_index_width)
    Backend.save_environment_map(save_path_final)

    return Backend

def get_snapshot_save_path(
    snapshot_index: int,
    save_path: str = 'output',
    file_name: str = 'environment_map',
    snapshot_index_width: int = 4
) -> str:
    """
    Generate a padded file path for saving simulation snapshots.

    Args:
        snapshot_index: Index of the snapshot.
        save_path: Directory to save the snapshot.
        file_name: Base file name for the snapshot.
        snapshot_index_width: Width for zero-padding the index.

    Returns:
        str: Full file path for the snapshot.
    """
    padded_index = f"{snapshot_index:0{snapshot_index_width}d}"
    return os.path.join(save_path, f"{file_name}_{padded_index}.npy")

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

    # Number of steps (in dt)
    number_of_steps = int(config.get('simulation').get('number_of_steps') * 24 / Backend._timedelta)
    downsampling = int(config.get('simulation').get('downsampling') * 24 / Backend._timedelta)
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
            Backend.plot_environment_with_heatmap(
                plot_agents=False, 
                plot_visit_markers=False, 
                plot_agent_trajectories=False,
                plot_motion_destination=False,
            )            
            Backend.save_environment_map(save_path, i // downsampling)
        Backend.step()
        clear_output(wait=True)

    # Final plots
    Backend.plot_environment_with_heatmap(
        plot_agents=False, 
        plot_visit_markers=False, 
        plot_agent_trajectories=False,
        plot_motion_destination=False,
    )        
    Backend.save_environment_map(save_path, i // downsampling)
    Backend.save_backend_pickle(os.path.join(save_path, "final_backend.pkl"))

    return Backend
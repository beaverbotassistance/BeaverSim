from beaversim.ral.backend.base_backend import BaseBackend
from beaversim.ral.environment.environment_beavers_backend import BeaversEnvironmentBackend
from IPython.display import clear_output
from tqdm import tqdm
import os
import glob

def standard_beavers_scenario(config):        
    
    # init backend
    Basebackend = BaseBackend()     
    Backend = Basebackend.initiate_backend(**config)    
    
    # number of steps (in hours)
    number_of_steps = int(config.get('simulation').get('number_of_steps')) * 24    
    downsampling = config.get('simulation').get('downsampling')
    save_path = config.get('simulation').get('save_path')
    file_name = config.get('simulation').get('file_name')
    max_snapshot_index = number_of_steps // downsampling
    snapshot_index_width = len(str(max_snapshot_index))    
        
    # init agents    
    Backend.generate_agents(**config)    
    
    # Clear save folder before starting
    if os.path.isdir(save_path):
        for f in glob.glob(os.path.join(save_path, '*.npy')):
            os.remove(f)
    
    # cycle
    for i in range(number_of_steps):     
        if i % downsampling == 0:
            Backend.plot_environment_with_heatmap(plot_agents=False)
            save_path_final = get_snapshot_save_path(i // downsampling, \
                save_path, file_name, snapshot_index_width)
            Backend.save_environment_map(save_path_final)
            # Backend.plot_simulation_recap()
                
        Backend.step()
        clear_output(wait=True)
    
    # final plots
    Backend.plot_environment_with_heatmap(plot_agents=False) 
    Backend.plot_simulation_recap()
    save_path_final = get_snapshot_save_path(number_of_steps // downsampling, \
        save_path, file_name, snapshot_index_width)
    Backend.save_environment_map(save_path_final)
    
    return Backend

def get_snapshot_save_path(snapshot_index, save_path='output', file_name='environment_map', snapshot_index_width=4):
        padded_index = f"{snapshot_index:0{snapshot_index_width}d}"
        return os.path.join(save_path, f"{file_name}_{padded_index}.npy")
        
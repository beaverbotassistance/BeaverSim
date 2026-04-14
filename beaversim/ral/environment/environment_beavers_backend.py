# Import parent class
from beaversim.ral.environment.environment_backend import BaseEnvironmentBackend

# The BeaversEnvironmentBackend class transforms raw geographic data into a standardized NxM matrix representing spatial vegetation quality.
class BeaversEnvironmentBackend(BaseEnvironmentBackend):
    """Backend for Beavers environment simulation."""    
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        
    def initiate_environment(self, **kwargs):
        """Initialize environment: load terrain, setup growth parameters, initialize time tracking."""
        super().initiate_environment(**kwargs)
        
        # General parameters
        self._vegetation_quality_range = self._environment.get('vegetation_quality_range')
        self._print = self._environment.get('print')
        self._visits_reset = self._environment.get('visits_reset')
        
        # River parameters
        flow_info = self._environment.get('flow_info', {'direction': [0, 0], 'strength': 0, 'streams_depth': 10})
        self._streams_depth = flow_info.get('streams_depth', 10)
        self._flow_direction = flow_info.get('direction', [0, 0])
        self._flow_strength = flow_info.get('strength', 0)
        self._river_growth_velocity = flow_info.get('river_growth_velocity', 0.0)
        self._river_growth_interval = flow_info.get('river_growth_interval', [-3, 0])
        
        # Grass growth parameters (2.6% per day = 0.00107/hour, 3 weeks to full growth)
        self._grass_growth_rate = self._environment.get('grass_growth_rate', 1e-5)        
        self._grass_growth_interval = self._environment.get('grass_growth_interval')
        self._grass_growth_sigma = self._environment.get('grass_growth_sigma', 0.3)
        self._mean_reversion_strength = self._environment.get('mean_reversion_strength', 0.0005)
        
        # Map file path
        self._elevation_file_path = self._environment.get('elevation_file_path', None)
        
        # Load map (sets self._width, self._height, self._map_original)
        self.load_map_from_file()
        
        # Initialize map state
        self._initial_map = self._map_original.copy()
        self._map = self._map_original.copy()
        self._map_visits = self.np.zeros(self._map_original.shape)
        self._map_visits_roles = self.np.zeros(self._map_original.shape)
        
        # Time tracking
        self._current_time = 0
        self._current_day = []
        self._current_hour = []
        self._time_of_day = []
        self.update_time_of_day()
        # Growth stats tracking
        self._init_growth_stats()
        
        # Home base
        self._home_base_position_store = None                
        
        return self   
    
    def _init_growth_stats(self):
        self._growth_stats = {
            'day': [],
            'growth_factor_mean': [],
            'growth_factor_std': [],
            'veg_mean': [],
            'veg_std': [],
            'random_growth_mean': [],
            'random_growth_std': []
        }
    
    def update_time_of_day(self) -> None:
        """Update time of day (currently always 'day')."""
        self._current_hour = self._current_time % 24
        self._current_day = self._current_time // 24
        
        # Currently always 'day' (remove "or True" to enable day/night cycle)
        if self._current_hour > 6 and self._current_hour < 18 or True:
            self._time_of_day = 'day'
        else:
            self._time_of_day = 'night'   
    
    def step_environment(self, dt, map, map_visits, home_base_position_store, grass_growth_interval, misc) -> None:
        """Update environment for one time step: update maps, grow grass, deepen rivers."""
        self._current_time += dt
        self.update_time_of_day()
        
        # Update maps from agent observations
        self._map = map.copy()
        self._map_visits = map_visits.copy()
        map_visits_roles = misc.get('map_visits_roles', self.np.zeros(self._map_original.shape))
        self._map_visits_roles = map_visits_roles.copy()
        self._home_base_position_store = home_base_position_store

        # Grow grass and deepen rivers
        self.grow_grass(grass_growth_interval, self._grass_growth_rate)
        self.grow_rivers()
        
        if self._print:
            print(f"Environment step at time {self._current_time}")
    
    def load_map_from_file(self) -> None:
        """Load elevation map from .npy file, transform coordinates, and rescale values."""
        if self._elevation_file_path is None:
            raise ValueError("Elevation file path must be provided")
        
        try:
            elevation_data = self.np.load(self._elevation_file_path)
        except Exception as e:
            raise ValueError(f"Error loading NPY file: {str(e)}")
        
        # Transform coordinates: DEM (rows=y, cols=x, origin=lower-left) -> Environment ([x,y], origin=top-left)
        elevation_data = self.np.flipud(elevation_data)
        elevation_data = self.np.rot90(elevation_data, -1)
        self._width, self._height = elevation_data.shape
        
        # Replace NaN with 0.0
        elevation_data = self.np.nan_to_num(elevation_data, nan=0.0)
        
        # Linear rescaling to simulation range
        min_val = self.np.min(elevation_data)
        max_val = self.np.max(elevation_data)
        target_min = -self._streams_depth
        target_max = self._vegetation_quality_range[1]
        
        if max_val > min_val:
            self._map_original = (elevation_data - min_val) / (max_val - min_val) * (target_max - target_min) + target_min
            rescaling_info = f"[{min_val:.3f}, {max_val:.3f}] -> [{target_min:.3f}, {target_max:.3f}]"
        else:
            self._map_original = elevation_data * 0 + (target_max + target_min) / 2
            rescaling_info = f"Constant {min_val:.3f} -> {(target_max + target_min) / 2:.3f}"
        
        if self._print:
            print(f"Loaded map: {self._elevation_file_path}")
            print(f"Size: {self._width}x{self._height}, Range: {self.np.min(self._map_original):.3f} to {self.np.max(self._map_original):.3f}")
            print(f"Rescaling: {rescaling_info}")

    def grow_grass(self, grass_growth_interval, base_rate) -> None:
        """
        Simulate vegetation growth with a skewed seasonal structure and a seasonal stable mean state.
        Growth follows a skewed normal seasonal curve (right-skewed: fast rise, slow decay),
        while a mean-reversion feedback keeps the average vegetation close to a seasonal target.
        """
        
        # Requires scipy for skewnorm 
        from scipy.stats import skewnorm
        
        growth_mask = (self._map >= grass_growth_interval[0]) & (self._map <= grass_growth_interval[1])
        vegetation_mask = (self._map > 0.05)
        if not self.np.any(growth_mask):
            # Save day, mean_growth, veg_mean, veg_std        
            self._growth_stats['day'].append(int(self._current_day))
            self._growth_stats['growth_factor_mean'].append(float(self._growth_stats['growth_factor_mean'][-1]) if self._growth_stats['growth_factor_mean'] else 0.0)
            self._growth_stats['growth_factor_std'].append(float(self._growth_stats['growth_factor_std'][-1]) if self._growth_stats['growth_factor_std'] else 0.0)
            self._growth_stats['veg_mean'].append(float(self._growth_stats['veg_mean'][-1]) if self._growth_stats['veg_mean'] else 0.0)
            self._growth_stats['veg_std'].append(float(self._growth_stats['veg_std'][-1]) if self._growth_stats['veg_std'] else 0.0)
            return

        # --- Time-dependent mean growth rate (skewed normal, peak in April/June, slow decay) ---               
        days_in_year = 365
        day_of_year = int(self._current_day) % days_in_year
        
        # --- Parameters for the seasonal curve ---
        peak_day = 90  # Peak at end of March
        width = 50      # Controls width of the season (higher = longer season)
        skew = 5        # Positive = right-skewed (slow decay after peak)
                
        # Center the distribution at peak_day
        sn_pdf = skewnorm.pdf(day_of_year, a=skew, loc=peak_day, scale=width)
        # Find max for normalization (peak at peak_day)
        max_pdf = skewnorm.pdf(peak_day, a=skew, loc=peak_day, scale=width)
        sn_norm = sn_pdf / max_pdf if max_pdf > 0 else 0.0
        
        # Baseline for winter decay
        baseline = -1.0 * base_rate
        mean_growth = baseline + 2.0 * base_rate * sn_norm
        
        # Allow for stronger negative growth in winter (simulate decay):
        min_growth = -2 * base_rate
        max_growth = 2 * base_rate
        mean_growth = self.np.clip(mean_growth, min_growth, max_growth)
        
        # Seasonal stable state: preserve the skewed seasonal structure while keeping
        # the average vegetation close to a seasonal target mean.
        current_mean = float(self.np.mean(self._map[growth_mask]))
        initial_mask_values = self._initial_map[growth_mask]
        initial_mean = float(self.np.mean(initial_mask_values)) if initial_mask_values.size > 0 else current_mean
        max_vegetation = float(self._vegetation_quality_range[1])
        
        target_mean_winter = self.np.clip(0.8 * initial_mean, 0.05, max_vegetation)
        target_mean_summer = self.np.clip(1.2 * initial_mean, 0.05, max_vegetation)
        target_mean = target_mean_winter + (target_mean_summer - target_mean_winter) * sn_norm
        mean_feedback = self._mean_reversion_strength * (target_mean - current_mean)
        effective_mean_growth = self.np.clip(mean_growth + mean_feedback, min_growth, max_growth)
        
        # Per-pixel randomization using the environment RNG stream.
        # This avoids coupling with global NumPy random state seeded elsewhere.
        random_growth = self.rng.normal(
            loc=effective_mean_growth,
            scale=self._grass_growth_sigma * abs(base_rate),
            size=self._map.shape
        )
        
        # Clip to min_growth (allow negative, but not too much)
        random_growth = self.np.clip(random_growth, min_growth, max_growth)
        random_growth[~growth_mask] = 0.0

        # Apply only to growth_mask
        self._map = self._map + random_growth
        # Enforce lower and upper bounds
        self._map[growth_mask] = self.np.clip(self._map[growth_mask], 0.05, self._vegetation_quality_range[1])
        
        # --- Store stats for visualization ---
        veg_values = self._map[vegetation_mask]
        veg_mean = float(self.np.mean(veg_values)) if veg_values.size > 0 else 0.0
        veg_std = float(self.np.std(veg_values)) if veg_values.size > 0 else 0.0
        
        # Save day, mean_growth, veg_mean, veg_std        
        self._growth_stats['day'].append(int(self._current_day))
        self._growth_stats['growth_factor_mean'].append(float(effective_mean_growth))
        self._growth_stats['growth_factor_std'].append(float(self.np.std(random_growth[growth_mask])))
        self._growth_stats['veg_mean'].append(veg_mean)
        self._growth_stats['veg_std'].append(veg_std)
        self._growth_stats['random_growth_mean'].append(float(self.np.mean(random_growth[growth_mask])))
        self._growth_stats['random_growth_std'].append(float(self.np.std(random_growth[growth_mask])))

    def grow_rivers(self) -> None:
        """Simulate river deepening by subtracting growth velocity."""
        if self._river_growth_velocity > 0:
            negative_mask = (self._map >= self._river_growth_interval[0]) & (self._map <= self._river_growth_interval[1])
            self._map[negative_mask] = self._map[negative_mask] - self._river_growth_velocity
            self._map[negative_mask] = self.np.clip(
                self._map[negative_mask],
                self._river_growth_interval[0],
                self._river_growth_interval[1]
            )
        
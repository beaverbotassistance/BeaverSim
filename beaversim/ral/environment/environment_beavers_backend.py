# Import parent class
from beaversim.ral.environment.environment_backend import BaseEnvironmentBackend
from typing import Any, Dict, Optional

class BeaversEnvironmentBackend(BaseEnvironmentBackend):
    """Backend for Beavers environment simulation."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def initiate_environment(self, **kwargs) -> 'BeaversEnvironmentBackend':
        """
        Initialize environment: load terrain, setup growth parameters, initialize time tracking.
        Only parameters from the config/environment dictionary are used; all others are hardcoded.
        """
        super().initiate_environment(**kwargs)
        env: Dict[str, Any] = self._environment
        self._vegetation_quality_range = env.get('vegetation_quality_range')
        self._print = env.get('print')
        self._visits_reset = env.get('visits_reset')
        
        # River parameters
        flow_info = env.get('flow_info', {'direction': [0, 0], 'strength': 0, 'streams_depth': 10})
        self._streams_depth = flow_info.get('streams_depth', 10)
        self._flow_direction = flow_info.get('direction', [0, 0])
        self._flow_strength = flow_info.get('strength', 0.0)
        self._river_growth_velocity = flow_info.get('river_growth_velocity', 0.0)
        self._river_growth_interval = flow_info.get('river_growth_interval', [-3, 0])
        
        # Grass growth parameters
        self._grass_growth_rate = env.get('grass_growth_rate', 5e-4)
        self._grass_growth_interval = env.get('grass_growth_interval', [0, 8])
        self._grass_growth_sigma = env.get('grass_growth_sigma', 1.0)
        self._mean_reversion_strength = env.get('mean_reversion_strength', 0.0005)
        
        # Map file path
        self._elevation_file_path = env.get('elevation_file_path', None)
        
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

    def _init_growth_stats(self) -> None:
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

    def step_environment(
        self,
        dt: int,
        map: Any,
        map_visits: Any,
        home_base_position_store: Any,
        grass_growth_interval: Optional[list],
        misc: dict
    ) -> None:
        """
        Update environment for one time step: update maps, grow grass, deepen rivers.
        """
        # --- 1. Advance simulation time and update time of day ---
        self._current_time += dt
        self.update_time_of_day()

        # --- 2. Update maps from agent observations ---
        self._map = map.copy()
        self._map_visits = map_visits.copy()
        map_visits_roles = misc.get('map_visits_roles', self.np.zeros(self._map_original.shape))
        self._map_visits_roles = map_visits_roles.copy()
        self._home_base_position_store = home_base_position_store

        # --- 3. Grow grass and deepen rivers ---
        self.grow_grass(self._grass_growth_interval, self._grass_growth_rate)
        self.grow_rivers()

        # --- 4. Optional debug print ---
        if self._print:
            print(f"Environment step at time {self._current_time}")

    def load_map_from_file(self) -> None:
        """
        Load elevation map from .npy file, transform coordinates, and rescale values.
        """
        # --- 1. Check for valid file path ---
        if self._elevation_file_path is None:
            raise ValueError("Elevation file path must be provided")
        try:
            elevation_data = self.np.load(self._elevation_file_path)
        except Exception as e:
            raise ValueError(f"Error loading NPY file: {str(e)}")

        # --- 2. Transform coordinates to simulation convention ---
        elevation_data = self.np.flipud(elevation_data)
        elevation_data = self.np.rot90(elevation_data, -1)
        self._width, self._height = elevation_data.shape

        # --- 3. Replace NaN with 0.0 ---
        elevation_data = self.np.nan_to_num(elevation_data, nan=0.0)

        # --- 4. Linear rescaling to simulation range ---
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
        # --- 5. Optional debug print ---
        if self._print:
            print(f"Loaded map: {self._elevation_file_path}")
            print(f"Size: {self._width}x{self._height}, Range: {self.np.min(self._map_original):.3f} to {self.np.max(self._map_original):.3f}")
            print(f"Rescaling: {rescaling_info}")

    def grow_grass(self, grass_growth_interval: list, base_rate: float) -> None:
        """
        Simulate vegetation growth with a skewed seasonal structure and a seasonal stable mean state.
        Growth follows a skewed normal seasonal curve (right-skewed: fast rise, slow decay),
        while a mean-reversion feedback keeps the average vegetation close to a seasonal target.
        """
        from scipy.stats import skewnorm
        # --- 1. Compute growth and vegetation masks ---
        # 1.1. growth_mask: Where grass is allowed to grow (elevation in allowed interval)
        # 1.2. vegetation_mask: Where there is any vegetation (for stats)
        growth_mask = (self._map >= grass_growth_interval[0]) & (self._map <= grass_growth_interval[1])
        vegetation_mask = (self._map > 0.05)
        if not self.np.any(growth_mask):
            # 1.3. If no growth possible, propagate previous stats and exit
            self._growth_stats['day'].append(int(self._current_day))
            self._growth_stats['growth_factor_mean'].append(float(self._growth_stats['growth_factor_mean'][-1]) if self._growth_stats['growth_factor_mean'] else 0.0)
            self._growth_stats['growth_factor_std'].append(float(self._growth_stats['growth_factor_std'][-1]) if self._growth_stats['growth_factor_std'] else 0.0)
            self._growth_stats['veg_mean'].append(float(self._growth_stats['veg_mean'][-1]) if self._growth_stats['veg_mean'] else 0.0)
            self._growth_stats['veg_std'].append(float(self._growth_stats['veg_std'][-1]) if self._growth_stats['veg_std'] else 0.0)
            return

        # --- 2. Compute seasonal growth curve ---
        # 2.1. Calculate day of year for seasonal effect
        days_in_year = 365
        day_of_year = int(self._current_day) % days_in_year
        # 2.2. Skewed normal parameters: peak, width, skewness
        peak_day = 90  # Peak at end of March
        width = 50     # Controls width of the season (higher = longer season)
        skew = 5       # Positive = right-skewed (slow decay after peak)
        # 2.3. Compute normalized seasonal growth factor (0=winter, 1=peak)
        sn_pdf = skewnorm.pdf(day_of_year, a=skew, loc=peak_day, scale=width)
        max_pdf = skewnorm.pdf(peak_day, a=skew, loc=peak_day, scale=width)
        sn_norm = sn_pdf / max_pdf if max_pdf > 0 else 0.0

        # --- 3. Compute mean growth and mean-reversion feedback ---
        # 3.1. Baseline for winter decay (negative growth)
        baseline = -1.0 * base_rate
        # 3.2. Mean growth for this day (seasonal)
        mean_growth = baseline + 2.0 * base_rate * sn_norm
        # 3.3. Clamp mean growth to allowed range
        min_growth = -2 * base_rate
        max_growth = 2 * base_rate
        mean_growth = self.np.clip(mean_growth, min_growth, max_growth)
        # 3.4. Compute current and initial mean vegetation in growth_mask
        current_mean = float(self.np.mean(self._map[growth_mask]))
        initial_mask_values = self._initial_map[growth_mask]
        initial_mean = float(self.np.mean(initial_mask_values)) if initial_mask_values.size > 0 else current_mean
        max_vegetation = float(self._vegetation_quality_range[1])
        # 3.5. Compute seasonal target mean (winter/summer)
        target_mean_winter = self.np.clip(0.8 * initial_mean, 0.05, max_vegetation)
        target_mean_summer = self.np.clip(1.2 * initial_mean, 0.05, max_vegetation)
        target_mean = target_mean_winter + (target_mean_summer - target_mean_winter) * sn_norm
        # 3.6. Mean-reversion feedback: pulls mean towards seasonal target
        mean_feedback = self._mean_reversion_strength * (target_mean - current_mean)
        # 3.7. Effective mean growth (seasonal + feedback, clamped)
        effective_mean_growth = self.np.clip(mean_growth + mean_feedback, min_growth, max_growth)

        # --- 4. Per-pixel randomization using the environment RNG stream ---
        # 4.1. Each cell gets a random growth value centered at effective_mean_growth
        random_growth = self.rng.normal(
            loc=effective_mean_growth,
            scale=self._grass_growth_sigma * abs(base_rate),
            size=self._map.shape
        )
        # 4.2. Clamp random growth to allowed range
        random_growth = self.np.clip(random_growth, min_growth, max_growth)
        # 4.3. Only apply growth to valid cells
        random_growth[~growth_mask] = 0.0

        # --- 5. Apply growth and enforce bounds ---
        # 5.1. Add random growth to map
        self._map = self._map + random_growth
        # 5.2. Clamp vegetation to allowed range in growth_mask
        self._map[growth_mask] = self.np.clip(self._map[growth_mask], 0.05, self._vegetation_quality_range[1])

        # --- 6. Store stats for visualization ---
        # 6.1. Compute stats for current vegetation
        veg_values = self._map[vegetation_mask]
        veg_mean = float(self.np.mean(veg_values)) if veg_values.size > 0 else 0.0
        veg_std = float(self.np.std(veg_values)) if veg_values.size > 0 else 0.0
        # 6.2. Store all relevant stats for this day
        self._growth_stats['day'].append(int(self._current_day))
        self._growth_stats['growth_factor_mean'].append(float(effective_mean_growth))
        self._growth_stats['growth_factor_std'].append(float(self.np.std(random_growth[growth_mask])))
        self._growth_stats['veg_mean'].append(veg_mean)
        self._growth_stats['veg_std'].append(veg_std)
        self._growth_stats['random_growth_mean'].append(float(self.np.mean(random_growth[growth_mask])))
        self._growth_stats['random_growth_std'].append(float(self.np.std(random_growth[growth_mask])))

    def grow_rivers(self) -> None:
        """
        Simulate river deepening by subtracting growth velocity.
        """
        # --- 1. Deepen rivers in specified elevation range ---
        if self._river_growth_velocity > 0:
            negative_mask = (self._map >= self._river_growth_interval[0]) & (self._map <= self._river_growth_interval[1])
            self._map[negative_mask] = self._map[negative_mask] - self._river_growth_velocity
            self._map[negative_mask] = self.np.clip(
                self._map[negative_mask],
                self._river_growth_interval[0],
                self._river_growth_interval[1]
            )

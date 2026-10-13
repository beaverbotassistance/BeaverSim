
# 1. General imports
from mesa import Agent, Model
from mesa.time import RandomActivation

# 2. Backend imports
from beaversim.ral.backend.base_backend import BaseBackend
from beaversim.ral.robot.robot_beavers_backend import BeaversRobotBackend
from beaversim.ral.environment.environment_beavers_backend import BeaversEnvironmentBackend

# 3. Module imports
import beaversim.ral.algorithms.module_misc as module_misc
from typing import Any, Dict, Optional, List, Tuple



class BeaversVisualizerBackend(BaseBackend, Model):
    """
    Visualization backend for Beavers earth-moving simulation.

    Responsibilities:
    1. Manage simulation parameters and agent/environment instantiation.
    2. Step through simulation time, updating environment and agents.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        1. Initialize the visualization backend with simulation parameters.
        2. Set up random number generators and scheduler.
        3. Store configuration and prepare for agent/environment creation.
        """
        # BaseBackend.__init__ does not chain, so initialize both parents explicitly
        BaseBackend.__init__(self, **kwargs)
        Model.__init__(self)
        self._kwargs: Dict[str, Any] = kwargs
        simulation: Optional[Dict[str, Any]] = self._kwargs.get('simulation')
        if simulation is None:
            raise ValueError("Missing 'simulation' configuration in kwargs.")

        # 1. Set simulation parameters from config
        self._seed: int = simulation.get('seed', 0)
        self.rng = self.np.random.default_rng(self._seed)
        # Mesa seeds self.random in __new__ from a 'seed' kwarg we never pass, so reseed it here
        self.reset_randomizer(self._seed)
        self._timedelta: float = simulation.get('timedelta', 1.0)
        self._schedule_policy: str = simulation.get('schedule_policy', 'sequential')
        self._N_agents: int = simulation.get('number_of_agents', 1)
        self._print: bool = simulation.get('print', False)

        # 2. Mesa scheduler and state
        self._schedule: RandomActivation = RandomActivation(self)
        self._current_time: float = 0.0

    def generate_agents(self, **kwargs: Any) -> None:
        """
        1. Generate environment and agent instances for the simulation.
        2. Initialize the environment agent (not added to scheduler).
        3. Add beaver agents to the scheduler.
        """
        # 1. Generate environment agent
        self._environment: EnvironmentVisualizerAgent = EnvironmentVisualizerAgent(self._N_agents, self, **kwargs)
        self._environment.rng = self.np.random.default_rng(self._seed)
        self._width: int = self._environment._width
        self._height: int = self._environment._height

        # 2. Generate beaver agents
        for i in range(self._N_agents):
            agent = BeaversVisualizerAgent(i, self, **kwargs)
            agent.rng = self.np.random.default_rng(self._seed + i + 1)
            self._schedule.add(agent)

    def step(self) -> None:
        """
        1. Advance the simulation by one time step.
        2. Update current time.
        3. Step the environment first, then all agents according to schedule policy.
        4. Raise ValueError if schedule policy is invalid.
        """
        self._current_time += self._timedelta

        # 1. Step environment first
        if not hasattr(self, '_environment') or self._environment is None:
            raise RuntimeError("Environment not initialized. Call generate_agents() first.")
        self._environment.step()

        # 2. Step agents according to schedule policy
        if self._schedule_policy == 'sequential':
            sorted_agents = sorted(self._schedule.agents, key=lambda agent: agent.unique_id)
            for agent in sorted_agents:
                agent.step()
        elif self._schedule_policy == 'random':
            self._schedule.step()
        else:
            raise ValueError(f"Invalid schedule policy: {self._schedule_policy}")
    


class BeaversVisualizerAgent(BeaversRobotBackend, Agent):
    """
    Beaver agent for visualization-based simulations.

    1. Inherits robot logic and agent interface.
    2. Steps through simulation, measuring environment and updating state.
    3. Links environment data and flow information for agent logic.
    """

    def __init__(self, unique_id: int, model: BeaversVisualizerBackend, **kwargs: Any) -> None:
        """
        1. Initialize the beaver agent with unique ID and model reference.
        2. Set up robot backend and agent state.
        3. Store simulation time delta.
        """
        BeaversRobotBackend.__init__(self, **kwargs)
        Agent.__init__(self, unique_id, model)
        self.initiate_robot(**kwargs)
        self._timedelta: float = model._timedelta

    def step(self) -> None:
        """
        1. Execute one simulation step for the beaver agent.
        2. Measure environment at current position.
        3. Link environment and flow data to agent.
        4. Step beaver logic and update environment map.
        """
        # 1. Get data from environment
        dt: float = self._timedelta
        time_of_day: str = self.model._environment._time_of_day
        local_map, cell_value = module_misc.measure(self.model._environment._map, self._position)

        # 2. Get map limits
        limits = module_misc.get_map_limits(self.model._environment._map)

        # 3. Link environment data to agent
        self._vegetation_quality_range = self.model._environment._vegetation_quality_range
        self._range_x = self.model._environment._width
        self._range_y = self.model._environment._height
        self._home_base_position_store = self.model._environment._home_base_position_store

        # 4. Link flow information
        misc = {
            'direction': self.model._environment._flow_direction,
            'strength': self.model._environment._flow_strength,
            'visits': self.model._environment._map_visits_roles
        }

        # 5. Step the agent
        self.step_beaver(dt, time_of_day, local_map, cell_value, limits, misc)


class EnvironmentVisualizerAgent(BeaversEnvironmentBackend, Agent):
    """
    Environment agent for visualization-based simulations.

    1. Aggregates agent activities and updates environmental state.
    2. Inherits environment backend and agent interface.
    3. Steps through simulation, updating maps and home base positions.
    """

    def __init__(self, unique_id: int, model: BeaversVisualizerBackend, **kwargs: Any) -> None:
        """
        1. Initialize the environment agent with unique ID and model reference.
        2. Set up environment backend and agent state.
        3. Store simulation time delta.
        """
        BeaversEnvironmentBackend.__init__(self, **kwargs)
        Agent.__init__(self, unique_id, model)
        self.initiate_environment(**kwargs)
        self._timedelta: float = model._timedelta
        self._init_plotting_stats()

    def _init_plotting_stats(self) -> None:
        self._plotting_stats = {
            'water_pixel_density': [],
            'land_pixel_density': [],
            'land_pixel_mean': [],
            'explorer_spatial_footprint': [],
            'explorer_canalization_ratio': [],
            'builder_spatial_footprint': [],
            'builder_canalization_ratio': []
        }

    def store_plotting_stats(self) -> None:
        """
        Store pixel densities for water/land, and track the absolute spatial footprint
        and active canalization ratios (traffic share of the top 5% active cells).
        """
        total_pixels = self._width * self._height

        # --- WATER & LAND STATS ---
        water_pixel_density = float(self.np.sum(self._map < 0.0) / total_pixels)
        land_pixel_density = float(self.np.sum(self._map >= 0.0) / total_pixels)
        land_pixel_mean = float(self.np.mean(self._map >= 0.0))

        # =====================================================================
        # --- EXPLORER TRAIL STATS (Negative values) ---
        # =====================================================================
        # 1. ABSOLUTE SPATIAL FOOTPRINT (Using an independent permanent explorer footprint)
        explorer_footprint_mask = (self._map_visits_roles_explorer != 0)
        explorer_footprint = int(self.np.sum(explorer_footprint_mask))
        explorer_canalization = 0.0
        
        # 2. Extract ONLY the active traffic from the decaying map for canalization
        active_mask_e = (self._map_visits_roles < -1e-3)
        active_values_e = self.np.abs(self._map_visits_roles[active_mask_e])
        
        if explorer_footprint > 0 and len(active_values_e) > 0:
            # Volume of traffic on top 5% of active cells
            total_traffic_e = float(self.np.sum(active_values_e))
            if total_traffic_e > 0:
                top_5_threshold_e = float(self.np.percentile(active_values_e, 95))
                heavy_traffic_vol_e = float(self.np.sum(active_values_e[active_values_e >= top_5_threshold_e]))
                explorer_canalization = heavy_traffic_vol_e / total_traffic_e

        # =====================================================================
        # --- BUILDER TRAIL STATS (Positive values) ---
        # =====================================================================
        # 1. ABSOLUTE SPATIAL FOOTPRINT (Using an independent permanent builder footprint)
        builder_footprint_mask = (self._map_visits_roles_builder != 0)
        builder_footprint = int(self.np.sum(builder_footprint_mask))
        builder_canalization = 0.0
        
        # 2. Extract ONLY the active traffic from the decaying map for canalization
        active_mask_b = (self._map_visits_roles > 1e-3)
        active_values_b = self._map_visits_roles[active_mask_b]
        
        if builder_footprint > 0 and len(active_values_b) > 0:
            # Volume of traffic on top 5% of active cells
            total_traffic_b = float(self.np.sum(active_values_b))
            if total_traffic_b > 0:
                top_5_threshold_b = float(self.np.percentile(active_values_b, 95))
                heavy_traffic_vol_b = float(self.np.sum(active_values_b[active_values_b >= top_5_threshold_b]))
                builder_canalization = heavy_traffic_vol_b / total_traffic_b

        # --- STORE STATS ---
        self._plotting_stats['water_pixel_density'].append(water_pixel_density)
        self._plotting_stats['land_pixel_density'].append(land_pixel_density)
        self._plotting_stats['land_pixel_mean'].append(land_pixel_mean)
        
        self._plotting_stats['explorer_spatial_footprint'].append(explorer_footprint)
        self._plotting_stats['explorer_canalization_ratio'].append(explorer_canalization)
        
        self._plotting_stats['builder_spatial_footprint'].append(builder_footprint)
        self._plotting_stats['builder_canalization_ratio'].append(builder_canalization)

    def step(self) -> None:
        """
        1. Aggregate agent activities and update environmental state.
        2. Collect visit maps and home base positions from all agents.
        3. Update map and visits for explorer/expander roles.
        4. Step the environment backend with updated data.
        5. Handles errors gracefully if agent data is missing.
        """
        # 1. Aggregate visit maps from all agents
        map_visits = self._map_visits.copy()
        map_visits_roles = self._map_visits_roles.copy()
        map = self._map.copy()
        home_base_position_store: List[Tuple[int, int]] = []

        for agent in self.model._schedule.agents:
            if isinstance(agent, BeaversVisualizerAgent):
                if getattr(agent, '_local_map_visits', None) is not None:
                    try:
                        map_visits[agent._position[0], agent._position[1]] = agent._local_map_visits[agent._position[0], agent._position[1]]
                        map[agent._position[0], agent._position[1]] = agent._map_quality_measure_position
                        if getattr(agent, '_role', None) == 'explorer':
                            map_visits_roles[agent._position[0], agent._position[1]] = -map_visits[agent._position[0], agent._position[1]]
                        else:
                            map_visits_roles[agent._position[0], agent._position[1]] = map_visits[agent._position[0], agent._position[1]]
                    except Exception as e:
                        print(f"Error updating map visits for agent {agent}: {e}")
                if getattr(agent, '_home_base_position_store', None) is not None:
                    for pos in agent._home_base_position_store:
                        home_base_position_store.append(pos)

        map_visits = map_visits * self._visits_reset
        map_visits_roles = map_visits_roles * self._visits_reset
        misc = {'map_visits_roles': map_visits_roles}
        home_base_position_store = list(set(tuple(pos) for pos in self.np.array(home_base_position_store)))

        # 2. Step the environment
        self.step_environment(self._timedelta, map, map_visits, home_base_position_store, misc)

        # 3. Collect stats for plotting AFTER environment has been updated
        self.store_plotting_stats()
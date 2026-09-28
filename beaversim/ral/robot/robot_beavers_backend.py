
from beaversim.ral.robot.robot_backend import BaseRobotBackend
from beaversim.ral.robot.modules.module_control import Controller, Dynamics
import beaversim.ral.algorithms.module_misc as module_misc
import beaversim.ral.robot.modules.module_beaver as module_beaver


class BeaversRobotBackend(BaseRobotBackend):
    """
    Backend for beaver robot agent logic, including task selection, movement, harvesting, and adaptive exploration.
    
    This class manages the robot's state, decision-making, and interaction with the environment.
    Main methods implement a finite state machine for agent behavior, with utilities for map and state updates.
    """
    
    def initiate_robot(self, **kwargs) -> 'BeaversRobotBackend':
        """
        Initialize the robot's parameters and internal state.

        Args:
            **kwargs: Additional keyword arguments (passed to parent).

        Returns:
            BeaversRobotBackend: self
        """
        super().initiate_robot(**kwargs)
        
        # get resolution from environment config
        resolution_m = 1.0
        if getattr(self, 'model', None) is not None:
            try:
                resolution_m = float(getattr(self.model._environment, '_resolution_m', 1.0))
            except (TypeError, ValueError):
                resolution_m = 1.0
        if resolution_m <= 0:
            resolution_m = 1.0
        self._resolution_m = resolution_m

        # Parameters loaded from external config
        home_base_position = self._robot.get('home_base_position')
        if home_base_position is None:
            raise ValueError('home_base_position must be defined')

        home_base_position_list = list(home_base_position)
        if home_base_position_list and isinstance(home_base_position_list[0], (list, tuple, self.np.ndarray)):
            self._home_base_position_store = [[int(coord / resolution_m) for coord in pos] for pos in home_base_position_list]
            self._home_base_position = [self._home_base_position_store[0]]
        else:
            self._home_base_position_store = [[int(coord / resolution_m) for coord in home_base_position_list]]
            self._home_base_position = [self._home_base_position_store[0]]
        self._maximum_load = self._robot.get('maximum_load')                        
        self._harvest_interval = self._robot.get('harvest_interval')
        self._epsilon_greedy = self._robot.get('epsilon_greedy')        
        self._decay_values = self._robot.get('decay_values')        
        self._vegetation_removal = self._robot.get('vegetation_removal')
        self._visit_increase = self._robot.get('visit_increase')
        self._exploration_map = self._robot.get('exploration_map')        
        self._print = self._robot.get('print')
        
        # I would like to random pick the role.
        role_list = self._robot.get('role')
        n_roles = len(role_list) if isinstance(role_list, list) else 1
        if n_roles >= 1:
            selected_role = self.random.choice(role_list)
            self._role = selected_role
        
        # get the values depending on the role
        if self._role == 'explorer':            
            self._harvest_interval = self._harvest_interval[0]
            self._exploration_map = self._exploration_map[0]
            self._epsilon_greedy = self._epsilon_greedy[0]  
            self._maximum_load = self._maximum_load[0]
            self._vegetation_removal = self._vegetation_removal[0]      
        elif self._role == 'builder':                        
            self._harvest_interval = self._harvest_interval[1]
            self._exploration_map = self._exploration_map[1]
            self._epsilon_greedy = self._epsilon_greedy[1]
            self._maximum_load = self._maximum_load[1]
            self._vegetation_removal = self._vegetation_removal[1]
        else:
            raise ValueError(f'Invalid role: {self._role}')
        
        self._maximum_load_init = self._maximum_load

        # Hardcoded parameters (not from config)
        self._exploration_N_recovery = int(8 / resolution_m)
        self._range_x = [int(-5 / resolution_m), int(5 / resolution_m)]
        self._range_y = [int(-5 / resolution_m), int(5 / resolution_m)]       
        

        self._exploration_distance_m = 10.0
        exploration_cells = max(1, int(round(float(self._exploration_distance_m) / resolution_m)))
        self._exploration_mode = f'gradient_D{exploration_cells:03d}'
        self._measurement_mode = 'full_map'
        self._measure_step = 1
        self._n_traces = 0
        self._exploration_eta = 1.0

        self._current_time = 0
        self._map_quality_measure = None
        self._map_quality_measure_position = None
        self._map_quality_update = False
        self._motion_destination = None
        self._neighbourhood = None
        self._neighbourhood_reached_flag = None
        self._neighbourhood_current_index = None
        self._local_map = None
        self._local_map_visits = None
        self._harvesting_actions_counter = 0
        self._in_water_counter = 0
        self._reset_integral = 50
        self._min_home_distance = 500
        self._last_explored_position = None

        self._vegetation_quality_range = None

        # Position initialization
        position = 'random_home'
        if position == 'random':
            self._position = [self.random.randint(self._range_x[0], self._range_x[1] - 1),
                              self.random.randint(self._range_y[0], self._range_y[1] - 1)]
        elif position == 'home':
            self._position = self._home_base_position[0]
        elif position == 'random_home':
            # Choose a random home base from the list
            if isinstance(self._home_base_position_store, list) and len(self._home_base_position_store) > 0:
                selected_base = list(self.random.choice(self._home_base_position_store))
                # Randomly select a position around the chosen home base within the allowed range
                self._position = [
                    selected_base[0] + self.random.randint(self._range_x[0], self._range_x[1] - 1),
                    selected_base[1] + self.random.randint(self._range_y[0], self._range_y[1] - 1)
                ]
            else:
                raise ValueError('home_base_position must be a non-empty list for random_home initialization')
        elif position is None:
            self._position = [0, 0]
        elif isinstance(position, list):
            self._position = position
            self._position[0] = self.np.clip(self._position[0], self._range_x[0], self._range_x[1])
            self._position[1] = self.np.clip(self._position[1], self._range_y[0], self._range_y[1])
        else:
            raise ValueError('Invalid position value: {}'.format(position))

        self._load = 0
        self._controller = Controller(**self._robot)
        self._controller._max = self._exploration_distance_m / 2
        initial_state = self.np.array([self._position, self.np.zeros(self._controller._dimension)])
        self._dynamics = Dynamics(initial_state, **self._robot)
        self._local_map_control = None

        self._status_robot = 'IDLE'
        self._status_task = 'IDLE'
        self._status_motion = 'IDLE'
        self._current_task = None
        self._current_action = None

        self._destination_store = []
        self._action_store = []
        self._position_store = []
        self._error_store = []
        self._load_store = []
        self._task_store = []
        self._time_store = []
        self._exploration_eta_store = []
        self._harvest_interval_store = []
        self._maximum_load_store = []

        self._exploration_eta_init = self._exploration_eta
        self._harvest_interval_init = self._harvest_interval.copy()
        self._wait_b4_explore_init = 24.0
        self._wait_b4_explore = 0.0
        return self
    
    def step_beaver(self, dt: float, time_of_day: str, map_quality: list, limits: list, misc: dict = None) -> None:
        """
        Main step function for the beaver agent. Updates state, decides and executes tasks, and manages adaptation.

        Args:
            dt (int): Time increment.
            time_of_day (str): Current time of day (e.g., 'day').
            map_quality (list): Environmental quality measurements.
            limits (list): Movement boundaries.
            misc (dict, optional): Additional info from environment.
        """

        # --- 1. Update time and controller/dynamics integration step ---
        self._current_time += dt
        self._controller._dt = dt
        self._dynamics._dt = dt
        self._dt_init = dt

        # --- 2. Gather and update environmental observations ---
        self._map_quality_measure = map_quality
        self._map_quality_measure_position = self._map_quality_measure[1][-1]  # Current cell quality
        self.update_local_map(self._map_quality_measure, misc)
        self._map_quality_update = False

        # --- 3. Periodically reset controller integral error ---
        if self._current_time % self._reset_integral == 0:
            self._controller._error_integral = 0.0

        # --- 4. Decide and execute the agent's next task ---
        self.decide_task(time_of_day, limits, misc)
        self.do_task(time_of_day, limits, misc)

        # --- 5. Adapt exploration/harvest parameters if needed ---
        self.select_exploration_eta(dt=self._wait_b4_explore_init, dt_percentage=0.25, decay=self._decay_values)

        # --- 6. Check if environment needs to be updated (after harvest/store) ---
        needs_env_update = (
            (self._current_task == 'harvest' and self._status_task == 'FINISHED') or
            (self._current_task == 'store' and (
                self._status_task == 'FINISHED' or
                (self._status_task == 'INPROGRESS' and self._status_motion == 'FINISHED')
            ))
        )
        self._map_quality_update = needs_env_update

        # --- 7. If environment was updated, refresh local map at current position ---
        if self._map_quality_update:
            self._map_quality_measure = [[self._position], [self._map_quality_measure_position]]
            self.update_local_map(self._map_quality_measure, misc)
        self._map_quality_measure_position = self._local_map[self._position[0], self._position[1]]

        # --- 8. Store step data for analysis/debugging ---
        self._destination_store.append(self._motion_destination)
        self._action_store.append(self._current_action)
        self._position_store.append(self._position)
        self._error_store.append(self._controller._error)
        self._load_store.append(self._load)
        self._task_store.append(self._current_task)
        self._time_store.append(time_of_day)
        self._exploration_eta_store.append(self._exploration_eta)
        self._harvest_interval_store.append(self._harvest_interval.copy())
        self._maximum_load_store.append(self._maximum_load)

        # --- 9. Optional debug print ---
        if self._print:
            print(f't= {self._current_time}: Agent {self.unique_id} is doing {self._current_action}')
            
    ############################################################
    # POLICIES AND IMPLEMENTATIONS
    ############################################################

    def decide_task(self, time_of_day: str, limits: list, misc: dict = None) -> None:
        """
        Decide the next task for the agent based on current state and policy.

        Args:
            time_of_day (str): Current time of day.
            limits (list): Movement boundaries.
            misc (dict, optional): Additional info.
        """

        # --- 1. Close the FSM loop if the current task is finished ---
        if self._status_task == 'FINISHED':
            self._status_task = 'IDLE'

        # --- 2. Task selection logic ---
        cond_atomic = True  # Always true for atomic implementation

        # Epsilon-greedy: with probability epsilon, allow random exploration
        rand = self.random.uniform(0, 1)
        cond_rand = rand < self._epsilon_greedy

        # --- 3. Task decision based on state ---
        # Priority: store if full, then harvest if in range, else explore
        if cond_atomic and (
            self._load >= self.np.floor(self._maximum_load) or
            self._maximum_load <= 0.1 * self._maximum_load_init
        ):
            self._current_task = 'store'
        elif (
            cond_atomic and cond_rand and
            self._map_quality_measure_position > 1 * self._harvest_interval[0] and
            self._map_quality_measure_position < self._harvest_interval[1] and
            (not any(
                self._position[0] == pos[0] and self._position[1] == pos[1]
                for pos in self._home_base_position_store
            ))
        ):
            self._current_task = 'harvest'
        else:            
            self._current_task = 'explore'

        # --- 4. Set the task status to STARTING for the new cycle ---
        self._status_task = 'STARTING'
       
    def do_task(self, time_of_day: str = None, limits: list = None, misc: dict = None) -> None:
        """
        Execute the current task based on its type (explore, harvest, store).

        Args:
            time_of_day (str, optional): Current time of day.
            limits (list, optional): Movement boundaries.
            misc (dict, optional): Additional info.
        """

        # --- 1. Handle each task type with its initialization logic ---
        if self._current_task == 'explore':
            # On first entry, initialize neighborhood and set status
            if self._status_task == 'STARTING':
                self.get_neighbourhood()
                self._status_task = 'INPROGRESS'
            # Perform exploration step
            self.explore(time_of_day, limits, misc)

        elif self._current_task == 'harvest':
            # On first entry, set status to INPROGRESS
            if self._status_task == 'STARTING':
                self._status_task = 'INPROGRESS'
            # Perform harvesting step
            self.harvest(time_of_day, limits, misc)

        elif self._current_task == 'store':
            # On first entry, set destination to closest home base and set status
            if self._status_task == 'STARTING':
                self.set_home_base_position()
                self._status_task = 'INPROGRESS'
            # Perform storing step
            self.store(time_of_day, limits, misc)

        else:
            raise ValueError(f'Invalid task: {self._current_task}')
    
    def do_action(self, time_of_day: str = None, limits: list = None, misc: dict = None) -> bool:
        """
        Execute the current action and return success status.

        Args:
            time_of_day (str, optional): Current time of day.
            limits (list, optional): Movement boundaries.
            misc (dict, optional): Additional info.

        Returns:
            bool: True if action was executed as requested, False otherwise.
        """        
        requested_action = self._current_action
        
        # Execute the action based on time of day
        if time_of_day == 'day':
            if self._current_action == 'move':
                self._status_robot = 'ACTING'
                self.move(time_of_day, limits, misc)
            elif self._current_action == 'remove_vegetation':
                self._status_robot = 'ACTING'
                self.remove_vegetation(time_of_day, limits, misc)
            elif self._current_action == 'idle':
                self._status_robot = 'IDLE'
        else:
            raise ValueError('Invalid time_of_day: {}'.format(time_of_day))
        
        return requested_action == self._current_action
        
    ############################################################
    # TASKS
    ############################################################
    
    def harvest(self, time_of_day: str = None, limits: list = None, misc: dict = None) -> None:
        """
        Task: Remove vegetation at the current position.

        Args:
            time_of_day (str, optional): Current time of day.
            limits (list, optional): Movement boundaries.
            misc (dict, optional): Additional info.
        """
        # Set the current action to remove vegetation
        self._current_action = 'remove_vegetation'

        # Attempt to perform the action
        success = self.do_action(time_of_day, limits, misc)

        # If the action was successful, mark the task as finished
        if success:
            self._status_task = 'FINISHED'

    def explore(self, time_of_day: str = None, limits: list = None, misc: dict = None) -> None:
        """
        Task: Explore the environment by visiting neighborhood cells.

        Args:
            time_of_day (str, optional): Current time of day.
            limits (list, optional): Movement boundaries.
            misc (dict, optional): Additional info.
        """
        # --- Decide the next exploration action based on motion status ---
        if self._status_motion == 'IDLE':
            # Agent is ready to select a new cell to explore
            try:
                # Find the next unexplored cell in the neighborhood
                self._neighbourhood_current_index = self._neighbourhood_reached_flag.index(False)
            except ValueError:
                # All neighborhood cells have been explored
                self._neighbourhood_current_index = None

            if self._neighbourhood_current_index is not None:
                # Set the next cell as the motion destination
                self._motion_destination = [
                    self._neighbourhood[self._neighbourhood_current_index][0],
                    self._neighbourhood[self._neighbourhood_current_index][1]
                ]
                # Ensure the destination is within movement limits
                if limits is not None:
                    self._motion_destination[0] = self.np.clip(
                        self._motion_destination[0], limits[0][0], limits[0][1]
                    )
                    self._motion_destination[1] = self.np.clip(
                        self._motion_destination[1], limits[1][0], limits[1][1]
                    )
                # Set action and status for movement
                self._current_action = 'move'
                self._status_task = 'INPROGRESS'
            else:
                # No more cells to explore; finish the task
                self._motion_destination = None
                self._current_action = 'idle'
                self._status_task = 'FINISHED'

        elif self._status_motion == 'ACTIVE':
            # Agent is currently moving to a destination
            self._current_action = 'move'
            self._status_task = 'INPROGRESS'

        elif self._status_motion == 'FINISHED':
            # Agent has reached the destination; mark cell as explored
            self._neighbourhood_reached_flag[self._neighbourhood_current_index] = True
            # Reset controller errors for next move
            self._controller._error_integral = 0.0
            self._controller._error_old = 0.0
            self._controller._dt = self._dt_init
            self._dynamics._dt = self._dt_init
            self._current_action = 'move'
            self._status_task = 'FINISHED'

        else:
            # Unexpected motion status
            raise ValueError(f'Invalid status_motion: {self._status_motion}')
        
        ####### DEBUG - HARD CODED DESTINATION (REMOVE THIS) #######
        # self._motion_destination = [int(90*self._resolution_m), int(450*self._resolution_m)]

        # Execute the decided action (move or idle)        
        self.do_action(time_of_day, limits, misc)
        
    def store(self, time_of_day: str = None, limits: list = None, misc: dict = None) -> None:
        """
        Task: Move to home base and store collected vegetation.

        Args:
            time_of_day (str, optional): Current time of day.
            limits (list, optional): Movement boundaries.
            misc (dict, optional): Additional info.
        """
        # --- 1. Set up for storing: move towards home base ---
        self._current_action = 'move'
        self._last_explored_position = self._position.copy() 

        # Attempt to move to home base
        success = self.do_action(time_of_day, limits, misc)

        # --- 2. If arrived at home base, store vegetation and reset state ---
        if success and self._status_motion == 'FINISHED':
            # Store the collected vegetation at home base
            self.store_vegetation(time_of_day, limits)

            # Restore original control gains after storing
            self._controller._Kp = self._controller._Kp_init
            self._controller._Kd = self._controller._Kd_init
            self._controller._Ki = self._controller._Ki_init

            # Reset task and agent state for next cycle
            self._status_task = 'FINISHED'
            self._current_action = 'idle'
            self._in_water_counter = 0
            self._maximum_load = self._maximum_load_init

    ############################################################
    # ACTIONS
    ############################################################
    
    def move(self, time_of_day: str = None, limits: list = None, misc: dict = None) -> None:
        """
        Action: Move towards destination using the selected controller.

        Args:
            time_of_day (str, optional): Current time of day.
            limits (list, optional): Movement boundaries.
            misc (dict, optional): Additional info (e.g., flow direction/strength).
        """                
                
        setpoint = self._motion_destination
        
        # --- 1. Pre-calculate static elements for P_repulsive (Optimization) ---
        # The local map doesn't change during micro-steps, so we evaluate this ONCE outside the loop.        
        if self._controller._name == 'P_repulsive':
            if self._controller._map_repulsive == 'vegetation_quality':                
                self._local_map_control = self._local_map.copy()**2            
            elif self._controller._map_repulsive == 'vegetation_visits':
                self._local_map_control = self._local_map.copy()**2 / (1 + self._local_map_visits.copy()**2)
            else:
                raise ValueError(f'Invalid map_repulsive value: {self._controller._map_repulsive}')
                
            flow_direction = self.np.array(misc.get('direction', [1, 0]))
            flow_strength = misc.get('strength', 1.0)
            
            # Apply harvest interval mask to local map control to create repulsion from non-harvestable areas
            harvest_mask = (self._local_map >= self._harvest_interval[0]) & (self._local_map <= self._harvest_interval[1])
            self._local_map_control[harvest_mask] = 0

        # --- 2. Use the current simulation dt directly (no micro-stepping) ---
        dt_total = self._controller._dt if self._controller._dt is not None else self._dt_init
        self._controller._dt = dt_total
        self._dynamics._dt = dt_total

        # A. Evaluate Controller
        if self._controller._name == 'P':
            self._controller.step(setpoint, self._position)

        elif self._controller._name == 'P_repulsive':
            _neighbourhood = module_misc.DN_neighbourhood(
                self._position, limits, N=self._controller._neighbourhood_size, step=self._measure_step
            )

            _neighbourhood_values = [
                self._local_map_control[int(pos[0]), int(pos[1])] for pos in _neighbourhood
            ]                                    
            
            if self._local_map[self._position[0], self._position[1]] < 0.0:
                self._controller.step(setpoint, self._position, [_neighbourhood, _neighbourhood_values, flow_direction, flow_strength])
            else:
                self._controller.step(setpoint, self._position, [_neighbourhood, _neighbourhood_values, flow_direction, 0.0])
        else:
            raise ValueError(f'Invalid controller name: {self._controller._name}')

        # B. Integrate the dynamics using the calculated force
        force = self._controller._output
        self._dynamics.step(force)

        # C. Update the agent's continuous position
        self._position = self._dynamics._output[0].copy()

        # Apply boundaries
        self._position[0] = self.np.clip(self._position[0], limits[0][0], limits[0][1])
        self._position[1] = self.np.clip(self._position[1], limits[1][0], limits[1][1])
                 
        # --- 4. Final state updates and constraints ---                            
        # integer position for map indexing and consistency
        self._position = [int(coord) for coord in self._position]
        
        # Update motion status for the FSM
        self._status_motion = self._controller._status
        
    def remove_vegetation(self, time_of_day: str = None, limits: list = None, misc: dict = None) -> None:
        """
        Action: Remove vegetation at current position and add to load.

        Args:
            time_of_day (str, optional): Current time of day.
            limits (list, optional): Movement boundaries.
            misc (dict, optional): Additional info.
        """
        # Cannot harvest from water (negative quality means water)
        if self._map_quality_measure_position < 0:
            return

        # Edge case: vegetation_removal should be positive
        if self._vegetation_removal is None or self._vegetation_removal <= 0:
            return

        # Calculate the value after removal
        post_removal_value = self._map_quality_measure_position - self._vegetation_removal

        # Check if removal would result in negative values (water creation)
        if post_removal_value < 0:
            # Check if there's a river (negative value) in D8 neighborhood
            if limits is not None:
                # Get D8 neighborhood around current position
                d8_neighborhood = module_misc.DN_neighbourhood(self._position, limits, N=2, step=self._measure_step)

                # Check if any neighboring cell has negative values (is water/river)
                river_nearby = False
                for neighbor_pos in d8_neighborhood:
                    neighbor_x, neighbor_y = int(neighbor_pos[0]), int(neighbor_pos[1])

                    # Check bounds to avoid index errors
                    if (0 <= neighbor_x < self._local_map.shape[0] and 
                        0 <= neighbor_y < self._local_map.shape[1]):

                        if self._local_map[neighbor_x, neighbor_y] < 0:
                            river_nearby = True
                            break

                # Only allow digging to negative values if river is nearby
                if not river_nearby:
                    # Limit removal to prevent going below 0
                    max_allowed_removal = max(0, 0.99 * self._map_quality_measure_position)
                    if max_allowed_removal > 0:
                        actual_removal = min(self._vegetation_removal, max_allowed_removal)
                        self._harvesting_actions_counter += 1
                        self._map_quality_measure_position -= actual_removal
                        self._load += actual_removal
                    return

        # Normal harvesting (either won't go negative, or river is nearby)
        self._harvesting_actions_counter += 1
        self._map_quality_measure_position -= self._vegetation_removal
        self._load += self._vegetation_removal

    def store_vegetation(self, time_of_day: str = None, limits: list = None, misc: dict = None) -> bool:
        """
        Action: Store collected vegetation at home base position.

        Args:
            time_of_day (str, optional): Current time of day.
            limits (list, optional): Movement boundaries.
            misc (dict, optional): Additional info.

        Returns:
            bool: True if vegetation was stored, False otherwise.
        """
        # Edge case: vegetation_quality_range must be set and valid
        if not self._vegetation_quality_range or len(self._vegetation_quality_range) != 2:
            return False

        # Edge case: nothing to store
        if self._load is None or self._load <= 0:
            return False

        # Calculate available space at home base
        max_quality = self._vegetation_quality_range[1]
        min_quality = self._vegetation_quality_range[0]
        current_quality = self._map_quality_measure_position
        available_space = self.np.inf * max_quality - self.np.ceil(current_quality)

        if available_space > 0:
            # Store as much as possible, up to available space
            store_amount = min(available_space, self._load)
            self._map_quality_measure_position += store_amount
            self._map_quality_measure_position = self.np.clip(self._map_quality_measure_position, min_quality, max_quality)
            self._load -= store_amount
            return True
        else:
            return False
        s
    ############################################################
    # UTILITIES
    ############################################################
        
    def get_neighbourhood(self) -> None:
        """
        Compute the neighborhood cells to explore based on exploration strategy and agent role.
        Updates self._neighbourhood, self._neighbourhood_reached_flag, and self._neighbourhood_current_index.
        """

        # Early exit if neighborhood is already computed and not all reached
        if self._neighbourhood is not None and self._neighbourhood_reached_flag is not None:
            if self.np.any(self._neighbourhood_reached_flag) == False:
                return

        # Edge case: ensure local maps are initialized
        if self._local_map is None or self._vegetation_quality_range is None:
            self._neighbourhood = []
            self._neighbourhood_reached_flag = []
            self._neighbourhood_current_index = None
            return

        # Current position
        position = self._position

        # Behavioral logic model
        eps = 1e0
        threshold_mask = (self._local_map >= self._harvest_interval[0]) & (self._local_map <= self._harvest_interval[1])

        # Copy maps for manipulation
        local_map = self._local_map.copy()
        local_visits_map = self._local_map_visits.copy()

        # Rescale local_visits_map between 0 and max vegetation quality
        visits_min = self.np.nanmin(local_visits_map)
        visits_max = self.np.nanmax(local_visits_map)
        if visits_max > visits_min:  # Avoid division by zero
            local_visits_map = (local_visits_map - visits_min) / (visits_max - visits_min) * self._vegetation_quality_range[1]
        else:
            local_visits_map = self.np.zeros_like(local_visits_map)

        # Apply exploration strategy based on map type and agent role
        if self._exploration_map == 'vegetation_quality':
            local_map[~threshold_mask] = self.np.nan
            if self._role == 'explorer':
                local_map[threshold_mask] = (eps + local_map[threshold_mask]) ** 2
            elif self._role == 'builder':
                local_map[threshold_mask] = 1 / (eps + local_map[threshold_mask]) ** 2
        elif self._exploration_map == 'vegetation_visits':
            local_map[~threshold_mask] = self.np.nan
            if self._role == 'explorer':
                local_map[threshold_mask] = (eps + local_visits_map[threshold_mask]) ** 1 * (eps + local_map[threshold_mask]) ** 1
            elif self._role == 'builder':
                local_map[threshold_mask] = (eps + local_visits_map[threshold_mask]) ** 1 / ((eps + local_map[threshold_mask]) ** 1)
        else:
            raise ValueError(f'Invalid exploration_map value: {self._exploration_map}')

        # Set movement limits based on local map size
        if self._local_map is not None:
            limits = [[0, self._local_map.shape[0] - 1], [0, self._local_map.shape[1] - 1]]
        else:
            limits = [[self._position[0], self._position[0]], [self._position[1], self._position[1]]]

        # Parse exploration mode into prefix and suffix
        if len(self._exploration_mode) > 2:
            exploration_prefix = self._exploration_mode[:-3]
            exploration_suffix = int(self._exploration_mode[-3:])
        else:
            exploration_prefix = self._exploration_mode
            exploration_suffix = None

        # Compute neighborhood using the selected exploration strategy
        if exploration_prefix == 'gradient_D':
            neighbourhood_cells, reached_flags, current_index = module_beaver.exploration_gradient_DN(
                position, limits, local_map, N=exploration_suffix,
                home_base_store=self._home_base_position_store, eta=self._exploration_eta,
                N_recovery=self._exploration_N_recovery, step=self._measure_step)
        else:
            raise ValueError(f'Invalid exploration mode: {self._exploration_mode}')

        # Assign results to class attributes
        self._neighbourhood = neighbourhood_cells
        self._neighbourhood_reached_flag = reached_flags
        self._neighbourhood_current_index = current_index                
        
        
    def update_local_map(self, map_quality: list, misc: dict = None) -> None:
        """
        Update the local map with new measurements from the environment.

        Args:
            map_quality (list): [positions, values] or ['all', [full_map]].
            misc (dict, optional): Additional info (e.g., global visits map).
        """
        # --- 1. Ensure the local map is initialized ---
        if self._local_map is None:
            self._local_map = self.np.full((1, 1), self.np.nan)

        # --- 2. Extract measurement positions and values ---
        measure_positions = map_quality[0]
        measure_values = map_quality[1]

        # --- 3. Determine visit increase (could be adaptive in future) ---
        visit_increase = self._visit_increase

        # --- 4. Handle full map update (global observation) ---
        if measure_positions == 'all':
            # Replace local map with full observed map
            self._local_map = measure_values[0]
            global_visits_map = misc.get('visits', None).copy() if misc else None
                        
            
            self._local_map_visits = self.np.abs(global_visits_map) if global_visits_map is not None else None
            # Increment visits at current position
            if self._local_map_visits is not None:                
                self._local_map_visits[self._position[0], self._position[1]] += visit_increase
            return

        # --- 5. Expand local map if new measurements are out of bounds ---
        max_x = max(pos[0] for pos in measure_positions)
        max_y = max(pos[1] for pos in measure_positions)
        if max_x >= self._local_map.shape[0]:
            pad_x = max_x - self._local_map.shape[0] + 1
            self._local_map = self.np.pad(
                self._local_map,
                ((0, pad_x), (0, 0)),
                mode='constant', constant_values=self.np.nan
            )
        if max_y >= self._local_map.shape[1]:
            pad_y = max_y - self._local_map.shape[1] + 1
            self._local_map = self.np.pad(
                self._local_map,
                ((0, 0), (0, pad_y)),
                mode='constant', constant_values=self.np.nan
            )

        # --- 6. Update vegetation quality at measured positions ---
        for pos, val in zip(measure_positions, measure_values):
            self._local_map[pos[0], pos[1]] = val

        # --- 7. Track time spent in water at current position ---
        current_cell_value = self._local_map[self._position[0], self._position[1]]
        if current_cell_value < 0:
            self._in_water_counter += 1
        else:
            self._in_water_counter = 0
        
    def set_home_base_position(self) -> None:
        """
        Set the motion destination to the closest home base.
        Updates self._motion_destination.
        """        
                
        # Define the motion destination as the closest home base position
        self._motion_destination = min(
            self._home_base_position_store,
            key=lambda pos: self.np.sqrt(
                (self._position[0] - pos[0]) ** 2 +
                (self._position[1] - pos[1]) ** 2
            )
        )

    def select_exploration_eta(self, dt: float, dt_percentage: float, decay: list) -> None:
        """
        Adaptively adjust exploration parameters (eta, harvest interval, max load)
        based on recent agent performance (load accumulation).

        Args:
            dt (float): Time window in simulation hours for adaptation.
            dt_percentage (float): Fraction of steps with positive load change required to avoid decay.
            decay (list): Decay rates [eta_decay, harvest_decay, load_decay].
        """
        # --- 1. Unpack decay rates ---
        eta_decay = 0.0
        load_decay = decay[0]
        harvest_decay = decay[1]        

        # --- 2. Compute load derivative over the recent time window ---
        # Convert the requested time window (hours) to a number of stored samples.
        current_dt = self._dt_init if getattr(self, '_dt_init', None) not in (None, 0) else 1.0
        window_steps = max(2, int(round(dt / current_dt)))

        # Only proceed if enough history is available
        if len(self._load_store) < window_steps + 1:
            return
        load_derivative = self.np.diff(self._load_store[-(window_steps + 1):])
        self._wait_b4_explore += current_dt

        # --- 3. Adapt parameters if window is complete and enough time has passed ---
        if len(load_derivative) >= window_steps - 1 and self._wait_b4_explore >= dt:
            self._wait_b4_explore = 0.0
            # If not enough positive load changes, decay parameters
            positive_steps = (load_derivative > 0).sum()
            if positive_steps < dt_percentage * window_steps and self._load < self._maximum_load and self._maximum_load > 0.1 * self._maximum_load_init:
                # Decay exploration eta, max load, and widen harvest interval
                self._exploration_eta *= (1 - eta_decay)
                self._maximum_load *= (1 - load_decay)
                self._harvest_interval = [
                    (1 - harvest_decay) * self._harvest_interval[0],
                    (1 + harvest_decay) * self._harvest_interval[1]
                ]
            else:
                # Reset to initial values if load is decreasing (agent is making progress)
                self._exploration_eta = self._exploration_eta_init
                self._harvest_interval = self._harvest_interval_init.copy()
                self._maximum_load = self._maximum_load_init

            # --- 4. Clip parameters to valid ranges ---
            self._exploration_eta = self.np.clip(self._exploration_eta, 1e-2, 10)
            self._maximum_load = self.np.clip(self._maximum_load, 0.0, self.np.inf)
            if self._vegetation_quality_range is not None:
                max_quality = self._vegetation_quality_range[1]
                self._harvest_interval[0] = self.np.clip(self._harvest_interval[0], 0.0, max_quality)
                self._harvest_interval[1] = self.np.clip(self._harvest_interval[1], 0.0, max_quality)
                self._harvest_interval = sorted(self._harvest_interval)
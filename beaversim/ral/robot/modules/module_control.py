from curses import error

import numpy as np
from typing import Any, Optional, List

class Controller:
    """Multi-purpose controller: P (proportional) and P_repulsive (with potential field obstacle avoidance)."""
    
    def __init__(self, **kwargs) -> None:
        controller = kwargs.get('controller')
        self._name: str = controller.get('name')        
        self._max: float = controller.get('max', np.inf)
        self._accuracy: float = controller.get('accuracy', 1e0)
        self._dimension: int = controller.get('dimension', 2)
        
        self._Kp: float = controller.get('Kp', None)
        self._Kd: float = controller.get('Kd', None)
        self._Ki: float = controller.get('Ki', None)
        
        if self._name == 'P_repulsive':
            self._map_repulsive = controller.get('map_repulsive', None)
            self._neighbourhood_size = controller.get('neighbourhood_size', None)
            self._beta_repulsive: float = controller.get('beta_repulsive', None)            
            
        
        self._Kp_init, self._Kd_init, self._Ki_init = self._Kp, self._Kd, self._Ki
        self._status: str = 'IDLE'
        self._dt: Optional[float] = None
        self._max_scaled: Optional[float] = None
        self._current_value: Any = None
        self._setpoint: Any = None
        self._error: float = 0.0
        self._error_old: float = 0.0
        self._error_integral: float = 0.0
        self._output: Any = None
    
    def compute_error(self, setpoint: float, current_value: float) -> float:
        """Compute control error (setpoint - current_value) and update internal state."""
        error = setpoint - (current_value[-1] if self._name == 'P_repulsive' else current_value)
        self._current_value = current_value
        self._setpoint = setpoint
        self._error_old = self._error
        self._error = error
        self._error_integral += self._error
        self._max_scaled = self._max
        
        # anti windup for integral term
        if self._Ki != 0:
            integral_limit = self._max_scaled / self._Ki
            self._error_integral = np.clip(self._error_integral, -integral_limit, integral_limit)
        return error
    
    def compute_output(self, error: float, neighbourhood: Optional[Any] = None) -> np.ndarray:
        """Compute control output: P uses Kp*error, P_repulsive combines attractive/repulsive forces from neighbourhood."""
        if self._name == 'P':
            error_d = error - self._error_old
            control = self._Kp * error + self._Kd * error_d + self._Ki * self._error_integral
        
        elif self._name == 'P_repulsive':
            # 1. Normalize neighbourhood values (Consider increasing neighbourhood_size if obstacles are large)
            neighbourhood_pos, neighbourhood_values, flow_direction, flow_strength = neighbourhood[0], neighbourhood[1], neighbourhood[2], neighbourhood[3]
            
            # 1. Normalize terrain FIRST
            min_val, max_val = np.min(neighbourhood_values), np.max(neighbourhood_values)
            if max_val > min_val:
                neighbourhood_values = (neighbourhood_values - min_val) / (max_val - min_val)
            else:
                neighbourhood_values = np.zeros_like(neighbourhood_values)
                
            # 4. Extract the agent's precise center value safely
            agent_val = 0.0
            agent_pos_arr = np.array(self._current_value[-1])
            for pos, val in zip(neighbourhood_pos, neighbourhood_values):
                if pos[0] == agent_pos_arr[0] and pos[1] == agent_pos_arr[1]:
                    agent_val = val
                    break
            
            # 5. Compute repulsive potential properly aligned to the agent
            potential_array = []
            if np.linalg.norm(error) > 4.0:
                for pos, val in zip(neighbourhood_pos, neighbourhood_values):
                    pos_arr = np.array(pos)
                    
                    # Skip self-comparison
                    if pos_arr[0] == agent_pos_arr[0] and pos_arr[1] == agent_pos_arr[1]:
                        continue
                        
                    # Vector pointing FROM the neighbor TO the agent
                    direction = agent_pos_arr - pos_arr
                    
                    # If neighbor is higher (val > agent_val), difference is negative.
                    # Negative difference * direction (which points away from neighbor) 
                    # yields a force pushing the agent down the slope, away from the obstacle.
                    potential = (agent_val - val) * direction
                    potential_array.append(potential)
            else:
                potential_array = [np.array((0.0, 0.0))]
                                
            # PID control
            error_d = error - self._error_old
            control_attractive = self._Kp * error + self._Kd * error_d + self._Ki * self._error_integral
            repulsive_error = np.sum(potential_array, axis=0) if potential_array else np.zeros_like(control_attractive)
            repulsive_error_normalized = repulsive_error / (np.linalg.norm(repulsive_error) + 1e-6) * np.linalg.norm(error)            
            control_repulsive = self._Kp * repulsive_error_normalized
            control = self._beta_repulsive * control_repulsive + (1 - self._beta_repulsive) * control_attractive
            
            # account for flow influence                         
            flow_influence = flow_direction * flow_strength * (np.linalg.norm(error) / (np.linalg.norm(error) + 1e-6))
            control += flow_influence
        else:
            raise NotImplementedError()
        return np.clip(control, -self._max_scaled, self._max_scaled).reshape((1, self._dimension))
    
    def P_controller(self, setpoint: float, current_value: float) -> np.ndarray:
        """Simple P controller: output = Kp * (setpoint - current_value)."""
        return self.compute_output(self.compute_error(np.array(setpoint), np.array(current_value)))
    
    def P_repulsive_controller(self, setpoint: float, current_value: float, _neighbourhood_values: list) -> np.ndarray:
        """P controller with repulsive potential field for obstacle avoidance using neighbourhood values."""
        setpoint, current_value = np.array(setpoint), np.array(current_value)
        pos_values = np.array(_neighbourhood_values[0])
        return self.compute_output(self.compute_error(setpoint, pos_values), _neighbourhood_values)
    
    def step(self, setpoint: float, current_value: float, _neighbourhood: Optional[Any] = None) -> None:
        """Execute one control step, update status based on error convergence (IDLE/ACTIVE/FINISHED)."""
        if self._status == 'FINISHED':
            self._status = 'IDLE'
            return
        if self._name == 'P':
            self._output = self.P_controller(setpoint, current_value)
        elif self._name == 'P_repulsive':
            self._output = self.P_repulsive_controller(setpoint, current_value, _neighbourhood)
        self._status = 'FINISHED' if np.linalg.norm(self._error) <= self._accuracy else 'ACTIVE'

class Dynamics:
    """System dynamics simulator for robotic motion (integrator: double integrator with friction)."""
    
    def __init__(self, initial_state: np.ndarray, **kwargs) -> None:
        dynamics = kwargs.get('dynamics')
        self._name: str = dynamics.get('name')
        if self._name == 'integrator':
            self._mass: float = dynamics.get('mass')
            self._friction: float = dynamics.get('friction')
            self._status: str = 'IDLE'
        self._dt: Optional[float] = None
        self._state: np.ndarray = initial_state
        self._force: Any = []
        self._output: Any = []
    
    def SS_dynamics(self, dt: float, input: Any) -> None:
        """State-space dynamics: x[k+1] = A*x[k] + B*u[k], y[k] = C*x[k]. Hybrid system stops velocity on zero input."""
        A = np.array([[1, dt], [0, 1 - self._friction / self._mass]])
        B = np.array([[0], [dt / self._mass]])
        C = np.array([[1, 0]])
        D = np.array([[0]])
        u = np.array(input).reshape((1, self._state.shape[0]))
        # Hybrid system: zero control stops velocity
        for i, control in enumerate(u[0]):
            if control == 0:
                self._state[1][i] = 0
        self._state = np.dot(A, self._state) + np.dot(B, u)
        self._output = np.dot(C, self._state) + np.dot(D, u)
    
    def step(self, input: Any) -> None:
        """Execute one dynamics step with given force input."""
        if self._name == 'integrator':
            self._force = input
            self.SS_dynamics(self._dt, input)
        else:
            raise NotImplementedError()
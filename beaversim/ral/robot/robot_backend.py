class BaseRobotBackend(): 
    
    # imports
    import numpy as np
    # No class-level `import random`: it would shadow mesa.Agent.random (the model's seeded RNG)

    def __init__(self, **kwargs) -> None:
        pass
    
    def initiate_robot(self, **kwargs) -> None:
        self._kwargs = kwargs        
        self._robot = self._kwargs.get('robot')        
        self._name = self._robot.get('name') 
        
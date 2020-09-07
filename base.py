from utils import *

class SimulationObject:
    
    speed = None
    object_type = None


    def __init__(self, env, name, x, y):
        self.env = env
        self.name = name
        self.x, self.y = x, y
        self.odometer = 0
        
        
    def __repr__(self):
        return f'{self.object_type} "{self.name}"'
    
    
    def move(self, target):
        dist_to_target = dist(self.x, self.y, target.x, target.y)
        travel_time = dist_to_target / self.speed

        self.debug(f'Двигаюсь к {target} ({target.x:.2f}, {target.y:.2f}), '
                   f'{dist_to_target:.1f} км, займет {travel_time:.1f} ч, '
                   f'ETA {self.env.now + travel_time:.1f}')

        yield self.env.timeout(travel_time)

        self.x, self.y = target.x, target.y            
        self.debug(f'Приехал к {target} ({target.x:.2f}, {target.y:.2f})')

        if self.parcels_in_hold:
            for p in self.parcels_in_hold:
                p.x, p.y = self.x, self.y
        
        self.odometer += dist_to_target

    def debug(self, msg):
       self.env.debug(f'{self}: {msg}')


    def info(self, msg):
        self.env.info(f'{self}: {msg}')


    def find_closest(self, object_list):
        closest = None
        closest_dist = self.env.CITY_RADUIS_KM * 2
        
        for contender in object_list:
            contender_dist = dist(self.x, self.y, contender.x, contender.y)
            if contender_dist < closest_dist:
                closest = contender
                closest_dist = contender_dist
        
        return closest

    
    def created_log(self):
        self.debug(f'Cоздан по координатам ({self.x:.2f}, {self.y:.2f})')
        
        
    def dist(self, target):
        return dist(self.x, self.y, target.x, target.y)
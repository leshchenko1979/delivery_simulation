from base import SimulationObject
from utils import *

class Truck(SimulationObject):
    
    object_type = 'Грузовик'


    def __init__(self, env, name, starting_wh):
        self.current_wh = starting_wh
        super().__init__(env, name, self.current_wh.x, self.current_wh.y)
        
        self.await_dispatch = self.env.event()
        self.parcels_in_hold = set()
        self.speed = env.TRUCK_SPEED_KMH

        self.env.process(self.run())


    def run(self):
        
        self.created_log()
        
        while True:
            self.env.truck_dispatcher.request_dispatch(self)

            self.await_dispatch = self.env.event()

            self.debug('Запросил следующее задание, ожидаю')
            yield self.await_dispatch

            yield self.env.process(self.load())
            yield self.env.process(self.move_to_target_wh())
            yield self.env.process(self.unload())
            

    def load(self):
        self.debug(f'Загружаюсь со {self.current_wh}')

        parcels_to_load = self.to_load

        if parcels_to_load:
            yield self.env.timeout(len(parcels_to_load) * self.env.PARCEL_TRUCK_LOAD_UNLOAD_TIME_HRS)
        
            for p in parcels_to_load:
                p.truck_pickup()
                self.current_wh.pickup_parcel(p)
                
            self.parcels_in_hold.update(parcels_to_load)

            self.to_load = None

            self.debug(f'{len(parcels_to_load)} посылок загружено, {len(self.parcels_in_hold)} в кузове')
        

    def move_to_target_wh(self):
        yield self.env.process(self.move(self.target_wh))
        self.current_wh = self.target_wh
        self.target_wh = None
        
        
    def unload(self):       
        self.debug(f'Разгружаюсь на {self.current_wh}')

        parcels_to_unload = self.to_unload
        
        if parcels_to_unload:
            yield self.env.timeout(len(parcels_to_unload) * self.env.PARCEL_TRUCK_LOAD_UNLOAD_TIME_HRS)
        
            for p in parcels_to_unload:
                p.truck_dropoff()
                self.current_wh.dropoff_parcel(p)
                
            self.parcels_in_hold -= parcels_to_unload

            self.to_unload = None
    
            self.debug(f'{len(parcels_to_unload)} посылок разгружено, {len(self.parcels_in_hold)} в кузове')


    def accept_task(self, target_wh, to_load = None, to_unload = None):
        self.debug(f'Получил задание следовать к {target_wh}')
        self.target_wh = target_wh
        
        self.to_load = to_load
        for p in to_load:
            p.truck_assign()
        
        self.to_unload = to_unload
        
        succeed(self.await_dispatch)
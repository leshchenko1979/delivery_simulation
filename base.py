import collections
from enums import OperationTypes
import simpy

from utils import *


class SimulationObject:
    
    object_type = None


    def __init__(self, env, name, x, y):
        self.env : simpy.Environment = env
        self.name = name
        self.x, self.y = x, y
        self.log_created()        


    def log_created(self):
        self.debug(f'Cоздан по координатам ({self.x:.2f}, {self.y:.2f})')

        
    def __repr__(self):
        return self.object_type + (f' "{self.name}"' if self.name != None else '')
    
    
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

    
    def dist(self, target):
        return dist(self.x, self.y, target.x, target.y)
    
    
class StorageAbstract(SimulationObject):

    def __init__(self, env, name, x, y):
        super().__init__(env, name, x, y)
        self.parcels_in_hold = set()


    def dropoff_parcel(self, parcel, mover):
        yield self.env.timeout(self.operation_time(OperationTypes.DROPOFF, mover))
        self.parcels_in_hold.add(parcel)
        parcel.holder = self
        parcel.dropoff(mover)
        self.debug(f'Получена {parcel}')


    def pickup_parcel(self, parcel, mover):
        yield self.env.timeout(self.operation_time(OperationTypes.PICKUP, mover))
        if parcel in self.parcels_in_hold:
            parcel.pickup(mover)
            self.parcels_in_hold -= {parcel}
            parcel.holder = mover
            self.debug(f'Отгружена {parcel}')
        else:
            raise ValueError(f'{self}: {parcel} не найдена для отгрузки')


    def operation_time(self, operation_type, mover):
        raise NotImplementedError
    

    def get_parcels_awaiting_couriers(self):
        return {p for p in self.parcels_in_hold if p.is_awaiting_courier()}


    def get_parcels_awaiting_trucks(self):
        return {p for p in self.parcels_in_hold if p.is_awaiting_truck()}


class ParcelMover(StorageAbstract):

    def __init__(self, env, object_type, speed, name, dispatcher, current_store):

        self.object_type = object_type

        super().__init__(env, name, current_store.x, current_store.y)
        
        self.speed = speed
        self.disp : DispatcherAbstract = dispatcher
        self.current_storage = current_store
        self.target_storage = None
        self.odometer = 0
        
        self.await_dispatch = self.env.event()
        
        self.timer = Timer(env, ParcelMoverTimer)

        env.process(self.run())


    def run(self):
        while True:
            self.disp.request_dispatch(self)

            self.await_dispatch = self.env.event()

            self.debug('Запросил следующее задание, ожидаю')

            if self.parcels_in_hold:
                self.timer.punch(ParcelMoverTimer.AWAIT_DISPATCH_LOADED)
            else:
                self.timer.punch(ParcelMoverTimer.AWAIT_DISPATCH_EMPTY)

            yield self.await_dispatch

            self.timer.punch(ParcelMoverTimer.LOADING)

            yield self.env.process(self.load())
            
            if self.parcels_in_hold:
                self.timer.punch(ParcelMoverTimer.MOVE_LOADED)
            else:
                self.timer.punch(ParcelMoverTimer.MOVE_EMPTY)

            yield self.env.process(self.move_to_target())

            self.timer.punch(ParcelMoverTimer.UNLOADING)

            yield self.env.process(self.unload())
            

    def load(self):
        parcels_to_load = self.to_load

        if parcels_to_load:
            self.debug(f'Загружаюсь в точке: {self.current_storage}')

            for p in parcels_to_load:
                yield self.env.process(self.current_storage.pickup_parcel(p, self))
                
            self.parcels_in_hold.update(parcels_to_load)

            self.to_load = None

            self.debug(f'{len(parcels_to_load)} посылок загружено, несу {len(self.parcels_in_hold)} всего')
        

    def move_to_target(self):
        t = self.target
        dist_to_target = dist(self.x, self.y, t.x, t.y)
        travel_time = dist_to_target / self.speed

        self.debug(f'Двигаюсь к {t} ({t.x:.2f}, {t.y:.2f}), '
                   f'{dist_to_target:.1f} км, займет {travel_time:.1f} ч, '
                   f'ETA {self.env.now + travel_time:.1f}')

        yield self.env.timeout(travel_time)

        self.x, self.y = t.x, t.y
        self.debug(f'Приехал к {t} ({t.x:.2f}, {t.y:.2f})')

        if self.parcels_in_hold:
            for p in self.parcels_in_hold:
                p.x, p.y = self.x, self.y
        
        self.odometer += dist_to_target

        self.current_storage = t
        self.target = None


    def unload(self):       
        parcels_to_unload = self.to_unload
        
        if parcels_to_unload:
            self.debug(f'Разгружаюсь на {self.current_storage}')

            for p in parcels_to_unload:
                yield self.env.process(self.current_storage.dropoff_parcel(p, self))
                p.dropoff(self)
                
            self.parcels_in_hold -= parcels_to_unload

            self.to_unload = None
    
            self.debug(f'{len(parcels_to_unload)} посылок разгружено, несу {len(self.parcels_in_hold)} посылок всего')


    def accept_task(self, target, to_load = None, to_unload = None):
        if not isinstance(target, StorageAbstract):
            raise ValueError(f'{target} должен быть типа {StorageAbstract}')
        
        for p in to_load | to_unload:
            if p.object_type != 'Посылка':
                raise ValueError(f'{p} должен быть типа Parcel')
        
        self.debug(f'Получил задание следовать к {target}')
        self.target = target
        
        self.to_load = to_load
        for p in to_load:
            p.assign()
        
        self.to_unload = to_unload
        
        succeed(self.await_dispatch)
        
        
class DispatcherAbstract(SimulationObject):
    
    def __init__(self, env, name):
        super().__init__(env, name, 0, 0)
        self.dispatch_requests = collections.deque()
        self.movers_awaiting_dispatch_present = env.event()
                
        self.env.process(self.run())


    def log_created(self):
        pass


    def run(self):
        while True:
            if sum([len(m.parcels_in_hold) for m in self.dispatch_requests]) == 0:
                yield self.cycle_start_event()

            mover = self.pop_next_mover()
            self.debug(f'Нужно выдать распоряжение для {mover}, и еще {len(self.dispatch_requests)} в очереди')

            self.assign_task(mover)
            

    def cycle_start_event(self):
        raise NotImplementedError
        

    def assign_task(self, mover):
        raise NotImplementedError

            
    def pop_next_mover(self):
        non_empty_movers = [m for m in self.dispatch_requests if m.parcels_in_hold]

        if non_empty_movers:
            mover = non_empty_movers[0]
            self.dispatch_requests.remove(mover)
        else:        
            mover = self.dispatch_requests.popleft()

        if len(self.dispatch_requests) == 0:
            self.movers_awaiting_dispatch_present = self.env.event()

        return mover
        
        
    def request_dispatch(self, mover):
        self.debug(f'{mover} запросил задачу')

        succeed(self.movers_awaiting_dispatch_present)
        self.dispatch_requests.append(mover)

    
class Warehouse(StorageAbstract):

    object_type = 'Склад'


    def __init__(self, DispatcherClass, env, name, x, y):
        super().__init__(env, name, x, y)
        
        self.disp = DispatcherClass(env, self, f'Склад {name}')


    def operation_time(self, operation_type, mover):
        if mover.object_type == 'Курьер':
            if operation_type == OperationTypes.PICKUP:
                return self.env.COURIER_WAREHOUSE_PICKUP_TIME_HRS
            else:
                return self.env.COURIER_WAREHOUSE_DEPOSIT_TIME_HRS
        elif mover.object_type == 'Грузовик':
            return self.env.PARCEL_TRUCK_LOAD_UNLOAD_TIME_HRS
        else:
            raise TypeError(f'Время разгрузки не определено для {mover}')


class Courier(ParcelMover):
    def __init__(self, env, wh, disp, name):
        super().__init__(env, 'Курьер', env.COURIER_SPEED_KMH, name, disp, wh) 
        self.wh = wh
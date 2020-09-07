import collections

from utils import *
from base import SimulationObject


AWAIT_COURIER = 0
AWAIT_TRUCK = 1
MOVE_COURIER = 2
MOVE_TRUCK = 3


class ParcelGenerator:
    
    def __init__(self, env):
        self.env = env
        self.parcels = collections.deque()
        env.process(self.run())
        
        
    def run(self):
        x = 0
        while True:
            self.parcels.append(Parcel(self.env, x))
            yield self.env.timeout(self.env.PARCEL_INTERVAL_HRS)
            x += 1
            
    
    def post_metrics(self, m):
        m['parcels_generated'] = len(self.parcels)
        m['parcels_direct_dist_total'] = int(sum([p.direct_dist for p in self.parcels]))

        delivered_parcels = [p for p in self.parcels if p.await_last_mile_dropoff.triggered]
        m['parcels_delivered_total'] = len(delivered_parcels)
        m['parcels_delivered_direct_dist_total'] = int(sum(p.direct_dist for p in delivered_parcels))

        if len(delivered_parcels) > 0:
            m['parcel_time_total'] = \
                sum(p.timer.total() for p in delivered_parcels) / len(delivered_parcels)
            m['parcel_time_await_courier'] = \
                sum(p.timer.timings[AWAIT_COURIER] for p in delivered_parcels) / len(delivered_parcels)
            m['parcel_time_await_truck'] = \
                sum(p.timer.timings[AWAIT_TRUCK] for p in delivered_parcels) / len(delivered_parcels)
            m['parcel_time_move_courier'] = \
                sum(p.timer.timings[MOVE_COURIER] for p in delivered_parcels) / len(delivered_parcels)
            m['parcel_time_move_truck'] = \
                sum(p.timer.timings[MOVE_TRUCK] for p in delivered_parcels) / len(delivered_parcels)


    def post_results(self, s):
        pass
    

class Customer(SimulationObject):
    object_type = 'Клиент'
        

class Parcel(SimulationObject):
    
    object_type = 'Посылка'
    
    def __init__(self, env, name):
        
        while True:
            x, y = env.random_point()
            self.sender = Customer(env, '', x, y)
            
            x, y = env.random_point()
            self.addressee = Customer(env, '', x, y)
            
            whs = env.warehouse_manager.warehouses
            self.first_mile_wh = self.sender.find_closest(whs)
            self.last_mile_wh = self.addressee.find_closest(whs)
        
            if env.ALLOW_SAME_WH_PARCELS or self.first_mile_wh != self.last_mile_wh:
                break
        
        super().__init__(env, name, self.sender.x, self.sender.y)
        
        self.direct_dist = dist(self.sender.x, self.sender.y, 
                                self.addressee.x, self.addressee.y)
        self.timer = Timer(env, {AWAIT_COURIER, AWAIT_TRUCK, MOVE_COURIER, MOVE_TRUCK})
        
        self.await_first_mile_pickup = self.env.event()
        self.await_first_mile_dropoff = self.env.event()
        self.await_truck_assignment = self.env.event()
        self.await_truck_pickup = self.env.event()
        self.await_truck_dropoff = self.env.event()
        self.await_last_mile_pickup = self.env.event()
        self.await_last_mile_dropoff = self.env.event()

        self.env.process(self.run())


    def run(self):
        self.created_log()
        
        self.first_mile_wh.request_courier(self)

        self.timer.punch(AWAIT_COURIER)
        yield self.await_first_mile_pickup
        self.debug('Забрана курьером у отправителя')
        
        if not self.is_delivery_within_same_wh():
            yield self.await_first_mile_dropoff
            self.debug('Оставлена на складе первой мили, ожидаю назначения на перевозку')
            
            while True:
                yield self.await_truck_assignment
                self.debug('Назначена на перевозку, ожидаю перевозки грузовиком')
                
                yield self.await_truck_pickup
                self.debug('Забрана грузовиком')
            
                yield self.await_truck_dropoff

                if self.current_wh == self.last_mile_wh:
                    self.debug('Доставлена грузовиком на конечный склад, ожидаю доставки курьером отправителю')
                    break
                else:
                    self.debug('Доставлена грузовиком на промежуточный склад, ожидаю дальнейшей перевозки грузовиком')
                    self.await_truck_assignment = self.env.event()
                    self.await_truck_pickup = self.env.event()
                    self.await_truck_dropoff = self.env.event()
            
            self.last_mile_wh.request_courier(self)

            yield self.await_last_mile_pickup
            self.debug('Забрана курьером для доставки получателю')

        yield self.await_last_mile_dropoff
        self.debug('Доставлена получателю')
        
        self.timer.punch(None)


    def first_mile_pickup(self):
        succeed(self.await_first_mile_pickup)
        self.timer.punch(MOVE_COURIER)
    

    def first_mile_dropoff(self):
        succeed(self.await_first_mile_dropoff)
        self.x, self.y = self.first_mile_wh.x, self.first_mile_wh.y
        self.timer.punch(AWAIT_TRUCK)


    def truck_assign(self):
        succeed(self.await_truck_assignment)
    

    def truck_pickup(self):
        succeed(self.await_truck_pickup)
        self.timer.punch(MOVE_TRUCK)
    

    def truck_dropoff(self):
        succeed(self.await_truck_dropoff)
        self.x, self.y = self.last_mile_wh.x, self.last_mile_wh.y
        self.timer.punch(AWAIT_COURIER)


    def last_mile_pickup(self):
        succeed(self.await_last_mile_pickup)
        self.timer.punch(MOVE_COURIER)
    

    def last_mile_dropoff(self):
        succeed(self.await_last_mile_dropoff)
        self.x, self.y = self.addressee.x, self.addressee.y
    
    
    def is_delivery_within_same_wh(self):
        return self.first_mile_wh == self.last_mile_wh
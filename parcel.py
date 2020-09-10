import collections

from simpy.core import Environment

from utils import *
from base import SimulationObject, StorageAbstract
from enums import OperationTypes, ParcelTimer


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
                sum(p.timer.timings[ParcelTimer.AWAIT_COURIER] for p in delivered_parcels) / len(delivered_parcels)
            m['parcel_time_await_truck'] = \
                sum(p.timer.timings[ParcelTimer.AWAIT_TRUCK] for p in delivered_parcels) / len(delivered_parcels)
            m['parcel_time_move_courier'] = \
                sum(p.timer.timings[ParcelTimer.MOVE_COURIER] for p in delivered_parcels) / len(delivered_parcels)
            m['parcel_time_move_truck'] = \
                sum(p.timer.timings[ParcelTimer.MOVE_TRUCK] for p in delivered_parcels) / len(delivered_parcels)


    def post_results(self, s):
        pass
    

class Customer(StorageAbstract):

    def __init__(self, env, parcel):
        x, y = env.random_point()
        super().__init__(env, None, x, y)
        self.created_by = parcel


    def __repr__(self):
        return f'{super().__repr__()} ({self.created_by})'


    def log_created(self):
        pass
    
    
    def operation_time(self, operation_type, mover):
        if operation_type == OperationTypes.PICKUP:
            return self.env.COURIER_SENDER_PICKUP_TIME_HRS
        else:
            return self.env.COURIER_ADDRESSEE_DEPOSIT_TIME_HRS


class Sender(Customer):

    object_type = 'Отправитель'

    def __init__(self, env, parcel):
        super().__init__(env, parcel)        
        self.parcels_in_hold = {parcel}


class Addressee(Customer):

    object_type = 'Получатель'
        

class Parcel(SimulationObject):
    
    object_type = 'Посылка'
    
    def __init__(self, env: Environment, name):
        
        whs = env.warehouse_manager.warehouses

        while True:
            self.sender = Sender(env, self)
            self.holder = self.sender
            
            self.addressee = Addressee(env, self)
            
            self.first_mile_wh = self.sender.find_closest(whs)
            self.last_mile_wh = self.addressee.find_closest(whs)
        
            if env.ALLOW_SAME_WH_PARCELS or self.first_mile_wh != self.last_mile_wh:
                break
        
        super().__init__(env, name, self.sender.x, self.sender.y)
        
        self.direct_dist = self.dist(self.addressee)
        self.timer = Timer(env, ParcelTimer)
        
        self.await_first_mile_pickup = self.env.event()
        self.await_first_mile_dropoff = self.env.event()
        self.await_truck_pickup = self.env.event()
        self.await_truck_dropoff = self.env.event()
        self.await_last_mile_pickup = self.env.event()
        self.await_last_mile_dropoff = self.env.event()

        self.env.process(self.run())


    def run(self):

        yield self.env.process(self.await_courier_assignment(self.first_mile_wh))        
        self.debug('Назначена на курьера первой мили')

        yield self.await_first_mile_pickup
        self.debug('Забрана курьером у отправителя')
        
        if not self.is_delivery_within_same_wh():
            yield self.await_first_mile_dropoff
            self.debug('Оставлена на складе первой мили, ожидаю назначения на перевозку')
            
            while True:
                self.await_assignment = self.env.event()
                yield self.await_assignment
                self.debug('Назначена на перевозку, ожидаю перевозки грузовиком')
                
                yield self.await_truck_pickup
                self.debug('Забрана грузовиком')
            
                yield self.await_truck_dropoff

                if self.holder == self.last_mile_wh:
                    self.debug('Доставлена грузовиком на конечный склад, ожидаю доставки курьером отправителю')
                    break
                else:
                    self.debug('Доставлена грузовиком на промежуточный склад, ожидаю дальнейшей перевозки грузовиком')
                    self.await_truck_pickup = self.env.event()
                    self.await_truck_dropoff = self.env.event()
            
            yield self.env.process(self.await_courier_assignment(self.last_mile_wh))        
            self.debug('Назначена на курьера последней мили')

            yield self.await_last_mile_pickup
            self.debug('Забрана курьером для доставки получателю')

        yield self.await_last_mile_dropoff
        self.debug('Доставлена получателю')
        

    def await_courier_assignment(self, wh):
        wh.disp.request_pickup(self)
        self.timer.punch(ParcelTimer.AWAIT_COURIER)
        self.await_assignment = self.env.event()
        yield self.await_assignment


    def is_delivery_within_same_wh(self):
        return self.first_mile_wh == self.last_mile_wh
    

    def assign(self):
        succeed(self.await_assignment)
    
    
    def pickup(self, mover):
        if self.holder == self.sender:
            succeed(self.await_first_mile_pickup)
            self.timer.punch(ParcelTimer.MOVE_COURIER)

        elif self.holder == self.last_mile_wh:
            succeed(self.await_last_mile_pickup)
            self.timer.punch(ParcelTimer.MOVE_COURIER)

        else:
            succeed(self.await_truck_pickup)
            self.timer.punch(ParcelTimer.MOVE_TRUCK)
        
        
    def dropoff(self, mover):
        if self.holder == self.first_mile_wh:
            succeed(self.await_first_mile_dropoff)
            self.timer.punch(ParcelTimer.AWAIT_TRUCK)
            
        elif self.holder == self.addressee:
            succeed(self.await_last_mile_dropoff)
            self.timer.punch(None)

        else:
            succeed(self.await_truck_dropoff)
            self.timer.punch(ParcelTimer.AWAIT_COURIER)
            
            
    def is_awaiting_courier(self):
        return (self.holder in {self.sender, self.last_mile_wh}
                and not self.await_assignment.triggered)
        
        
    def is_awaiting_truck(self):
        return (self.holder.object_type == 'Склад' 
                and self.holder != self.last_mile_wh
                and not self.await_assignment.triggered)
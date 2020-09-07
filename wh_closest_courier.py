import collections
import itertools

import circlify

from base import SimulationObject
from courier import Courier
from utils import *


class WarehouseManager:

    version = __name__
    
    def __init__(self, env):
        self.env = env
        
        env.log.setLevel("ERROR")
        circles = circlify.circlify([1 for i in range(self.env.WAREHOUSES_NUMBER)])
        env.log.setLevel(self.env.LOGGING_LEVEL)

        radius = self.env.CITY_RADUIS_KM
        self.warehouses = [
            Warehouse(env, x, c.x * radius, c.y * radius) 
            for x, c in enumerate(circles)
        ]        
        
        
    def post_metrics(self, m):
        m['free_couriers'] = sum([len(wh.dispatch_requests) for wh in self.warehouses])

        parcels_in_wh_hold = [len(wh.parcels_in_hold) for wh in self.warehouses]
        if parcels_in_wh_hold:
            m['parcels_in_hold_wh_max'] = max(parcels_in_wh_hold)
            m['parcels_in_hold_wh_total'] = sum(parcels_in_wh_hold)

        m['odo_courier_total'] = int(sum([c.odometer for c in 
            itertools.chain(*(wh.couriers for wh in self.warehouses))]))

            
    def post_results(self, m):
        m['ver_disp_courier'] = self.version

        courier_fixed_costs_mon = self.env.COURIER_COST_PER_MON \
            * self.env.COURIERS_PER_WAREHOUSE * self.env.WAREHOUSES_NUMBER
        wh_fixed_costs_mon = self.env.WAREHOUSE_COST_PER_MON * self.env.WAREHOUSES_NUMBER

        time_unit_mult = self.env.now / self.env.HRS_PER_MON / m['parcels_delivered_total']

        m['unit_costs_couriers'] = int(courier_fixed_costs_mon * time_unit_mult)
        m['unit_costs_wh'] = int(wh_fixed_costs_mon * time_unit_mult)

    
class Warehouse(SimulationObject):

    object_type = 'Склад'


    def __init__(self, env, name, x, y):
        super().__init__(env, name, x, y)
        
        self.couriers = {Courier(self, f'{self.name}_{x}') 
                         for x in range(env.COURIERS_PER_WAREHOUSE)}
        self.dispatch_requests = collections.deque()
        self.couriers_awaiting_dispatch = env.event()
        
        self.courier_requests = collections.deque()
        self.courier_requests_present = env.event()
        
        self.parcels_in_hold = set()
        
        self.env.process(self.run())


    def run(self):
        self.created_log()
        while True:
            yield self.courier_requests_present # ждем запроса на доставку
            self.debug('Получен запрос на курьера')
            yield self.couriers_awaiting_dispatch # ждем свободных курьеров
            self.debug('Появились свободные курьеры')
            
            parcel = self.pop_best_parcel_request()
            courier = self.pop_best_free_courier(parcel)
            courier.accept_task(parcel)
            self.debug(f'{courier} получил задачу принести {parcel}')
        

    def pop_best_parcel_request(self):
        request = self.courier_requests.popleft()
        if len(self.courier_requests) == 0:
            self.courier_requests_present = self.env.event()
        return request


    def pop_best_free_courier(self, parcel):
        closest_courier = parcel.find_closest(self.dispatch_requests)
        self.dispatch_requests.remove(closest_courier)
        if len(self.dispatch_requests) == 0:
            self.couriers_awaiting_dispatch = self.env.event()
        return closest_courier
        
        
    def request_dispatch(self, courier):
        self.debug(f'{courier} запросил задачу')

        succeed(self.couriers_awaiting_dispatch)
        self.dispatch_requests.append(courier)
        courier.await_dispatch = courier.env.event()


    def request_courier(self, parcel):
        self.debug(f'{parcel} запросила доставку')

        succeed(self.courier_requests_present)
        self.courier_requests.append(parcel)


    def dropoff_parcel(self, parcel):
        self.parcels_in_hold.add(parcel)
        parcel.current_wh = self
        self.debug(f'Получена {parcel}')
        
        
    def pickup_parcel(self, parcel):
        if parcel in self.parcels_in_hold:
            self.parcels_in_hold -= {parcel}
            self.debug(f'Отгружена {parcel}')
        else:
            raise ValueError(f'{self}: {parcel} не найдена для отгрузки')

    
    def get_parcels_awaiting_assignment(self):
        return {p for p in self.parcels_in_hold if not p.await_truck_assignment.triggered}
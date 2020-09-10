import itertools

from circlify import circlify

from base import ParcelMoverTimer, SimulationObject, Warehouse
from cd_many_parcels import CourierDispatcher

class WarehouseManager(SimulationObject):

    object_type = 'Менеджер складов'
    
    def __init__(self, env):
        super().__init__(env, None, 0, 0)
        
        self.debug('Расставляю склады')
        env.log.setLevel("ERROR")
        circles = circlify([1 for i in range(self.env.WAREHOUSES_NUMBER)])
        env.log.setLevel(self.env.LOGGING_LEVEL)

        radius = self.env.CITY_RADUIS_KM
        self.warehouses = [
            Warehouse(CourierDispatcher, env, x, c.x * radius, c.y * radius) 
            for x, c in enumerate(circles)
        ]
        
        
    def post_metrics(self, m):
        all_couriers = list(itertools.chain(*[wh.disp.couriers for wh in self.warehouses]))
        
        m['free_couriers'] = len([c for c in all_couriers if len(c.parcels_in_hold) == 0])
        m['odo_courier_total'] = int(sum(c.odometer for c in all_couriers))

        parcels = [len(wh.parcels_in_hold) for wh in self.warehouses]
        if parcels:
            m['parcels_in_hold_wh_max'] = max(parcels)
            m['parcels_in_hold_wh_total'] = sum(parcels)

        parcels = [len(c.parcels_in_hold) for c in all_couriers]
        if parcels:
            m['parcels_in_hold_courier_max'] = max(parcels)
            m['parcels_in_hold_courier_total'] = sum(parcels)

            
    def post_results(self, m):
        m['ver_disp_courier'] = CourierDispatcher.version

        courier_fixed_costs_mon = self.env.COURIER_COST_PER_MON \
            * self.env.COURIERS_PER_WAREHOUSE * self.env.WAREHOUSES_NUMBER
        wh_fixed_costs_mon = self.env.WAREHOUSE_COST_PER_MON * self.env.WAREHOUSES_NUMBER

        time_unit_mult = self.env.now / self.env.HRS_PER_MON / m['parcels_delivered_total']

        m['unit_costs_couriers'] = int(courier_fixed_costs_mon * time_unit_mult)
        m['unit_costs_wh'] = int(wh_fixed_costs_mon * time_unit_mult)
        
        all_couriers = list(itertools.chain(*[wh.disp.couriers for wh in self.warehouses]))

        bindings = {
            'courier_time_await_dispatch_empty':    ParcelMoverTimer.AWAIT_DISPATCH_EMPTY,
            'courier_time_await_dispatch_loaded':   ParcelMoverTimer.AWAIT_DISPATCH_LOADED,
            'courier_time_loading':                 ParcelMoverTimer.LOADING,
            'courier_time_unloading':               ParcelMoverTimer.UNLOADING,
            'courier_time_move_empty':              ParcelMoverTimer.MOVE_EMPTY,
            'courier_time_move_loaded':             ParcelMoverTimer.MOVE_LOADED
        }        

        for stat_key, timing_category in bindings.items():
            m[stat_key] = sum(c.timer.timings[timing_category] for c in all_couriers) / \
                len(all_couriers) / self.env.SIMULATION_TIME_HRS

                

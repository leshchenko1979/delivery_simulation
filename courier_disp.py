from base import DispatcherAbstract, Warehouse, Courier, ParcelMover
from utils import succeed

class CourierDispatcherAbstract(DispatcherAbstract):
    
    object_type = 'Диспетчер курьеров'


    def __init__(self, env, wh: Warehouse, name):
        super().__init__(env, name)
        self.await_pickup_needed = env.event()
        self.wh = wh            
        self.couriers = {Courier(env, wh, self, f'{self.wh.name}_{x}')
                         for x in range(env.COURIERS_PER_WAREHOUSE)}
            
        self.pickup_requests = set()


    def cycle_start_event(self):
        return self.movers_awaiting_dispatch_present & self.await_pickup_needed
            

    def assign_task(self, courier: ParcelMover):

        self.debug(f'Рассчитываю задачу для {courier}')
        
        courier_task = self.get_courier_task(courier)

        if courier_task:
            (target_storage, to_load, to_unload) = courier_task
            courier.accept_task(target_storage, to_load, to_unload)
            self.pickup_request_served(target_storage)
            self.debug(f'Приказываю {courier}: '
                       f'загрузить {to_load} на {courier.current_storage}, '
                       f'двигаться к {target_storage} '
                       f'и разгрузить там {to_unload}')
        
        else:            
            self.debug('Нечего делать, буду ждать новых заказов на курьера')
            self.request_dispatch(courier)
            
        self.patch_pickup_requests()


    def get_courier_task(courier):
        raise NotImplementedError


    def request_pickup(self, parcel):
        self.pickup_requests |= {parcel.holder}
        succeed(self.await_pickup_needed)
        

    def pickup_request_served(self, holder):
        if holder != self.wh:
            self.pickup_requests -= {holder}

        self.debug(f'Удалил {holder} из списка запросов на вывоз, осталось {len(self.pickup_requests)}')


    def patch_pickup_requests(self):
        if self.wh in self.pickup_requests:
            if not self.wh.get_parcels_awaiting_couriers():
                self.debug('Убираю склад из списка на вывоз - на складе ни одной посылки на вывоз нет')
                self.pickup_requests -= {self.wh}

            couriers_heading_to_wh = len([c for c in self.couriers if c.target_storage == self.wh])
            if self.couriers_needed_for_wh_pickup() <= couriers_heading_to_wh:
                self.debug('Убираю склад из списка на вывоз - на склад направлено достаточно курьеров')
                self.pickup_requests -= {self.wh}
            
        if not self.pickup_requests:
            self.await_pickup_needed = self.env.event()
            
    
    def couriers_needed_for_wh_pickup(self):
        raise NotImplementedError

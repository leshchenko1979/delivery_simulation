from base import Courier
from parcel import Sender
from courier_disp import CourierDispatcherAbstract

class CourierDispatcher(CourierDispatcherAbstract):
    
    object_type = 'Диспетчер курьеров'
    version = __name__


    def get_courier_task(self, courier: Courier):

        at_wh = courier.current_storage == self.wh
        at_sender = isinstance(courier.current_storage, Sender)

        if at_sender:
            parcels = courier.current_storage.parcels_in_hold.copy()
            target_storage = self.wh

        elif at_wh and (self.wh in self.pickup_requests):
            outgoing_parcels = self.wh.get_parcels_awaiting_couriers()
            # TODO: в силу того, что текущий механизм оставляет склад в pickup_requests, 
            # пока оттуда не заберут все посылки, то сейчас на склад направляется 
            # избыток курьеров
            if len(outgoing_parcels):
                parcel = max(self.wh.get_parcels_awaiting_couriers(),
                    key = lambda p: p.timer.total())
                target_storage = parcel.addressee
                parcels = {parcel}
            else: # посылочку с центра перехватил и увез кто-то другой
                return None

        elif self.pickup_requests:
            parcels = set()
            target_storage = courier.find_closest(self.pickup_requests)
            self.debug(f'Ближайший запрос из {len(self.pickup_requests)} активных - от {target_storage}')
            
            # если есть более близкие свободные курьеры, то запрос не берем 
            if self.dispatch_requests:
                self.debug(f'Проверяем, есть ли более близкие курьеры из '
                           f'{len(self.dispatch_requests)} свободных, исключая {courier}')
                closest_free_courier : Courier = target_storage.find_closest(
                    set(self.dispatch_requests) | {courier})
                if (closest_free_courier != courier) and \
                        (closest_free_courier.current_storage != courier.current_storage):
                    self.debug(f'Найден более близкий свободный {closest_free_courier}')
                    return None
        else:
            return None

        return target_storage, parcels.copy(), parcels.copy()
    

    def couriers_needed_for_wh_pickup(self):
        return len(self.wh.get_parcels_awaiting_couriers())

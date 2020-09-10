from base import Courier
from parcel import Addressee, Sender
from courier_disp import CourierDispatcherAbstract
from utils import *


class CourierDispatcher(CourierDispatcherAbstract):
    
    object_type = 'Диспетчер курьеров'
    version = __name__
    


    def get_courier_task(self, courier: Courier):
        complete_task_list = self.get_complete_task_list(courier)
        
        task_num = len(complete_task_list)

        if task_num:
            self.debug(f'Выбираю из {task_num} заданий')

            closest_point = courier.find_closest(complete_task_list)
            to_load = self.get_load_task(courier)

            planned_hold = courier.parcels_in_hold | to_load
            to_unload = self.get_unload_task(closest_point, planned_hold)

            return closest_point, to_load, to_unload                
        else:
            return None


    def get_complete_task_list(self, courier):
        first_mile_dropoff = {p.first_mile_wh 
                              for p in courier.parcels_in_hold 
                              if p.first_mile_wh == self.wh}

        last_mile_dropoff = {p.addressee for p in courier.parcels_in_hold 
                                    if p.last_mile_wh == self.wh}

        return self.pickup_requests | first_mile_dropoff | last_mile_dropoff
            
            
    def get_load_task(self, courier):
        if courier.current_storage == self.wh:
            # если мы на складе, то забираем всю последнюю милю
            # TODO: загружать все неправильно - нужно распределять ношу на всех курьеров
            to_load = self.wh.get_parcels_awaiting_couriers() 
            
        elif isinstance(courier.current_storage, Sender):
            # если у отправителя, то забираем посылку
            to_load = courier.current_storage.parcels_in_hold.copy()
        
        else:
            # если у получателя, то ничего не загружаем
            to_load = set()
        return to_load


    def get_unload_task(self, closest_point, planned_hold):
        if closest_point == self.wh:
            # если идем на склад, то разгружаем первую милю 
            to_unload = {p for p in planned_hold
                        if p.first_mile_wh == self.wh}
        
        elif isinstance(closest_point, Addressee):
            # если идем к получателю, то только доставляем
            target_parcel = [p for p in planned_hold if p.addressee == closest_point][0]
            to_unload = {target_parcel}
        
        else:
            # если идем к отправителю, но ничего не разгружаем
            to_unload = set()
        return to_unload


    def couriers_needed_for_wh_pickup(self):
        return 1 if self.wh.get_parcels_awaiting_couriers() else 0
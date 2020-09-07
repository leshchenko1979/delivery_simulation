from base import SimulationObject
from utils import *

class Courier(SimulationObject):
    
    object_type = 'Курьер'


    def __init__(self, wh, name):
        super().__init__(wh.env, name, wh.x, wh.y)
        self.wh = wh
        self.parcels_in_hold = None
        self.speed = self.env.COURIER_SPEED_KMH

        
        self.env.process(self.run())
    
    
    def run(self):
        #TODO: сейчас прямая доставка поле получения, а нужно придумать, как по дороге собирать попутные посылки
        
        self.created_log()
        
        while True:
            self.wh.request_dispatch(self)
            yield self.await_dispatch
            
            self.debug(f'Получил задачу доставить {self.target_parcel}')
            
            if (self.target_parcel.x != self.x) or (self.target_parcel.y != self.y):
                yield self.env.process(self.move(self.target_parcel))

            if (self.target_parcel.x == self.wh.x) and (self.target_parcel.y == self.wh.y):
                yield self.env.process(self.pickup_parcel_at_wh())
                yield self.env.process(self.deliver_last_mile())
            else:
                yield self.env.process(self.pickup_parcel_from_sender())

                if self.target_parcel.is_delivery_within_same_wh():
                    self.debug('Прямая доставка в пределах одного склада')
                    yield self.env.process(self.deliver_last_mile())
                else:
                    yield self.env.process(self.drop_off_at_wh())


    def accept_task(self, parcel):
        self.target_parcel = parcel
        succeed(self.await_dispatch)


    def pickup_parcel_at_wh(self):
        self.debug(f'Получаю {self.target_parcel} со {self.wh}')
        
        yield self.env.timeout(self.env.COURIER_WAREHOUSE_PICKUP_TIME_HRS)
        try:
            self.wh.pickup_parcel(self.target_parcel)
        except:
            raise RuntimeError(f'{self}: {self.target_parcel} не найдена на {self.wh}')
        self.target_parcel.last_mile_pickup()
        self.parcels_in_hold = {self.target_parcel}
        self.debug(f'Забрал посылку {self.target_parcel} со {self.wh}')


    def deliver_last_mile(self):
        yield self.env.process(self.move(self.target_parcel.addressee))
        
        yield self.env.timeout(self.env.COURIER_ADDRESSEE_DEPOSIT_TIME_HRS)
        self.target_parcel.last_mile_dropoff()
        self.parcels_in_hold = None
        self.debug(f'Отдал {self.target_parcel} получателю')


    def pickup_parcel_from_sender(self):
        self.debug(f'Забираю {self.target_parcel} у отправителя')
        
        yield self.env.timeout(self.env.COURIER_SENDER_PICKUP_TIME_HRS)
        self.target_parcel.first_mile_pickup()
        self.parcels_in_hold = {self.target_parcel}
        self.debug(f'Забрал {self.target_parcel} у отправителя')


    def drop_off_at_wh(self):
        yield self.env.process(self.move(self.wh))
        
        yield self.env.timeout(self.env.COURIER_WAREHOUSE_DEPOSIT_TIME_HRS)
        self.target_parcel.first_mile_dropoff()
        self.wh.dropoff_parcel(self.target_parcel)
        self.parcels_in_hold = None
        self.debug(f'Сдал {self.target_parcel} на {self.wh}')
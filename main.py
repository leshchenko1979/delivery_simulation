import configparser
import datetime
import itertools
import logging
import os
import random
import sys

import simpy
import tqdm

from utils import *
from parcel import ParcelGenerator
from wh_closest_courier import WarehouseManager
from td_tsp_central_wh import TruckDispatcher
from metrics import MetricsManager

class DeliveryEnvironment(simpy.Environment):
    
    def __init__(self):
        super().__init__()
        
        self.read_config()

        self.init_logging()
        
        self.metrics = MetricsManager(self)

        self.parcel_generator = ParcelGenerator(self)
        self.metrics.track_object(self.parcel_generator)
        
        self.warehouse_manager = WarehouseManager(self)
        self.metrics.track_object(self.warehouse_manager)
        
        self.truck_dispatcher = TruckDispatcher(self)        
        self.metrics.track_object(self.truck_dispatcher)

    
    def init_logging(self):
        self.results_timestamp = datetime.datetime.now().strftime("%m%d-%H%M")        
        log_path = f'logs/{self.results_timestamp}.log'
        
        try:
            os.remove(log_path)
        except:
            pass
        
        self.log = logging.getLogger()
        self.log.setLevel(self.LOGGING_LEVEL)

        formatter = logging.Formatter('%(message)s')

        handler = logging.FileHandler(log_path, encoding='utf-8')
        handler.setFormatter(formatter)
        self.log.addHandler(handler)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        self.log.addHandler(handler)


    def read_config(self):
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')

        flat_config = dict(list(itertools.chain(*[config.items(s) for s in config.sections()])))

        for key in flat_config:
            value = flat_config[key]
            try:
                value = float(value)
                if value % 1 == 0:
                    value = int(value)
            except:
                pass
            flat_config[key] = value
            self.__setattr__(key.upper(), value)

        self.flat_config = flat_config
        

    def info(self, msg):
        self.log.info(f'{self.now:.2f}: {msg}')


    def debug(self, msg):
        self.log.debug(f'{self.now:.2f}: {msg}')


    def random_point(self):
        while True:
            x = random.random() * 2 - 1
            y = random.random() * 2 - 1
            if dist(x, y, 0, 0) <= 1:
                return (x * self.CITY_RADUIS_KM, y * self.CITY_RADUIS_KM)
            
            
if __name__ == "__main__":
    env = DeliveryEnvironment()
    with tqdm.tqdm(total = env.SIMULATION_TIME_HRS) as env.pbar:
        env.run(until = env.SIMULATION_TIME_HRS)
    env.metrics.save_results()
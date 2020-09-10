import collections
import pandas as pd


class MetricsManager:            
    
    def __init__(self, env):
        self.env = env
        self.tracked_objects = set()
        self.metrics_log = collections.deque()
        self.results_timestamp = env.results_timestamp

        env.process(self.run())
        
    
    def track_object(self, obj):
        self.tracked_objects.add(obj)


    def run(self):
        interval = self.env.MONITORING_INTERVAL_HRS
        while True:
            self.report_metrics()
            self.env.pbar.update(interval)
            yield self.env.timeout(interval)


    def report_metrics(self):
        
        m = {'time': self.env.now}

        for obj in self.tracked_objects:
            obj.post_metrics(m)

        self.log_metrics_to_console(m)

        self.metrics_log.append(m)


    def log_metrics_to_console(self, m):
        info = self.env.info
        
        info('')
        info('===== Замер KPI =====')
        for key in m:
            info(f'{key}: {m[key]}')

        info('=====================')
        info('')


    def save_results(self):
        
        self.report_metrics()

        pd.DataFrame(self.metrics_log).to_csv(f'metrics/{self.results_timestamp}.csv', index = None)

        results = self.prepare_results()
        self.log_metrics_to_console(results)


        try:
            df = pd.read_csv('simulations.csv')
        except:
            df = pd.DataFrame()
        
        df.append(results, ignore_index = True).to_csv('simulations.csv', index = None)
        

    def prepare_results(self):
        results = {
            'timestamp': self.results_timestamp
        }

        results.update(self.env.flat_config)
                
        results.update(self.metrics_log.pop())
        
        for obj in self.tracked_objects:
            obj.post_results(results)

        self.calc_unit_costs_total(results)

        return results

        
    def calc_unit_costs_total(self, m):

        m['unit_costs_total'] = sum(m[key] for key in m if 'unit_costs_' in key)
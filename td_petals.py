import collections

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from base import DispatcherAbstract, ParcelMover
from utils import dist


class TruckDispatcher(DispatcherAbstract):

    object_type = 'Диспетчер грузовиков'
    version = __name__

        
    def __init__(self, env):
        super().__init__(env, None)

        self.whs = env.warehouse_manager.warehouses
        self.wh_dist_matrix = [[p1.dist(p2) for p2 in self.whs] for p1 in self.whs]
        self.central_wh = min(self.whs, key = lambda wh: dist(wh.x, wh.y, 0, 0))
        self.central_wh.name = f'{self.central_wh.name} (Центральный)'
        
        self.trucks = [ParcelMover(env, 'Грузовик', env.TRUCK_SPEED_KMH, x, self, self.central_wh) 
                       for x in range(env.TRUCKS_NUMBER)]

        self.debug('Рассчитываю шаблонные маршруты грузовиков')
        self.compose_routes()


    def cycle_start_event(self):
        return self.movers_awaiting_dispatch_present
    

    def compose_routes(self):

        # Create the routing index manager.
        central_wh_index = self.whs.index(self.central_wh)
        manager = pywrapcp.RoutingIndexManager(len(self.wh_dist_matrix),
                                            len(self.trucks), central_wh_index)

        # Create Routing Model.
        routing = pywrapcp.RoutingModel(manager)

        # Create and register a transit callback.
        def distance_callback(from_index, to_index):
            """Returns the distance between the two nodes."""
            # Convert from routing variable Index to distance matrix NodeIndex.
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return self.wh_dist_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)

        # Define cost of each arc.
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Add Distance constraint.
        # [START distance_constraint]
        dimension_name = 'Distance'
        routing.AddDimension(
            transit_callback_index,
            0,  # no slack
            self.env.MAX_ROUTE_LEN,  # vehicle maximum travel distance
            True,  # start cumul to zero
            dimension_name)
        distance_dimension = routing.GetDimensionOrDie(dimension_name)
        distance_dimension.SetGlobalSpanCostCoefficient(10000)
        # [END distance_constraint]

        # Setting first solution heuristic.
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

        # Solve the problem.
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            
            self.routes = []
            for vehicle_id, truck in enumerate(self.trucks):
                index = routing.Start(vehicle_id)
                segments = collections.deque()
                while not routing.IsEnd(index):
                    node_index = manager.IndexToNode(index)
                    segments.append(self.whs[node_index])
                    index = solution.Value(routing.NextVar(index))
                segments.rotate(-1)
                self.routes.append(CircularRoute(self, truck, segments))
                
        else:
            raise RuntimeError('Не могу построить маршруты грузовиков')

        for r in self.routes:
            r.assign_next_segment()
    

    def assign_task(self, mover):
        route = self.find_route(mover)
        route.assign_next_segment()
        

    def find_route(self, truck):
        return self.routes[[r.truck for r in self.routes].index(truck)]


    def post_metrics(self, m):
        m['trucks_empty'] = len([t for t in self.trucks if len(t.parcels_in_hold) == 0])
        m['parcels_in_hold_wh_central'] = len(self.central_wh.parcels_in_hold)
        if self.env.TRUCKS_NUMBER:
            m['parcels_in_hold_truck_max'] = max([len(t.parcels_in_hold) for t in self.trucks])
            m['parcels_in_hold_truck_total'] = sum([len(t.parcels_in_hold) for t in self.trucks])
        
        m['odo_truck_total'] = int(sum([t.odometer for t in self.trucks]))


    def post_results(self, m):
        m['ver_disp_truck'] = self.version

        time_unit_mult = self.env.now / self.env.HRS_PER_MON / m['parcels_delivered_total']

        truck_fixed_costs_mon = self.env.TRUCK_COST_PER_MON * self.env.TRUCKS_NUMBER
        fuel_costs = self.env.FUEL_USAGE_L_PER_100_KM * m['odo_truck_total'] / 100 \
            * self.env.FUEL_COST_PER_LITRE
        
        m['unit_costs_trucks'] = int(truck_fixed_costs_mon * time_unit_mult)
        m['unit_costs_fuel'] = int(fuel_costs / m['parcels_delivered_total'])
        
        total_odo = m['odo_truck_total'] + m['odo_courier_total'] 
        m['travel_efficiency_parcels_delivered'] = \
            m['parcels_delivered_direct_dist_total'] / total_odo                

        
class CircularRoute:
    
    def __init__(self, td, truck, segments):
        self.td = td
        self.truck = truck
        self.segments = segments
        self.peripheral_whs = {wh for wh in self.segments 
                               if wh != td.central_wh}

    
    def assign_next_segment(self):
        t = self.truck
        
        if len(self.segments) == 1:
            return
        
        current_wh = t.current_storage
        central_wh = self.td.central_wh        
        
        target_wh = self.segments[0]
        self.segments.rotate(-1)
        
        if target_wh != current_wh:
            self.td.debug(f'Отдаю задачу {self.truck} ехать на {target_wh}')
            
            if current_wh == central_wh:
                to_load = {p for p in central_wh.get_parcels_awaiting_trucks()
                           if p.last_mile_wh in self.peripheral_whs}
            else:
                to_load = current_wh.get_parcels_awaiting_trucks()
            
            resulting_parcels = to_load | t.parcels_in_hold

            if target_wh == central_wh:
                to_unload = {p for p in resulting_parcels 
                             if p.last_mile_wh not in self.segments}
            else:
                to_unload = {p for p in resulting_parcels 
                             if p.last_mile_wh == target_wh}
            
        else:
            self.td.debug(f'{self.truck} получил указание стоять на месте')
            to_load = {}
            to_unload = {}
            
        t.accept_task(target_wh, to_load, to_unload)
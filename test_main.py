import pytest
import simpy
from main import DeliveryEnvironment, Parcel, Warehouse, succeed
from base import Timer


@pytest.fixture
def get_env():
    return DeliveryEnvironment()

@pytest.fixture
def get_warehouse(get_env):
    env = get_env
    return Warehouse(env, 1)


def test_get_parcels_awaiting_trucking(get_warehouse):
    wh = get_warehouse
    p1 = Parcel(wh.env, 1)
    wh.dropoff_parcel(p1)
    p2 = Parcel(wh.env, 2)
    wh.dropoff_parcel(p2)
    succeed(p2.await_truck_dropoff)
    assert len(wh.get_parcels_awaiting_trucking()) == 1
    
    
def test_timer():
    env = simpy.Environment()
    timer = Timer(env, [0, 1])
    
    def run(env, timer):
        timer.punch(0)
        yield env.timeout(1)
        timer.punch(1)
        yield env.timeout(2)
        timer.punch(0)
        yield env.timeout(3)
        timer.punch(None)

    env.process(run(env, timer))
    env.run()
    
    assert timer.total() == 6
    assert timer.timings[0] == 4
    assert timer.timings[1] == 2
    
    
def test_td(get_env):
    env = get_env
    td = env.truck_dispatcher

    wh = set()
    for r in td.routes:
        assert len(r.segments) > 1    
        wh.update(set(r.segments))
        assert list(r.segments)[-1] == td.central_wh
        
    assert len(wh) == len(env.warehouses)
            

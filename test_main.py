import pytest
import simpy
from main import DeliveryEnvironment
from base import Timer


@pytest.fixture
def get_env():
    return DeliveryEnvironment()

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
        timer.punch(0)
        yield env.timeout(3)
        timer.punch(None)

    env.process(run(env, timer))
    env.run()
    
    assert timer.total() == 9
    assert timer.timings[0] == 7
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
            

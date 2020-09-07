import math
import random


def dist(x1, y1, x2, y2):
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)


def succeed(event):
    if not event.triggered:
        event.succeed()
        
        
class Timer:
    '''Keep track of what time gets spent on during an object's lifetime'''
    
    def __init__(self, env, categories):
        self.env = env
        self.categories = categories
        self.timings = {c: 0 for c in categories}
        self.current = None
        
    
    def punch(self, new_category):
        now = self.env.now
        if self.current != None:
            self.timings[self.current] += now - self.last_clock
        self.last_clock = now
        self.current = new_category
        
    
    def total(self):
        return sum(self.timings.values())
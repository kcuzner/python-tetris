"""
Event module

Containues classes for managing evenst and such
"""

class EventDispatcher(object):
    """
    Event object which operates like C# events
    
    "event += handler" adds a handler to this event
    "event -= handler" removes a handler from this event
    "event(*arguments)" calls all of the handlers with the passed
    arguments
    
    Events may be temporarily suppressed by using them in a with
    statement. The context returnd will be this event object.
    """
    def __init__(self):
        """
        Initializes a new event
        """
        self.__handlers = []
        self.__supress_count = 0
    def __call__(self, e):
        if self.__supress_count > 0:
            return
        for h in self.__handlers:
            h(e)
    def __iadd__(self, other):
        if other not in self.__handlers:
            self.__handlers.append(other)
        return self
    def __isub__(self, other):
        self.__handlers.remove(other)
        return self
    def __enter__(self):
        self.__supress_count += 1
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.__supress_count -= 1

class Event(object):
    """
    Instance of an event to be dispatched
    """
    def __init__(self, target, name, *args, **kwargs):
        self.target = target
        self.name = name
        self.args = args
        self.kwargs = kwargs

class EventedObject(object):
    """
    Object with an event and support for bubbling
    """
    def __init__(self, parent=None):
        self.__parent = parent
        self.changed_event = EventDispatcher()
        self.changed_event += self.__on_changed
    def __on_changed(self, e):
        if hasattr(self.__parent, 'changed_event'):
            self.__parent.changed_event(e)
    @property
    def parent(self):
        return self.__parent
    @parent.setter
    def parent(self, value):
        l = self.position
        self.__parent = value
        self.changed_event(Event(self, "parent-changed", current=self.position, last=l))

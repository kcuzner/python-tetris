"""
Main game module for tetris
"""

import random, datetime, math, asyncore
from events import *

class Movable(EventedObject):
    """
    Object with a moveable event and parentage
    
    The moved event has the following siguature:
    (self, current_position, last_position)
        self: The block object that initiated the event
        current_position: self explanatory
        last_position: position as recorded directly before movement
    """
    def __init__(self, local_position, parent=None):
        super().__init__(parent)
        if hasattr(self.parent, 'event'):
            self.parent.event += self.__on_parent_event
        self.__local_position = local_position
    def __on_event(self, e):
        # update parent event handler
        if e.target is self and e.name == "parent-changing":
            if hasattr(e.kwargs['current'], 'event'):
                e.kwargs['current'].event -= self.__on_parent_event
        if e.target is self and e.name == "parent-changed":
            if hasattr(e.kwargs['current'], 'event'):
                e.kwargs['current'].event += self.__on_parent_event
    def __on_parent_event(self, e):
        if e.target is self.parent and e.name == "position-changed":
            # we echo back this event with our new position because
            # we depend on the parent position
            l = self.__translate_position(e.kwargs['last'])
            self.event(Event(self, "position-changed",\
                             current=self.position, last=l))
    @property
    def local_position(self):
        return self.__local_position
    @local_position.setter
    def local_position(self, value):
        l = self.position
        self.__local_position = value
        self.event(Event(self, "position-changed",\
                         current=self.position, last=l))
    @property
    def position(self):
        origin = (0,0)
        if hasattr(self.parent, 'position'):
            origin = self.parent.position
        return self.__translate_position(origin)
        
    def __translate_position(self, origin):
        """
        Returns this block's position translated to an origin
        """
        return (origin[0] + self.__local_position[0], origin[1] + \
                self.__local_position[1])

class Block(Movable):
    """
    Block with a moved event
    """
    def __init__(self, local_position, color, parent=None):
        """
        Initializes the block
        
        parent: Object with a position property used as an origin.
          If none, (0,0) is used. If the parent has a moved event, it
          will be subscribed to
        lx: x position relative to parent
        ly: y position relative to parent
        color: color number to use
        """
        super().__init__(local_position, parent)
        self.__color = color
    @property
    def color(self):
        return self.__color
    @property
    def render(self):
        return (self.color, '#')

class Polyomino(Movable):
    def __init__(self, local_position, parent=None):
        super().__init__(local_position, parent)
        self.blocks = []
    def __check_locations(self, locations):
        pos = self.local_position
        if self.parent is None or not hasattr(self.parent, 'is_clear'):
            return True
        for l in locations:
            if not self.parent.is_clear((pos[0] + l[0], pos[1] + l[1])):
                #raise Exception(pos, l)
                return False
        return True
    def rotate_left(self):
        """
        Attempts to rotate this polyomino left
        """
        new_local_positions = []
        # rotation equation: sin(90)=1 cos(90)=0
        # x' = x*cos(theta) - y*sin(theta)
        # y' = x*sin(theta) + y*cos(theta)
        for b in self.blocks:
            x = b.local_position[0]
            y = b.local_position[1]
            new_local_positions.append((-y, x, b))
        if not self.__check_locations(new_local_positions):
            return False
        for p in new_local_positions:
            p[2].local_position = (p[0], p[1])
        self.event(Event(self, "rotated"))
        return True
    def rotate_right(self):
        """
        Attempts to rotate this polyomino right
        """
        new_local_positions = []
        # rotation equation: sin(-90)=-1 cos(-90)=0
        # x' = x*cos(theta) - y*sin(theta)
        # y' = x*sin(theta) + y*cos(theta)
        for b in self.blocks:
            x = b.local_position[0]
            y = b.local_position[1]
            new_local_positions.append((y, -x, b))
        if not self.__check_locations(new_local_positions):
            return False
        for p in new_local_positions:
            p[2].local_position = (p[0], p[1])
        self.event(Event(self, "rotated"))
        return True
    def move_delta(self, delta):
        """
        Attempts to move this polyomino to the passed position
        """
        new_local_positions = []
        dx = delta[0]
        dy = delta[1]
        for b in self.blocks:
            x = b.local_position[0]
            y = b.local_position[1]
            new_local_positions.append((x + dx, y + dy, b))
        if not self.__check_locations(new_local_positions):
            return False
        l = self.position
        # update our position, no need to opdate our children's position
        self.local_position = (self.local_position[0] + dx,\
                               self.local_position[1] + dy)
        self.event(Event(self, "position-changed",\
                         current=self.position, last=l))
        return True
        
class PolyominoFactory(object):
    """
    Factory callable class for polyominos
    """
    def __init__(self, blocktuples, color):
        """
        Creates a new factory
        
        blocktupes: Set of tuples of (x,y) for each block location
        color: Color number to use for this polyomino
        """
        self.tuples = blocktuples
        self.color = color
    def __call__(self, grid, position):
        """
        Creates a polyomino at the passed location
        """
        polyomino = Polyomino(position, parent=grid)
        for pos in self.tuples:
            polyomino.blocks.append(Block(pos, self.color, \
                                          parent=polyomino))
        return polyomino

class Grid(Movable):
    """
    Represents a game grid
    """
    def __init__(self, position=(0,0), width=10, height=20,parent=None):
        super().__init__(position, parent)
        self.width = width
        self.height = height
        self.grid = []
        for x in range(width):
            self.grid.append([])
            for y in range(height):
                self.grid[x].append(None)
    def is_clear(self, position):
        """
        Returns true if the passed relative position is clear on the
        board
        """
        x = position[0]
        y = position[1]
        if y < 0:
            return True # we have no bound on the upper side
        if x < 0 or x >= self.width or y >= self.height:
            return False
        return True if self.grid[x][y] is None else False
    def add_polyomino(self, polyomino):
        """
        Adds the passed block to this grid. This modifies the blocks
        in the passed polyomino to be relative to the grid. If the
        polyomino's parent is this grid, it no longer has a parent
        """
        # we want the block positions relative to the polyomino, not
        # relative to the parent of the polyomino (us).
        if polyomino.parent is self:
            polyomino.parent = None # should make the origin (0,0)
        for b in polyomino.blocks:
            # we can suppress the move event here since we are simply
            # removing a level of parentage
            lp = b.local_position
            p = b.position
            with b.event: # suppress events from the block
                b.local_position = b.position # as we change position
                b.parent = None
            self.grid[b.position[0]][b.position[1]] = b
            b.parent = self # the block is relative to us now
            self.event(Event(self, "block-added", block=b))
    def clear_rows(self):
        removed = []
        for y in range(self.height):
            row = True
            for x in range(self.width):
                if self.grid[x][y] is None:
                    row = False
                    break
            if row:
                # move the blocks above this one down one row
                # we can do this since we proceed from row 0 upwards
                for x in range(self.width):
                    removed.append(self.grid[x][y])
                for y_p in range(y, 0, -1):
                    for x in range(self.width):
                        self.grid[x][y_p] = self.grid[x][y_p-1]
                        if self.grid[x][y_p] is not None:
                            lpos = self.grid[x][y_p].local_position
                            self.grid[x][y_p].local_position =\
                                (lpos[0], lpos[1]+1)
                for x in range(self.width):
                    self.grid[x][0] = None
        for r in removed:
            self.event(Event(self, "block-removed", block=r))
        return removed

class MasterTetris(EventedObject):
    """
    Tetris game
    """
    def __init__(self, position, block_factories):
        """
        Initializes this tetris game with the passed block_types.
        """
        super().__init__()
        self.grid = Grid(position, parent=self)
        self.__current_piece = None
        self.delta = datetime.timedelta()
        self.__score = 0
        self.__level = 1
        self.__lines = 0
        self.possible_blocks = block_factories
    def __get_new_block(self, position):
        n = random.randrange(0, len(self.possible_blocks))
        return self.possible_blocks[n](self.grid, position)
    @property
    def current_piece(self):
        return self.__current_piece
    @current_piece.setter
    def current_piece(self, value):
        l = self.current_piece
        self.__current_piece = value
        self.event(Event(self, "current-piece-changed",\
                current_pice=self.current_piece, last=l))
    @property
    def score(self):
        return self.__score
    @score.setter
    def score(self, value):
        self.__score = value
        self.event(Event(self, "score-changed",\
                score=self.score))
    @property
    def level(self):
        return self.__level
    @level.setter
    def level(self, value):
        self.__level = value
        self.event(Event(self, "level-changed",\
                level=self.level))
    @property
    def lines(self):
        return self.__lines;
    @lines.setter
    def lines(self, value):
        self.__lines = value
        self.event(Event(self, "lines-changed",\
                lines=self.lines))
    def step(self, delta):
        self.delta += delta
        min_delta = datetime.timedelta(seconds=0.5 / self.level)
        if self.delta >= min_delta:
            self.delta = datetime.timedelta()
            new_piece = False
            if self.current_piece == None:
                new_piece = True
                self.current_piece = \
                    self.__get_new_block((int(self.grid.width / 2), 0))
            # attempt to move the piece down
            if not self.down():
                if new_piece:
                    return False # the game is done
                # check for rows
                self.grid.add_polyomino(self.current_piece)
                self.current_piece = None
                cleared = self.grid.clear_rows()
                self.lines += int(len(cleared) / self.grid.width)
                self.score += int(len(cleared) * (len(cleared) /\
                                                      self.grid.width))
                self.level = int(math.floor(self.lines / 10)) + 1
        return True # continue the game
    def rotate_left(self):
        if self.current_piece is not None:
            if self.current_piece.rotate_left():
                self.event(Event(self, "piece-rotated-left"))
                return True
        return False
    def rotate_right(self):
        if self.current_piece is not None:
            if self.current_piece.rotate_right():
                self.event(Event(self, "piece-rotated-right"))
                return True
        return False
    def left(self):
        if self.current_piece is not None:
            if self.current_piece.move_delta((-1, 0)):
                self.event(Event(self, "piece-moved"))
                return True
        return False
    def right(self):
        if self.current_piece is not None:
            if self.current_piece.move_delta((1, 0)):
                self.event(Event(self, "piece-moved"))
                return True
        return False
    def down(self):
        if self.current_piece is not None:
            if self.current_piece.move_delta((0, 1)):
                self.event(Event(self, "piece-moved"))
                return True
        return False

class SlaveTetris(EventedObject):
    """
    Game that follows another. When this object is called, it processes
    an event as if it were a tetris game
    """
    pass

class NetworkTetrisHost(asyncore.dispatcher):
    """
    Host end of a multiplayer tetris game
    
    Before the game is marked as started, any number of clients can
    connect. After tha game begins, new connections will be closed after
    giving them a message of some sort.
    
    Events are set along the socket. Each block is tracked by using its
    id number, which is unique per game-instance (of which there are
    many)
    
    The host serves as a repeater for each client, so that each client
    sees the events that happen on every other client including the
    host.
    
    It may be possible to do a headless host that just forwards packets
    around.
    
    When everyone's game has ended, the winner is announced.
    
    The host gives each player an identifier. When a client joins, it
    is informed of all the other identifers and the names attached to
    them.
    """
    def __init__(self, host, port, username):
        """
        Initializes the host game
        """
        pass

class NetworkTetrisClient(object):
    """
    """
    pass

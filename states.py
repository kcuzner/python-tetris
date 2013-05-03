"""
Game state manager for tetris
"""

import curses
import time, datetime, math, os, threading
import xml.etree.ElementTree as ET
from abc import ABCMeta, abstractmethod

from events import *
from game import *

class StateManager(object):
    """
    Manages game state and serves as a gateway to the active state
    """
    def __init__(self, initial_state):
        """
        Creates a new manager with an initial state
        
        initial_state: State that will be initialized and entered into
        """
        self.__states = []
        self.__data = {} # shared data for the states
        self.push_state(initial_state)
        self.empty = EventDispatcher() # happens when there are no states
    def push_state(self, state):
        """
        Pushes a new state onto the stack and makes it active
        """
        if self.active_state is not None:
            self.active_state.exit()
        state.init(self)
        state.enter()
        self.__states.append(state)
    def pop_state(self):
        """
        Pops the active state from the stack if it exists and enters
        the next state down
        """
        if self.active_state is not None:
            self.active_state.exit()
            self.__states.pop()
        if self.active_state is not None:
            self.active_state.enter()
        else:
            self.empty(self)
    def replace_state(self, state):
        """
        Replaces the current state with the passed state
        """
        if self.active_state is None:
            self.push_state(state)
        else:
            self.active_state.exit()
            self.__states.pop()
            self.push_state(state)
    @property
    def active_state(self):
        """
        Returns the active state
        """
        if len(self.__states) > 0:
            return self.__states[-1]
        return None
    @property
    def data(self):
        """
        Returns the shared data for this manager
        """
        return self.__data
    def input(self, char):
        """
        Sends the passed character into the active state as input
        """
        if self.active_state is not None:
            self.active_state.input(char)
    def render(self, window, delta, terminal_size=None):
        """
        Renders the current state onto the passed window
        
        window: Curses window to render to
        delta: Seconds that have passed since the last render
        """
        if self.active_state is not None:
            self.active_state.render(window, delta, terminal_size)

class State(metaclass=ABCMeta):
    """
    Base class for a state
    """
    @abstractmethod
    def init(self, manager):
        pass
    @abstractmethod
    def enter(self):
        pass
    @abstractmethod
    def exit(self):
        pass
    @abstractmethod
    def input(self, char):
        """
        Process the passed character as input
        """
        pass
    @abstractmethod
    def render(self, window, delta, terminal_size=None):
        """
        Render this state to the passed window
        """
        pass
        

class StateInitializationException(Exception):
    """
    Exception to be raised when a state cannot initialize itself due
    to one reason or another
    """
    def __init__(self, reason):
        self.reason = reason
    def __str__(self):
        return repr(self.reason)
        
class LoadState(State):
    """
    State which loads the initial resources for the game
    """
    def __load(self):
        # attempt to load the data
        colordefs = {}
        block_types = {}
        tree = ET.parse('data.xml')
        root = tree.getroot()
        if root is not None:
            for color in root.findall('color'):
                colordefs[color.get('id')] = \
                    (get_curses_color(color.get('fg')), \
                     get_curses_color(color.get('bg')))
            for t in root.findall('type'):
                polyominoes = []
                for p in t.findall('polyomino'):
                    blocktuples = []
                    for b in p.findall('block'):
                        blocktuples.append((int(b.get('x')), \
                                            int(b.get('y'))))
                    polyominoes.append(PolyominoFactory(blocktuples,\
                                       int(p.get('color'))))
                block_types[t.get('name')] = polyominoes
        self.manager.data["block_types"] = block_types
        # set up the color definitions
        for i in colordefs:
            color = colordefs[i]
            curses.init_pair(int(i), color[0], color[1])
    def init(self, manager):
        self.manager = manager
        self.loading_thread = threading.Thread(target=self.__load)
        self.loading_thread.start()
    def enter(self):
        pass
    def exit(self):
        pass
    def input(self, char):
        if char == 27: # end this state
            self.loading_thread.join()
            self.manager.pop_state()
    def render(self, window, delta, terminal_size=None):
        if not self.loading_thread.is_alive(): # become the main menu
            self.manager.replace_state(MainMenuState())
            return
        window.clear()
        window.border()
        if terminal_size is None:
            window.addstr(1, 1, "Loading...%s" % str(delta))
        else:
            window.addstr(int(terminal_size.lines / 2),\
                          int(terminal_size.columns / 2) - 5,\
                          "Loading...")

class MainMenuState(State):
    """
    State for when the game is at the main menu
    """
    MENU = [ "New Game", "High Scores", "Quit" ]
    NEW_GAME_INDEX = 0
    HIGH_SCORES_INDEX = 1
    QUIT_INDEX = 2
    def init(self, manager):
        self.manager = manager
        self.changed = False
        self.last_size = None
        self.selected = 0 # selected menu index
    def enter(self): 
        self.changed = True # when we enter, we change
    def exit(self):
        pass
    def input(self, char):
        if char == 27:
            self.manager.pop_state()
        elif char == curses.KEY_UP and self.selected > 0:
            self.selected -= 1
            self.changed = True
        elif char == curses.KEY_DOWN and \
                self.selected < len(MainMenuState.MENU) - 1:
            self.selected += 1
            self.changed = True
        elif char == 10:
            if self.selected == MainMenuState.NEW_GAME_INDEX:
                self.manager.push_state(NewGameMenuState())
            elif self.selected == MainMenuState.HIGH_SCORES_INDEX:
                self.manager.push_state(HighScoresState())
            elif self.selected == MainMenuState.QUIT_INDEX:
                self.manager.pop_state()
            self.changed = True
    def render(self, window, delta, terminal_size=None):
        if not self.changed:
            return
        window.clear()
        window.border()
        title = "Tetris"
        dash = "---"
        menu = "Main Menu"
        window.addstr(1, self.__get_column(terminal_size, title), title)
        window.addstr(3, self.__get_column(terminal_size, dash), dash)
        window.addstr(4, self.__get_column(terminal_size, menu), menu)
        for i in range(len(MainMenuState.MENU)):
            phrase = MainMenuState.MENU[i]
            attr = curses.A_STANDOUT if i == self.selected else 0
            window.addstr(6 + i, \
                          self.__get_column(terminal_size, phrase),\
                          phrase, attr)
        self.changed = False
    def __get_column(self, terminal_size, phrase):
        if terminal_size == None:
            return 0
        else:
            return int(terminal_size.columns / 2) - int(len(phrase) / 2)

class NewGameMenuState(State):
    """
    State for when creating a new game
    """
    def init(self, manager):
        self.manager = manager
        if "block_types" not in self.manager.data:
            raise Exception(self.manager.data)
            #raise StateInitializationException(\
            #        "Block types uninitialized")
        if len(self.manager.data["block_types"]) == 0:
            raise StateInitializationException("No block types loaded")
        self.block_types = list(self.manager.data["block_types"].keys())
        self.block_types.sort()
        self.selected = 0
        self.changed = False
        self.last_size = None
    def enter(self):
        self.changed = True
    def exit(self):
        pass
    def input(self, char):
        if char == curses.KEY_UP and self.selected > 0:
            self.selected -= 1
            self.changed = True
        elif char == curses.KEY_DOWN and\
                self.selected < len(self.block_types)-1:
            self.selected += 1
            self.changed = True
        elif char == 10:
            # create a new game
            blocks = self.manager.data["block_types"][self.block_types[self.selected]]
            self.manager.replace_state(GameState(blocks))
    def render(self, window, delta, terminal_size=None):
        if not self.changed and self.last_size == terminal_size:
            return
        window.clear()
        window.border()
        title = "Select a game type:"
        window.addstr(2, self.__get_column(terminal_size, title), title)
        for i in range(len(self.block_types)):
            phrase = self.block_types[i]
            attr = curses.A_STANDOUT if i == self.selected else 0
            window.addstr(4 + i, \
                          self.__get_column(terminal_size, phrase),\
                          phrase, attr)
        self.changed = False
    def __get_column(self, terminal_size, phrase):
        if terminal_size == None:
            return 0
        else:
            return int(terminal_size.columns / 2) - int(len(phrase) / 2)
    
class HighScoresState(State):
    """
    State for viewing the high scores
    """
    def init(self, manager):
        self.manager = manager
    def enter(self):
        pass
    def exit(self):
        pass
    def input(self, char):
        pass
    def render(self, window, delta, terminal_size=None):
        self.manager.pop_state()
    
class GameState(State):
    """
    State for playing a game
    """
    def __init__(self, blocks):
        self.changed = False
        self.last_size = None
        self.game = Tetris((35, 1), blocks)
        self.game.changed_event += self.__on_game_changed
    def __on_game_changed(self, e):
        self.changed = True
    def init(self, manager):
        self.manager = manager
    def enter(self):
        self.changed = True
    def exit(self):
        pass
    def input(self, char):
        if char == 27:
            self.manager.pop_state()
        elif char == curses.KEY_UP:
            self.game.rotate_left()
        elif char == curses.KEY_LEFT:
            self.game.left()
        elif char == curses.KEY_RIGHT:
            self.game.right()
        elif char == curses.KEY_DOWN:
            self.game.down()
        elif char == 32:
            self.manager.push_state(PausedState())
    def render(self, window, delta, terminal_size=None):
        if not self.game.step(delta):
            self.manager.pop_state()
            return
        if not self.changed:
            return # nothing to do here
        window.clear()
        window.border()
        window.hline(21, 34, ord('-'), 12)
        window.vline(1, 34, ord('|'), 20)
        window.vline(1, 45, ord('|'), 20)
        if self.game.current_piece is not None:
            for b in self.game.current_piece.blocks:
                window.addch(b.position[1], b.position[0],\
                             ord('#'),\
                             curses.color_pair(b.color))
        for x in range(self.game.grid.width):
            for y in range(self.game.grid.height):
                b = self.game.grid.grid[x][y]
                if b is not None:
                    window.addch(b.position[1], b.position[0],\
                                 ord('#'),\
                                 curses.color_pair(b.color))
        window.addstr(10, 50, "Score: %i" % self.game.score)
        window.addstr(11, 50, "Lines: %i" % self.game.lines)
        window.addstr(12, 50, "Level: %i" % self.game.level)
        self.changed = False
        
class PausedState(State):
    """
    State during which the game is paused. This only overwrites a
    small portion of the screen
    """
    def init(self, manager):
        self.manager = manager
        self.changed = False
    def enter(self):
        self.changed = True
    def exit(self):
        pass
    def input(self, char):
        self.manager.pop_state() # any input makes us leave
    def render(self, window, delta, terminal_size=None):
        if not self.changed:
            return
        t = "Paused"
        p = "Press any key to unpause"
        rb = 0 #row base
        if terminal_size is not None:
            rb = int(math.ceil(terminal_size.lines / 2)) - 1
        window.addstr(rb, self.__get_column(terminal_size, t), t,\
            curses.A_STANDOUT)
        window.addstr(rb + 1, self.__get_column(terminal_size, p), p,\
            curses.A_STANDOUT)
        self.changed = False
    def __get_column(self, terminal_size, phrase):
        if terminal_size == None:
            return 0
        else:
            return int(terminal_size.columns / 2) - int(len(phrase) / 2)
        
def get_curses_color(name):
    if name == "black":
        return curses.COLOR_BLACK
    elif name == "blue":
        return curses.COLOR_BLUE
    elif name == "cyan":
        return curses.COLOR_CYAN
    elif name == "green":
        return curses.COLOR_GREEN
    elif name == "magenta":
        return curses.COLOR_MAGENTA
    elif name == "red":
        return curses.COLOR_RED
    elif name == "white":
        return curses.COLOR_WHITE
    elif name == "yellow":
        return curses.COLOR_YELLOW
    else:
        return None

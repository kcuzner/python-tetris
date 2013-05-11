Tetris
======

But not really
--------------

By Kevin Cuzner

TODO
----

 * Handle window resizing
 * High score screen
 * Network games
 * Move from curses to pyglet
   * Yay 3D!

Network Stuff
-------------

 * A network game object has two grids
 * It sends events for one and receives events for another
 * Game modes
   * Direct P2P - Games open some high numbered port and wait for a
     connection
   * Online matchup - Requires me to make a server for it...probably
     using nodejs or something...but maybe python for consistency
 * Each block gets an identifier. This comes from a statically
   incrementing variable
 * 

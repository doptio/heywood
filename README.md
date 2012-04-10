Heywood
=======

Python port of the Ruby Procfile runner foreman, with a few twists:

 * Does not force every process to run inside a shell.
 * Restart process when one fails, instead of kill all others.
 * Restart all processes on file-changes (using pyinotify).

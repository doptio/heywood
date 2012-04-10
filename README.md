= Heywood

Python port of the Ruby Procfile runner foreman, with a few twists:

 * Restart process when one fails, instead of kill all others.
 * Restart all processes on file-changes (using pyinotify).

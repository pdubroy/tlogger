# About tlogger

tlogger is a Firefox extension for capturing click-stream web browsing logs.
In other words, it collects data about how the browser is used. Mainly it
records navigation events and tab events, as well as the UI actions that cause
those events. It's roughly similar to the [Spectator extension](https://addons.mozilla.org/en-US/firefox/addon/6326), but with a few key differences:

- it's compatible with Firefox 2 *and* 3

- it doesn't submit **ANY** data automatically, to anyone. Everything stays on
in your profile directory, in a human-readable format.

- URLs are obfuscated on a per-user basis. From the log file, someone can see 
when the user revisits a site or a URI, but there is no way to determine what 
the actual URI is. It's also not possible to make comparisons between users.

- it can log a few things that Spectator can't, like when javascript on a web page changes window.location.href.

tlogger was originally developed for web browsing study performed in late 2008
by [Patrick Dubroy](http://dubroy.com) at the University of Toronto. The "t" stands for "tab", or
maybe "Toronto" -- take your pick.

The tlogger source is managed on GitHub at <http://github.com/pdubroy/tlogger/>.

## License

Licensed under the GNU GPL version 2 (see GPL-LICENSE.txt).

## Credits

Copyright (c) 2009 [Patrick Dubroy](http://dubroy.com), with a few exceptions:

- parseUri.js is (c) 2007 [Steven Levithan](http://stevenlevithan.com) and was 
originally licensed under the MIT License.
- json2.js (http://www.json.org/json2.js) is public domain.
- Screengrab.js is (c) 2004-2007 Andy Mutton <andy@5263.org>, with some 
modifications by Patrick Dubroy.

# Instructions

## Installation

tlogger can be installed like any old Firefox add-on. 

**Development:**

Go to your Firefox profile (see [here](http://support.mozilla.com/kb/Profiles)
for instructions on how to find it). In the "extensions" directory, create a
file named "tlogger@dubroy.com" containing a single line with the path to
this directory. E.g.,

  /Users/Patrick/dev/tlogger
  
**Distribution:**

You can create an XPI for distribution by simply zipping up the contents of
this directory. The XPI can then be installed by navigating to the XPI in
Firefox (either on disk or on a webserver).

You can find the (hopefully) latest XPI [here](http://dubroy.com/tlogger/tlogger.xpi).

## Log file

tlogger creates a directory named "tlogger" in the user's profile directory
containing three files:

- extstore.dat: the main log file. The format is made for simple parsing: each
line contains a timestamp and a JSON object.
- strings.dat: contains the mappings for the obfuscated URIs
- focus.dat: contains information about when Firefox gains and loses focus

tlogger also adds a menu under Tools with two entries:

- "Show log file" creates a copy of extstore.dat and reveals it in a file
browser. This allows users to view their log file without running the risk
of modifying or deleting the original.
- "Search for string" allows the user to figure out what the obfuscated version
of a site is. This is useful if the user is willing to reveal the identity of
some of the sites they visit, e.g. search engines.


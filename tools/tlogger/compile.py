#! /user/bin/env python

# Copyright (c) 2009 Patrick Dubroy (http://dubroy.com)
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

from __future__ import with_statement

__author__ = "Patrick Dubroy (http://dubroy.com)"
__license__ = "GNU GPL v2"

import collections
import logging as _logging
import pdb

# Get a JSON library. Prefer cjson if it's installed (it's about 10x faster),
# but fall back to json (if Python >= 2.6) or simplejson
try:
	import cjson as json
except ImportError:
	try:
		import json
	except ImportError:
		import simplejson as json

import sys
import traceback

import simpleopt
import tlogger

__all__ = ["compile", "write_to_file"]

#-----------------------------------------------------------------------------
# Constants
#-----------------------------------------------------------------------------

# User-triggered events which can be the cause of a navigation action
USER_NAVIGATION_EVENTS = [
	"URLBarCommand",
	"SearchBarSearch",
	"RightClickSearch",
	"LINK_CLICK",
	"RIGHT_CLICK",
	"GoHome", # Fx3 only
	"BrowserHomeClick", # Fx2 only
	"openOneBookmark", # Fx2 only
	"history openURLIn", # Fx2 only
	"NEW_WINDOW", # Opens the home page

	# These don't always start a navigation action, but they can

	"NEW_TAB", # Will normally open a blank page
	"DOCUMENT_CLICK",
	"window_mousedown",
	"document_mousedown"
]

# These event might be triggered by the user or by javascript, although they
# will usually be preceeded by a user action either way
OTHER_NAVIGATION_EVENTS = [
	"gotoHistoryIndex",
	"OnHistoryGoBack",
	"BrowserForward",
	"OnHistoryReload",
	"form_submit",
	"js_location_change" # Fx2 only
]

# These are user-triggered events that do not cause navigation to occur
USER_NON_NAVIGATION_EVENTS = [
	"TabClose",
	"answer",
	"window_unload",
	"TabSelect",
	"TabMove",
]

#-----------------------------------------------------------------------------
# Various helpers
#-----------------------------------------------------------------------------

def is_user_action(event):
	name = event["event"]
	return (name in USER_NAVIGATION_EVENTS or name in USER_NON_NAVIGATION_EVENTS)

def is_navigation_cause(event):
	name = event["event"]
	return (name in USER_NAVIGATION_EVENTS or name in OTHER_NAVIGATION_EVENTS)

def get_url(event, default=None):
	"""Get the URL from the event without having to remember what it's called."""

	if event["event"] == "LINK_CLICK":
		return event["href"]
	elif event["event"] == "form_submit": 
		return event.get("action", default)
	else:
		return event.get("url", default)

def millis_between(event1, event2):
	return abs(event1["time"] - event2["time"])
	
def seconds_between(time_or_evt1, time_or_evt2):
	"""Returns a float indicating the number of seconds between the events or times."""

	time1 = time_or_evt1["time"] if isinstance(time_or_evt1, dict) else time_or_evt1
	time2 = time_or_evt2["time"] if isinstance(time_or_evt2, dict) else time_or_evt2
	return abs(time1 - time2) / 1000.0

#-----------------------------------------------------------------------------
# Debug helpers -- some simple code for debugging problems with log files.
#-----------------------------------------------------------------------------

class MyLogger(object):
	"""A custom Logger-like class whose sole purpose is to allow us to
	include the line number from the data file in the messages. There are 
	other ways to do this, but they're all more complicated than this."""

	def __init__(self, iterator):
		# By creating everything we need for logging at this point,
		# it allows the caller to redirect sys.stderr
		self._logger = _logging.getLogger("tlogger.compile")
		self._logger.setLevel(_logging.INFO)
		self._handler = _logging.StreamHandler(sys.stderr)
		self._handler.setFormatter(_logging.Formatter("%(levelname)s: %(message)s"))
		self._logger.addHandler(self._handler)
		self._it = iterator

	def cleanup(self):
		self._handler.close()
		self._logger.removeHandler(self._handler)

	def debug(self, msg, *args, **kwargs):
		self._logger.debug(("  (%5s) " % self._it._line_count) + msg, *args, **kwargs)

	def info(self, msg, *args, **kwargs):
		self._logger.info(("   (%5s) " % self._it._line_count) + msg, *args, **kwargs)

	def warning(self, msg, *args, **kwargs):
		self._logger.warning(("(%5s) " % self._it._line_count) + msg, *args, **kwargs)

	def error(self, msg, *args, **kwargs):
		self._print_error(msg, *args, **kwargs)
		raise Exception, msg

	def _print_error(self, msg, *args, **kwargs):
		self._logger.error((" (%5s) " % self._it._line_count) + msg, *args, **kwargs)

def _assert(condition, msg=""):
	if not condition:
		logger.error(msg)

#-----------------------------------------------------------------------------
# Functions for emitting the high-level events
#-----------------------------------------------------------------------------
		
def Event(orig_event, name=None, keys=None, **kwargs): 
		"""Create a new event with the given name, copying the attributes 
		specified by 'keys' from the original event. If 'name' is none, it will 
		be taken from the original event. If 'keys' is None, all keys will be 
		copied from the original event. Any kwargs specified will also be added 
		to the event data."""

		data = {}

		# If no keys are specified, use all the keys from the original event
		if orig_event is not None:
			if keys is not None:
				for key in keys:
					data[key] = orig_event[key]
			else:
				data = orig_event.copy()

			# Always copy the 'time' field
			if "time" in orig_event:
				data["time"] = orig_event["time"]

		data.update(kwargs)

		# If the name is not specified, use the name of the original event
		data["event"] = name or orig_event["event"]

		_assert("time" in data, "Event must have a time")

		return data
	
#-----------------------------------------------------------------------------
# Classes representing the current state of the browser
#-----------------------------------------------------------------------------

class Window(object):
	def __init__(self, win_id):
		self.winId = win_id
		self.tabs = []
		self.gotohistoryindex_event = None
		self._tab_selections = [] # A history of all tab selections
		self.tlogger_init = False
		self.navigation_causes = collections.deque()
		self.pending_tab_close_index = -1

	def __str__(self):
		return self.winId

	def get_selected_tab(self, millis=None):
		if len(self._tab_selections) == 0:
			return None

		if millis is None:
			return self._tab_selections[-1][1]

		# Return the tab that was selected at the given time
		for sel_time, tab in reversed(self._tab_selections):
			if sel_time < millis:
				return tab

	def select_tab(self, millis, tab):
		self._tab_selections.append((millis, tab))

	def insert_tab(self, millis, tab, index):
		"""Insert the tab at the given index. If the index exceeds the current
		number of tabs, the tab array will be grown to accomodate it."""

		# After the selected tab is closed, events up to and including the next
		# TabSelect will have a tabIndex that doesn't yet reflect the TabClose.
		if 0 <= self.pending_tab_close_index < index:
			index -= 1

		if len(self.tabs) == 0:
			self.select_tab(millis, tab)

		if index < len(self.tabs):
			# When TabOpen events arrive out of order, we put in placeholders.
			# If there's a placeholder at the given index, assume it should be
			# overwritten. Otherwise, insert and grow the list. 
			if self.tabs[index] is None:
				self.tabs[index] = tab
			else:
				self.tabs.insert(index, tab)
		else:
			self.tabs += [None] * (index - len(self.tabs))
			self.tabs.append(tab)

	def check_tab_index(self, tab, event):			
		index = event["tabIndex"]
		# After the selected tab is closed, events up to and including the next
		# TabSelect will have a tabIndex that doesn't yet reflect the TabClose.
		if 0 <= self.pending_tab_close_index < index:
			index -= 1

		_assert(tab.get_index() == index, "%s has inconsistent tabIndex" % tab.tabId)

class BackStack(object):
	def __init__(self):
		self._stack = []
		self._current_index = -1

	def process(self, nav_action):
		cause_descr = nav_action.get_cause_descr()
		url = nav_action.url
		distance = 0

		back_distance = self._search(self._current_index, url, backwards=True)
		if back_distance is not None:
			back_distance = abs(back_distance)
		fwd_distance = self._search(self._current_index, url, backwards=False)

		if cause_descr == "OnHistoryGoBack":
			if back_distance is None:
				logger.warning("No match for back URL")
			else:
				self._current_index -= back_distance
				if back_distance != 1:
					logger.info("Actual back distance: %d" % back_distance)
		elif cause_descr == "BrowserForward":
			if fwd_distance is None:
				logger.warning("No match for forward URL")
			else:
				self._current_index += fwd_distance
				if fwd_distance != 1:
					logger.info("Actual fwd distance: %d" % fwd_distance)

		# All nav actions will include these attributes, for info purposes
		nav_action.back_distance = back_distance
		nav_action.forward_distance = fwd_distance

		if cause_descr == "gotoHistoryIndex":
			index = nav_action.cause["index"]
			# If the URL's not found at the given index, look for the closest match
			matches = []
			matches.append(self._search(index, url, backwards=False))
			if matches[0] != 0:
				matches.append(self._search(index, url, backwards=True))
			matches = [x for x in matches if x is not None]
			if len(matches) > 0:
				matches.sort(lambda a, b: cmp(abs(a), abs(b)))
				self._current_index = index + matches[0]
				if matches[0] != 0:
					logger.info("gotoHistoryIndex index off by %d" % abs(matches[0]))
				nav_action.match_index = self._current_index
			else:
				logger.warning("No match for gotoHistoryIndex URL")

		if cause_descr not in ["OnHistoryGoBack", "BrowserForward", "gotoHistoryIndex"]:
			# Don't push a URL that matches the current one, unless the cause
			# was form_submit (because there is POST data)
			if (len(self._stack) == 0 or cause_descr == "form_submit"
			or (url != self._stack[-1][0] and url != self._stack[-1][1])):
				# Push the URL onto the stack
				self._current_index += 1
				self._stack[self._current_index:] = [(url, nav_action.original_url)]

	def _search(self, i, target, backwards=True):
		'''Beginning at index i, search for the target URL in the back stack.
		Return the distance from i at which the target was found, or None if
		the target was not found.

		'''
		if backwards:
			seq = reversed(self._stack[:i+1])
			sign = -1
		else:
			seq = self._stack[i:]
			sign = 1

		for dist, (url, orig_url) in enumerate(seq):
			if url == target or orig_url == target:
				return dist * sign
		return None

class Tab(object):
	def __init__(self, win, tab_reg_event, cause_event, opened_new_tab_with):
		# These attributes always exist
		self.tabId = tab_reg_event["tabId"]
		self.win = win
		self.tab_open_cause = cause_event
		self.opened_new_tab_with = opened_new_tab_with

		self.tab_open_event = None
		self.restored = False
		self.nav_action = None
		self.last_nav_action = None
		self.current_url = None
		
		# Ensure that a nav cause can never occur before the cause of a previous nav action
		self.last_navigation_time = 0

		self.back_stack = BackStack()

	def __str__(self):
		return self.tabId

	def complete_tab_open(self, event):
		self.win.insert_tab(event["time"], self, int(event["tabIndex"]))
		
		# Emit the top_open event
		cause = self.tab_open_cause
		if cause is None:
			cause_descr = "unknown"
		elif cause["event"] == "window_onload":
			cause_descr = "default"
		else:
			cause_descr = cause["event"]
			if self.opened_new_tab_with:
				cause_descr += "+openNewTabWith"
		
		self.tab_open_event = Event(
			event, "tab_open", cause=cause_descr, tab_count=len(self.win.tabs))
		event_stream.append(self.tab_open_event)

	def has_navigated(self):
		"""Return True if this tab has ever had a navigation action."""
		return not (self.nav_action is None and self.last_nav_action is None) 

	def _get_navigation_cause(self, nav_event):
		url = nav_event["href"]
		cause = None
		javascript_used = False

		# Check if the event was triggered by javascript
		# We don't treat that as a cause in and of itself, though.

		# Look for the "cause" attribute; if it's not there, it's not js-caused
		cause_attr = nav_event.get("cause", None)
		if cause_attr:
			javascript_used = cause_attr.startswith(("javascript:", "http"))
		
		# In Fx2, js-caused events are preceded by a js_location_change event	
		if browser_state.event_history[-1]["event"] == "js_location_change":
			javascript_used = True

		for tab, evt in reversed(self.win.navigation_causes):
			# Don't search too far back
			if evt["time"] < self.last_navigation_time or seconds_between(nav_event, evt) > 5:
				break

			# If the URL matches, this is the most likely cause
			if get_url(evt, None) == url:
				cause = evt
				break
			elif cause is None and tab is self:
				cause = evt

		# If it's the first nav action on the tab, take cause from tab_open
		if not self.has_navigated() and (cause is None or self.restored):
			cause = self.tab_open_cause

		if cause:
			cause_url = get_url(cause, None)
			if cause_url:
				# The HREF of a link might be a "javascript://" url
				if cause_url.startswith("javascript:"):
					javascript_used = True
				
				# If the URL is there, make sure they match. Too many false negatives with js though
				if not javascript_used and cause_url != url:
					logger.warning("Nav action %s for %s URL %s" % (cause_url, cause["event"], url))
		return (cause, javascript_used)

	def _new_navigation_action(self, nav_event, from_url):
		url = nav_event["href"]

		# We don't have real key down events; insert a fake ones as appropriate
		keyDownTime = nav_event["lastKeyDownTime"]
		if browser_state.event_history[-1]["time"] < keyDownTime:
			tab = self.win.get_selected_tab(keyDownTime)
			self.win.navigation_causes.append(
				(tab, { "event":"keyDown", "time":keyDownTime, "win":nav_event["win"] }))
	
		cause, js_used = self._get_navigation_cause(nav_event)
		self.last_navigation_time = nav_event["time"]
		return NavigationAction(self, url, from_url, cause, js_used)

	def load_start(self, event):
		url = event["href"]

		if self.nav_action:
			# See if we have consecutive load_start events on the same tab
			prev_event = browser_state.event_history[-1]
			if prev_event["event"] == "load_start" and prev_event["tabId"] == event["tabId"]:
				if url == self.nav_action.url:
					pass # Duplicate event, just ignore it
				else:
					# Treat it as a redirect
					self.nav_action.redirect(self.nav_action.url, url)
				return
		elif not self.has_navigated() and event["href"] == "about:blank":
			# Ignore all events for about:blank on a new tab
			return

		new_nav_action = self._new_navigation_action(event, self.current_url)

		# Check if we appear to be in the middle of a nav action (i.e., have seen
		# load_start but no LocationChange yet		
		if self.nav_action:
			cause_descr = new_nav_action.get_cause_descr()
			if self.nav_action.cause == new_nav_action.cause:
				if self.nav_action.url == url:
					logger.warning("Ignoring duplicate load_start (same URL and cause)")
				else:
					logger.error("Different load_starts (%s vs. %s) share cause %s" %
						(self.nav_action.url, url, cause_descr))
				return

			# The events have distinct causes, so assume they're separate events

			old_cause_descr = self.nav_action.get_cause_descr()
			if self.nav_action.url == url:
				if old_cause_descr == cause_descr:
					logger.info("Duplicate load_starts caused by %s %ss apart" % 
						(cause_descr, seconds_between(self.nav_action.cause, new_nav_action.cause)))
				else:
					logger.info("Duplicate load_start events, but different causes")
			else:
				time_diff = (event["time"] - self.nav_action.start_time)/1000.
				logger.warning("load_start[%s] %.2fs after load_start[%s]" %
					(cause_descr, time_diff, old_cause_descr))
			self.last_nav_action = self.nav_action
			self.last_nav_action.emit_event()
		elif new_nav_action.cause is None:
			prev = self.last_nav_action
			if prev.is_loaded():
				# If it's very soon after a load, good chance it's a meta redirect
				# Maybe this happens quicker than 200ms?
				if (event["time"] - prev.load_time) < 150:
					new_nav_action.cause = {"event":"meta-redirect?"}
			elif (event["time"] - prev.location_change_time) < 150:
				new_nav_action.cause = {"event":"js-redirect?"}

		self.nav_action = new_nav_action			
		self.nav_action.load_start(url, event["time"])
		
	def redirect(self, event):
		if self.nav_action is None or self.nav_action.url is None:
			logger.error("redirect without load_start")
		self.nav_action.redirect(event["from_url"], event["to_url"])
		
	def location_change(self, event):
		if self.nav_action is None:
			if not self.has_navigated() and event["href"] == "about:blank":
				# Ignore all events for about:blank on a new tab
				return

			nav_action = self._new_navigation_action(event, self.current_url)
			
			if not self.has_navigated():
				if nav_action.cause is None:
					# Assume this was caused by whatever opened the tab
					nav_action.cause = self.tab_open_cause
			elif nav_action.shares_cause(self.last_nav_action):
				if nav_action.url == self.last_nav_action.url:
					logger.warning("Ignoring LocationChange (has duplicate url and cause)")
					return
				# They're different nav actions, so they can't share a cause
				nav_action.cause = None			
			self.nav_action = nav_action

		self.back_stack.process(self.nav_action)

		if self.nav_action.location_change(event):
			self.current_url = event["href"]
			self.last_nav_action = self.nav_action
			self.nav_action = None
		
	def get_index(self):
		try:
			return self.win.tabs.index(self)
		except ValueError:
			return -1
			
	def set_restored(self):
		"""This tab is being restored. There's no reason to ever do the opposite."""
		if self.nav_action or self.last_nav_action:
			logger.warning("TabRestore on non-fresh tab")
		self.restored = True

class NavigationAction(object):
	def __init__(self, tab, url, from_url, cause_evt, javascript_used):
		self.tab = tab
		self.url = url
		self.original_url = None # If the request was redirected
		self.from_url = from_url or ""
		self.cause = cause_evt
		self.cause_time = None 
		self.javascript_used = javascript_used

		self.start_time = None
		self.load_started = False
		self.location_change_time = 0
		self.load_time = None

		# These fields indicate how far away the URL was in the back/fwd stack
		# (Used for all navigation events, not just back and forward events)
		self.back_distance = None
		self.forward_distance = None

	def shares_cause(self, other_nav_action):
		"""Return True if nav_action has the same non-None cause is this one."""
		if self.cause is None or other_nav_action is None:
			return False
		return self.cause == other_nav_action.cause

	def is_started(self):
		return (self.start_time is not None)

	def _is_hash_change_only(self, old_url, new_url):
		# Check if everything before the '#' is the same in the two URLs
		return old_url.split("#")[0] == new_url.split("#")[0]

	def check_url(self, url, event_name):
		if self.url != url:
			if not (event_name == "load" and self._is_hash_change_only(self.url, url)):
				logger.warning("%s (%s) doesn't match nav action (%s)" % 
					(event_name, url, self.url))
				
	def load_start(self, url, start_time):
		if self.load_started:
			logger.error("Multiple load_start events")
		self.load_started = True
	
		# Only some causes (LINK_CLICK, form_submit, etc.) will set the URL
		if self.url is not None:
			self.check_url(url, "load_start")
		self.url = url
		self.start_time = start_time
		
	def redirect(self, from_url, to_url):
		self.check_url(from_url, "redirect")
		if self.original_url is None:
			self.original_url = self.url
		self.url = to_url
		
	def location_change(self, event):
		"""Return True if the caller should continue processing this event."""

		if self.url and not self._is_hash_change_only(self.url, event["href"]):
			logger.warning("Ignoring LocChange to %s, expected %s" % (event["href"], self.url))
			# The LocationChange doesn't match the load_start, so ignore it. This seems 
			# to only happen when the matching LocationChange is coming up next
			return False
		self.url = event["href"] # URL from this event is canonical

		# If only the hash changed, don't expect a corresponding load event
		old_url = self.tab.current_url or ""
		if not self.is_started() and not self._is_hash_change_only(old_url, event["href"]):
			# Don't print an error if this is the first nav event on this tab
			# When the tab was opened from another tab, we'll be missing
			# the load_start and redirect events
			if self.tab.last_nav_action is not None:
				logger.warning("LocationChange without load_start")

		self.location_change_time = event["time"]
		if self.start_time is None:
			self.start_time = self.location_change_time

		self.emit_event()
		return True
			
	def load(self, url, timestamp):
		self.check_url(url, "load")
		self.load_time = timestamp
		
	def is_loaded(self):
		return self.load_time is not None

	def get_cause_descr(self):
		if self.cause is None:
			return "unknown"
		return self.cause["event"]

	def emit_event(self):
		nav_event = Event(None, "navigation",
			time=self.start_time,
			win=str(self.tab.win),
			tabId=str(self.tab),
			url=self.url,
			from_url=self.from_url,
			location_changed=(self.location_change_time != 0))
		cause_descr = self.get_cause_descr()
		if self.cause_time is not None:
			diff_in_secs = (self.start_time - self.cause_time) / 1000.0
			nav_event["secs_since_cause"] = diff_in_secs
		if self.javascript_used:
			cause_descr += "+js"
		nav_event["cause"] = cause_descr
		if self.original_url:
			nav_event["original_url"] = self.original_url
		if self.back_distance is not None:
			nav_event["back_distance"] = self.back_distance
		if self.forward_distance is not None:
			nav_event["forward_distance"] = self.forward_distance

		# This is only for events caused by gotoHistoryIndex, to indicate the
		# index in the back/fwd stack at which the matching URL was found
		if hasattr(self, "match_index"):
			nav_event["match_index"] = self.match_index
		
		event_stream.append(nav_event)
			
class BrowserState(object):
	def __init__(self):
		self.windows = {}
		self._all_tabs = {}
		self.nav_action = None
		self.active_window = None
		self.last_window_closed = None
		self.event_history = collections.deque()
		
	def get_window(self, event):
		return self.windows.get(event["win"], None)
		
	def get_tab(self, event):
		if "tabId" in event:
			return self._all_tabs[event["tabId"]]
		win = self.get_window(event)
		if "tabIndex" in event:
			return win.tabs[event["tabIndex"]]
		return win.get_selected_tab()	

	def new_window(self, event):
		win_id = event["win"]
		_assert(win_id not in self.windows, "Duplicate win id")

		# Determine what caused the tab to be opened
		if len(self.event_history) == 0:
			cause_descr = "default"
		else:
			cause = self.event_history[-1]
			if cause["event"] == "openNewWindowWith":
				root_cause = self.event_history[-2]
				cause_descr = "%s/%s" % (root_cause["event"], cause["event"])
			else:
				cause_descr = cause["event"]
		event_stream.append(Event(event, "window_open", cause=cause_descr))

		self.windows[win_id] = Window(win_id)
		return self.windows[win_id]
		
	def close_window(self, win, time):
		del self.windows[win.winId]
		self.last_window_closed = (win.winId, time)
		
	def window_recently_closed(self, event):
		prev_event = self.event_history[-1]
		if prev_event["event"] == "window_unload" and prev_event["win"] == event["win"]:
			return True
		if self.last_window_closed is not None:
			win_id, time = self.last_window_closed
			# Check if the window was very recently closed
			return win_id == event["win"] and (event["time"] - time) < 500
		return False

	def new_tab(self, tab_reg_event):
		tabId = tab_reg_event["tabId"]
		_assert(tabId not in self._all_tabs, "Duplicate tabId")

		win = self.get_window(tab_reg_event)

		# Determine what caused the tab to be opened
		cause_event = self.event_history[-1]
		openNewTabWith = False
		if cause_event["event"] == "window_onload":
			if len(win.tabs) != 0:
				logger.error("Expected to be first tab on window")
		elif cause_event["event"] == "openNewTabWith":
			# The user chose to open a link in a new tab. Find the root cause
			openNewTabWith = True
			cause_event = self.event_history[-2]
		
		tab = Tab(win, tab_reg_event, cause_event, openNewTabWith)
		self._all_tabs[tabId] = tab
		return tab
		
	def get_all_registered_tabs(self):
		return self._all_tabs.values()
		
	def update_active_window(self, event):
		win = self.windows[event["win"]]
		self.active_window = win
		if "tabId" in event and win.get_selected_tab().tabId != event["tabId"]:
			logger.error("%s has inconsistent tabIndex" % event["name"])

	def process_event(self, event):
		"""A simple wrapper for the real event handling method, that ensures that
		the event is added to the event history."""
		self._handle_event(event["event"], event)
		self.event_history.append(event)

	def _handle_event(self, name, event):
		"""Handle the given event. It is safe to return early from this function
		if there's no more processing to be done."""

		if name == "ERROR":
			logger.warning(event["message"])
			return
		if name == "WARNING":
			logger.warning(event["msg"])
			return
			
		if name == "window_onload":
			self.new_window(event)
			return

		win = browser_state.get_window(event)

		if win is None and self.window_recently_closed(event):
			name, id = event["event"], event["win"]
			logger.warning("Ignoring %s on recently-closed window %s" % (name, id))
			return

		if name == "window_unload":
			self.close_window(win, event["time"])
			event_stream.append(Event(event, "window_close"))
			return

		if name == "tab_registered":
			self.new_tab(event)
			return

		tab = self.get_tab(event)

		# Keep track of events which might cause a future navigation
		# If isTopLevel=False, ignore it; but otherwise assume it might be a cause
		if is_navigation_cause(event) and event.get("isTopLevel", True):
			# Don't assume that non-user actions occurred on the selected tab
			event_tab = tab if is_user_action(event) else None
			win.navigation_causes.append((event_tab, event))

		if name in ["tablogger_init", "tlogger_init"]:
			win.tlogger_init = True
			return

		# After a window is created, expect to see a tab_registered and a
		# TabOpen for the first tab. After that, we better see tlogger_init
		if not win.tlogger_init:
			if name == "TabOpen" and event["cause"] == "default":
				if event["tabIndex"] != 0:
					logger.warning("Default tab has tabIndex %d" % event["tabIndex"])
			else:
				logger.error("No tlogger_init yet for new window")

		# After a tab_registered event, the next event will contain the tabIndex.
		# It's usually TabOpen, but TabRestore can sometimes appear instead.
		# With some extensions (e.g. TabsOpenRelative), a TabMove might come first.
		if tab.tab_open_event is None:
			tab.complete_tab_open(event)
			if name not in ["TabOpen", "TabRestore", "TabMove", "TabSelect"]:
				logger.warning(name + " immediately after tab_registered")

		# Check that the tabIndex looks consistent. Ignore for TabMove,
		# because the tabIndex attr refers to the new position, not current
		if name != "TabMove" and "tabIndex" in event:
			win.check_tab_index(tab, event)

		if name == "TabOpen":
			pass # No further action required here		
		elif name == "TabRestore":
			tab.set_restored()
		elif name == "TabMove":
			win.tabs.remove(tab)
			win.tabs.insert(event["tabIndex"], tab)
			event_stream.append(Event(event, "tab_move"))
		elif name == "TabSelect":
			win.select_tab(event["time"], tab)
			event_stream.append(Event(event, "tab_select"))
			# tabIndex attributes should be consistent again; reset this value
			win.pending_tab_close_index = -1
		elif name == "TabClose":
			if tab is win.get_selected_tab():
				win.select_tab(event["time"], None)
				# When the selected tab is closed, any events up to and 
				# including the next TabSelect won't have their tabIndex
				# adjusted yet. Remember the index to recover from this.
				win.pending_tab_close_index = tab.get_index()
			win.tabs.remove(tab)
			event_stream.append(Event(event, "tab_close", tab_count=len(win.tabs)))
		elif name in ["openNewTabWith", "openNewWindowWith"]:
			# These events will be used once the window/tab is opened
			pass
		elif name == "load_start":
			# Every navigation action *should* begin with a load_start event
			# Remember the event and the (probable) cause, but don't emit the
			# navigation event until we see LocationChange

			# Ignore any events that aren't top-level
			if not event["isTopLevel"]:
				return
			tab.load_start(event)	
		elif name == "redirect":
			tab.redirect(event)
		elif name == "LocationChange":
			# Ignore any events that aren't top-level events
			if not event["isTopLevel"]:
				return

			tab.location_change(event)
		elif name == "load":
			# Make sure this event corresponds to a previous navigation event
		
			# TODO: Might want to recover here, and emit some kind of
			# navigation event anyways

			if event["isTopLevel"]:
				if event["url"] == "about:blank":
					# Ignore spurious loads of "about:blank"
					return

				if tab.last_nav_action is None:
					logger.warning("Ignoring load of %s without a navigation action" % event["url"])
				else:
					tab.last_nav_action.load(event["url"], event["time"])
					event_stream.append(Event(event))
		elif name == "question":
			event_stream.append(Event(event))
		elif name == "bookmark_visit":
			# This particular event only occurs in Fx3. In Fx2, it's openOneBookmark and openGroupBookmark.
			# It's complicated to deal with -- it doesn't appear until *after* the navigation has occurred. 
			# Also, there is a bug: we get one event for every open window.

			prev_evt = self.event_history[-1]
			if prev_evt["event"] == "bookmark_visit" and prev_evt["url"] == event["url"]:
				pass # Ignore this event, it's a duplicate
			else:
				# Since we're always just processing the first event, the window and tab may not
				# be set correctly. Just look for a recent nav event that matches, and change its cause.

				matching_event = None
				for evt in reversed(event_stream):
					if seconds_between(evt, event) > 10:
						break
					if evt["event"] == "navigation" and evt["url"] == event["url"]:
						matching_event = evt
						break
						
				if matching_event:
					matching_event["cause"] = "bookmark_visit"
					# TODO: Check that it was the last nav event that occurred on the tab
				else:
					logger.warning("No matching nav event for bookmark_visit to " + event["url"])
		elif is_navigation_cause(event):
			pass # It's been remembered as a possible navigation cause; nothing further needed
		elif is_user_action(event):
			self.update_active_window(event)
		else:
			logger.error("Unexpected event on tab %s: %s" % (tab.tabId, name))

# Global variable that maintains the current known state of the browser
browser_state = None
log_version = None

def AppClosed(events):
	logger.debug("Entering state 'AppClosed'")
	
	global browser_state
	browser_state = None

	while True:
		event = events.next()
		name = event["event"]

		if name == "LOG_OPEN":
			event_stream.append(Event(event, "browser_start", {}))
			global log_version
			log_version = int(event["version"])
			return AppStartup
		else:
			logger.warning("Unexpected event: " + name)

def AppStartup(events):
	# TODO: Watch for other hints that the startup is complete (e.g. time)

	logger.debug("Entering state 'AppStartup'")

	global browser_state
	browser_state = BrowserState()

	is_session_restore = False

	# window_onload should always be the first event we see in this state
	name = events.peek()["event"]
	if name != "window_onload":
		logger.warning("Expected window_onload as first event, got '%s'" % name)

	next_state = None
	while next_state is None:
		# Peek at the events without consuming them.
		# The event will be consumed at the end of the loop. To avoid this,
		# use 'continue' rather than falling out of the 'if' statement.
		event = events.peek()
		name = event["event"]

		if name == "TabRestore":
			is_session_restore = True
	
		if name == "gotoHistoryIndex":
			win = browser_state.get_window(event)
			if win.gotohistoryindex_event is None:
				win.gotohistoryindex_event = event
			else:
				logger.warning(
					"Found >1 goToHistoryIndex on %s during startup" % win.winId)
				browser_state.process_event(event)
		elif name == "quit-application":
			next_state = AppClosed
			event_stream.append(Event(event, "browser_quit", {}))
		elif (is_user_action(event) 
		and name not in ["TabMove", "TabSelect", "gotoHistoryIndex"]):
			# Those three events are excluded because they can occur during
			# startup without being caused by the user
			next_state = AppOpen
			continue # Don't consume the event
		elif name == "LOG_OPEN":
			logger.info("LOG_OPEN during AppStartup: possible crash")
			next_state = AppClosed
			continue # This event will be consumed by AppClosed
		else:
			browser_state.process_event(event)

		events.next() # Consume the event from the stream

	# Ensure the events we've seen are consistent with currently open tabs
	all_registered_tabs = browser_state.get_all_registered_tabs()
	for tab in all_registered_tabs:
		_assert(tab.tab_open_event is not None, "Tab registered but no tab_open")
		if is_session_restore and not tab.restored:
			logger.warning("No TabRestore for " + tab.tabId)

	# Find all the events emitted during this startup
	startup_events = None
	for i, event in enumerate(reversed(event_stream)):
		if event["event"] == "browser_start":
			startup_events = event_stream[-i:]
			break
	_assert(startup_events is not None, "browser_start event not found")
	
	# The first window never has any particular cause
	if startup_events[0]["event"] == "window_open":
		startup_events[0]["cause"] = "default"
	else:
		logger.error("found %s instead of window_open event" % startup_events[0]["event"])

	if is_session_restore:	
		# All other events were caused by the session restore
		for event in startup_events[2:]:
			event["cause"] = "restore"

	if len(all_registered_tabs) > 1 and not is_session_restore:
		logger.warning("> 1 tab opened during AppStartup, but not restoring")

	return next_state

def AppOpen(events):
	logger.debug("Entering state 'AppOpen'")

	next_state = None
	while next_state is None:
		event = events.peek()
		name = event["event"]

		if name == "LOG_OPEN":
			logger.info("LOG_OPEN during AppOpen: possible crash")
			next_state = AppClosed
			continue # Don't consume the event
		elif name == "quit-application":
			event_stream.append(Event(event, "browser_quit", {}))
			next_state = AppClosed
		else:
			browser_state.process_event(event)
		
		events.next()
	return next_state

def compile(path, debug):
	"""
	Compile a low-level tlogger log file to a higher-level representation.
	
	debug -- Drop to the Python debugger (pdb) on an unhandled exception

	"""

	event_iterator = tlogger.LogIterator(path)

	global event_stream, logger
	event_stream = []
	logger = MyLogger(event_iterator)

	next_state = AppClosed # Initial state
	try:
		while True: 
			next_state = next_state(event_iterator)
	except StopIteration:
		pass
	except Exception, ex:
		logger._print_error(ex.message)
		if debug:
			traceback.print_exc()
			exc_class, exc, tb = sys.exc_info()
			pdb.post_mortem(tb)
		else:
			raise
		# Signal the error by returning None
		return None
	finally:
		result = event_stream
		event_stream = None
		if logger:
			logger.cleanup()
	return result
	
def write_to_file(events, f):
	for event in events:
		event = event.copy()
		timestamp = event["time"]
		del event["time"] # Don't want this in the JSON output
		if json.__name__ == "cjson":
			json_output = json.encode(event)
		else:
			json_output = json.dumps(event)
		f.write("%s %s\n" % (timestamp, json_output))

def main(input_filename, output_filename=None, debug=False):
	"""
	Compile a low-level tlogger log file to a higher-level representation.
	
	debug -- Drop to the Python debugger (pdb) on an unhandled exception
	"""
	if output_filename:
		output_file = open(output_filename, "w")
	else:
		output_file = sys.stdout

	try:
		events = compile(input_filename, debug)
		write_to_file(events, output_file)
	finally:
		if output_file is not sys.stdout:
			output_file.close()

if __name__ == "__main__":
	"""Iterate through each event in the log file, and move from state to state"""

	import simpleopt
	simpleopt.parse_args(main)


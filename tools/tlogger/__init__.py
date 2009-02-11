#! /user/bin/env python

"""
This module contains some classes and functions useful for dealing with the
log files generated by the tlogger Firefox extension.

The compile function can be used from the command line. For example:

	python -m tlogger.compile /path/to/browsinglog.txt
	
will print warnings & info to stderr, and the resultig compiled log to
stdout. The output file can also be specified:

	python -m tlogger.compile /path/to/browsinglog.txt -o log.out
	
Try 'python -m tlogger.compile --help' for more info.

"""
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

__author__ = "Patrick Dubroy (http://dubroy.com)"
__license__ = "GNU GPL v2"

__all__ = ["LogIterator", "compile"]

import re
try:
	import json
except:
	import simplejson as json

import compile

class LogIterator(object):
	"""Iterator for tlogger log files. 
	
	This class implements an iterator which returns a dictionary for each 
	non-blank line in the log file. The keys are the same as the JSON
	representation in the log, plus an extra key named "time" which
	contains the timestamp that appears at the beginning of each log line.
	
	NOTE: If you do not finish iterating with this object, it will leave 
	the file open. In that case, you should call the close() method.
	
	Examples:
	
		for event in LogIterator("/path/to/browsinglog.txt"):
			print "At %s, %s occurred" % (event["time"], event["event"]) 
	
	"""
	def __init__(self, filename, ignored_events=[]):
		"""ignore_events - optional list of event types that will be ignored"""
		self._ignored_events = ignored_events
		self._filename = filename
		self._f = open(filename, "r")
		self._f_iter = iter(self._f)
		self._line_count = 0
		self._lookahead = []
		
	def __iter__(self):
		return self
		
	def close(self):
		"""It's only necessary to call this method if you don't finish iterating 
		with this object."""
		self._f.close()
		
	@property
	def current_line_number(self):
		"""The line number of the last event returned from the next() method."""
		return self._line_count

	def next(self):
		if len(self._lookahead) > 0:
			return self._lookahead.pop(0)
		return self._next_impl()
		
	def _next_impl(self):
		while True:
			next_line = ""
			try:
				# Skip over any blank lines in the log
				while len(next_line.strip()) == 0:
					next_line = self._f_iter.next()
					self._line_count += 1
			except StopIteration:
				# After last line of the file, close the file, and end the iterator
				self.close()
				raise StopIteration

			# Ensure every non-empty lines is of the form: 
			# "<timestamp> { <json_text> }" or just "{ <json_text> }"
			match = re.match(r"(\d+[ \t]+)?(\{.*\})", next_line)
			if match is None:
				description = ("Line %s - Unexpected format: '%s'" % 
					(self._line_count, next_line[:-1]))
				raise Exception(description)
			json_text = match.groups()[-1]
			try:
			# Is specifying latin-1 necessary or even correct?
			#	event_obj = json.loads(json_text, encoding="latin-1")
				event_obj = json.loads(json_text)
			except Exception, e:
				raise Exception(
					("Line %s - Exception parsing JSON: " + str(e)) % self._line_count)
			if len(match.groups()) >= 2:
				event_obj["time"] = int(match.group(1).strip())

			if event_obj["event"] not in self._ignored_events:
				return event_obj

	def peek(self, index=0):
		"""Return, but do not consume, the token at the given index in the
		lookahead buffer. By default, return the next token (index 0).
		Return None if there are not enough tokens left."""
		while len(self._lookahead) <= index:
			self._lookahead.append(self._next_impl())
		return self._lookahead[index]


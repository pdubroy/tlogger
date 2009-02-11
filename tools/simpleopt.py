#! /usr/bin/env python

"""simpleopt: Dead simple command-line option parsing.

Best described with an example. The following function:

	def example(input_file, output_file, passes=3, debug=False, quiet=True):
		'''Do some cool stuff and write the results to a new file.

		passes -- the number of passes to make on input_file
		debug -- Print extra debug information to the console
		quiet -- Print as little information as possible
		'''
		pass

wrapped like this:

	import simpleopt
	simpleopt.parse_args(example)
	
allows you to parse the command line options just like you'd expect:

	Usage: example.py [OPTION]... <input_file> <output_file> 

	Do some cool stuff and write the results to a new file.

	Options:
	  -h, --help            show this help message and exit
	  -d, --debug           Print extra debug information to the console
	  -p PASSES, --passes=PASSES
			                the number of passes to make on input_file
	  -q, --quiet           Print as little information as possible

"""

# This project is maintained at http://github.com/pdubroy/simpleopt/
#
# Copyright (c) 2009 Patrick Dubroy (http://dubroy.com)
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

__version__ = "0.2"
__author__ = "Patrick Dubroy (http://dubroy.com)"
__license__ = "MIT License"

import inspect
import optparse
import sys

__all__ = ["parse_args", "ArgumentError"]

class ArgumentError(Exception):
	pass

def parse_args(func, usage=None):
	"""Parse command line arguments and pass them in to func.

	Based on the function signature, build an optparse.OptionParser to parse
	the command line arguments and pass them in to func. If the usage string is
	not specified, attempt to do a reasonable job based on the docstring.
	
	"""
	
	arg_count = len(sys.argv) - 1

	parser = _build_parser(func, usage)
	options, pos_args = parser.parse_args()

	try:
		func(*pos_args, **options.__dict__)
	except TypeError:
		# If there's only one frame in the traceback, then the exception
		# occurred on the call to func. Otherwise, re-raise the exception.
		exc_class, exc, tb = sys.exc_info()
		if tb.tb_next is not None:
			raise
		if arg_count == 0:
			parser.print_help()
		else:
			parser.error("Incorrect arguments")
	except ArgumentError, ex:
		parser.error(ex)

def _build_parser(func, usage=None):
	"""Return the parser (built using optparse) for the given function."""
	
	class Option(object): pass

	args, varargs, varkw, defaults = inspect.getargspec(func)
	args = args or []
	defaults = defaults or []
	num_required_args = len(args) - len(defaults)
	required_args = args[:num_required_args]

	options = {}

	for name, value in zip(args[num_required_args:], defaults):
		opt = Option()
		options[name] = opt
		opt.default = value
	
		if isinstance(value, bool):
			# Whatever the default value is, the action is the opposite
			opt.action = "store_false" if value else "store_true"
		else:
			opt.action = "store"
			
			# Figure out the type of the argument. But, if the default value
			# is None, you're getting a string whether you like it or not.
			# TODO: Maybe allow types to be specified by a decorator? 
			if isinstance(value, int): opt.type = "int"
			elif isinstance(value, long): opt.type = "long"
			elif isinstance(value, float): opt.type = "float"
			elif isinstance(value, complex): opt.type = "complex"
			else: opt.type = "string"

		opt.help = "" # We'll fill this in later

	if usage is None:
		# Build the usage message from the function docstring, assuming that it
		# follows the conventions of PEP 257. In particular, look for a preamble
		# of one or more lines, followed by a blank line, and then a special
		# section describing the function arguments that looks like this: 
		#  
		# 	arg1 -- The description for arg1 goes here
		# 	arg2 -- Blah blah blah de blah
		# 
		# The descriptions must not be more than one line. Lines that match a
		# required argument will be placed verbatim after the preamble, and ones
		# that match an optional argument will be modified to replace the
		# argument name with the command-line switches.	

		usage = "%prog [OPTION]... "
		for arg in required_args:
			usage += "<%s> " % arg

		doc = inspect.getdoc(func)
		if doc:
			preamble = ""
			arg_doc_expected = False
			arg_docs_found = 0
			for line in doc.splitlines(True):
				if arg_doc_expected:
					try:
						name, doc = line.split(" -- ", 1)
						if name in required_args:
							preamble += line
						else:
							options[name].help = doc
						arg_docs_found += 0
						continue
					except (ValueError, KeyError):
						# Everything after the args documentation is ignored
						if arg_docs_found > 0:
							break
						# Otherwise, it's not an argument doc line -- fall through
				preamble += line
				# After a blank line, anticipate an option doc line
				arg_doc_expected = len(line.strip()) == 0
			usage += "\n\n" + preamble.strip()

		parser = optparse.OptionParser()

		short_opts = {}
		for name, opt in options.items():	
			long_opt = "--%s" % name

			# Find the first character that isn't already a short opt
			i = 0
			while name[i] in short_opts:
				i += 1
			if i < len(name):
				short_opt = "-%s" % name[i]
				short_opts[name[i]] = opt
				
			parser.add_option(short_opt, long_opt, **opt.__dict__)

	parser.set_usage(usage)
	return parser

def run_tests(verbose):
	def test0(): pass

	def test1(req_one):
		return req_one

	def test2(req_one, req_two): 
		return (req_one, req_two)

	def test3(opt1=True):
		return opt1

	def test4(opt_one="foo", opt_two="bar"):
		return (opt_one, opt_two)

	def test5(req_one, opt_one="foo"):
		return (opt_one, opt_two)

	def test6(input_file, output_file, passes=3, debug=False, quiet=True):
		"""Do some cool stuff and write the results to a new file.
	
		passes -- the number of passes to make on input_file
		debug -- Print extra debug information to the console
		quiet -- Print as little information as possible

		"""
		return (input_file, output_file, passes, debug, quiet)

	for func in [test0, test1, test2, test3, test4, test5, test6]:
		parser = _build_parser(func)
		if verbose:
			print "Function definition:\n<<"
			print inspect.getsource(func)
			print ">> parser.print_help()"
			parser.print_help()
			print "-----"

def main(test=False, verbose=False, extra=None, times=0):
	"""Tests and examples of the simpleopt module.
	
	test -- Run the unit tests
	extra -- Some extra text to print
	times -- The number of times to print 'extra'

	"""
	if test:
		import unittest
		testCase = unittest.FunctionTestCase(lambda: run_tests(verbose))
		unittest.TextTestRunner().run(testCase)
		
	if extra:
		print extra * times
	elif times > 0:
		raise ArgumentError("'extra' must be specified if 'times' is")

if __name__ == "__main__":
	parse_args(main)


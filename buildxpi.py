#! /usr/bin/env python

import os
import sys
import zipfile

if __name__ == "__main__":
	"""This script just does the equilent of the following:
	
		cd <tlogger_repo>/extension; zip -r OUTFILE .; cd -
	
	"""

	script_dir, script_name = os.path.split(sys.argv[0])
	if len(sys.argv) != 2:
		print "Usage: %s OUTFILE" % script_name
		print "Create an XPI archive for the tlogger Firefox extension."
		return_code = 0 if len(sys.argv) == 1 else 1
		sys.exit(return_code)

	orig_dir = os.getcwd()
	zipf = zipfile.ZipFile(sys.argv[1], "w")
	try:
		ext_dir = os.path.join(script_dir, "extension")
		print "Entering %s" % ext_dir
		os.chdir(ext_dir)
		for root, dirs, files in os.walk("."):
			for name in files:
				filename = os.path.join(root, name)
				zipf.write(filename)
				print "  adding: %s" % filename
	finally:
		zipf.close()
		os.chdir(orig_dir)


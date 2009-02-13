/*
 * tlogger: a Firefox extension for capturing click-stream web browsing logs
 *
 * Copyright (c) 2009 Patrick Dubroy (http://dubroy.com)
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 *
 */

// UUID generated from http://kruithof.xs4all.nl/uuid/uuidgen
const CLASS_ID = Components.ID("{1044e410-477c-11dd-ae16-0800200c9a66}");

// description
const CLASS_NAME = "Global object for the tlogger extension";

// textual unique identifier
const CONTRACT_ID = "@dubroy.com/tlogger/globals;1";

// Change this whenever any changes are introduced to the log format
const LOG_VERSION = 20090211;

const Cc = Components.classes;
const Ci = Components.interfaces;

// According to http://developer.mozilla.org/en/docs/Code_snippets:File_I/O#Writing_to_a_file
const FILE_APPEND_MODE = 0x02 | 0x10; 

/**
 * Class definition
 */

// Class constructor
function TLoggerGlobals() {
	// Required for us to be able to access the component from JS without an IDL
	this.wrappedJSObject = this;
	
	// This is required by all XPCOM components
	function QueryInterface(aIID)
	{
		if (!aIID.equals(Ci.nsISupports))
			throw Components.results.NS_ERROR_NO_INTERFACE;
		return this;
	}

	// Pull in json2.js
	var loader = Cc["@mozilla.org/moz/jssubscript-loader;1"]
		.getService(Ci.mozIJSSubScriptLoader);
	loader.loadSubScript("chrome://tlogger/content/json2.min.js");
	
	var nextWindowId = 0;
	var log;
	var focusLog;
	
	const FORMAT_HEX = 16;

	// Figure out whether we are running Fx2 or Fx3
	// Other versions are not supported
	var firefoxMajorVersion = -1;
	var appInfo = Cc["@mozilla.org/xre/app-info;1"].getService(Ci.nsIXULAppInfo);
	var comp = Cc["@mozilla.org/xpcom/version-comparator;1"].getService(Ci.nsIVersionComparator);
	if (comp.compare(appInfo.version, "3.0") >= 0) {
		firefoxMajorVersion = 3;
	} else if (comp.compare(appInfo.version, "2.0") >= 0) {
		firefoxMajorVersion = 2;
	} else {
		Components.utils.reportError(new Error(
			"Only Firefox 2.x and 3.x are supported"));
	}
	
	function getWindowId(win)
	{
		var id = "W" + nextWindowId.toString(FORMAT_HEX);
		nextWindowId += 1;
		return id;
	}

	/*
	 * Return an instance of nsIFile that represents the data dir for the extension.
	 * If 'create' is true and the directory does not already exist, it will be created.
	 */
	function getDataDir(create)
	{
		var dir = Cc["@mozilla.org/file/directory_service;1"]
			.getService(Ci.nsIProperties)
			.get("ProfD", Ci.nsILocalFile);
		dir.append("tlogger");
	
		if (dir.exists()) {
			if (!dir.isDirectory()) {
				throw("A file with the same name as the data dir already exists!");
			}
		} else {
			if (create) {
				dir.create(Ci.nsIFile.DIRECTORY_TYPE, 0777);
			}
		}
		
		return dir;
	}
	
	/*
	 * Given a filename, return an instance of nsIFile with the given name
	 * and located in the extension's data dir. Files will be created if
	 * they don't exist.
	 */
	function getDataDirFile(filename, create)
	{
		var file = getDataDir(create);
		file.append(filename);
		
		// Create the file, if necessary
		if (create && !file.exists()) {
			file.create(Ci.nsIFile.NORMAL_FILE_TYPE, 0666);
			file.QueryInterface(Ci.nsILocalFile);
		}
	
		return file;
	}

	var lastQuestionTimeMillis = 0;

	function StringTable()
	{
		var obfuscatedStrings = {};
		var obfuscatedStringCount = 0;
		var stringOutputStream;

		/**
		 * Restore the string table from the file in the user's profile.
		 */
		function readStringFile(nsiFile) {
			// open an input stream from file
			// from http://developer.mozilla.org/en/Code_snippets/File_I%2f%2fO#Line_by_line
			var istream = Cc["@mozilla.org/network/file-input-stream;1"]
				.createInstance(Ci.nsIFileInputStream);
			istream.init(nsiFile, 0x01, 0444, 0);
			istream.QueryInterface(Ci.nsILineInputStream);

			// read lines into array
			var line = {}, hasmore;
			var line_count = 0;
			do {
				line_count += 1;
				hasmore = istream.readLine(line);
				if (line.value.length > 0) {
					try {
						var entry = JSON.parse(line.value);
					} catch(ex) {
						var message = "Exception parsing string file on line " + line_count;
						Components.utils.reportError(new Error(message));
						var errorDetails = {};
						errorDetails.message = message;
						errorDetails.exception = ex.toString();
						log.write("ERROR", errorDetails);
					}
					obfuscatedStrings[entry.string] = entry.id;
					obfuscatedStringCount += 1;
				}
			} while(hasmore);
			istream.close();
		}

		/**
		 * add - obfuscate a string by mapping it to a unique base-36
		 * representation. If the same string is passed in multiple times, the
		 * result will always be the same. This way, we can identify strings
		 * uniquely without actually knowing their values.
		 */	
		function obfuscateString(str) {
			var radix = 36;
		
			if (str in obfuscatedStrings) {
				return obfuscatedStrings[str];
			}
			var stringId = obfuscatedStringCount.toString(radix);
			obfuscatedStrings[str] = stringId;
			obfuscatedStringCount += 1;
			
			// Write this entry to the permanent file
			var entry = JSON.stringify({ "string": str, "id": stringId }) + "\n";
			stringOutputStream.write(entry, entry.length);
			
			return stringId;
		}
		
		function search(str) {
			var result = [];
			for (var key in obfuscatedStrings) {
				if (key.indexOf(str.toLowerCase()) >= 0) {
					result.push([key, obfuscatedStrings[key]]);
				}
			}
			return result;
		}

		var stringFile = getDataDirFile("strings.dat", true);
		readStringFile(stringFile);

		stringOutputStream = Cc["@mozilla.org/network/file-output-stream;1"]
			.createInstance(Ci.nsIFileOutputStream);
	   
		stringOutputStream.init(stringFile, FILE_APPEND_MODE, 0666, 0);
		
		// Return the public functions
		return { "obfuscateString":obfuscateString, "search":search };
	}	
	
	/*
	 * Log Class
	 */
	function Log()
	{
		/**
		 * Log.write - write an event to the log.
		 * @param event the event identifier (for now, a string)
		 * @args_dict a dictionary containing key/values pairs of additional info
		 */
		this.write = function(event, args_dict)
		{
			var currentTimeMillis = (new Date()).getTime();
	
			logEntry = {};
			logEntry.event = event;
	
			if (arguments.length > 1) {
				var iterator = Iterator(args_dict);
				for (var each in iterator) {
					logEntry[each[0]] = each[1];
				}
			}
	
	
			var message = currentTimeMillis + " " + JSON.stringify(logEntry) + "\n";
			logOutputStream.write(message, message.length);
		}
		
		this.close = function()
		{
			logOutputStream.close();
		}
		
		this.getNsIFile = function()
		{
			return logFile;
		}
	
		var logFile = getDataDirFile("extstore.dat", true);
		var logOutputStream = Cc["@mozilla.org/network/file-output-stream;1"]
			.createInstance(Ci.nsIFileOutputStream);

		logOutputStream.init(logFile, FILE_APPEND_MODE, 0666, 0); 
	
		var firstEvent;
		if (logFile.exists()) {
			firstEvent = "LOG_OPEN";
		} else {
			firstEvent = "LOG_CREATE"; 
		}
	
		// Include a human readable date on the open or create message
		this.write(firstEvent, {"date":Date().toString(), "version":LOG_VERSION,
			"firefox_version":appInfo.version});	
	}
	
	function FocusLog()
	{
		var file = getDataDirFile("focus.dat", true);
		var outputStream = Cc["@mozilla.org/network/file-output-stream;1"]
			.createInstance(Ci.nsIFileOutputStream);
	   
		outputStream.init(file, FILE_APPEND_MODE, 0666, 0);

		this.write = function(message) {
			outputStream.write(message, message.length);
		};
		
		this.close = function() {
			outputStream.close();
		};
	}

	/*
	 * Returns a function with the same signature as Log.write(), above.
	 * @param extra_args - a dictionary of key/value pairs which will be
	 * automatically included in every event that is logged. If the same key
	 * appears in extra_args and in the args_dict passed to the write function,
	 * extra_args takes precendence.
	 */
	function buildLogFunction(extra_args)
	{
		return function(event, args_dict) {
			var actual_args = args_dict || {};
			for (key in extra_args) {
				actual_args[key] = extra_args[key];
			}
			return log.write(event, actual_args);
		};
	}
	
	log = new Log();
	function getLog() { return log; }

	try {
		focusLog = new FocusLog();
	} catch(ex) {
		Components.utils.reportError(ex);
	}
	function getFocusLog() { return focusLog; }

	function showLogFile()
	{
		try {
			var dir = getDataDir();
			dir.append("log");
			if (!dir.exists()) {
				dir.create(Ci.nsIFile.DIRECTORY_TYPE, 0777);
			}
			var filename = "browsinglog.txt";
			var logCopy = dir.clone();
			logCopy.append(filename);
			if (logCopy.exists()) {
				logCopy.permissions = 0666;
				logCopy.remove(false);
			}
			getLog().getNsIFile().copyTo(dir, filename);

			// Make the copy read-only
			logCopy.permissions = 0444;

			// Bring up a file browser showing the file
			try {
				logCopy.QueryInterface(Ci.nsILocalFile);
				logCopy.reveal();
			} catch (e) {
				// reveal doesn't work on some platforms
				var uri = Cc["@mozilla.org/network/io-service;1"].
					getService(Ci.nsIIOService).newFileURI(dir);
				var protocolSvc = Cc["@mozilla.org/uriloader/external-protocol-service;1"].
					getService(Ci.nsIExternalProtocolService);
				protocolSvc.loadUrl(uri);
			}
		} catch(ex) {
			Console.utils.reportError(ex);
		}
	}
	
	// Register an observer for quit-application
	var globalObserver = { 
		observe : function(subject, topic, data)
		{
			if (topic == "quit-application") {
				 log.write("quit-application");
			}
		}
	};
	
	var service = Cc["@mozilla.org/observer-service;1"]
		.getService(Ci.nsIObserverService);
	service.addObserver(globalObserver, "quit-application", false);

	// For now, always create the string table...
	var stringTable = new StringTable();

	// ...but set the obfuscation function based on the pref
	var obfuscateString;
	var prefManager = Cc["@mozilla.org/preferences-service;1"].getService(Ci.nsIPrefBranch);
	if (prefManager.getBoolPref("extensions.tlogger.obfuscateURLs")) {
		obfuscateString = stringTable.obfuscateString;
	} else {
		obfuscateString = function(str) { return str; }; // no-op
	}	

	// Public members
	this.QueryInterface = QueryInterface;
	this.getWindowId = getWindowId;
	this.buildLogFunction = buildLogFunction;
	this.getDataDirFile = getDataDirFile;
	this.getLog = getLog;
	this.getFocusLog = getFocusLog;
	this.lastQuestionTimeMillis = lastQuestionTimeMillis;
	this.firefoxMajorVersion = firefoxMajorVersion;
	this.showLogFile = showLogFile;

	this.obfuscateString = obfuscateString;
	this.searchStringTable = stringTable.search;
};


/**
 * Class factory
 */
var TLoggerGlobalsFactory = {
	createInstance: function (aOuter, aIID)
	{
		if (aOuter != null)
			throw Components.results.NS_ERROR_NO_AGGREGATION;
		return (new TLoggerGlobals()).QueryInterface(aIID);
	}
};

/**
 * Module definition (xpcom registration)
 */
var TLoggerGlobalsModule = {
	registerSelf: function(aCompMgr, aFileSpec, aLocation, aType)
	{
		aCompMgr = aCompMgr.
			QueryInterface(Ci.nsIComponentRegistrar);
		aCompMgr.registerFactoryLocation(CLASS_ID, CLASS_NAME, 
			CONTRACT_ID, aFileSpec, aLocation, aType);
	},
	
	unregisterSelf: function(aCompMgr, aLocation, aType)
	{
		aCompMgr = aCompMgr.
			QueryInterface(Ci.nsIComponentRegistrar);
		aCompMgr.unregisterFactoryLocation(CLASS_ID, aLocation);        
	},
	
	getClassObject: function(aCompMgr, aCID, aIID)
	{
		if (!aIID.equals(Ci.nsIFactory))
			throw Components.results.NS_ERROR_NOT_IMPLEMENTED;
		
		if (aCID.equals(CLASS_ID))
			return TLoggerGlobalsFactory;
		
		throw Components.results.NS_ERROR_NO_INTERFACE;
	},
	
	canUnload: function(aCompMgr) { return true; }
};

/**
 * Module initialization
 * When the application registers the component, this function is called.
 */
function NSGetModule(aCompMgr, aFileSpec) { return TLoggerGlobalsModule; }


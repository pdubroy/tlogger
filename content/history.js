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

com_dubroy_tlogger_history = function() {

var log_write;
var obf_url;
var old_openURLIn;

function window_openURLIn(where)
{
	// These two lines lifted from the original openURLIn implementation in history.js
	var currentIndex = gHistoryTree.currentIndex;
	var builder = gHistoryTree.builder.QueryInterface(Components.interfaces.nsIXULTreeBuilder);
	var url = builder.getResourceAtIndex(currentIndex).ValueUTF8;	

	log_write("history openURLIn", {"where":where, "url":obf_url(url)});
	return old_openURLIn(where);
}

function window_onload()
{
	var mainWindow = window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
		.getInterface(Components.interfaces.nsIWebNavigation)
		.QueryInterface(Components.interfaces.nsIDocShellTreeItem)
		.rootTreeItem
		.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
		.getInterface(Components.interfaces.nsIDOMWindow);

	log_write = mainWindow.com_dubroy_tlogger.log_write;
	obf_url = mainWindow.com_dubroy_tlogger.obf_url;

	// Check what version of Firefox we are running, because the interface
	// has changed substantially in Fx3	
	var appInfo = Components.classes["@mozilla.org/xre/app-info;1"]
		.getService(Components.interfaces.nsIXULAppInfo);
	var versionChecker = Components.classes["@mozilla.org/xpcom/version-comparator;1"]
		.getService(Components.interfaces.nsIVersionComparator);

	if(versionChecker.compare(appInfo.version, "3.0.0") < 0) {
		// Firefox 2 version
		old_openURLIn = window.openURLIn;
		window.openURLIn = window_openURLIn;
	} else {
		// Firefox 3 version not implemented yet
		log_write("WARNING", {msg:"Sidebar history logging not implemented for Fx3 yet"});
	}
}

function window_onunload()
{
	window.openURLIn = old_openURLIn;
}

// Code below here is run when the overlay is loaded

window.addEventListener("load", window_onload, false);
window.addEventListener("unload", window_onunload, false);

var public_attributes = {
};
return public_attributes;

}();


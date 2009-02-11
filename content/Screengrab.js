/*
Copyright (C) 2004-2007  Andy Mutton <andy@5263.org>
Some modifications (C) 2008 Patrick Dubroy (http://dubroy.com)

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

*/

// Includes.js

// pld: I don't need this stuff
//SGPrefs = {
//	captureMethod : "extensions.screengrab.captureMethod",
//	includeTimeStampInFilename : "extensions.screengrab.includeTimeStampInFilename",
//	imageFormat : "extensions.screengrab.imageFormat"
//}

// Dimensions.js

var org_screengrab = function() {

var SGDimensions = {

	Box : function(x, y, width, height) {
		this.x = x;
		this.y = y;
		this.width = width;
		this.height = height;  
	},

	FrameDimensions : function() {
		this.frame = SGNsUtils.getActiveFrame();
		this.doc = this.frame.document;
		this.viewport = new SGDimensions.BrowserViewportDimensions()
	},

	BrowserWindowDimensions : function() {
	},

	BrowserViewportDimensions : function() {
	}
}

SGDimensions.Box.prototype = {

	getX : function() {
		return this.x;
	},

	getY : function() {
		return this.y;
	},

	getWidth : function() {
		return this.width;
	},

	getHeight : function() {
		return this.height;
	}
}

SGDimensions.BrowserViewportDimensions.prototype = {

	getWindow : function() {
		return SGNsUtils.getCurrentBrowserWindow();
	},

	getBrowser : function() {
		return document.getElementById("content").selectedBrowser;
	},

	getScreenX : function() {
		return this.getBrowser().boxObject.screenX;
	},

	getScreenY : function() {
		return this.getBrowser().boxObject.screenY;
	},

	getScrollX : function() {
		return window.content.scrollX;
	},

	getScrollY : function() {
		return window.content.scrollY;
	},

	getHeight : function() {
		var height = 0;
		if (window.content.document.compatMode == "CSS1Compat") {
			// standards mode
			height = window.content.document.documentElement.clientHeight;
		} else { //if (compatMode == "BackCompat") 
			// quirks mode
			height = window.content.document.body.clientHeight;
		}
		return height;
	},

	getWidth : function() {
		if (window.content.document.compatMode == "CSS1Compat") {
			// standards mode
			return window.content.document.documentElement.clientWidth;
		} else { //if (compatMode == "BackCompat")
			// quirks mode
			return window.content.document.body.clientWidth;
		}
	}
}

SGDimensions.BrowserWindowDimensions.prototype = {

	getWindow : function() {
		return window;
	},

	getScreenX : function() {
		return window.screenX + window.screen.availLeft;
	},

	getScreenY : function() {
		return window.screenY + window.screen.availTop;
	},

	getWidth : function() {
		return window.outerWidth + window.screen.availLeft;
	},

	getHeight : function() {
		return window.outerHeight + window.screen.availTop;
	},

	getHeightIgnoringExternalities : function() {
		return window.outerHeight;
	}
}

SGDimensions.FrameDimensions.prototype = {

	getWindow : function() {
		return this.frame;
	},

	getFrameHeight : function() {
		if (this.doc.compatMode == "CSS1Compat") {
			// standards mode
			return this.doc.documentElement.clientHeight;
		} else {
			// quirks mode
			return this.doc.body.clientHeight;
		}
	},

	getFrameWidth : function() {
		if (this.doc.compatMode == "CSS1Compat") {
			// standards mode
			return this.doc.documentElement.clientWidth;
		} else {
			// quirks mode
			return this.doc.body.clientWidth;
		}
	},

	getDocumentHeight : function() {
		return this.doc.documentElement.scrollHeight;
	},

	getDocumentWidth : function() {
		if (this.doc.compatMode == "CSS1Compat") {
			// standards mode
			return this.doc.documentElement.scrollWidth;
		} else {
			// quirks mode
			return this.doc.body.scrollWidth;
		}
	},

	getScreenX : function() {
		var offsetFromOrigin = 0;
		if (this.frame.frameElement) {
			offsetFromOrigin = this.frame.frameElement.offsetLeft;
		}
		return this.viewport.getScreenX() + offsetFromOrigin;
	},

	getScreenY : function() {
		var offsetFromOrigin = 0;
		if (this.frame.frameElement) {
			offsetFromOrigin = this.frame.frameElement.offsetTop;
		}
		return this.viewport.getScreenY() + offsetFromOrigin;
	}
}

// NsUtils.js

var SGNsUtils = {

	isMac : function() {
		return navigator.userAgent.toLowerCase().indexOf("mac") != -1;
	},

	getCurrentBrowserWindow : function() {
		var currentWindow = Components.classes["@mozilla.org/appshell/window-mediator;1"].getService(Components.interfaces.nsIWindowMediator).getMostRecentWindow("navigator:browser");
		return currentWindow.getBrowser().contentWindow;
	},

	getActiveFrame : function() {
		return document.commandDispatcher.focusedWindow;
	},

	askUserForFile : function(defaultName) {
		// get the file picker
		var result;
		var nsIFilePicker = Components.interfaces.nsIFilePicker;
		var filePicker = Components.classes["@mozilla.org/filepicker;1"].createInstance(nsIFilePicker);

		var saveas = document.getElementById("screengrab-strings").getString("SaveAsMessage");
		filePicker.init(window, saveas, nsIFilePicker.modeSave);
		filePicker.appendFilters(nsIFilePicker.filterImages);
		filePicker.defaultString = defaultName;

		result = filePicker.show();
		if (result == nsIFilePicker.returnOK || result == nsIFilePicker.returnReplace) {
			return filePicker.file;
		}
		return null;
	},

	dataUrlToBinaryInputStream : function(dataUrl) {
		var nsIoService = Components.classes["@mozilla.org/network/io-service;1"].getService(Components.interfaces.nsIIOService);
		var channel = nsIoService.newChannelFromURI(nsIoService.newURI(dataUrl, null, null));

		var binaryInputStream = Components.classes["@mozilla.org/binaryinputstream;1"].createInstance(Components.interfaces.nsIBinaryInputStream);
		binaryInputStream.setInputStream(channel.open());
		return binaryInputStream;
	},

	newFileOutputStream : function(nsFile) {
		var writeFlag = 0x02; // write only
		var createFlag = 0x08; // create
		var truncateFlag = 0x20; // truncate

		var fileOutputStream = Components.classes["@mozilla.org/network/file-output-stream;1"].createInstance(Components.interfaces.nsIFileOutputStream);
		fileOutputStream.init(nsFile, writeFlag | createFlag | truncateFlag, 0664, null);
		return fileOutputStream;
	},

	writeBinaryInputStreamToFileOutputStream : function(binaryInputStream, fileOutputStream) {
		var numBytes = binaryInputStream.available();
		var bytes = binaryInputStream.readBytes(numBytes);

		fileOutputStream.write(bytes, numBytes);
	}
}

// NsGrab.js

SGNsGrab = {

	NsGrab : function(grabToClipboard) {
		if (null == grabToClipboard) {
			this.grabToClipboard = false;
		} else {
			this.grabToClipboard = grabToClipboard;
		}
	}
}

SGNsGrab.NsGrab.prototype = {

	/** entire page */
	grabPage : function() {
		var frameDim = new SGDimensions.FrameDimensions();
		var width = frameDim.getDocumentWidth();
		var height = frameDim.getDocumentHeight();
		if (frameDim.getFrameWidth() > width) width = frameDim.getFrameWidth();
		if (frameDim.getFrameHeight() > height) height = frameDim.getFrameHeight();

		var box = new SGDimensions.Box(0, 0, width, height);
		this.grab(frameDim.getWindow(), box);
	},

	/** selection in box */
	grabSelection : function(grabBox) {
		var viewDim = new SGDimensions.BrowserViewportDimensions();
		var box = new SGDimensions.Box(viewDim.getScrollX() + grabBox.getX(), viewDim.getScrollY() + grabBox.getY(), grabBox.getWidth(), grabBox.getHeight());
		this.grab(SGNsUtils.getCurrentBrowserWindow(), box);
	},

	/** visible portion in window */
	grabVisiblePage : function() {
		var viewDim = new SGDimensions.BrowserViewportDimensions();
		var box = new SGDimensions.Box(viewDim.getScrollX(), viewDim.getScrollY(), viewDim.getWidth(), viewDim.getHeight());
		this.grab(SGNsUtils.getCurrentBrowserWindow(), box);
	},

	/** entire browser window. */
	grabBrowser : function() {
		var browserDim = new SGDimensions.BrowserWindowDimensions();
		var box = new SGDimensions.Box(0, 0, browserDim.getWidth(), browserDim.getHeightIgnoringExternalities());
		this.grab(browserDim.getWindow(), box);
	},

	grab : function(windowToGrab, box) {
		var format = Screengrab.format();
		var canvas = this.prepareCanvas(box.getWidth(), box.getHeight());
		var context = this.prepareContext(canvas, box);
		context.drawWindow(windowToGrab, box.getX(), box.getY(), box.getWidth(), box.getHeight(), "rgb(0,0,0)");
		context.restore();
		var dataUrl = canvas.toDataURL("image/" + format);

		if (this.grabToClipboard) {
			this.saveToClipboard(dataUrl);
		} else {
			this.saveToFile(dataUrl, format);
		}
	},

	saveToFile : function(dataUrl, format) {
		var nsFile = SGNsUtils.askUserForFile(Screengrab.defaultFileName() + "." + format);
		if (nsFile != null) {
			var binaryInputStream = SGNsUtils.dataUrlToBinaryInputStream(dataUrl);
			var fileOutputStream = SGNsUtils.newFileOutputStream(nsFile);
			SGNsUtils.writeBinaryInputStreamToFileOutputStream(binaryInputStream, fileOutputStream);
			fileOutputStream.close();
		}
	},
	
	/**
	 * Grab the contents of the current tab, and save the image to the indicated filename.
	 *
	 * pld: This code is almost all taken from grab(), grabBrowser(), and saveToFile()
	 */
	grabViewportToFile : function(nsFile) {
//		var browserDim = new SGDimensions.BrowserWindowDimensions();
//		var windowToGrab = browserDim.getWindow();
//		var box = new SGDimensions.Box(0, 0, browserDim.getWidth(), browserDim.getHeightIgnoringExternalities());

		var viewDim = new SGDimensions.BrowserViewportDimensions();
		var box = new SGDimensions.Box(viewDim.getScrollX(), viewDim.getScrollY(), viewDim.getWidth(), viewDim.getHeight());
		var windowToGrab = SGNsUtils.getCurrentBrowserWindow();
   
		var format = Screengrab.format();
		var canvas = Screengrab.nsGrab.prepareCanvas(box.getWidth(), box.getHeight());
		var context = Screengrab.nsGrab.prepareContext(canvas, box);
		context.drawWindow(windowToGrab, box.getX(), box.getY(), box.getWidth(), box.getHeight(), "rgb(0,0,0)");
		context.restore();
		var dataUrl = canvas.toDataURL("image/" + format);
   
		if (nsFile != null) {
			var binaryInputStream = SGNsUtils.dataUrlToBinaryInputStream(dataUrl);
			var fileOutputStream = SGNsUtils.newFileOutputStream(nsFile);
			SGNsUtils.writeBinaryInputStreamToFileOutputStream(binaryInputStream, fileOutputStream);
			fileOutputStream.close();
		}
	},

	saveToClipboard : function(dataUrl) {
		var image = window.content.document.createElement("img");
		image.setAttribute("style", "display: none");
		image.setAttribute("id", "screengrab_buffer");
		image.setAttribute("src", dataUrl);
		var body = window.content.document.getElementsByTagName("html")[0];
		body.appendChild(image);
		setTimeout(this.makeClipboardFinishClosure(image, body, document), 200);
	},

	makeClipboardFinishClosure : function(image, body, documenty) {
		return (function () {
			documenty.popupNode = image;
			try {
				goDoCommand('cmd_copyImage');
			} catch (ex) {
				alert(ex);
			}
			body.removeChild(image);    
		});
	},

	prepareContext : function(canvas, box) {
		var context = canvas.getContext("2d");
		context.clearRect(box.getX(), box.getY(), box.getWidth(), box.getHeight());
		context.save();
		return context;
	},

	prepareCanvas : function(width, height) {
		var styleWidth = width + "px";
		var styleHeight = height + "px";

		var grabCanvas = document.getElementById("screengrab_buffer_canvas");
		grabCanvas.width = width;
		grabCanvas.style.width = styleWidth;
		grabCanvas.style.maxWidth = styleWidth;
		grabCanvas.height = height;
		grabCanvas.style.height = styleHeight;
		grabCanvas.style.maxHeight = styleHeight;

		return grabCanvas;
	}
}

// Screengrab.js

// pld: All the code commented out below to remove stuff I don't need

Screengrab = {
	nsGrab : new SGNsGrab.NsGrab(false),
//	nsCbGrab : new SGNsGrab.NsGrab(true),
//	javaGrab : new SGJavaGrab.JavaGrab(),

	grabber : function() {
//		if (nsPreferences.getIntPref(SGPrefs.captureMethod) == 0) {
//			return this.javaGrab;
//		} else {
			return this.nsGrab;
//		}
	},

	format : function() {
//		if (nsPreferences.getIntPref(SGPrefs.imageFormat) == 0) {
			return "png";
//		} else {
//			return "jpeg";
//		}
	},

	defaultFileName : function() {
		filename = window.content.document.title;
		if (nsPreferences.getBoolPref(SGPrefs.includeTimeStampInFilename)) {
			dt = new Date();
			filename = filename + "_" + dt.getTime();    
		}
		return filename;
	},

	grabCompleteDocument : function() {
		this.grabber().grabPage();
	},

	grabVisibleDocument : function() {
		this.grabber().grabVisiblePage()
	},

	grabDocumentPortion : function(offsetX, offsetY, width, height) {
		this.grabber().grabSelection(new SGDimensions.Box(offsetX, offsetY, width, height))
	},

	grabBrowserWindow : function() {
		this.grabber().grabBrowser()
	},
	
	grabViewportToFile : function(nsFile) {
		this.grabber().grabViewportToFile(nsFile)
	},

	copyCompleteDocument : function() {
		this.nsCbGrab.grabPage();
	},

	copyVisibleDocument : function() {
		this.nsCbGrab.grabVisiblePage()
	},

	copyDocumentPortion : function(offsetX, offsetY, width, height) {
		this.nsCbGrab.grabSelection(new SGDimensions.Box(offsetX, offsetY, width, height))
	},

	copyBrowserWindow : function() {
		this.nsCbGrab.grabBrowser()
	}
}

// Return a dictionary of all the "public" attributes
return {
	"Screengrab":Screengrab
};

}(); // End and execute anonymous wrapper function

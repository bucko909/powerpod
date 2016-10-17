var elem = document.createElement('script');

elem.src = chrome.extension.getURL('/js/main.js');

//elem.onload = function () {
//	this.parentNode.removeChild(this);
//};

(document.head || document.documentElement).appendChild(elem);

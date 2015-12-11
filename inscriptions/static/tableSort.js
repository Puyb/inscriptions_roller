/*
    Make a table sortable by clicking on its header cells. Expects a table of the form:

    <table>
	<thead>
	    <tr><td class="numeric">ID</td><td class="text">Summary</td><td class="date">Occurred on</td></tr>
	</thead>
	<tbody>
	    <tr> some cells...</tr>
	</tbody>
    </table>

    where the classes of the table cell headers determine the way that the columns are sorted. It is unlikely
    to work correctly if the table contains rowspans or colspans.

    Inspired by Stuart Langridge's code at http://www.kryogenix.org/code/browser/sorttable/.

    Requires Prototype 1.5+ (http://prototype.conio.net/)
    Requires Logging (http://www.timdown.co.uk/code/)

    This is released under the Creative Commons Attribution-ShareAlike 2.5 license.
    (http://creativecommons.org/licenses/by-sa/2.5/). 

    Copyright Inigo Surguy, 24th March 2006
*/
var log = log4javascript.getDefaultLogger();

function init() {
    log.debug("Looking for tables to make sortable");
    $$("table.sortable thead td").each( function(cell) { 
	log.debug( "Making column header '"+getText(cell)+"' sortable"); 
	cell.innerHTML="<span onclick='sort(this)'>"+cell.innerHTML+"</span>";
    } );
}

function sort(span) {
    log.info("Sorting table column '"+getText(span)+"'");
    var table = getAncestor(span, "table");
    var rows = $A(table.rows);
    var bodyRows = rows.without(rows.first());
    var position = getCellIndex(getAncestor(span, "td"));
    log.debug("There are "+bodyRows.length+" rows to be sorted - sorting the column in position "+position);
    var getCellText = function(row) { return getText($A(row.getElementsByTagName("td"))[position]); }
    var columnValues = bodyRows.map(getCellText);
    log.debug("Current column values order is "+columnValues);

    var simpleCompare = function(a,b) { return a < b ? -1 : a == b ? 0 : 1; };
    var compareComposer = function(normalizeFn) { return function(a,b) { return simpleCompare(normalizeFn(a), normalizeFn(b) ) }; }
    var compareFunctions = {
	"caseSensitive" : simpleCompare ,
	"text" : compareComposer(function(a) { return a.toLowerCase(); }) ,
	// Extracts the first numeric part of a string
	"numeric" : compareComposer(function(a) { return parseInt(a.replace(/^.*?(\d+).*$/,"$1")) }) ,
	// Expects an ISO date format "13 MAR 2006 10:17:02 GMT"
	"date" : compareComposer(Date.parse) ,
	// Converts a date "13 MAR 10:17" to "13 MAR 2000 10:17", which is an ISO date format usable by Date.parse
	"shortDate" : compareComposer(function(a) { return Date.parse(a.replace(/^(\d+)\s*(\w+)\s*(\d+:\d+)$/,"$1 $2 2000 $3")); })
    }
    var className = getAncestor(span, "td").className;
    log.debug("Cell's CSS class is "+className);
    var sortfn = (compareFunctions[className]!=null) ? compareFunctions[className] : compareFunctions["text"] ;

    var order = (span.className=="ascending") ? 1 : -1;
    span.className= (order==-1) ? "ascending" : "descending";
    bodyRows.sort(function(rowA, rowB) { return order * sortfn( getCellText(rowA), getCellText(rowB) ); });
    bodyRows.each(function(row) { table.tBodies[0].appendChild(row); })
    log.debug("Table sorted");
}

function getText(element) { return (element.textContent) ? element.textContent : element.innerText; }

// The td.cellIndex member doesn't work in Safari, so use a function to do the same task
function getCellIndex(td) { return $A(td.parentNode.cells).indexOf(td); }

function getAncestor(element, type) { 
    var ancestor = element; 
    while(ancestor && ancestor.tagName.toUpperCase()!=type.toUpperCase()) { ancestor=ancestor.parentNode; } 
    return ancestor; 
}

Event.observe(window, 'load', init, false);

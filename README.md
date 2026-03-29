This QGIS plugin draws lines from bearings and distances, often referred to as "CoGo" (Coordinate Geometry). This plugin is based on the "Azimuth and Distance Plugin" [qgsazimuth](https://github.com/mpetroff/qgsazimuth).

Version 3.x is compatible with QGIS version 3.x. Version 4.x is compatible with QGIS version 4.x. 

This plugin:

+ is tailored to the conventions common in deeds in the United States
+ adds shorthand bearing entry that can be done entirely on a 10-key number pad
+ uses less screen space than qgsazimuth

Bearings start from either the north or south followed by an angle to the east or west. For example: **N45°27'18"E**. The shorthand entry is numeric: **QDD.MMSS** where:

+ Q is the quadrant, 1=NE, 2=SE, 3=SW, 4=NW
+ DD is degrees (must be 2 digits)
+ a decimal point separates degrees from minutes
+ MM - minutes, optional (must be 2 digits)
+ SS - seconds, optional (must be 2 digits)

Examples:

+ `N45°27'18"E  -  145.2718`
+ `S05°12'38"E  -  205.1238` (note that 5 degrees is entered as "05")
+ `S19°02'44"W  -  319.0244` (note that 2 minutes is entered as "02")
+ `N79°55'12"W  -  479.5512`

For curves, the bearing is the chord bearing, the distance is the chord bearing and the arc radius and direction are required. If you do not have all of the necessary curve components the missing one can be calculated from the curve calculator at [https://greenwoodmap.com/tools/](https://greenwoodmap.com/tools/curve1.html)



# ---------------------------------------------------------------------
#
# licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# ---------------------------------------------------------------------

import math
import os
from unicodedata import decimal

from qgis.PyQt.QtCore import Qt, QFileInfo, QSettings, QSize, QPoint
from qgis.PyQt.QtWidgets import QAction, QTableWidgetItem, QFileDialog
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.core import *

from .ui_control import Dock
from . import resources_rc
from .compat import (
    exec_dialog,
    qgs_attribute_editor_mode,
    qgs_geometry_type,
    qgs_rubberband_icon,
    qt_dock_widget_area,
    qt_global_color,
    qt_pen_style,
)
from math import *
from .getcoordtool import *
from .maptool import LineTool

from . import utils


class gwmapcogo(object):
    """
    Base class for the gwmapcogo plugin
    - Provides a means to draw a feature by specifying the angle and distance beetween points.
    - Supports angles in either the conventional 0.0 - 360.0 clockwise from North
        or the surveyor's 'Easting' system with bearings plus or minus 90 deg. from North or South
    - Supports magnetic declination as degrees plus or minus for East or West respectively
    - supports inputs in feet or the current CRS units
    """

    # just a test to see if mods are taking

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.fPath = (
            ""
        )  # set default working directory, updated from config file & by Import/Export
        self.bands = []

    def log(self, message):
        QgsMessageLog.logMessage(str(message), "Plugin")
        self.iface.messageBar().pushCritical("Error", str(message))

    def initGui(self):
        # create action that will start plugin configuration
        self.action = QAction(
            QIcon(os.path.join(os.path.dirname(__file__), "trav.png")),
            "Bearing and distance",
            self.iface.mainWindow(),
        )
        self.action.setWhatsThis("Bearing and distance")
        self.action.triggered.connect(self.run)

        self.bandpoint = QgsRubberBand(self.canvas, qgs_geometry_type("PointGeometry"))
        self.bandpoint.setIcon(qgs_rubberband_icon("ICON_CROSS"))
        self.bandpoint.setColor(QColor.fromRgb(255, 50, 255))
        self.bandpoint.setWidth(3)
        self.bandpoint.setIconSize(20)

        # add toolbar button and menu item
        self.iface.addPluginToMenu("&Topography", self.action)
        self.iface.addToolBarIcon(self.action)

        self.dock = Dock(self.iface.mainWindow())
        self.iface.addDockWidget(qt_dock_widget_area("BottomDockWidgetArea"), self.dock)
        self.dock.hide()
        self.pluginGui = self.dock.widget()

        self.dock.closed.connect(self.cleanup)
        self.pluginGui.pushButton_vertexAdd.clicked.connect(self.addRow)
        self.pluginGui.pushButton_vertexInsert.clicked.connect(self.insertRow)
        self.pluginGui.pushButton_segListRowDel.clicked.connect(self.delRow)
        self.pluginGui.pushButton_segListLoad.clicked.connect(self.loadList)
        self.pluginGui.pushButton_segListClear.clicked.connect(self.clearList)
        self.pluginGui.pushButton_objectDraw.clicked.connect(self.addgeometry)
        self.pluginGui.pushButton_startCapture.clicked.connect(self.startgetpoint)
        self.pluginGui.pushButton_segListSave.clicked.connect(self.saveList)
        self.pluginGui.pushButton_useLast.clicked.connect(self.use_last_vertex)

        self.pluginGui.pickAngle1_button.clicked.connect(self.select_angle1)
        self.pluginGui.pickAngle2_button.clicked.connect(self.select_angle2)
        self.pluginGui.clearMarkers_button.clicked.connect(self.clear_markers)
        self.pluginGui.copyDiff_button.clicked.connect(self.copy_diff_offset)

        # self.pluginGui.table_segmentList.cellChanged.connect(self.render_temp_band)

        self.pluginGui.table_segmentList.setCurrentCell(0, 0)

        self.tool = GetCoordTool(self.canvas)
        self.tool.finished.connect(self.getpoint)
        self.tool.locationChanged.connect(self.pluginGui.update_startpoint)
        self.tool.locationChanged.connect(self.update_marker_location)

        self.angletool = LineTool(self.canvas)
        self.angletool.geometryComplete.connect(self.update_angle1)
        self.angletool.locationChanged.connect(self.update_marker_location)

        self.angletool2 = LineTool(self.canvas)
        self.angletool2.geometryComplete.connect(self.update_angle2)
        self.angletool2.locationChanged.connect(self.update_marker_location)

        self.pluginGui.azimuth1_edit.textChanged.connect(self.update_angle_calc)
        self.pluginGui.azimuth2_edit.textChanged.connect(self.update_angle_calc)
        # rwg
        self.pluginGui.lineEdit_nextDistance.returnPressed.connect(self.rwg_dist_change)
        self.pluginGui.lineEdit_nextAzimuth.returnPressed.connect(self.rwg_bearing_change)


        self.pluginGui.lineEdit_magNorth.textChanged.connect(self.update_offsetlabel)
        self.pluginGui.radioButton_defaultNorth.toggled.connect(self.update_offsetlabel)

    def rwg_bearing_change(self, *args):
        self.pluginGui.lineEdit_nextDistance.setFocus()
        self.pluginGui.lineEdit_nextDistance.selectAll()

    def rwg_dist_change(self, *args):
        self.addRow()

    # angle is a float, decimal degrees
    def rwg_dd2dms(self, angle):
        # math.modf() splits whole number and decimal into tuple
        # eg 53.3478 becomes (0.3478, 53)
        split = math.modf(angle)

        # the whole number [index 1] is the degrees
        degrees = abs(int(split[1]))

        # multiply the decimal part by 60: 0.3478 * 60 = 20.868
        # split the whole number part of the total as the minutes: 20
        # abs() absoulte value - no negative
        minutes = abs(int(math.modf(split[0] * 60)[1]))

        # multiply the decimal part of the split above by 60 to get the seconds
        # 0.868 x 60 = 52.08, round excess decimal places to 2 places
        # abs() absoulte value - no negative
        seconds = abs(int(round(math.modf(split[0] * 60)[0] * 60, 2)))

        if seconds == 60:
            minutes += 1
            seconds = 0
        if minutes == 60:
            degrees += 1
            minutes = 0
        return str(degrees) + u"\u00b0 " + str(minutes).rjust(2, '0') + '′ ' + str(seconds).rjust(2, '0') + '″'

    # add or subtract an angle measured relative to the last line (backsight)
    # angle is a string in HP calculator angle format dd.mmss,
    # returns forward bearing
    def rwg_angle(self, angle):
        if angle.find('.') == -1:
            angle = angle + '.'
        decimal =  angle.find('.')
        degrees = int(angle[:decimal])
        minutesSeconds = angle[decimal + 1:].ljust(4, '0')
        frac = int(minutesSeconds[2:]) / 60
        frac = frac + int(minutesSeconds[0:2])
        frac = frac / 60
        if degrees >= 0:
            angelDD = degrees + frac
        else:
            angelDD = degrees - frac
        points = self.get_points(self.surveytype, self.arc_count)
        try:
            baz = points[-1].azimuth(points[-2])  # back azimuth
        except:
            self.say('Error: No previous line to measure angle from.')
            return
        if baz < 0:
            baz += 360
        direction = baz + angelDD
        if direction > 360:
            direction = direction - 360
        if direction < 0:
            direction = 360 + direction
        if direction < 90:
            prefix = 'N '
            suffix = ' E'
            bearingDD = direction
        elif direction < 180:
            prefix = 'S '
            suffix = ' E'
            bearingDD = 180 - direction
        elif direction < 270:
            prefix = 'S '
            suffix = ' W'
            bearingDD = direction -180
        elif direction < 360:
            prefix = 'N '
            suffix = ' W'
            bearingDD = 360 - direction
        else:
            self.say('Error: Invalid direction: ' + str(direction))
            return
        bearing = prefix + self.rwg_dd2dms(bearingDD) + suffix
        # bearing = prefix + to_dms(bearingDD, 'x', 0) + suffix # to_dms() is a QGIS function, but how to import?
        print('in rwg_angle baz:' + str(baz) + ', angelDD:' +str(angelDD) + ', direction:' + str(direction))

        return bearing

    def update_offsetlabel(self, *args):
        mag = self.mag_dev
        # self.pluginGui.offsetLabel.setText(str(mag))

    def copy_diff_offset(self):
        diff = self.pluginGui.azimuthDiff_edit.text()
        self.pluginGui.lineEdit_magNorth.setText(diff)

    def clear_markers(self):
        self.angletool2.reset()
        self.angletool.reset()
        self.pluginGui.azimuth1_edit.setText(str(0))
        self.pluginGui.azimuth2_edit.setText(str(0))

    def update_angle_calc(self):
        a1 = self.pluginGui.azimuth1_edit.text()
        a2 = self.pluginGui.azimuth2_edit.text()
        a1 = utils.dmsToDd(a1)
        a2 = utils.dmsToDd(a2)
        try:
            a1 = float(a1)
            a2 = float(a2)
        except ValueError:
            self.pluginGui.azimuthDiff_edit.setText("")
            return

        diff = a2 - a1
        self.pluginGui.azimuthDiff_edit.setText(str(diff))

    def select_angle1(self):
        self.canvas.setMapTool(self.angletool)

    def update_angle1(self, geometry):
        az = utils.azimuth_from_line(geometry)
        az = str(az)
        self.pluginGui.azimuth1_edit.setText(az)

    def update_angle2(self, geometry):
        az = utils.azimuth_from_line(geometry)
        az = str(az)
        self.pluginGui.azimuth2_edit.setText(az)

    def select_angle2(self):
        self.canvas.setMapTool(self.angletool2)

    def update_marker_location(self, point):
        self.bandpoint.setToGeometry(QgsGeometry.fromPointXY(point), None)

    def unload(self):
        # remove the plugin menu item and icon
        self.saveConf()
        self.iface.removeDockWidget(self.dock)
        self.iface.removePluginMenu("&Topography", self.action)
        self.iface.removeToolBarIcon(self.action)
        self.bandpoint.reset()
        self.tool.cleanup()
        self.clear_markers()
        del self.angletool2
        del self.angletool
        del self.tool
        del self.bandpoint

    def run(self):
        # misc init
        self.loadConf()  # get config data
        self.clearList()
        self.setStartAt("0;0;90")  # remove previous StartAt point

        # self.pluginGui.lineEdit_crs.setText(
        #     self.iface.mapCanvas().mapSettings().destinationCrs().description()
        # )

        # if self.iface.activeLayer():
        #     self.updatelayertext(self.iface.activeLayer())
        #     self.pluginGui.radioButton_useActiveLayer.setChecked(True)
        # else:
        #     self.pluginGui.radioButton_useActiveLayer.setEnabled(False)
        #     self.pluginGui.radioButton_useMemoryLayer.setChecked(True)
        self.iface.currentLayerChanged.connect(self.updatelayertext)
        if not self.dock.isVisible():
            self.dock.show()

        # for debugging convenience
        self.notes = self.pluginGui.plainTextEdit_note

    def cleanup(self):
        self.tool.cleanup()
        self.clear_bands()
        self.saveConf()

    def updatelayertext(self, layer):
        x = 1
        # if not layer:
        #     self.pluginGui.radioButton_useActiveLayer.setEnabled(False)
        # else:
        #     self.pluginGui.radioButton_useActiveLayer.setEnabled(True)
        #     self.pluginGui.radioButton_useActiveLayer.setText(
        #         "Active Layer ({0})".format(layer.name())
        #     )

    @property
    def useactivelayer(self):
        # return self.pluginGui.radioButton_useActiveLayer.isChecked()
        return 1

    def render_temp_band(self, *args):
        """
        Render a temp rubber band for showing the user the results
        """

        self.clear_bands()

        featurelist, vectorlayer = self.create_feature()
        if not featurelist or not vectorlayer:
            return

        for feature in featurelist:
            band = QgsRubberBand(self.iface.mapCanvas())
            if hasattr(band, "setLineStyle"):
                band.setLineStyle(qt_pen_style("DotLine"))
            band.setWidth(4)
            band.setColor(qt_global_color("darkMagenta"))
            band.setToGeometry(feature.geometry(), vectorlayer)
            band.show()
            self.bands.append(band)
        pass

    @property
    def should_open_form(self):
        return self.pluginGui.checkBox_openForm.isChecked()

    @should_open_form.setter
    def should_open_form(self, value):
        return self.pluginGui.checkBox_openForm.setChecked(value)

    def addgeometry(self):
        featurelist, vectorlayer = self.create_feature()
        if not featurelist or not vectorlayer:
            return

        if not self.useactivelayer:
            QgsProject.instance().addMapLayer(vectorlayer)

        vectorlayer.startEditing()
        for feature in featurelist:
            if self.should_open_form:
                form = self.iface.getFeatureForm(vectorlayer, feature)
                form.setMode(qgs_attribute_editor_mode("AddFeatureMode"))
                if not exec_dialog(form):
                    continue
            else:
                print(feature.isValid())
                print(feature.geometry().asWkt())
                # error = vectorlayer.addFeature(feature)
                # print(error, feature)
                # if error:
                #     self.log("Error in adding feature")
                result = vectorlayer.addFeature(feature)
                # print(result, feature)

        self.iface.mapCanvas().refresh()
        self.clear_bands()

    def clear_bands(self):
        for band in self.bands:
            band.reset()
        self.bands = []

    def update_draw_button_state(self):
        x, y, z = self.starting_point()
        enabled = True
        if (x == 0 and y == 0 and z == 90) or (
            self.pluginGui.table_segmentList.rowCount() == 0
        ):
            enabled = False
        self.pluginGui.pushButton_objectDraw.setEnabled(enabled)

    def starting_point(self):
        # Get starting point coordinates
        X = float(str(self.pluginGui.lineEdit_vertexX0.text()))
        Y = float(str(self.pluginGui.lineEdit_vertexY0.text()))
        Z = float(str(self.pluginGui.lineEdit_vertexZ0.text()))
        return X, Y, Z

    @property
    def angletype(self):
        if  self.pluginGui.radioButton_bearingAngle.isChecked():
            return "bearing"
        elif self.pluginGui.radioButton_azimuthAngle.isChecked():
            return "azimuth"
        elif self.pluginGui.radioButton_polarCoordAngle.isChecked():
            return "polor"

    @angletype.setter
    def angletype(self, value):
        if value == "azimuth":
            self.pluginGui.radioButton_azimuthAngle.setChecked(True)
        elif value == "bearing":
            self.pluginGui.radioButton_bearingAngle.setChecked(True)
        elif value == "polor":
            self.pluginGui.radioButton_polarCoordAngle.setChecked(True)
        else:
            self.pluginGui.radioButton_azimuthAngle.setChecked(True)

    @property
    def distanceunits(self):
        if self.pluginGui.radioButton_defaultUnits.isChecked():
            return "default"
        elif self.pluginGui.radioButton_englishUnits.isChecked():
            return "feet"

    @distanceunits.setter
    def distanceunits(self, value):
        if value == "default":
            self.pluginGui.radioButton_defaultUnits.setChecked(True)
        elif value == "feet":
            self.pluginGui.radioButton_englishUnits.setChecked(True)
        else:
            self.pluginGui.radioButton_defaultUnits.setChecked(True)

    @property
    def angleunit(self):
        return "degree"
        # if self.pluginGui.radioButton_degreeUnit.isChecked():
        #     return "degree"
        # elif self.pluginGui.radioButton_gradianUnit.isChecked():
        #     return "gradian"

    @angleunit.setter
    def angleunit(self, value):
        x = 1
        # if value == "degree":
        #     self.pluginGui.radioButton_degreeUnit.setChecked(True)
        # elif value == "gradian":
        #     self.pluginGui.radioButton_gradianUnit.setChecked(True)
        # else:
        #     self.pluginGui.radioButton_degreeUnit.setChecked(True)

    @property
    def northtype(self):
        if self.pluginGui.radioButton_magNorth.isChecked():
            return "magnetic"
        else:
            return "default"

    @northtype.setter
    def northtype(self, value):
        if value == "magnetic":
            self.pluginGui.radioButton_magNorth.setChecked(True)
        else:
            self.pluginGui.radioButton_defaultNorth.setChecked(True)

    @property
    def mag_dev(self):
        if self.pluginGui.radioButton_magNorth.isChecked():
            value = str(self.pluginGui.lineEdit_magNorth.text())
            try:
                return float(value)
            except ValueError:
                try:
                    if self.pluginGui.radioButton_gradianUnit.isChecked():
                        value = utils.gradianToDd(value)
                    return float(utils.dmsToDd(value))
                except IndexError:
                    return 0.0
        elif self.pluginGui.radioButton_defaultNorth.isChecked():
            return 0.0
        else:
            return 0.0

    @mag_dev.setter
    def mag_dev(self, value):
        self.pluginGui.lineEdit_magNorth.setText(str(value))

    @property
    def surveytype(self):
        if self.pluginGui.radioButton_radialSurvey.isChecked():
            surveytype = "radial"
        elif self.pluginGui.radioButton_boundarySurvey.isChecked():
            surveytype = "polygonal"
        return surveytype

    @surveytype.setter
    def surveytype(self, value):
        if value == "radial":
            self.pluginGui.radioButton_radialSurvey.setChecked(True)
        elif value == "polygonal":
            self.pluginGui.radioButton_boundarySurvey.setChecked(True)
        else:
            self.pluginGui.radioButton_boundarySurvey.setChecked(True)

    def use_last_vertex(self):
        # Get the last point from the last band
        x, y, z = 0, 0, 90
        arcpoint_count = self.arc_count
        points = self.get_points(self.surveytype, arcpoint_count)
        try:
            point = points[-1]
            x, y, z = point.x, point.y, point.z
        except IndexError:
            # Don't do anything if there is no last point
            return

        point = QgsPointXY(x, y)
        self.pluginGui.update_startpoint(point, z)
        self.update_marker_location(point)
        self.clearList()

    def table_entries(self):
        """
        Return the entries for each row in the table
        """
        rows = self.pluginGui.table_segmentList.rowCount()
        for row in range(rows):
            az = self.pluginGui.table_segmentList.item(row, 0).text()
            dis = float(str(self.pluginGui.table_segmentList.item(row, 1).text()))
            # zen = self.pluginGui.table_segmentList.item(row, 2).text()
            zen = 90
            direction = self.pluginGui.table_segmentList.item(row, 4).text()
            direction = utils.Direction.resolve(direction)

            try:
                radius = float(self.pluginGui.table_segmentList.item(row, 3).text())
            except ValueError:
                radius = None

            yield az, dis, zen, direction, radius

    def get_points(self, surveytype, arcpoint_count):
        """
        Return a list of calculated points for the full run.
        :param surveytype:
        :return:
        """
        X, Y, Z = self.starting_point()

        if (X == 0 and Y == 0 and Z == 90) or (
            self.pluginGui.table_segmentList.rowCount() == 0
        ):
            return []

        vlist = []
        vlist.append(utils.Point(X, Y, Z))
        # convert segment list to set of vertice
        for az, dis, zen, direction, radius in self.table_entries():
            if self.pluginGui.radioButton_englishUnits.isChecked():
                # adjust for input in feet, not meters
                dis = float(dis) * 0.3048

            # checking degree input
            if self.pluginGui.radioButton_azimuthAngle.isChecked():
                if self.pluginGui.radioButton_gradianUnit.isChecked():
                    az = utils.gradianToDd(az)
                    zen = utils.gradianToDd(zen)
                else:
                    az = float(utils.dmsToDd(az))
                    zen = float(utils.dmsToDd(zen))
            elif self.pluginGui.radioButton_bearingAngle.isChecked():
                az = float(self.bearingToDd(az))
                # zen = float(self.bearingToDd(zen))
                zen = float(90)

            # correct for magnetic compass headings if necessary
            self.magDev = self.mag_dev

            az = float(az) + float(self.magDev)

            # correct for angles outside of 0.0-360.0
            while az > 360.0:
                az = az - 360.0

            while az < 0.0:
                az = az + 360.0

            # checking survey type
            if surveytype == "radial":
                reference_point = vlist[0]  # reference first vertex

            if surveytype == "polygonal":
                reference_point = vlist[-1]  # reference previous vertex

            nextpoint = utils.nextvertex(reference_point, dis, az, zen)

            if radius:
                # If there is a radius then we are drawing a arc.
                if self.pluginGui.radioButton_englishUnits.isChecked():
                    # adjust for input in feet, not meters
                    radius = float(radius) * 0.3048

                # Make sure distance <= diameter
                if dis > 2 * radius:
                    self.log("Invalid arc: distance can't be greater than diameter")
                    return []

                # Calculate the arc points.
                points = list(
                    utils.arc_points(
                        reference_point,
                        nextpoint,
                        dis,
                        radius,
                        point_count=arcpoint_count,
                        direction=direction,
                        zenith_angle=zen,
                    )
                )

                if direction == utils.Direction.ANTICLOCKWISE:
                    points = reversed(points)

                # Append them to the final points list.
                vlist.extend(points)

            vlist.append(nextpoint)

        return vlist

    @property
    def drawing_layer(self):
        if self.useactivelayer:
            vectorlayer = self.iface.activeLayer()
        else:
            code = self.iface.mapCanvas().mapSettings().destinationCrs().authid()
            vectorlayer = QgsVectorLayer(
                "LineString?crs={}".format(code), "tmp_plot", "memory"
            )
        return vectorlayer

    @property
    def arc_count(self):
        """
        The number of points to use when drawing arcs
        """
        return self.pluginGui.spin_arclines.value()

    @arc_count.setter
    def arc_count(self, value):
        """
        The number of points to use when drawing arcs
        """
        self.pluginGui.spin_arclines.setValue(value)

    def create_feature(self):
        vectorlayer = self.drawing_layer

        # reprojecting to projects SRS
        arcpoint_count = self.arc_count
        points = self.get_points(self.surveytype, arcpoint_count)

        if not points:
            return None, None

        vlist = self.reproject(points, vectorlayer)

        as_segments = self.pluginGui.checkBox_asSegments.isChecked()

        featurelist = []
        geometrytype = vectorlayer.geometryType()
        if geometrytype == qgs_geometry_type("PointGeometry"):
            points = utils.to_qgspoints(vlist)
            features = utils.createpoints(points)
            featurelist.extend(features)
        elif geometrytype == qgs_geometry_type("LineGeometry"):
            if as_segments:
                # If the line is to be draw as segments then we loop the pairs and create a line for each one.
                points_to_join = []
                in_arc = False
                for pair in utils.pairs(
                    vlist, matchtail=self.surveytype == "polygonal"
                ):
                    start, end = pair[0], pair[1]
                    # If we are not drawing the arc then just add the pair to get a single line
                    if not start.arc_point and not end.arc_point:
                        points_to_join = pair
                    else:
                        # If we are in a arc we need to handle drawing it as one line
                        # which means grabbing each pair until we are finished the arc
                        if not start.arc_point and end.arc_point:
                            points_to_join = []
                            in_arc = True

                        if start.arc_point and not end.arc_point:
                            points_to_join.append(start)
                            points_to_join.append(end)
                            in_arc = False

                        if in_arc:
                            points_to_join.append(start)
                            points_to_join.append(end)
                            continue
                    pointlist = utils.to_qgspoints(
                        points_to_join, repeatfirst=self.surveytype == "radial"
                    )
                    feature = utils.createline(pointlist)
                    featurelist.append(feature)
            else:
                pointlist = utils.to_qgspoints(
                    vlist, repeatfirst=self.surveytype == "radial"
                )
                feature = utils.createline(pointlist)
                featurelist.append(feature)
        elif geometrytype == qgs_geometry_type("PolygonGeometry"):
            polygon = utils.to_qgspoints(vlist)
            feature = utils.createpolygon([polygon])
            if feature:
                featurelist.append(feature)

        # Add the fields for the current layer
        for feature in featurelist:
            feature.setFields(vectorlayer.fields())

        return featurelist, vectorlayer

    def bearingToDd(self, dms):
        # allow survey bearings in form:  - N 25d 34' 40" E
        # where minus ('-') sign allows handling bearings given in reverse direction
        dms = dms.strip()
        if dms[0] == "-":
            rev = True
            dms = dms[1:].strip()
        else:
            rev = False

        baseDir = dms[0].upper()
        if baseDir in ["N", "S"]:
            adjDir = dms[-1].upper()
            bearing = True
            if baseDir == "N":
                if adjDir == "E":
                    base = 0.0
                    adj = "add"
                elif adjDir == "W":
                    base = 360.0
                    adj = "sub"
                else:
                    return 0
            elif baseDir == "S":
                base = 180.0
                if adjDir == "E":
                    adj = "sub"
                elif adjDir == "W":
                    adj = "add"
                else:
                    return 0
        else:
            bearing = False

        # if self.pluginGui.radioButton_gradianUnit.isChecked():
        #     dd = utils.gradianToDd(dms)
        # else:
        #     dd = utils.dmsToDd(dms)
        dd = utils.dmsToDd(dms)

        if rev:
            dd = float(dd) + 180.0

        if bearing == True:
            if adj == "add":
                dd = float(base) + float(dd)
            elif adj == "sub":
                dd = float(base) - float(dd)

        return dd

    def clearList(self):
        self.pluginGui.table_segmentList.clearContents()
        self.pluginGui.table_segmentList.setSortingEnabled(False)
        self.pluginGui.table_segmentList.setRowCount(0)
        self.pluginGui.table_segmentList.setCurrentCell(
            0, 0
        )  # substitute for missing setCurrentRow()
        self.render_temp_band()
        # retranslateUi


    def newVertex(self):
        # adds a vertex from the gui
        self.addrow(
            self.pluginGui.lineEdit_nextAzimuth.text(),
            self.pluginGui.lineEdit_nextDistance.value(),
            self.pluginGui.lineEdit_nextVertical.text(),
            self.pluginGui.spin_radius.value(),
        )

    def addRow(self):
        # this and following must be split to handle both GUI & FILE inputs
        az = self.pluginGui.lineEdit_nextAzimuth.text()
        # rwg
        # dist = self.pluginGui.lineEdit_nextDistance.value()
        dist = self.pluginGui.lineEdit_nextDistance.text()
        # zen = self.pluginGui.lineEdit_nextVertical.text()
        zen = 90.00
        radius = self.pluginGui.spin_radius.value()
        if radius == 0:
            radius = None
            direction = None
        else:
            if self.pluginGui.radio_anticlockwise.isChecked():
                direction = "anticlockwise"
            else:
                direction = "clockwise"
        self.addrow(az, dist, zen, radius, direction)
        # rwg - zero out the radius
        self.pluginGui.spin_radius.setValue(0)

    def addrow(self, az=0, dist=0, zen=90, radius=None, direction=None):

        # begin rwg - this breaks a true azimuth entry but gets it formatted nicely in the data grid
        # print(self.angletype) # bearing | azimuth
        if self.angletype == 'bearing': # try not to break true azimuth entry
            if az[0] == "1" or az[0] == "2" or az[0] == "3" or az[0] == "4" :
                az = az.strip()
                az = az.ljust(8, '0')
            if az[0] == "1":
                az = 'N ' + az[1:3] + '°' + az[4:6] + "′" + az[6:] + '″ E'
            elif az[0] == "2":
                az = 'S ' + az[1:3] + '°' + az[4:6] + "′" + az[6:] + '″ E'
            elif az[0] == "3":
                az = 'S ' + az[1:3] + '°' + az[4:6] + "′" + az[6:] + '″ W'
            elif az[0] == "4":
                az = 'N ' + az[1:3] + '°' + az[4:6] + "′" + az[6:] + '″ W'
            elif az[0] == '-':
                az = self.rwg_angle(az)
            elif az[0] == '+':
                az = self.rwg_angle(az)
            # else:
            #     self.say('invalid angle prefix: ' + az[0])

        # add the vertex to the end of the table
        row = self.pluginGui.table_segmentList.rowCount()
        self.pluginGui.table_segmentList.insertRow(row)
        self.pluginGui.table_segmentList.setItem(
            row, 0, QTableWidgetItem(str(az).upper())
        )
        self.pluginGui.table_segmentList.setItem(row, 1, QTableWidgetItem(str(dist)))
        self.pluginGui.table_segmentList.setItem(row, 2, QTableWidgetItem(str(zen)))
        self.pluginGui.table_segmentList.setItem(row, 3, QTableWidgetItem(str(radius)))
        self.pluginGui.table_segmentList.setItem(
            row, 4, QTableWidgetItem(str(direction))
        )
        self.render_temp_band()
        # rwg move focus to bearing input:
        self.pluginGui.lineEdit_nextAzimuth.setFocus()
        self.pluginGui.lineEdit_nextAzimuth.selectAll()

    def insertRow(self):
        az = self.pluginGui.lineEdit_nextAzimuth.text()
        dist = self.pluginGui.lineEdit_nextDistance.value()
        # zen = self.pluginGui.lineEdit_nextVertical.text()
        zen = 90.00
        radius = self.pluginGui.spin_radius.value()

        if radius == 0:
            radius = None
            direction = None
        else:
            if self.pluginGui.radio_anticlockwise.isChecked():
                direction = "anticlockwise"
            else:
                direction = "clockwise"

        # insert the vertex into the table at the current position
        row = self.pluginGui.table_segmentList.currentRow()
        self.pluginGui.table_segmentList.insertRow(row)
        self.pluginGui.table_segmentList.setItem(
            row, 0, QTableWidgetItem(str(az).upper())
        )
        self.pluginGui.table_segmentList.setItem(row, 1, QTableWidgetItem(str(dist)))
        self.pluginGui.table_segmentList.setItem(row, 2, QTableWidgetItem(str(zen)))
        self.pluginGui.table_segmentList.setItem(row, 3, QTableWidgetItem(str(radius)))
        self.pluginGui.table_segmentList.setItem(
            row, 4, QTableWidgetItem(str(direction))
        )
        self.render_temp_band()

    def delRow(self):
        self.pluginGui.table_segmentList.removeRow(
            self.pluginGui.table_segmentList.currentRow()
        )
        self.render_temp_band()

    def moveup(self):
        self.render_temp_band()
        pass

    def movedown(self):
        self.render_temp_band()
        pass

    def startgetpoint(self):
        # point capture tool
        self.saveTool = self.canvas.mapTool()
        self.canvas.setMapTool(self.tool)

    def getpoint(self, pt):
        self.clear_markers()
        self.pluginGui.update_startpoint(pt)
        self.canvas.setMapTool(self.saveTool)
        # rwg move focus to bearing input:
        self.pluginGui.lineEdit_nextAzimuth.setFocus()
        self.pluginGui.lineEdit_nextAzimuth.selectAll()

    def reproject(self, vlist, vectorlayer):
        renderer = self.canvas.mapSettings()
        for row, point in enumerate(vlist):
            new_point = renderer.layerToMapCoordinates(
                vectorlayer, QgsPointXY(point[0], point[1])
            )
            # Translate it into our new point with arc_point info
            new_point = utils.Point(
                new_point.x(), new_point.y(), arc_point=point.arc_point
            )
            vlist[row] = new_point
        return vlist

    def setAngle(self, s):
        # self.say('processing angleType='+s)
        if s == "azimuth":
            self.pluginGui.radioButton_azimuthAngle.setChecked(True)
        elif s == "bearing":
            self.pluginGui.radioButton_bearingAngle.setChecked(True)
        elif s == "polar":
            self.pluginGui.radioButton_polorCoordAngle.setChecked(True)
        else:
            self.say("invalid angle type: " + s)

    def setHeading(self, s):
        # self.say('processing headingType='+s)
        if s == "coordinate_system":
            self.pluginGui.radioButton_defaultNorth.setChecked(True)
        elif s == "magnetic":
            self.pluginGui.radioButton_magNorth.setChecked(True)
        else:
            self.say("invalid heading type: " + s)

    def setDeclination(self, s):
        # self.say('processing declination='+s)
        self.pluginGui.lineEdit_magNorth.setText(s)
        self.magDev = float(s)

    def setDistanceUnits(self, s):
        # self.say('processing distance units='+s)
        if s == "feet":
            self.pluginGui.radioButton_englishUnits.setChecked(True)
        else:
            self.pluginGui.radioButton_defaultUnits.setChecked(True)

    def setAngleUnit(self, s):
        if s == "gradian":
            self.pluginGui.radioButton_gradianUnit.setChecked(True)
        else:
            self.pluginGui.radioButton_degreeUnit.setChecked(True)

    def setStartAt(self, s):
        # self.say('processing startAt='+s)
        coords = [float(v) for v in s.split(";")]
        point = QgsPointXY(coords[0], coords[1])
        self.pluginGui.update_startpoint(point, coords[2])

    def setSurvey(self, s):
        # self.say('processing surveyType='+s)
        if s == "polygonal":
            self.pluginGui.radioButton_boundarySurvey.setChecked(True)
        elif s == "radial":
            self.pluginGui.radioButton_radialSurvey.setChecked(True)
        else:
            self.say("invalid survey type: " + s)

    def say(self, txt):
        # present a message box on screen
        warn = QgsMessageViewer()
        warn.setMessageAsPlainText(txt)
        warn.showMessage()

    def tell(self, txt):
        # write to bottom of Note area at top of screen
        self.notes.appendPlainText(txt)

    # ---------------------------------------------------------------------------------------------------------------------------------
    #               File handling
    # This section deals with saving the user data to disk, and loading it
    #
    # format:
    #   line 1: angle=Azimuth|Bearing|Polar
    #   line 2: heading=Coordinate System|Magnetic
    #   line 3: declination=[- ]x.xxd[ xx.x'] [E|W]
    #   line 4: distunits=Default|Feet
    #   line 5: startAt=xxxxx.xxxxx, xxxxxx.xxxxx
    #   line 6: survey=Polygonal|Radial
    #   line 7: [data]
    #   line 8 through end: Azimuth; dist; zen
    #
    #       note: lines 1 through 5 are optional if hand entered, but will always be generated when 'saved'
    # ---------------------------------------------------------------------------------------------------------------------------------
    def loadList(self):
        self.fileName, _ = QFileDialog.getOpenFileName(
            None, "Load data separated by ';'", self.fPath, ""
        )
        if not os.path.exists(self.fileName):
            return 0
        # update selected file's folder
        fInfo = QFileInfo(self.fileName)
        self.fPath = fInfo.absolutePath()
        self.saveConf()

        self.render_temp_band()
        # get saved data
        try:
            f = open(self.fileName)
            lines = f.readlines()
            f.close()
            self.clearList()
            for line in lines:
                # remove trailing 'new lines', etc and break into parts
                parts = ((line.strip()).lower()).split("=")
                if len(parts) > 1:
                    # self.say("line="+line+'\nparts[0]='+parts[0]+'\nparts[1]='+parts[1])
                    if parts[0].lower() == "angle":
                        self.setAngle(parts[1].lower())
                    elif parts[0].lower() == "heading":
                        self.setHeading(parts[1].lower())
                    elif parts[0].lower() == "declination":
                        self.setDeclination(parts[1].lower())
                    elif parts[0].lower() == "dist_units":
                        self.setDistanceUnits(parts[1].lower())
                    elif parts[0].lower() == "angle_unit":
                        self.setAngleUnit(parts[1].lower())
                    elif parts[0].lower() == "startat":
                        self.setStartAt(parts[1].lower())
                    elif parts[0].lower() == "survey":
                        self.setSurvey(parts[1].lower())
                else:
                    coords = tuple((line.strip()).split(";"))
                    if coords[0].lower() == "[data]":
                        pass
                    else:
                        self.addrow(*coords)
        except:
            self.say("Invalid input")

    def saveList(self):
        file, _ = QFileDialog.getSaveFileName(
            None, "Save segment list to file.", self.fileName, ""
        )
        if file == "":
            return
        f = open(file, "w")
        # update selected file's folder
        fInfo = QFileInfo(file)
        self.fPath = fInfo.absolutePath()
        self.saveConf()

        if self.pluginGui.radioButton_azimuthAngle.isChecked():
            s = "Azimuth"
        elif self.pluginGui.radioButton_bearingAngle.isChecked():
            s = "Bearing"
        f.write("angle=" + s + "\n")

        if self.pluginGui.radioButton_defaultNorth.isChecked():
            s = "Coordinate_System"
        elif self.pluginGui.radioButton_magNorth.isChecked():
            s = "Magnetic"
        f.write("heading=" + s + "\n")

        if hasattr(self, "magDev") and self.magDev != 0.0:
            f.write("declination=" + str(self.magDev) + "\n")

        if self.pluginGui.radioButton_defaultUnits.isChecked():
            s = "Default"
        elif self.pluginGui.radioButton_englishUnits.isChecked():
            s = "Feet"
        f.write("dist_units=" + s + "\n")

        if self.pluginGui.radioButton_degreeUnit.isChecked():
            s = "degree"
        elif self.pluginGui.radioButton_gradianUnit.isChecked():
            s = "gradian"
        f.write("angle_unit=" + s + "\n")

        f.write(
            "startAt="
            + str(self.pluginGui.lineEdit_vertexX0.text())
            + ";"
            + str(self.pluginGui.lineEdit_vertexY0.text())
            + ";"
            + str(self.pluginGui.lineEdit_vertexZ0.text())
            + "\n"
        )

        if self.pluginGui.radioButton_boundarySurvey.isChecked():
            s = "Polygonal"
        elif self.pluginGui.radioButton_radialSurvey.isChecked():
            s = "Radial"
        f.write("survey=" + s + "\n")

        f.write("[data]\n")
        for row in range(self.pluginGui.table_segmentList.rowCount()):
            line = (
                str(self.pluginGui.table_segmentList.item(row, 0).text())
                + ";"
                + str(self.pluginGui.table_segmentList.item(row, 1).text())
                + ";"
                + str(self.pluginGui.table_segmentList.item(row, 2).text())
                + ";"
                + str(self.pluginGui.table_segmentList.item(row, 3).text())
                + ";"
                + str(self.pluginGui.table_segmentList.item(row, 4).text())
            )
            f.write(line + "\n")

        f.close()

    # ------------------------
    def loadConf(self):
        settings = QSettings()
        size = settings.value("/Plugin-gwmapcogo/size", QSize(800, 600), type=QSize)
        position = settings.value(
            "/Plugin-gwmapcogo/position", QPoint(0, 10), type=QPoint
        )
        self.fPath = settings.value("/Plugin-gwmapcogo/inp_exp_dir", "", type=str)
        self.angletype = settings.value("/Plugin-gwmapcogo/angletype", "", type=str)

        self.should_open_form = settings.value(
            "/Plugin-gwmapcogo/open_form", True, type=bool
        )
        self.surverytype = settings.value("/Plugin-gwmapcogo/type", "", type=str)
        self.northtype = settings.value("/Plugin-gwmapcogo/northtype", "", type=str)
        self.mag_dev = settings.value(
            "/Plugin-gwmapcogo/northtype_value", 0.0, type=float
        )
        self.distanceunits = settings.value(
            "/Plugin-gwmapcogo/distanceunits", "", type=str
        )
        self.angleunit = settings.value("/Plugin-gwmapcogo/angleunit", "", type=str)
        if self.angleunit == "gradian":
            self.pluginGui.lineEdit_nextVertical.setText("100")
        self.angletype = settings.value("/Plugin-gwmapcogo/angletype", "", type=str)
        self.arc_count = settings.value("/Plugin-gwmapcogo/arcpoints", 6, type=int)

        self.pluginGui.resize(size)
        self.pluginGui.move(position)
        self.fileName = self.fPath
        # settings.restoreGeometry(settings.value("Geometry"), QByteArray(), type=QByteArray)

    def saveConf(self):
        settings = QSettings()
        # settings.setValue("Geometry", self.saveGeometry())
        settings.setValue("/Plugin-gwmapcogo/size", self.pluginGui.size())
        settings.setValue("/Plugin-gwmapcogo/position", self.pluginGui.pos())
        settings.setValue("/Plugin-gwmapcogo/inp_exp_dir", self.fPath)
        settings.setValue("/Plugin-gwmapcogo/open_form", self.should_open_form)
        settings.setValue("/Plugin-gwmapcogo/type", self.surveytype)
        settings.setValue("/Plugin-gwmapcogo/northtype", self.northtype)
        settings.setValue("/Plugin-gwmapcogo/northtype_value", self.mag_dev)
        settings.setValue("/Plugin-gwmapcogo/distanceunits", self.distanceunits)
        settings.setValue("/Plugin-gwmapcogo/angleunit", self.angleunit)
        settings.setValue("/Plugin-gwmapcogo/angletype", self.angletype)
        settings.setValue("/Plugin-gwmapcogo/arcpoints", self.arc_count)

    def sortedDict(self, adict):
        keys = list(adict.keys())
        keys.sort()
        return list(map(adict.get, keys))

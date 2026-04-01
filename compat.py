from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes
from qgis.gui import QgsRubberBand

try:
    from qgis.core import QgsAttributeEditorContext
except ImportError:  # QGIS 3 may expose this in qgis.gui
    from qgis.gui import QgsAttributeEditorContext


def qt_global_color(name):
    if hasattr(Qt, "GlobalColor"):
        return getattr(Qt.GlobalColor, name)
    return getattr(Qt, name)


def qt_pen_style(name):
    if hasattr(Qt, "PenStyle"):
        return getattr(Qt.PenStyle, name)
    return getattr(Qt, name)


def qt_dock_widget_area(name):
    if hasattr(Qt, "DockWidgetArea"):
        return getattr(Qt.DockWidgetArea, name)
    return getattr(Qt, name)


def qgs_geometry_type(name):
    if hasattr(QgsWkbTypes, name):
        return getattr(QgsWkbTypes, name)
    return getattr(QgsWkbTypes.GeometryType, name)


def qgs_rubberband_icon(name):
    if hasattr(QgsRubberBand, name):
        return getattr(QgsRubberBand, name)
    return getattr(QgsRubberBand.IconType, name)


def qgs_attribute_editor_mode(name):
    if hasattr(QgsAttributeEditorContext, name):
        return getattr(QgsAttributeEditorContext, name)
    return getattr(QgsAttributeEditorContext.Mode, name)


def exec_dialog(dialog):
    if hasattr(dialog, "exec"):
        return dialog.exec()
    return dialog.exec_()


def exec_app(app):
    if hasattr(app, "exec"):
        return app.exec()
    return app.exec_()

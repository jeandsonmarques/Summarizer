from __future__ import annotations

import sys
import types
from typing import Any


class DummyValue:
    def __call__(self, *args: Any, **kwargs: Any) -> "DummyValue":
        return self

    def __getattr__(self, name: str) -> "DummyValue":
        return self

    def __getitem__(self, key: Any) -> "DummyValue":
        return self

    def __iter__(self):
        return iter(())

    def __bool__(self) -> bool:
        return False

    def __len__(self) -> int:
        return 0

    def __or__(self, other: Any) -> int:
        return 0

    def __ror__(self, other: Any) -> int:
        return 0

    def __and__(self, other: Any) -> int:
        return 0

    def __rand__(self, other: Any) -> int:
        return 0

    def __add__(self, other: Any) -> "DummyValue":
        return self

    def __radd__(self, other: Any) -> "DummyValue":
        return self

    def __sub__(self, other: Any) -> "DummyValue":
        return self

    def __rsub__(self, other: Any) -> "DummyValue":
        return self

    def __repr__(self) -> str:
        return "<DummyValue>"

    def __str__(self) -> str:
        return ""


class DummyMeta(type):
    def __getattr__(cls, name: str):
        return DummyValue()


class DummyObject(metaclass=DummyMeta):
    def __init__(self, *args: Any, **kwargs: Any):
        pass

    def __getattr__(self, name: str) -> DummyValue:
        return DummyValue()

    def __bool__(self) -> bool:
        return False


class DummySettings(DummyObject):
    _store: dict[str, Any] = {}

    def value(self, key: str, default: Any = None, type: Any = None):  # noqa: A002
        if key in self._store:
            return self._store[key]
        if default is not None:
            return default
        if key == "locale/userLocale":
            return "en_US"
        return ""

    def setValue(self, key: str, value: Any):
        self._store[key] = value

    def remove(self, key: str):
        self._store.pop(key, None)


class DummyCoreApplication(DummyObject):
    @staticmethod
    def translate(context: str, message: str) -> str:
        return message

    @staticmethod
    def installTranslator(translator: Any) -> None:
        return None


class DummyIcon(DummyObject):
    def isNull(self) -> bool:
        return False

    def pixmap(self, *args: Any, **kwargs: Any) -> DummyValue:
        return DummyValue()


class DummyDateTime(DummyObject):
    @staticmethod
    def currentDateTime():
        return DummyDateTime()

    @staticmethod
    def currentDateTimeUtc():
        return DummyDateTime()

    @staticmethod
    def fromSecsSinceEpoch(*args: Any, **kwargs: Any):
        return DummyDateTime()

    @staticmethod
    def fromString(*args: Any, **kwargs: Any):
        return DummyDateTime()

    def toString(self, *args: Any, **kwargs: Any) -> str:
        return "2026-04-06T00:00:00"

    def toSecsSinceEpoch(self) -> int:
        return 0

    def isValid(self) -> bool:
        return True

    def addSecs(self, value: int):
        return DummyDateTime()


class DummyMessageLog(DummyObject):
    @staticmethod
    def logMessage(message: str, tag: str, level: Any = None) -> None:
        return None


class DummyQgis:
    Info = 0
    Warning = 1
    Critical = 2


class DummyAuthManager(DummyObject):
    def loadAuthenticationConfig(self, *args: Any, **kwargs: Any) -> bool:
        return False

    def storeAuthenticationConfig(self, *args: Any, **kwargs: Any) -> bool:
        return True

    def removeAuthenticationConfig(self, *args: Any, **kwargs: Any) -> bool:
        return True


class DummyProviderRegistry(DummyObject):
    def __bool__(self) -> bool:
        return True

    def addProvider(self, provider: Any) -> None:
        return None

    def removeProvider(self, provider: Any) -> None:
        return None


class DummyBrowserModel(DummyObject):
    def __bool__(self) -> bool:
        return True


class DummyGui(DummyObject):
    _browser_model = DummyBrowserModel()
    _provider_registry = DummyProviderRegistry()

    @staticmethod
    def instance():
        return DummyGui()

    def browserModel(self) -> DummyBrowserModel:
        return self._browser_model

    def dataItemProviderRegistry(self) -> DummyProviderRegistry:
        return self._provider_registry


class DummyQgsApplication(DummyObject):
    _provider_registry = DummyProviderRegistry()
    _auth_manager = DummyAuthManager()

    @staticmethod
    def getThemeIcon(path: str) -> DummyIcon:
        return DummyIcon()

    @staticmethod
    def dataItemProviderRegistry() -> DummyProviderRegistry:
        return DummyQgsApplication._provider_registry

    @staticmethod
    def authManager() -> DummyAuthManager:
        return DummyQgsApplication._auth_manager


class DummyProject(DummyObject):
    @staticmethod
    def instance():
        return DummyProject()

    def mapLayersByName(self, name: str):
        return []

    def mapLayers(self):
        return {}


class DummyIface:
    def __init__(self):
        self._main_window = DummyObject()
        self._menu_actions: list[tuple[str, Any]] = []
        self._toolbar_actions: list[Any] = []

    def mainWindow(self):
        return self._main_window

    def addPluginToMenu(self, menu: str, action: Any):
        self._menu_actions.append((menu, action))

    def addToolBarIcon(self, action: Any):
        self._toolbar_actions.append(action)

    def removePluginMenu(self, menu: str, action: Any):
        try:
            self._menu_actions.remove((menu, action))
        except ValueError:
            pass

    def removeToolBarIcon(self, action: Any):
        try:
            self._toolbar_actions.remove(action)
        except ValueError:
            pass

    def browserModel(self):
        return DummyObject()

    def messageBar(self):
        return DummyObject()

    def activeLayer(self):
        return None


def _module_with_defaults(name: str) -> types.ModuleType:
    module = types.ModuleType(name)

    def __getattr__(attr: str):
        return DummyObject

    module.__getattr__ = __getattr__  # type: ignore[attr-defined]
    return module


def install_qgis_stubs() -> None:
    if "qgis" in sys.modules:
        return

    qgis_module = types.ModuleType("qgis")
    pyqt_module = types.ModuleType("qgis.PyQt")
    qtcore_module = _module_with_defaults("qgis.PyQt.QtCore")
    qtgui_module = _module_with_defaults("qgis.PyQt.QtGui")
    qtwidgets_module = _module_with_defaults("qgis.PyQt.QtWidgets")
    core_module = _module_with_defaults("qgis.core")
    gui_module = _module_with_defaults("qgis.gui")
    utils_module = _module_with_defaults("qgis.utils")

    qtcore_module.QSettings = DummySettings
    qtcore_module.QCoreApplication = DummyCoreApplication
    qtcore_module.QDateTime = DummyDateTime
    qtcore_module.QTimer = DummyObject
    qtcore_module.QTranslator = DummyObject
    qtcore_module.QBuffer = DummyObject
    qtcore_module.QRectF = DummyObject
    qtcore_module.QSize = DummyObject
    qtcore_module.QSizeF = DummyObject
    qtcore_module.QPoint = DummyObject
    qtcore_module.QPointF = DummyObject
    qtcore_module.QModelIndex = DummyObject
    qtcore_module.QMimeData = DummyObject
    qtcore_module.QVariant = DummyObject
    qtcore_module.pyqtSignal = lambda *args, **kwargs: DummyValue()
    qtcore_module.Qt = DummyObject

    qtgui_module.QIcon = DummyIcon
    qtgui_module.QFont = DummyObject
    qtgui_module.QImage = DummyObject
    qtgui_module.QPainter = DummyObject
    qtgui_module.QColor = DummyObject
    qtgui_module.QCursor = DummyObject
    qtgui_module.QPen = DummyObject
    qtgui_module.QPainterPath = DummyObject
    qtgui_module.QStandardItem = DummyObject
    qtgui_module.QStandardItemModel = DummyObject

    qtwidgets_module.QAction = DummyObject
    qtwidgets_module.QDialog = DummyObject
    qtwidgets_module.QWidget = DummyObject
    qtwidgets_module.QFrame = DummyObject
    qtwidgets_module.QLabel = DummyObject
    qtwidgets_module.QPushButton = DummyObject
    qtwidgets_module.QToolButton = DummyObject
    qtwidgets_module.QVBoxLayout = DummyObject
    qtwidgets_module.QHBoxLayout = DummyObject
    qtwidgets_module.QGridLayout = DummyObject
    qtwidgets_module.QComboBox = DummyObject
    qtwidgets_module.QCheckBox = DummyObject
    qtwidgets_module.QLineEdit = DummyObject
    qtwidgets_module.QTextEdit = DummyObject
    qtwidgets_module.QPlainTextEdit = DummyObject
    qtwidgets_module.QScrollArea = DummyObject
    qtwidgets_module.QStackedWidget = DummyObject
    qtwidgets_module.QTabWidget = DummyObject
    qtwidgets_module.QGroupBox = DummyObject
    qtwidgets_module.QListWidget = DummyObject
    qtwidgets_module.QListWidgetItem = DummyObject
    qtwidgets_module.QFileDialog = DummyObject
    qtwidgets_module.QDialogButtonBox = DummyObject
    qtwidgets_module.QMessageBox = DummyObject
    qtwidgets_module.QProgressBar = DummyObject
    qtwidgets_module.QSizePolicy = DummyObject

    core_module.QgsApplication = DummyQgsApplication
    core_module.QgsMessageLog = DummyMessageLog
    core_module.Qgis = DummyQgis
    core_module.QgsProject = DummyProject

    gui_module.QgsGui = DummyGui
    gui_module.QgsMapLayerComboBox = DummyObject
    utils_module.iface = DummyIface()

    qgis_module.PyQt = pyqt_module
    qgis_module.core = core_module
    qgis_module.gui = gui_module
    qgis_module.utils = utils_module
    pyqt_module.QtCore = qtcore_module
    pyqt_module.QtGui = qtgui_module
    pyqt_module.QtWidgets = qtwidgets_module

    sys.modules["qgis"] = qgis_module
    sys.modules["qgis.PyQt"] = pyqt_module
    sys.modules["qgis.PyQt.QtCore"] = qtcore_module
    sys.modules["qgis.PyQt.QtGui"] = qtgui_module
    sys.modules["qgis.PyQt.QtWidgets"] = qtwidgets_module
    sys.modules["qgis.core"] = core_module
    sys.modules["qgis.gui"] = gui_module
    sys.modules["qgis.utils"] = utils_module


def install_missing_python_stubs() -> None:
    try:
        import numpy  # noqa: F401
    except ImportError:
        numpy_module = types.ModuleType("numpy")
        numpy_module.nan = float("nan")
        numpy_module.ndarray = DummyObject
        numpy_module.number = DummyObject
        numpy_module.__getattr__ = lambda name: DummyObject  # type: ignore[attr-defined]
        sys.modules["numpy"] = numpy_module

    try:
        import pandas  # noqa: F401
    except ImportError:
        pandas_module = types.ModuleType("pandas")
        pandas_api_module = types.ModuleType("pandas.api")
        pandas_types_module = types.ModuleType("pandas.api.types")

        pandas_module.DataFrame = DummyObject
        pandas_module.Series = DummyObject
        pandas_module.Index = DummyObject
        pandas_module.Timestamp = DummyObject
        pandas_module.concat = lambda *args, **kwargs: DummyObject()
        pandas_module.isna = lambda *args, **kwargs: False
        pandas_module.notna = lambda *args, **kwargs: True
        pandas_module.api = pandas_api_module
        pandas_module.__getattr__ = lambda name: DummyObject  # type: ignore[attr-defined]

        pandas_types_module.is_numeric_dtype = lambda *args, **kwargs: False
        pandas_types_module.is_datetime64_any_dtype = lambda *args, **kwargs: False
        pandas_types_module.is_bool_dtype = lambda *args, **kwargs: False
        pandas_types_module.is_object_dtype = lambda *args, **kwargs: False
        pandas_types_module.__getattr__ = lambda name: (lambda *args, **kwargs: False)  # type: ignore[attr-defined]

        pandas_api_module.types = pandas_types_module

        sys.modules["pandas"] = pandas_module
        sys.modules["pandas.api"] = pandas_api_module
        sys.modules["pandas.api.types"] = pandas_types_module


__all__ = ["DummyIface", "install_missing_python_stubs", "install_qgis_stubs"]

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from qgis_stubs import DummyIface, install_missing_python_stubs, install_qgis_stubs

install_missing_python_stubs()
install_qgis_stubs()

from plugin.power_bi_summarizer import classFactory


def main() -> None:
    iface = DummyIface()
    plugin = classFactory(iface)
    assert plugin is not None
    assert plugin.iface is iface

    plugin.initGui()
    assert getattr(plugin, "action", None) is not None

    plugin.run()
    assert getattr(plugin, "dlg", None) is not None

    plugin.unload()
    print("Plugin open smoke ok.")


if __name__ == "__main__":
    main()

import pytest
from pathlib import Path
import shutil

from ifc_core import IfcStore, IdsStore


@pytest.fixture(scope="session")
def real_ids_path():
    return Path(
        "tests/data/AT_3-1_Informationsanforderungskatalog für Hochbauprojekte_edited.ids"
    )


@pytest.fixture(scope="session")
def real_ifc_path():
    return Path("tests/data/HG_TWPL_TW_033.ifc")


@pytest.fixture(scope="session")
def real_ids_store(real_ids_path):
    return IdsStore(real_ids_path)


@pytest.fixture(scope="session")
def real_ifc_store(real_ifc_path):
    # Loaded once per session for reading
    return IfcStore(real_ifc_path)


@pytest.fixture
def mock_ifc_store(tmp_path, real_ifc_path):
    working_copy = tmp_path / real_ifc_path.name
    shutil.copyfile(real_ifc_path, working_copy)
    return IfcStore(working_copy)

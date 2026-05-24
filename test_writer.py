import sys
import ifcopenshell
import ifctester
from ifc_core.services.ids_reader import _map_facet_to_requirement
from ifc_core.services.writer import WriterService
from ifc_core.models.ifc import ConcreteRequirement

# Create a blank model
model = ifcopenshell.file()
# ... wait, creating a valid IFC from scratch using ifcopenshell.file() is tricky without project/setup.
# Let's see if there is a test IFC model in ifc-core or bsc_scripts.

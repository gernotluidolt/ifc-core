import ifcopenshell
import ifcopenshell.api
from typing import Dict, Any
from ..models.ifc import ModificationResult


def add_pset_to_element(
    model: ifcopenshell.file, guid: str, pset_name: str, properties: Dict[str, Any]
) -> ModificationResult:
    """Safely adds a Property Set to an IFC element using the official API."""
    try:
        element = model.by_guid(guid)
        if not element:
            return ModificationResult(success=False, msg=f"Element {guid} not found")

        # 1. Create the Pset container
        pset = ifcopenshell.api.run(
            "pset.add_pset", model, product=element, name=pset_name
        )

        # 2. Add properties to that container
        ifcopenshell.api.run("pset.edit_pset", model, pset=pset, properties=properties)

        return ModificationResult(
            success=True,
            msg=f"Successfully added {pset_name} to {guid}",
            express_id=pset.id(),
        )
    except Exception as e:
        return ModificationResult(success=False, msg=str(e))

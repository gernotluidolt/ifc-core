import ifcopenshell
import ifcopenshell.api
from typing import Dict, Any, List

from ifc_core.models.ids import SpecificationManifest
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


def apply_manifest_to_element(
    model: ifcopenshell.file, manifest: SpecificationManifest
) -> List[ModificationResult]:
    results = []
    element = model.by_guid(manifest.element_guid)

    if not element:
        return [ModificationResult(success=False, msg="Element GUID not found")]

    for req in manifest.requirements:
        try:
            if req.type == "Property":
                pset = ifcopenshell.api.run(
                    "pset.add_pset", model, product=element, name=req.property_set
                )
                ifcopenshell.api.run(
                    "pset.edit_pset", model, pset=pset, properties={req.name: req.value}
                )
                results.append(
                    ModificationResult(success=True, msg=f"Set Property {req.name}")
                )

            elif req.type == "Attribute":
                ifcopenshell.api.run(
                    "attribute.edit_attributes",
                    model,
                    product=element,
                    attributes={req.name: req.value},
                )
                results.append(
                    ModificationResult(success=True, msg=f"Set Attribute {req.name}")
                )

            # Add other types (Material, Classification) here...

        except Exception as e:
            results.append(
                ModificationResult(success=False, msg=f"Error in {req.name}: {str(e)}")
            )

    return results

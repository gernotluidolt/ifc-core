import ifcopenshell
import ifcopenshell.api
from typing import Dict, Any, List

from ..models.ids import SpecificationManifest, ConcreteRequirement
from ..models.ifc import ModificationResult, BulkSpecificationManifest


class ManifestWriter:
    """
    Service Layer class to handle applying requirements to elements.
    Maintains a temporary lookup of materials created during the session
    to prevent duplication during bulk operations.
    """
    def __init__(self, model: ifcopenshell.file):
        self.model = model
        self._materials_cache: Dict[str, Any] = {}

    def _get_or_create_material(self, name: str):
        if name in self._materials_cache:
            return self._materials_cache[name]
            
        # Check existing in model
        for mat in self.model.by_type("IfcMaterial"):
            if mat.Name == name:
                self._materials_cache[name] = mat
                return mat
                
        # Create new
        mat = ifcopenshell.api.run("material.add_material", self.model, name=name)
        self._materials_cache[name] = mat
        return mat

    def apply_requirement(self, element, req: ConcreteRequirement) -> ModificationResult:
        try:
            req_type = req.type.lower() if req.type else ""
            if req_type == "property":
                pset = ifcopenshell.api.run("pset.add_pset", self.model, product=element, name=req.property_set)
                ifcopenshell.api.run("pset.edit_pset", self.model, pset=pset, properties={req.name: req.value})
                return ModificationResult(success=True, msg=f"Set Property {req.name}")
                
            elif req_type == "attribute":
                ifcopenshell.api.run("attribute.edit_attributes", self.model, product=element, attributes={req.name: req.value})
                return ModificationResult(success=True, msg=f"Set Attribute {req.name}")
                
            elif req_type == "entity":
                ifcopenshell.api.run("root.reassign_class", self.model, product=element, new_class=req.value)
                return ModificationResult(success=True, msg=f"Reassigned class to {req.value}")
                
            elif req_type == "material":
                mat = self._get_or_create_material(req.value)
                ifcopenshell.api.run("material.assign_material", self.model, product=element, type="IfcMaterial", material=mat)
                return ModificationResult(success=True, msg=f"Assigned Material {req.value}")
                
            elif req_type == "classification":
                ifcopenshell.api.run("classification.add_reference", self.model, product=element, identification=req.value, name=req.name or req.value)
                return ModificationResult(success=True, msg=f"Assigned Classification {req.value}")
                
            return ModificationResult(success=False, msg=f"Unsupported req type: {req.type}")

        except Exception as e:
            return ModificationResult(success=False, msg=f"Error in {req.name}: {str(e)}")

    def apply_manifest(self, manifest: SpecificationManifest) -> List[ModificationResult]:
        results = []
        element = self.model.by_guid(manifest.element_guid)
        if not element:
            return [ModificationResult(success=False, msg="Element GUID not found")]
            
        for req in manifest.requirements:
            results.append(self.apply_requirement(element, req))
            
        return results

    def apply_bulk_manifest(self, manifest: BulkSpecificationManifest) -> List[ModificationResult]:
        all_results = []
        for guid in manifest.element_guids:
            element = self.model.by_guid(guid)
            if not element:
                all_results.append(ModificationResult(success=False, msg=f"Element {guid} not found"))
                continue
                
            for req in manifest.requirements:
                all_results.append(self.apply_requirement(element, req))
                
        return all_results

def apply_manifest_to_element(
    model: ifcopenshell.file, manifest: SpecificationManifest
) -> List[ModificationResult]:
    writer = ManifestWriter(model)
    return writer.apply_manifest(manifest)

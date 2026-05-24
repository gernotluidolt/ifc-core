from collections.abc import Callable
from typing import Any

import ifcopenshell
import ifcopenshell.api

from ..models.ids import ConcreteRequirement, SpecificationManifest
from ..models.ifc import BulkSpecificationManifest, ModificationResult


class ManifestWriter:
    """
    Service Layer to apply requirements to IFC elements.
    Includes caching for shared resources like materials and classifications.

    Pro-tip: For large-scale operations, consider using this class as a context manager or explicitly compacting the model after bulk writes to avoid orphaned entities (see IfcOpenShell docs).
    """

    def __init__(self, model: ifcopenshell.file):
        self.model = model
        # Pre-cache existing materials and classifications for performance
        self._materials_cache: dict[str, Any] = {
            m.Name: m for m in model.by_type("IfcMaterial") if getattr(m, "Name", None)
        }
        self._classifications_cache: dict[str, Any] = {
            getattr(c, "Name", ""): c for c in model.by_type("IfcClassification")
        }

        # Dispatch table for requirement types
        self._handlers: dict[
            str, Callable[[Any, ConcreteRequirement], ModificationResult]
        ] = {
            "property": self._handle_property,
            "attribute": self._handle_attribute,
            "entity": self._handle_entity,
            "material": self._handle_material,
            "classification": self._handle_classification,
            "pset": self._handle_property,
            "partof": self._handle_partof,
        }

    # --- Internal Helpers ---

    def _get_existing_pset_entity(self, element: Any, pset_name: str) -> Any | None:
        for rel in getattr(element, "IsDefinedBy", []) or []:
            if rel.is_a("IfcRelDefinesByProperties"):
                pset = rel.RelatingPropertyDefinition
                if pset.is_a("IfcPropertySet") and pset.Name == pset_name:
                    return pset
        return None

    def _normalize_ifc_class(self, raw: Any) -> str | None:
        text = str(raw or "").strip()
        if not text:
            return None
        # Only allow valid IFC entity names (simple heuristic)
        if text.lower().startswith("ifc"):
            base = "Ifc" + text[3:].capitalize()
        else:
            base = "Ifc" + text.capitalize()
        # Optionally, check against a known set of IFC classes here
        return base

    def _cast_value(self, value: Any, data_type: str | None) -> Any:
        if value is None or data_type is None:
            return value
            
        dt = data_type.strip().upper()
        try:
            if dt == "IFCINTEGER":
                return int(float(value)) if isinstance(value, (str, float)) else int(value)
            elif dt == "IFCREAL":
                return float(value)
            elif dt == "IFCBOOLEAN":
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "t", "yes", "y")
                return bool(value)
            # Other types like IFCLABEL, IFCTEXT, IFCIDENTIFIER will be string naturally
            return str(value)
        except (ValueError, TypeError):
            return value

    # --- Requirement Handlers ---

    def _handle_property(self, element, req) -> ModificationResult:
        pset_name = (req.property_set or "").strip()
        if not pset_name:
            return ModificationResult(
                success=False, msg=f"Missing property_set for {req.name}"
            )

        pset = self._get_existing_pset_entity(
            element, pset_name
        ) or ifcopenshell.api.run(
            "pset.add_pset", self.model, product=element, name=pset_name
        )

        casted_value = self._cast_value(req.value, getattr(req, "data_type", None))

        ifcopenshell.api.run(
            "pset.edit_pset", self.model, pset=pset, properties={req.name: casted_value}
        )
        return ModificationResult(success=True, msg=f"Set Property {req.name}")

    def _handle_attribute(self, element, req) -> ModificationResult:
        ifcopenshell.api.run(
            "attribute.edit_attributes",
            self.model,
            product=element,
            attributes={req.name: req.value},
        )
        return ModificationResult(success=True, msg=f"Set Attribute {req.name}")

    def _handle_entity(self, element, req) -> ModificationResult:
        target_class = self._normalize_ifc_class(req.value)
        if not target_class:
            return ModificationResult(success=False, msg="Invalid target IFC class")

        if element.is_a(target_class):
            return ModificationResult(success=True, msg=f"Class already {target_class}")

        # reassign_class already unassigns type if incompatible.

        ifcopenshell.api.run(
            "root.reassign_class", self.model, product=element, ifc_class=target_class
        )
        return ModificationResult(success=True, msg=f"Reassigned to {target_class}")

    def _handle_material(self, element, req) -> ModificationResult:
        name = req.value
        # Only use the pre-cached materials for performance
        mat = self._materials_cache.get(name)
        if not mat:
            mat = ifcopenshell.api.run("material.add_material", self.model, name=name)
            self._materials_cache[name] = mat
        ifcopenshell.api.run(
            "material.assign_material", self.model, products=[element], material=mat
        )
        return ModificationResult(success=True, msg=f"Assigned Material {name}")

    def _handle_classification(self, element, req) -> ModificationResult:
        # req.name is expected to be the classification system name (e.g., "Uniclass 2015").
        # If your workflow distinguishes system vs. item, adapt here.
        system_name = (req.name or "").strip()
        if not system_name:
            return ModificationResult(
                success=False, msg="Missing classification system name"
            )

        cls_obj = self._classifications_cache.get(system_name) or next(
            (
                c
                for c in self.model.by_type("IfcClassification")
                if getattr(c, "Name", "") == system_name
            ),
            None,
        )

        if not cls_obj:
            cls_obj = ifcopenshell.api.run(
                "classification.add_classification",
                self.model,
                classification=system_name,
            )

        self._classifications_cache[system_name] = cls_obj
        ifcopenshell.api.run(
            "classification.add_reference",
            self.model,
            products=[element],
            classification=cls_obj,
            identification=req.value,
            name=req.name or req.value,
        )
        return ModificationResult(
            success=True, msg=f"Assigned Classification {req.value}"
        )

    def _handle_partof(self, element, req) -> ModificationResult:
        target_entity = self._normalize_ifc_class(req.name)
        if not target_entity:
            return ModificationResult(success=False, msg="Invalid target entity for PartOf")
            
        target_relation = req.value
        
        # Find a suitable target object in the model
        target_obj = None
        for obj in self.model.by_type(target_entity):
            target_obj = obj
            break
            
        if not target_obj:
            return ModificationResult(success=False, msg=f"No instance of {target_entity} found to assign to")
            
        try:
            rel_upper = target_relation.upper() if target_relation else ""
            if rel_upper == "IFCRELCONTAINEDINSPATIALSTRUCTURE":
                ifcopenshell.api.run("spatial.assign_container", self.model, relating_structure=target_obj, products=[element])
            elif rel_upper == "IFCRELASSIGNSTOGROUP":
                ifcopenshell.api.run("group.assign_group", self.model, group=target_obj, products=[element])
            else:
                if target_obj.is_a("IfcSpatialStructureElement"):
                    ifcopenshell.api.run("spatial.assign_container", self.model, relating_structure=target_obj, products=[element])
                elif target_obj.is_a("IfcGroup"):
                    ifcopenshell.api.run("group.assign_group", self.model, group=target_obj, products=[element])
                else:
                    ifcopenshell.api.run("aggregate.assign_object", self.model, relating_object=target_obj, products=[element])
                    
            return ModificationResult(success=True, msg=f"Assigned to {target_entity}")
        except Exception as e:
            return ModificationResult(success=False, msg=f"Failed to assign PartOf: {str(e)}")

    # --- Public API ---

    def apply_requirement(
        self, element: Any, req: ConcreteRequirement
    ) -> ModificationResult:
        try:
            handler = self._handlers.get((req.type or "").lower())
            if not handler:
                return ModificationResult(
                    success=False, msg=f"Unsupported req type: {req.type}"
                )
            return handler(element, req)
        except Exception as e:
            return ModificationResult(
                success=False, msg=f"Error in {req.name}: {str(e)}"
            )

    def apply_manifest(
        self, manifest: SpecificationManifest
    ) -> list[ModificationResult]:
        element = self.model.by_guid(manifest.element_guid)
        if not element:
            return [
                ModificationResult(
                    success=False, msg=f"GUID {manifest.element_guid} not found"
                )
            ]

        results = []
        # Handle entity/class change first if present
        entity_req = next(
            (r for r in manifest.requirements if (r.type or "").lower() == "entity"),
            None,
        )
        if entity_req:
            results.append(self.apply_requirement(element, entity_req))
            # Re-fetch element after class change
            element = self.model.by_guid(manifest.element_guid)
            if not element:
                results.append(
                    ModificationResult(
                        success=False,
                        msg="Element missing after class change (possible model inconsistency)",
                    )
                )
                return results

        # Now handle all other requirements except entity
        for req in manifest.requirements:
            if (req.type or "").lower() == "entity":
                continue
            results.append(self.apply_requirement(element, req))
        return results

    def apply_bulk_manifest(
        self, manifest: BulkSpecificationManifest
    ) -> list[ModificationResult]:
        results = []
        for guid in manifest.element_guids:
            element = self.model.by_guid(guid)
            if not element:
                results.append(
                    ModificationResult(success=False, msg=f"Element {guid} not found")
                )
                continue

            # 1. Handle Entity change first
            entity_req = next(
                (
                    r
                    for r in manifest.requirements
                    if (r.type or "").lower() == "entity"
                ),
                None,
            )
            if entity_req:
                res = self.apply_requirement(element, entity_req)
                results.append(res)
                if res.success:
                    element = self.model.by_guid(guid)  # Re-fetch
                    if not element:
                        results.append(
                            ModificationResult(
                                success=False,
                                msg=f"Element {guid} missing after class change (possible model inconsistency)",
                            )
                        )
                        continue

            # 2. Handle others
            for req in manifest.requirements:
                if (req.type or "").lower() == "entity":
                    continue
                results.append(self.apply_requirement(element, req))
        return results


def apply_manifest_to_element(
    model: ifcopenshell.file, manifest: SpecificationManifest
) -> list[ModificationResult]:
    return ManifestWriter(model).apply_manifest(manifest)

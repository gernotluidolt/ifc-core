from collections.abc import Callable
from typing import Any

import ifcopenshell
import ifcopenshell.api

from ..models.ids import ConcreteRequirement, SpecificationManifest
from ..models.ifc import BulkSpecificationManifest, ModificationResult


def cast_value_by_type(value: Any, data_type: str | None) -> Any:
    if data_type is None or value is None:
        return value

    dt_lower = str(data_type).lower().strip()

    if dt_lower in ("boolean", "ifcboolean", "bool"):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    if dt_lower in ("integer", "ifcinteger", "int"):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return value

    if dt_lower in ("decimal", "real", "ifcreal", "double", "float") or any(
        x in dt_lower for x in ("measure", "density")
    ):
        try:
            return float(value)
        except (ValueError, TypeError):
            return value

    return value


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

        cast_val = cast_value_by_type(req.value, getattr(req, "data_type", None))

        # Wrap in exact IFC type if raw_data_type or data_type is provided
        dt_str = getattr(req, "raw_data_type", None) or getattr(req, "data_type", None)
        if dt_str:
            dt_str = str(dt_str).strip()
            if not dt_str.lower().startswith("ifc"):
                dt_str = "Ifc" + dt_str
            try:
                # Special handle for boolean/logical string casting
                if dt_str.lower() == "ifclogical" and isinstance(cast_val, str):
                    if cast_val.lower() in ("true", "1", "yes"):
                        cast_val = True
                    elif cast_val.lower() in ("false", "0", "no"):
                        cast_val = False
                    else:
                        cast_val = "UNKNOWN"
                elif dt_str.lower() == "ifcboolean" and isinstance(cast_val, str):
                    cast_val = cast_val.lower() in ("true", "1", "yes")

                cast_val = self.model.create_entity(dt_str, cast_val)
            except Exception:
                # Fallback to cast_val if wrapper creation fails
                pass

        ifcopenshell.api.run(
            "pset.edit_pset", self.model, pset=pset, properties={req.name: cast_val}
        )
        return ModificationResult(success=True, msg=f"Set Property {req.name}")

    def _handle_attribute(self, element, req) -> ModificationResult:
        cast_val = cast_value_by_type(req.value, getattr(req, "data_type", None))
        ifcopenshell.api.run(
            "attribute.edit_attributes",
            self.model,
            product=element,
            attributes={req.name: cast_val},
        )
        return ModificationResult(success=True, msg=f"Set Attribute {req.name}")

    def _handle_entity(self, element, req) -> ModificationResult:
        target_class = self._normalize_ifc_class(req.value)
        if not target_class:
            return ModificationResult(success=False, msg="Invalid target IFC class")

        if element.is_a(target_class):
            return ModificationResult(success=True, msg=f"Class already {target_class}")

        # Clean up types before reassignment
        for rel in list(getattr(element, "IsTypedBy", []) or []):
            ifcopenshell.api.run("root.remove_product", self.model, product=rel)

        ifcopenshell.api.run(
            "root.reassign_class", self.model, product=element, ifc_class=target_class
        )
        return ModificationResult(success=True, msg=f"Reassigned to {target_class}")

    def _handle_material(self, element, req) -> ModificationResult:
        name = req.value
        if not name:
            return ModificationResult(success=False, msg="Missing material name")

        target_name = str(name).strip()
        material = next((m for m in self.model.by_type("IfcMaterial") if getattr(m, "Name", None) == target_name), None)
        if not material:
            material = self.model.create_entity("IfcMaterial", Name=target_name)

        # Clear old material associations for this element
        for rel in list(self.model.by_type("IfcRelAssociatesMaterial")):
            if element in rel.RelatedObjects:
                related = list(rel.RelatedObjects)
                related.remove(element)
                if not related:
                    self.model.remove(rel)
                else:
                    rel.RelatedObjects = related

        self.model.create_entity(
            "IfcRelAssociatesMaterial",
            GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[element],
            RelatingMaterial=material,
        )
        return ModificationResult(success=True, msg=f"Assigned Material {target_name}")

    def _handle_classification(self, element, req) -> ModificationResult:
        system_name = (req.name or "").strip()
        if not system_name:
            return ModificationResult(
                success=False, msg="Missing classification system name"
            )

        classification = next(
            (c for c in self.model.by_type("IfcClassification") if getattr(c, "Name", "") == system_name),
            None,
        )
        if not classification:
            classification = self.model.create_entity(
                "IfcClassification", Name=system_name, Source="IDS Specification"
            )

        classification_reference = self.model.create_entity(
            "IfcClassificationReference",
            Identification=str(req.value),
            ReferencedSource=classification,
        )

        self.model.create_entity(
            "IfcRelAssociatesClassification",
            GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[element],
            RelatingClassification=classification_reference,
        )
        return ModificationResult(
            success=True, msg=f"Assigned Classification {req.value}"
        )

    def _handle_partof(self, element, req) -> ModificationResult:
        relation_type = str(req.relation or "").upper().strip()
        if not relation_type:
            relation_type = "IFCRELCONTAINEDINSPATIALSTRUCTURE"

        if relation_type == "IFCRELCONTAINEDINSPATIALSTRUCTURE":
            target_name = str(req.value).strip()
            if not target_name:
                return ModificationResult(
                    success=False, msg="Missing spatial structure target name"
                )

            storeys = self.model.by_type("IfcBuildingStorey")
            target_storey = next((s for s in storeys if getattr(s, "Name", "") == target_name), None)

            if not target_storey:
                target_storey = self.model.create_entity(
                    "IfcBuildingStorey",
                    GlobalId=ifcopenshell.guid.new(),
                    Name=target_name
                )
                # Hang the newly created storey in the spatial hierarchy
                building = next(iter(self.model.by_type("IfcBuilding")), None)
                if building:
                    rel_aggregates = next(
                        (r for r in self.model.by_type("IfcRelAggregates") if r.RelatingObject == building),
                        None
                    )
                    if rel_aggregates:
                        related = list(rel_aggregates.RelatedObjects)
                        related.append(target_storey)
                        rel_aggregates.RelatedObjects = related
                    else:
                        self.model.create_entity(
                            "IfcRelAggregates",
                            GlobalId=ifcopenshell.guid.new(),
                            RelatingObject=building,
                            RelatedObjects=[target_storey]
                        )
                else:
                    project = next(iter(self.model.by_type("IfcProject")), None)
                    if project:
                        rel_aggregates = next(
                            (r for r in self.model.by_type("IfcRelAggregates") if r.RelatingObject == project),
                            None
                        )
                        if rel_aggregates:
                            related = list(rel_aggregates.RelatedObjects)
                            related.append(target_storey)
                            rel_aggregates.RelatedObjects = related
                        else:
                            self.model.create_entity(
                                "IfcRelAggregates",
                                GlobalId=ifcopenshell.guid.new(),
                                RelatingObject=project,
                                RelatedObjects=[target_storey]
                            )

            for rel in list(self.model.by_type("IfcRelContainedInSpatialStructure")):
                if element in rel.RelatedElements:
                    related = list(rel.RelatedElements)
                    related.remove(element)
                    if not related:
                        self.model.remove(rel)
                    else:
                        rel.RelatedElements = related

            self.model.create_entity(
                "IfcRelContainedInSpatialStructure",
                GlobalId=ifcopenshell.guid.new(),
                RelatedElements=[element],
                RelatingStructure=target_storey
            )
            return ModificationResult(
                success=True, msg=f"Assigned to spatial containment of '{target_name}'"
            )

        return ModificationResult(
            success=False, msg=f"Unsupported partOf relation: {relation_type}"
        )

    # --- Public API ---

    def apply_requirement(
        self, element: Any, req: ConcreteRequirement
    ) -> ModificationResult:
        try:
            if req.pattern and req.value is not None:
                import re
                val_str = str(req.value)
                try:
                    if not re.match(req.pattern, val_str):
                        return ModificationResult(
                            success=False,
                            msg=f"Value '{val_str}' does not match pattern '{req.pattern}'"
                        )
                except Exception as e:
                    return ModificationResult(
                        success=False,
                        msg=f"Invalid regex pattern '{req.pattern}': {str(e)}"
                    )

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

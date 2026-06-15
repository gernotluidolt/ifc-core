from typing import Any

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.classification


from ..models.ifc import ComparisonOperator, ComplexQuery, FilterCriterion


class QueryEngine:
    def __init__(self, model: ifcopenshell.file):
        self.model = model
        self.ids_store = None
        self._ifc_store = None

    def inject_context(self, ifc_store, ids_store):
        """Allows cyclical reference logic to evaluate dynamic Mapping Status natively."""
        self._ifc_store = ifc_store
        self.ids_store = ids_store

    def _evaluate_criterion(self, element, criterion: FilterCriterion) -> bool:
        category = criterion.category.lower()
        val = None

        if category == "attribute":
            val = getattr(element, criterion.name, None)
            if val is None:
                info = element.get_info()
                if criterion.name in info:
                    val = info[criterion.name]

        elif category == "quantity":
            for rel in getattr(element, "IsDefinedBy", []):
                if rel.is_a("IfcRelDefinesByProperties"):
                    prop_def = getattr(rel, "RelatingPropertyDefinition", None)
                    if prop_def and prop_def.is_a("IfcElementQuantity"):
                        for qty in getattr(prop_def, "Quantities", []):
                            qty_name = getattr(qty, "Name", None)
                            if qty_name == criterion.name:
                                for val_attr in ("LengthValue", "AreaValue", "VolumeValue", "CountValue", "WeightValue", "TimeValue"):
                                    qty_val = getattr(qty, val_attr, None)
                                    if qty_val is not None:
                                        val = qty_val
                                        break
                                if val is not None:
                                    break
                        if val is not None:
                            break


        elif category == "pset":
            psets = ifcopenshell.util.element.get_psets(element)

            # If name is omitted, short circuit to true if container matched
            if not criterion.name:
                if criterion.property_set in psets:
                    return True
                return False

            if (
                criterion.property_set in psets
                and criterion.name in psets[criterion.property_set]
            ):
                val = psets[criterion.property_set][criterion.name]

        elif category == "story":
            # For 'Story', find spatial container
            for rel in getattr(element, "ContainedInStructure", []):
                val = getattr(rel.RelatingStructure, "Name", None)
                if val:
                    break

        elif category == "mappingstatus" and self._ifc_store and self.ids_store:
            # Reusing the existing mapping logic directly
            # We use check_mapping_status logic internally
            guid = getattr(element, "GlobalId", None)
            spec_name = (
                criterion.property_set
            )  # Expecting property_set to hold the spec name

            if guid:
                for spec in self.ids_store.specifications:
                    if spec_name and spec.name != spec_name:
                        continue
                    cache_key = f"{guid}_{spec.name}"

                    status = None
                    if cache_key in self._ifc_store._mapping_cache:
                        status = self._ifc_store._mapping_cache[cache_key]
                    else:
                        from ..services.validator import (
                            check_mapping_status as validate_mapping_status,
                        )

                        status = validate_mapping_status(element, spec)
                        self._ifc_store._mapping_cache[cache_key] = status

                    # check actual mapping state
                    if status and status.state.value == criterion.value:
                        return True
            return False

        elif category == "material":
            material = ifcopenshell.util.element.get_material(element)
            if material:
                if material.is_a("IfcMaterialLayerSetUsage"):
                    mset = getattr(material, "ForLayerSet", None)
                    if mset:
                        val = getattr(mset, "MaterialSetName", None)
                if not val:
                    val = getattr(material, "Name", None)

        elif category == "classification":
            refs = []
            try:
                refs = ifcopenshell.util.classification.get_references(element)
            except Exception:
                for rel in getattr(element, "HasAssociations", []):
                    if rel.is_a("IfcRelAssociatesClassification"):
                        ref = getattr(rel, "RelatingClassification", None)
                        if ref:
                            refs.append(ref)

            for ref in refs:
                system = None
                try:
                    system = ifcopenshell.util.classification.get_classification(ref)
                except Exception:
                    system = getattr(ref, "ReferencedSource", None)

                system_name = getattr(system, "Name", None) if system else None

                if criterion.property_set and system_name != criterion.property_set:
                    continue

                # If the value is a placeholder meaning "any classification in this system"
                if criterion.value in (True, "True", "true", None):
                    return True

                code = getattr(ref, "Identification", getattr(ref, "ItemReference", None))
                name = getattr(ref, "Name", None)

                # Matcher fix: Match code, reference name, or system name
                if (self._compare(code, criterion.value, criterion.operator) or
                    self._compare(name, criterion.value, criterion.operator) or
                    self._compare(system_name, criterion.value, criterion.operator)):
                    return True
            return False


        return self._compare(val, criterion.value, criterion.operator)

    def _compare(self, actual: Any, target: Any, op: ComparisonOperator) -> bool:
        if actual is None:
            return False

        # Try numeric comparison if applicable
        if op in (
            ComparisonOperator.EQUALS,
            ComparisonOperator.NOT_EQUALS,
            ComparisonOperator.GREATER_THAN,
            ComparisonOperator.LESS_THAN,
            ComparisonOperator.GREATER_THAN_EQUALS,
            ComparisonOperator.LESS_THAN_EQUALS,
        ):
            try:
                actual_f = float(actual)
                target_f = float(target)
                if op == ComparisonOperator.EQUALS:
                    return actual_f == target_f
                elif op == ComparisonOperator.NOT_EQUALS:
                    return actual_f != target_f
                elif op == ComparisonOperator.GREATER_THAN:
                    return actual_f > target_f
                elif op == ComparisonOperator.LESS_THAN:
                    return actual_f < target_f
                elif op == ComparisonOperator.GREATER_THAN_EQUALS:
                    return actual_f >= target_f
                elif op == ComparisonOperator.LESS_THAN_EQUALS:
                    return actual_f <= target_f
            except (ValueError, TypeError):
                pass

        val_str = str(actual).lower()
        target_str = str(target).lower()

        if op == ComparisonOperator.EQUALS:
            return val_str == target_str
        elif op == ComparisonOperator.NOT_EQUALS:
            return val_str != target_str
        elif op == ComparisonOperator.CONTAINS:
            return target_str in val_str
        elif op == ComparisonOperator.STARTS_WITH:
            return val_str.startswith(target_str)
        elif op == ComparisonOperator.ENDS_WITH:
            return val_str.endswith(target_str)

        return False


    def _evaluate_node(
        self, element, query: ComplexQuery | FilterCriterion
    ) -> bool:
        if isinstance(query, FilterCriterion):
            return self._evaluate_criterion(element, query)

        if not query.criteria:
            return True

        op = query.logical_op.upper()
        if op == "AND":
            return all(self._evaluate_node(element, c) for c in query.criteria)
        elif op == "OR":
            return any(self._evaluate_node(element, c) for c in query.criteria)
        elif op == "NOT":
            return not any(self._evaluate_node(element, c) for c in query.criteria)

        return False

    def execute(self, query: ComplexQuery) -> list[str]:
        elements = self.model.by_type("IfcProduct")
        matched = []
        for el in elements:
            if self._evaluate_node(el, query):
                guid = getattr(el, "GlobalId", None)
                if guid:
                    matched.append(guid)
        return matched

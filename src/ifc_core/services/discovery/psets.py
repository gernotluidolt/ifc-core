from collections import defaultdict
from typing import Any
import ifcopenshell
from ...models.ifc import PSetSummary

def get_psets(model: ifcopenshell.file, element_guids: list[str] | set[str] | None = None) -> list[PSetSummary]:
    """List unique property sets, their parameters, and unique values with counts."""
    # Structure: pset_name -> prop_name -> value -> element_count
    data: dict[str, dict[str, dict[Any, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    pset_elements: dict[str, set[str]] = defaultdict(set)
    target_guids = set(element_guids) if element_guids else None

    for pset in model.by_type("IfcPropertySet"):
        pset_name = str(getattr(pset, "Name", "") or "Unnamed")
        
        # Find all elements assigned to this PSet
        elements_list = []
        rels = getattr(pset, "DefinesOccurrence", None) or getattr(pset, "PropertyDefinitionOf", [])
        for rel in rels:
            if rel.is_a("IfcRelDefinesByProperties"):
                related = getattr(rel, "RelatedObjects", [])
                elements_list.extend([getattr(e, "GlobalId", None) for e in related if getattr(e, "GlobalId", None)])
        
        if not elements_list:
            continue
            
        if target_guids:
            elements_list = [g for g in elements_list if g in target_guids]
            if not elements_list:
                continue
            
        pset_elements[pset_name].update(elements_list)
        el_count = len(elements_list)

        for prop in getattr(pset, "HasProperties", []):
            if not prop.is_a("IfcPropertySingleValue"):
                continue
                
            prop_name = str(getattr(prop, "Name", "") or "Unnamed")
            val = getattr(prop, "NominalValue", None)
            
            # Extract raw value from IfcValue (which is a wrapped type)
            raw_val = val.wrappedValue if hasattr(val, "wrappedValue") else val
            if raw_val is None:
                raw_val = ""
            
            # We increment by the number of elements this property set is assigned to
            data[pset_name][prop_name][raw_val] += el_count

    results = []
    for pset_name, props in sorted(data.items()):
        property_nodes = []
        for prop_name, values in sorted(props.items()):
            value_nodes = [
                PSetSummary(
                    name=str(v),
                    element_count=count,
                    parameters=[],
                    children=[]
                )
                for v, count in sorted(values.items(), key=lambda x: str(x[0]))
            ]
            
            # Aggregate total elements for this property
            total_prop_count = sum(v.element_count for v in value_nodes)
            
            property_nodes.append(
                PSetSummary(
                    name=prop_name,
                    element_count=total_prop_count,
                    parameters=[],
                    children=value_nodes
                )
            )

        results.append(
            PSetSummary(
                name=pset_name,
                element_count=len(pset_elements[pset_name]),
                parameters=list(props.keys()),
                children=property_nodes
            )
        )

    return results

from collections import defaultdict
from typing import Any
import ifcopenshell
from ...models.ifc import PSetSummary

def get_psets(model: ifcopenshell.file) -> list[PSetSummary]:
    """List unique property sets, their parameters, and unique values with counts."""
    # Structure: pset_name -> prop_name -> value -> element_count
    data: dict[str, dict[str, dict[Any, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    pset_elements: dict[str, set[str]] = defaultdict(set)

    for rel in model.by_type("IfcRelDefinesByProperties"):
        pset = rel.RelatingPropertyDefinition
        if not pset or not pset.is_a("IfcPropertySet"):
            continue

        pset_name = str(getattr(pset, "Name", "") or "Unnamed")
        related_elements = getattr(rel, "RelatedObjects", [])
        element_guids = [getattr(e, "GlobalId", None) for e in related_elements]
        element_guids = [g for g in element_guids if g]
        
        pset_elements[pset_name].update(element_guids)

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
            data[pset_name][prop_name][raw_val] += len(element_guids)

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

import sys
import copy
import ifcopenshell
import ifctester.ids
from pathlib import Path
from prettytable import PrettyTable

# Add ifc_core to path
sys.path.append("/Users/gernot/repos/ifc-core/src")
from ifc_core.services.ids_reader import parse_ids_file
from ifc_core.services.writer import ManifestWriter
from ifc_core.models.ids import ConcreteRequirement
from ifc_core.models.ifc import BulkSpecificationManifest

BASELINE_IFC = "/Users/gernot/repos/bsc_scripts/sampleData/synthetic_baseline.ifc"
TEST_IDS = "/Users/gernot/repos/bsc_scripts/sampleData/synthetic_test.ids"

def evaluate():
    # 1. Parse IDS with ifc_core to get the patcher specifications
    core_specs = parse_ids_file(Path(TEST_IDS))
    
    # 2. Open baseline model to get all target elements
    initial_model = ifcopenshell.open(BASELINE_IFC)
    # Get physical elements and proxies
    elements = initial_model.by_type("IfcBuildingElement") + initial_model.by_type("IfcBuildingElementProxy")
    # De-duplicate just in case
    element_guids = list(set([e.GlobalId for e in elements]))
    
    # Matrix for output
    matrix = []
    
    print(f"Testing {len(element_guids)} elements against {len(core_specs)} specifications...")
    
    for element_guid in element_guids:
        orig_class = initial_model.by_guid(element_guid).is_a()
        
        for core_spec in core_specs:
            # 3. State Reset: Reload fresh model to prevent mutation leakage
            model = ifcopenshell.open(BASELINE_IFC)
            target_element = model.by_guid(element_guid)
            
            if not target_element:
                continue
                
            # 4. Initial Compliance Check (AS-IS)
            tester_ids_initial = ifctester.ids.open(TEST_IDS)
            tester_ids_initial.validate(model)
                
            # 5. Application of Enrichment Logic
            writer = ManifestWriter(model)
            # Generate mock data that satisfies the requirements
            concrete_reqs = []
            for r in core_spec.requirements:
                val = r.value
                if val is None or val == "":
                    if r.options:
                        val = r.options[0]
                    elif r.pattern:
                        # Simple heuristics for known patterns in tests
                        val = "IFC-12345" if "IFC" in r.pattern else "Test1234"
                    elif r.min_inclusive is not None:
                        val = r.min_inclusive
                    elif r.data_type == "boolean":
                        val = "True"
                    else:
                        val = "TestValue"
                
                concrete_reqs.append(ConcreteRequirement(
                    id=f"{core_spec.name}_{r.name}_{r.type}",
                    type=r.type,
                    name=r.name,
                    value=val,
                    property_set=getattr(r, 'property_set', None),
                    data_type=getattr(r, 'data_type', None)
                ))
                
            manifest = BulkSpecificationManifest(
                element_guids=[element_guid],
                specification_name=core_spec.name,
                requirements=concrete_reqs
            )
            # Run the patcher
            writer.apply_bulk_manifest(manifest)
            
            # 6. Re-Validation with IFCTester (TO-BE)
            tester_ids = ifctester.ids.open(TEST_IDS)
            tester_ids.validate(model)
            
            tester_spec = next((s for s in tester_ids.specifications if s.name == core_spec.name), None)
            
            results = {
                "Entity": "[ ]",
                "Attribute": "[-]",
                "Property": "[-]",
                "Classification": "[-]",
                "Material": "[-]",
                "PartOf": "[-]"
            }
            
            if tester_spec:
                is_applicable = any(e.GlobalId == element_guid for e in tester_spec.applicable_entities)
                
                if not is_applicable:
                    # Entity failed to be patched correctly, so it's not even applicable
                    results["Entity"] = "[ ]"
                else:
                    results["Entity"] = "[x]"
                    
                    # Group facets by type to track if ANY failed for a specific type
                    facet_types = {
                        "Attribute": True, 
                        "Property": True, 
                        "Classification": True, 
                        "Material": True, 
                        "PartOf": True
                    }
                    facet_present = {
                        "Attribute": False, 
                        "Property": False, 
                        "Classification": False, 
                        "Material": False, 
                        "PartOf": False
                    }
                    
                    for req_facet in tester_spec.requirements:
                        f_type = req_facet.__class__.__name__
                        if f_type in facet_types:
                            facet_present[f_type] = True
                            # Check if THIS element failed this facet
                            failed = any(f["element"].GlobalId == element_guid for f in req_facet.failures)
                            if failed:
                                facet_types[f_type] = False
                                
                    # Assign results
                    for f_type in facet_types:
                        if not facet_present[f_type]:
                            results[f_type] = "[-]" # N/A
                        else:
                            results[f_type] = "[x]" if facet_types[f_type] else "[ ]"
                            
            matrix.append([
                f"{orig_class} ({element_guid[:5]})",
                core_spec.name,
                results["Entity"],
                results["Attribute"],
                results["Property"],
                results["Classification"],
                results["Material"],
                results["PartOf"]
            ])

    # 6. Build and Print Matrix
    table = PrettyTable()
    table.field_names = ["Input Element", "Target Specification", "Ent.", "Attr.", "Prop.", "Class.", "Mat.", "Rel."]
    # Left align for the first two columns
    table.align["Input Element"] = "l"
    table.align["Target Specification"] = "l"
    
    for row in matrix:
        table.add_row(row)
        
    print(table)
    
if __name__ == "__main__":
    evaluate()

/**
 * AUTO-GENERATED FILE - DO NOT EDIT MANUALLY
 * Source: ifc-core Pydantic models
 */

export interface AnchorGroup {
  value: string;
  count: number;
}

export interface AnchorGroupsResponse {
  ok: boolean;
  anchor_name: string;
  pivot_mode: string;
  groups: AnchorGroup[];
  unanchored_count: number;
  total_count: number;
  storey_guid: any;
  error: any;
}

export interface AnchorSelectResponse {
  ok: boolean;
  selected_count: number;
  candidate_count: number;
  error: any;
}

export interface BulkSpecificationManifest {
  element_guids: string[];
  specification_name: string;
  requirements: ConcreteRequirement[];
}

export interface ClassificationNode {
  id: string;
  type: string;
  name: string;
  count: any;
  children: ClassificationNode[];
}

export interface ClassificationTree {
  tree: ClassificationNode[];
  total_elements: number;
}

export type ComparisonOperator =
  | '=='
  | '!='
  | '>'
  | '<'
  | 'contains'
;

export interface ComplexQuery {
  logical_op: string;
  criteria: (FilterCriterion | ComplexQuery)[];
}

export interface ConcreteRequirement {
  type: string;
  name: string;
  value: any;
  property_set: any;
}

export interface CountedItem {
  name: string;
  element_count: number;
}

export interface FilterCriterion {
  category: string;
  name: any;
  operator: ComparisonOperator;
  value: any;
  property_set: any;
}

export interface IdsRequirement {
  type: string;
  name: any;
  value: any;
  property_set: any;
  instructions: any;
  options: string[];
  data_type: any;
  min_inclusive: any;
  max_inclusive: any;
}

export interface LayeredMaterialItem {
  layer_count: number;
}

export interface LayeredMaterialsSummary {
  materials: LayeredMaterialItem[];
  total_elements: number;
}

export type MappingState =
  | 'UNMAPPED'
  | 'INCOMPLETE'
  | 'INVALID'
  | 'COMPLIANT'
;

export interface MappingStatus {
  element_guid: string;
  spec_name: string;
  state: MappingState;
  missing_requirements: IdsRequirement[];
  invalid_requirements: IdsRequirement[];
}

export interface ModelMappingSummary {
  spec_name: string;
  total_applicable: number;
  compliant_count: number;
  invalid_count: number;
  incomplete_count: number;
  unmapped_count: number;
}

export interface ModelMetadata {
  schema_version: string;
  author: string;
  timestamp: string;
  file_name: any;
  has_multilayered_elements: boolean;
}

export interface ModificationResult {
  success: boolean;
  msg: string;
  express_id: any;
}

export interface PSetSummary {
  parameters: string[];
  children: any[];
}

export interface SelectionAnalysis {
  common_attributes: { [key: string]: SharedValue };
  common_psets: { [key: string]: { [key: string]: SharedValue } };
}

export interface SharedValue {
  value: any;
  is_mixed: boolean;
  other_values: any[];
}

export interface SpatialNode {
  guid: string;
  name: string;
  type: string;
  element_count: number;
  has_children: boolean;
  children: SpatialNode[];
}

export interface IdsSpecification {
  name: string;
  identifier: any;
  applicability: IdsRequirement[];
  requirements: IdsRequirement[];
}

export interface SpecificationManifest {
  element_guid: string;
  specification_name: string;
  requirements: ConcreteRequirement[];
}

export interface BimGroup {
  name: string;
  element_guids: string[];
}

export interface BimGroupSummary {
  name: string;
  count: number;
}

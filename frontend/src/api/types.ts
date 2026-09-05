export type Role = "ADMIN" | "SALES_REP" | "SALES_MANAGER" | "FINANCE";

export interface UserOut {
  id: string;
  email: string;
  name: string;
  role: Role;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Category {
  id: string;
  name: string;
  default_discount_ceiling_pct: string;
}

export interface ProductVariant {
  id: string;
  attribute_name: string;
  value: string;
  price_delta: string;
}

export interface Product {
  id: string;
  name: string;
  sku: string;
  category_id: string;
  unit: string;
  list_price: string;
  unit_cost: string;
  tax_pct: string;
  description: string | null;
  is_promoted: boolean;
  is_active: boolean;
  is_subscription: boolean;
  recurring_interval: string | null;
  quantity_on_hand: number;
  variants: ProductVariant[];
}

export interface CustomerTier {
  id: string;
  name: string;
  rank: number;
  base_discount_ceiling_pct: string;
}

export interface Customer {
  id: string;
  name: string;
  email: string;
  tier_id: string;
  currency: string;
}

export interface CeilingCell {
  tier_id: string;
  tier_name: string;
  category_id: string;
  category_name: string;
  ceiling_pct: string;
  is_override: boolean;
}

export interface CeilingMatrix {
  cells: CeilingCell[];
}

export interface ApprovalRule {
  id: string;
  name: string;
  level: number;
  min_blended: string | null;
  min_peak: string | null;
  min_erosion_amount: string | null;
  required_roles: Role[];
  sequence: number;
  is_active: boolean;
}

export interface Warehouse {
  id: string;
  name: string;
  code: string;
  shipping_cost_weight: string;
  is_active: boolean;
}

export interface StockLevel {
  id: string;
  warehouse_id: string;
  product_id: string;
  on_hand: number;
  reserved: number;
  reorder_point: number;
}

export type SubscriptionInterval = "MONTHLY" | "QUARTERLY" | "YEARLY";
export type ProrationPolicy = "DAILY_PRORATE" | "FULL_PERIOD" | "NONE";

export interface SubscriptionPlan {
  id: string;
  name: string;
  interval: SubscriptionInterval;
  interval_count: number;
  proration_policy: ProrationPolicy;
  cancellation_policy: string;
}

export interface ProductPairing {
  id: string;
  product_id: string;
  suggested_product_id: string;
  co_purchase_score: string;
  min_margin_pct: string;
}

export interface SystemSetting {
  key: string;
  value: unknown;
}

export type QuotationStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "SENT"
  | "UNDER_NEGOTIATION"
  | "CONFIRMED"
  | "FULFILLING"
  | "INVOICED"
  | "REJECTED"
  | "CANCELLED";

export type LineType = "ONE_TIME" | "RECURRING";

export interface QuotationLineIn {
  product_id: string;
  variant_id?: string | null;
  line_type?: LineType;
  qty: number;
  discount_pct: number;
  subscription_plan_id?: string | null;
  start_date?: string | null;
}

export interface LinePricing {
  product_id: string;
  product_name: string;
  variant_id: string | null;
  line_type: string;
  qty: number;
  unit_price: string;
  gross: string;
  discount_pct: string;
  discount_amount: string;
  net: string;
  tax_amount: string;
  unit_cost: string;
  cost_total: string;
  margin_amount: string;
  margin_pct: string;
  category_id: string;
  ceiling_pct: string;
  overage_pct: string;
  weight: string;
}

export interface QuotationPricing {
  lines: LinePricing[];
  subtotal: string;
  discount_total: string;
  tax_total: string;
  net_total: string;
  grand_total: string;
  margin_amount: string;
  margin_pct: string;
  explanations: string[];
}

export interface QuotationLineOut {
  id: string;
  product_id: string;
  variant_id: string | null;
  line_type: LineType;
  qty: number;
  unit_price: string;
  unit_cost: string;
  discount_pct: string;
  subscription_plan_id: string | null;
  start_date: string | null;
  computed: Record<string, string>;
}

export interface Quotation {
  id: string;
  number: string;
  customer_id: string;
  owner_user_id: string;
  status: QuotationStatus;
  currency: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  grand_total: string;
  margin_amount: string;
  margin_pct: string;
  blended_score: string;
  peak_overage: string;
  erosion_amount: string;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  lines: QuotationLineOut[];
}

export interface LineRiskBreakdown {
  product_name: string;
  ceiling_pct: string;
  discount_pct: string;
  overage_pct: string;
  weight: string;
  contribution: string;
}

export interface ApprovalStep {
  rule_id: string;
  rule_name: string;
  level: number;
  required_role: Role;
  sequence: number;
  reason: string;
}

export interface RiskResult {
  blended: string;
  peak: string;
  erosion: string;
  breakdown: LineRiskBreakdown[];
  chain: ApprovalStep[];
  chain_explanations: string[];
}

export interface QuotationPreview extends QuotationPricing {
  risk: RiskResult;
}

export type ApprovalRequestStatus = "PENDING" | "APPROVED" | "REJECTED" | "RETURNED" | "CANCELLED";

export interface ApprovalRequestOut {
  id: string;
  quotation_id: string;
  level: number;
  required_role: Role;
  status: ApprovalRequestStatus;
  sequence: number;
  acted_by_user_id: string | null;
  acted_by_name: string | null;
  acted_at: string | null;
  comment: string | null;
  snapshot: Record<string, string>;
  created_at: string;
}

export interface ApprovalListItem {
  quotation_id: string;
  quotation_number: string;
  customer_name: string;
  tier_name: string;
  grand_total: string;
  blended_score: string;
  peak_overage: string;
  required_roles: Role[];
  overall_status: "PENDING" | "RETURNED" | "APPROVED" | "REJECTED";
  stage: string;
  assigned_to: string;
  created_at: string;
}

export interface ApprovalInboxItem {
  approval_request_id: string;
  quotation_id: string;
  quotation_number: string;
  customer_name: string;
  owner_name: string;
  grand_total: string;
  blended_score: string;
  peak_overage: string;
  erosion_amount: string;
  sequence: number;
  level: number;
  created_at: string;
}

export interface AuditEventOut {
  id: string;
  entity_type: string;
  entity_id: string;
  actor_label: string;
  action: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Suggestion {
  product_id: string;
  product_name: string;
  is_promoted: boolean;
  co_purchase_score: string;
  margin_delta: string;
  new_grand_total: string;
  reason: string;
}

export type FulfillmentStatus = "PLANNED" | "ACCEPTED";

export interface FulfillmentAllocationOut {
  id: string;
  quotation_line_id: string;
  product_id: string;
  product_name: string;
  line_qty: number;
  warehouse_id: string | null;
  warehouse_name: string | null;
  qty: number;
  is_backorder: boolean;
  shipped_at: string | null;
}

export interface FulfillmentOut {
  id: string;
  quotation_id: string;
  quotation_number: string;
  customer_name: string;
  status: FulfillmentStatus;
  total_shipments: number;
  estimated_cost: string;
  is_manual_override: boolean;
  explanations: string[];
  allocations: FulfillmentAllocationOut[];
  created_at: string;
}

export interface FulfillmentListItem {
  fulfillment_id: string;
  quotation_id: string;
  order_number: string;
  customer_name: string;
  status_label: string;
  warehouse_names: string;
}

export interface OverrideAllocationIn {
  quotation_line_id: string;
  warehouse_id: string;
  qty: number;
}

export type BillingScheduleStatus = "ACTIVE" | "PAUSED" | "CANCELLED";
export type InvoiceType = "ONE_TIME" | "RECURRING";
export type InvoiceStatus = "DRAFT" | "ISSUED" | "PAID" | "PARTIAL" | "CREDITED";

export interface SubscriptionListItem {
  schedule_id: string;
  customer_name: string;
  plan_name: string;
  interval: SubscriptionInterval;
  next_billing_date: string;
  status: BillingScheduleStatus;
}

export interface OneTimeLineOut {
  product_name: string;
  qty: number;
  amount: string;
}

export interface PeriodOccurrenceOut {
  period_start: string;
  period_end: string;
  amount: string;
}

export interface SubscriptionDetailOut {
  schedule_id: string;
  order_id: string;
  order_number: string;
  customer_name: string;
  plan_name: string;
  interval: SubscriptionInterval;
  interval_count: number;
  qty: number;
  amount: string;
  next_billing_date: string;
  status: BillingScheduleStatus;
  proration_policy: string;
  cancellation_policy: string;
  one_time_lines: OneTimeLineOut[];
  upcoming: PeriodOccurrenceOut[];
}

export interface ProrationPreviewOut {
  old_qty: number;
  new_qty: number;
  delta_amount: string;
  is_credit: boolean;
  days_remaining: number;
  days_in_period: number;
  new_period_amount: string;
  summary: string;
}

export interface InvoiceListItem {
  id: string;
  number: string;
  customer_name: string;
  amount: string;
  tax: string;
  status: InvoiceStatus;
  type: InvoiceType;
  due_date: string;
}

export interface PaymentOut {
  id: string;
  amount: string;
  method: string;
  reference: string | null;
  received_at: string;
}

export interface InvoiceDetailOut {
  id: string;
  number: string;
  order_id: string;
  order_number: string;
  customer_name: string;
  type: InvoiceType;
  amount: string;
  tax: string;
  status: InvoiceStatus;
  issue_date: string;
  due_date: string;
  period_start: string | null;
  period_end: string | null;
  payments: PaymentOut[];
  stage: string;
}

export interface QuotationListItem {
  id: string;
  number: string;
  customer_id: string;
  customer_name: string;
  tier_name: string;
  owner_user_id: string;
  owner_name: string;
  status: QuotationStatus;
  grand_total: string;
  margin_pct: string;
  blended_score: string;
  peak_overage: string;
  required_roles: Role[];
  created_at: string;
  last_activity_at: string;
}

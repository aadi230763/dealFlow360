import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "@/features/auth/LoginPage";
import { SignupPage } from "@/features/auth/SignupPage";
import { AppShell } from "@/features/shell/AppShell";
import { ProtectedRoute } from "@/features/shell/ProtectedRoute";
import { Placeholder } from "@/features/shell/Placeholder";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { QuotationListPage } from "@/features/quotations/QuotationListPage";
import { QuotationBuilderPage } from "@/features/quotations/QuotationBuilderPage";
import { ApprovalsListPage } from "@/features/quotations/ApprovalsListPage";
import { ApprovalDetailPage } from "@/features/quotations/ApprovalDetailPage";
import { ProductCatalogPage } from "@/features/products/ProductCatalogPage";
import { ProductDetailPage } from "@/features/products/ProductDetailPage";
import { DiscountConfigPage } from "@/features/products/DiscountConfigPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />

          <Route path="/quotations" element={<QuotationListPage />} />
          <Route path="/quotations/new" element={<QuotationBuilderPage />} />
          <Route path="/quotations/:id" element={<QuotationBuilderPage />} />

          <Route path="/approvals" element={<ApprovalsListPage />} />
          <Route path="/approvals/:id" element={<ApprovalDetailPage />} />

          <Route path="/products" element={<ProductCatalogPage />} />
          <Route path="/products/discount-config" element={<DiscountConfigPage />} />
          <Route path="/products/:id" element={<ProductDetailPage />} />

          <Route
            path="/fulfillment"
            element={<Placeholder title="Fulfillment" message="Warehouse split and stock arrive in Phase 5." />}
          />
          <Route
            path="/subscriptions"
            element={<Placeholder title="Subscriptions" message="Recurring plans arrive in Phase 6." />}
          />
          <Route
            path="/invoices"
            element={<Placeholder title="Invoices" message="Billing and invoices arrive in Phase 6." />}
          />
          <Route
            path="/deal-health"
            element={<Placeholder title="Deal Health" message="Anomaly detection arrives in Phase 8." />}
          />
          <Route
            path="/reports"
            element={<Placeholder title="Reports" message="Reporting arrives in Phase 8." />}
          />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

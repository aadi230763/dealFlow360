"""End-to-end: hits the real HTTP endpoints (through the pricing/risk/routing engines,
unmodified) and asserts the right Notification rows land for the right people. This is
what actually proves the router call sites are wired to the dispatcher correctly, on top
of the pure dispatcher unit tests in test_notification_rules.py.
"""

import uuid
from decimal import Decimal

from app.models.approval_rule import ApprovalRule
from app.models.catalog import Category, Product
from app.models.customer import Customer, CustomerTier
from app.models.notification import Notification
from app.models.user import Role


def _seed_catalog(db_session):
    """One category with a 5% ceiling, one tier, one customer, one product, and an
    approval rule that requires a SALES_MANAGER once blended overage passes 1 point --
    a 50%-discount line against a 5% ceiling clears that easily."""
    category = Category(id=uuid.uuid4(), name="TestCategory", default_discount_ceiling_pct=Decimal("5"))
    tier = CustomerTier(id=uuid.uuid4(), name="TestTier", rank=1, base_discount_ceiling_pct=Decimal("5"))
    db_session.add_all([category, tier])
    db_session.flush()

    customer = Customer(id=uuid.uuid4(), name="Test Co", email="testco@test.example", tier_id=tier.id, currency="INR")
    product = Product(
        id=uuid.uuid4(),
        name="Test Widget",
        sku=f"TW-{uuid.uuid4().hex[:8]}",
        category_id=category.id,
        unit="each",
        list_price=Decimal("1000"),
        unit_cost=Decimal("500"),
        tax_pct=Decimal("10"),
    )
    rule = ApprovalRule(
        id=uuid.uuid4(),
        name="Test Manager Rule",
        level=1,
        min_blended=Decimal("1"),
        min_peak=None,
        min_erosion_amount=None,
        required_roles=["SALES_MANAGER"],
        sequence=1,
        is_active=True,
    )
    db_session.add_all([customer, product, rule])
    db_session.flush()
    return customer, product


def test_submitting_over_ceiling_notifies_the_manager(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-notif-1@test.example")
    manager = make_user(Role.SALES_MANAGER, "manager-notif-1@test.example")
    customer, product = _seed_catalog(db_session)

    create_res = as_user(rep).post(
        "/api/quotations",
        json={"customer_id": str(customer.id), "lines": [{"product_id": str(product.id), "qty": 1, "discount_pct": 50}]},
    )
    assert create_res.status_code == 201
    quotation_id = create_res.json()["id"]

    submit_res = as_user(rep).post(f"/api/quotations/{quotation_id}/submit")
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "PENDING_APPROVAL"

    manager_notifications = db_session.query(Notification).filter(Notification.user_id == manager.id).all()
    assert len(manager_notifications) == 1
    assert manager_notifications[0].event_type == "quotation_submitted_for_approval"
    assert manager_notifications[0].quotation_id == uuid.UUID(quotation_id)
    assert "needs your approval" in manager_notifications[0].message

    rep_notifications = db_session.query(Notification).filter(Notification.user_id == rep.id).all()
    assert rep_notifications == []


def test_auto_approved_submission_notifies_the_owner_not_a_manager(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-notif-2@test.example")
    make_user(Role.SALES_MANAGER, "manager-notif-2@test.example")
    customer, product = _seed_catalog(db_session)

    create_res = as_user(rep).post(
        "/api/quotations",
        # 0% discount, well under the 5% ceiling -- no rule should trigger.
        json={"customer_id": str(customer.id), "lines": [{"product_id": str(product.id), "qty": 1, "discount_pct": 0}]},
    )
    quotation_id = create_res.json()["id"]

    submit_res = as_user(rep).post(f"/api/quotations/{quotation_id}/submit")
    assert submit_res.json()["status"] == "APPROVED"

    rep_notifications = db_session.query(Notification).filter(Notification.user_id == rep.id).all()
    assert len(rep_notifications) == 1
    assert rep_notifications[0].event_type == "quotation_auto_approved"


def test_rejecting_a_quotation_notifies_its_owner(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-notif-3@test.example")
    manager = make_user(Role.SALES_MANAGER, "manager-notif-3@test.example")
    customer, product = _seed_catalog(db_session)

    create_res = as_user(rep).post(
        "/api/quotations",
        json={"customer_id": str(customer.id), "lines": [{"product_id": str(product.id), "qty": 1, "discount_pct": 50}]},
    )
    quotation_id = create_res.json()["id"]
    as_user(rep).post(f"/api/quotations/{quotation_id}/submit")

    approvals = as_user(manager).get(f"/api/quotations/{quotation_id}/approvals").json()
    approval_id = approvals[0]["id"]

    act_res = as_user(manager).post(
        f"/api/approvals/{approval_id}/act", json={"action": "reject", "comment": "not viable"}
    )
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "REJECTED"

    rep_notifications = (
        db_session.query(Notification)
        .filter(Notification.user_id == rep.id, Notification.event_type == "quotation_rejected")
        .all()
    )
    assert len(rep_notifications) == 1
    assert "was rejected" in rep_notifications[0].message


def test_returning_for_revision_notifies_the_owner(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-notif-4@test.example")
    manager = make_user(Role.SALES_MANAGER, "manager-notif-4@test.example")
    customer, product = _seed_catalog(db_session)

    create_res = as_user(rep).post(
        "/api/quotations",
        json={"customer_id": str(customer.id), "lines": [{"product_id": str(product.id), "qty": 1, "discount_pct": 50}]},
    )
    quotation_id = create_res.json()["id"]
    as_user(rep).post(f"/api/quotations/{quotation_id}/submit")

    approval_id = as_user(manager).get(f"/api/quotations/{quotation_id}/approvals").json()[0]["id"]
    as_user(manager).post(
        f"/api/approvals/{approval_id}/act", json={"action": "return_for_revision", "comment": "please justify"}
    )

    rep_notifications = (
        db_session.query(Notification)
        .filter(Notification.user_id == rep.id, Notification.event_type == "quotation_returned_for_revision")
        .all()
    )
    assert len(rep_notifications) == 1

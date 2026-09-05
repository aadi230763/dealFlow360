"""API-level tests for GET/POST /api/notifications* against a real (test) Postgres DB."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.models.customer import Customer, CustomerTier
from app.models.notification import Notification
from app.models.quotation import Quotation, QuotationStatus
from app.models.user import Role


def _add_notification(db_session, user_id, message="hi", quotation_id=None):
    notification = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        event_type="quotation_approved",
        message=message,
        quotation_id=quotation_id,
    )
    db_session.add(notification)
    db_session.flush()
    return notification


def test_list_notifications_is_scoped_to_the_current_user(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-a@test.example")
    other = make_user(Role.SALES_REP, "rep-b@test.example")
    mine = _add_notification(db_session, rep.id, "for me")
    _add_notification(db_session, other.id, "not for me")

    res = as_user(rep).get("/api/notifications")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["id"] == str(mine.id)


def test_new_notification_is_unread_by_default(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-h@test.example")
    _add_notification(db_session, rep.id, "brand new")

    res = as_user(rep).get("/api/notifications")

    assert res.json()[0]["read_at"] is None


def test_unread_only_filter_excludes_read_notifications(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-c@test.example")
    unread = _add_notification(db_session, rep.id, "unread")
    already_read = _add_notification(db_session, rep.id, "already read")
    already_read.read_at = datetime.now(timezone.utc)
    db_session.flush()

    res = as_user(rep).get("/api/notifications?unread_only=true")

    ids = {n["id"] for n in res.json()}
    assert str(unread.id) in ids
    assert str(already_read.id) not in ids


def test_mark_read_sets_a_timestamp(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-d@test.example")
    notification = _add_notification(db_session, rep.id, "mark me")

    res = as_user(rep).post(f"/api/notifications/{notification.id}/read")

    assert res.status_code == 200
    assert res.json()["read_at"] is not None


def test_mark_read_is_idempotent(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-i@test.example")
    notification = _add_notification(db_session, rep.id, "mark me twice")

    first = as_user(rep).post(f"/api/notifications/{notification.id}/read")
    second = as_user(rep).post(f"/api/notifications/{notification.id}/read")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["read_at"] == first.json()["read_at"]


def test_cannot_mark_another_users_notification_as_read(client, as_user, make_user, db_session):
    owner = make_user(Role.SALES_REP, "rep-e@test.example")
    intruder = make_user(Role.SALES_REP, "rep-f@test.example")
    notification = _add_notification(db_session, owner.id, "private")

    res = as_user(intruder).post(f"/api/notifications/{notification.id}/read")

    assert res.status_code == 404
    db_session.refresh(notification)
    assert notification.read_at is None


def test_mark_read_unknown_id_returns_404(client, as_user, make_user):
    rep = make_user(Role.SALES_REP, "rep-j@test.example")

    res = as_user(rep).post(f"/api/notifications/{uuid.uuid4()}/read")

    assert res.status_code == 404


def test_mark_all_read_clears_every_unread_notification(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-g@test.example")
    _add_notification(db_session, rep.id, "one")
    _add_notification(db_session, rep.id, "two")

    res = as_user(rep).post("/api/notifications/read-all")
    assert res.status_code == 204

    remaining_unread = as_user(rep).get("/api/notifications?unread_only=true").json()
    assert remaining_unread == []


def test_mark_all_read_does_not_touch_other_users_notifications(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-k@test.example")
    other = make_user(Role.SALES_REP, "rep-l@test.example")
    other_notification = _add_notification(db_session, other.id, "not yours")

    as_user(rep).post("/api/notifications/read-all")

    db_session.refresh(other_notification)
    assert other_notification.read_at is None


def test_notification_carries_the_quotation_number_when_linked(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-m@test.example")
    tier = CustomerTier(id=uuid.uuid4(), name="TestTier", rank=1, base_discount_ceiling_pct=Decimal("5"))
    db_session.add(tier)
    db_session.flush()
    customer = Customer(id=uuid.uuid4(), name="Test Co", email="test-co@test.example", tier_id=tier.id, currency="INR")
    db_session.add(customer)
    db_session.flush()
    quotation = Quotation(
        id=uuid.uuid4(),
        number="Q-TEST-0001",
        customer_id=customer.id,
        owner_user_id=rep.id,
        status=QuotationStatus.DRAFT,
    )
    db_session.add(quotation)
    db_session.flush()
    _add_notification(db_session, rep.id, "linked", quotation_id=quotation.id)

    res = as_user(rep).get("/api/notifications")

    assert res.json()[0]["quotation_id"] == str(quotation.id)
    assert res.json()[0]["quotation_number"] == "Q-TEST-0001"


def test_notification_without_a_quotation_has_no_quotation_number(client, as_user, make_user, db_session):
    rep = make_user(Role.SALES_REP, "rep-n@test.example")
    _add_notification(db_session, rep.id, "unlinked", quotation_id=None)

    res = as_user(rep).get("/api/notifications")

    assert res.json()[0]["quotation_id"] is None
    assert res.json()[0]["quotation_number"] is None

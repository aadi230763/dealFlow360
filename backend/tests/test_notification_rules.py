"""Unit tests for core/notifications.py in isolation -- a two-table in-memory SQLite DB
(User, Notification only), no Postgres, no FastAPI app. Fast, and exercises exactly the
three things the dispatcher owns: who gets notified, what a Notification row looks like
once created, and that an SSE event fires for each one.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import notifications as notifications_module
from app.core.notifications import RULES, _owner, _users_with_role, dispatch_event
from app.models.notification import Notification
from app.models.user import Role, User


@pytest.fixture()
def sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    Notification.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_user(session, role: Role, email: str) -> User:
    user = User(id=uuid.uuid4(), email=email, password_hash="x", name=email, role=role)
    session.add(user)
    session.flush()
    return user


class TestRecipientResolvers:
    def test_users_with_role_returns_only_matching_role(self, sqlite_session):
        manager = _make_user(sqlite_session, Role.SALES_MANAGER, "m@test.example")
        _make_user(sqlite_session, Role.SALES_REP, "r@test.example")

        assert _users_with_role(sqlite_session, "SALES_MANAGER") == [manager.id]

    def test_users_with_role_matches_multiple_users(self, sqlite_session):
        m1 = _make_user(sqlite_session, Role.FINANCE, "f1@test.example")
        m2 = _make_user(sqlite_session, Role.FINANCE, "f2@test.example")

        assert set(_users_with_role(sqlite_session, "FINANCE")) == {m1.id, m2.id}

    def test_users_with_role_unknown_role_string_returns_empty(self, sqlite_session):
        _make_user(sqlite_session, Role.SALES_MANAGER, "m@test.example")
        assert _users_with_role(sqlite_session, "NOT_A_REAL_ROLE") == []

    def test_users_with_role_no_matches_returns_empty(self, sqlite_session):
        _make_user(sqlite_session, Role.SALES_REP, "r@test.example")
        assert _users_with_role(sqlite_session, "FINANCE") == []

    def test_owner_resolver_returns_the_owner_id(self, sqlite_session):
        owner_id = uuid.uuid4()
        assert _owner(sqlite_session, {"owner_user_id": owner_id}) == [owner_id]

    def test_owner_resolver_missing_context_key_returns_empty(self, sqlite_session):
        assert _owner(sqlite_session, {}) == []

    def test_owner_resolver_none_owner_returns_empty(self, sqlite_session):
        assert _owner(sqlite_session, {"owner_user_id": None}) == []


class TestDispatchEvent:
    def test_unknown_event_type_creates_nothing_and_does_not_publish(self, sqlite_session, monkeypatch):
        published = []
        monkeypatch.setattr(notifications_module, "publish", published.append)

        result = dispatch_event(sqlite_session, "not_a_registered_event", {}, None)

        assert result == []
        assert sqlite_session.query(Notification).count() == 0
        assert published == []

    def test_role_based_event_notifies_every_user_with_that_role(self, sqlite_session, monkeypatch):
        published = []
        monkeypatch.setattr(notifications_module, "publish", published.append)
        m1 = _make_user(sqlite_session, Role.SALES_MANAGER, "m1@test.example")
        m2 = _make_user(sqlite_session, Role.SALES_MANAGER, "m2@test.example")
        _make_user(sqlite_session, Role.SALES_REP, "r@test.example")
        quotation_id = uuid.uuid4()

        created = dispatch_event(
            sqlite_session,
            "quotation_submitted_for_approval",
            {"number": "Q-0001", "role": "SALES_MANAGER"},
            quotation_id,
        )

        assert {n.user_id for n in created} == {m1.id, m2.id}
        assert sqlite_session.query(Notification).count() == 2
        for n in created:
            assert n.message == "Quotation Q-0001 needs your approval."
            assert n.quotation_id == quotation_id
            assert n.read_at is None
            assert n.event_type == "quotation_submitted_for_approval"

    def test_role_based_event_publishes_one_sse_event_per_recipient(self, sqlite_session, monkeypatch):
        published = []
        monkeypatch.setattr(notifications_module, "publish", published.append)
        m1 = _make_user(sqlite_session, Role.FINANCE, "f1@test.example")
        m2 = _make_user(sqlite_session, Role.FINANCE, "f2@test.example")
        quotation_id = uuid.uuid4()

        dispatch_event(
            sqlite_session,
            "quotation_routed_to_next_approver",
            {"number": "Q-0002", "role": "FINANCE"},
            quotation_id,
        )

        assert len(published) == 2
        seen_user_ids = set()
        for event in published:
            assert event["type"] == "notification_created"
            assert event["event_type"] == "quotation_routed_to_next_approver"
            assert event["quotation_id"] == str(quotation_id)
            assert "notification_id" in event
            seen_user_ids.add(uuid.UUID(event["user_id"]))
        assert seen_user_ids == {m1.id, m2.id}

    def test_owner_based_event_notifies_only_the_owner(self, sqlite_session, monkeypatch):
        monkeypatch.setattr(notifications_module, "publish", lambda payload: None)
        owner = _make_user(sqlite_session, Role.SALES_REP, "owner@test.example")
        _make_user(sqlite_session, Role.SALES_REP, "someone-else@test.example")
        quotation_id = uuid.uuid4()

        created = dispatch_event(
            sqlite_session,
            "quotation_approved",
            {"owner_user_id": owner.id, "number": "Q-0003"},
            quotation_id,
        )

        assert len(created) == 1
        assert created[0].user_id == owner.id
        assert created[0].message == "Quotation Q-0003 was approved."

    def test_no_matching_recipients_creates_nothing(self, sqlite_session, monkeypatch):
        published = []
        monkeypatch.setattr(notifications_module, "publish", published.append)

        created = dispatch_event(
            sqlite_session,
            "quotation_submitted_for_approval",
            {"number": "Q-0004", "role": "FINANCE"},
            uuid.uuid4(),
        )

        assert created == []
        assert sqlite_session.query(Notification).count() == 0
        assert published == []

    def test_missing_required_context_creates_nothing(self, sqlite_session, monkeypatch):
        monkeypatch.setattr(notifications_module, "publish", lambda payload: None)

        created = dispatch_event(sqlite_session, "quotation_approved", {"number": "Q-0005"}, uuid.uuid4())

        assert created == []

    def test_quotation_id_is_optional(self, sqlite_session, monkeypatch):
        published = []
        monkeypatch.setattr(notifications_module, "publish", published.append)
        owner = _make_user(sqlite_session, Role.SALES_REP, "owner2@test.example")

        created = dispatch_event(sqlite_session, "quotation_approved", {"owner_user_id": owner.id, "number": "Q-0006"}, None)

        assert created[0].quotation_id is None
        assert published[0]["quotation_id"] is None

    def test_duplicate_recipient_ids_are_deduplicated(self, sqlite_session, monkeypatch):
        monkeypatch.setattr(notifications_module, "publish", lambda payload: None)
        user = _make_user(sqlite_session, Role.SALES_REP, "dup@test.example")

        # Same user_id resolved twice (e.g. owner is also somehow in a role list) should
        # still only produce one Notification row.
        monkeypatch.setattr(
            notifications_module,
            "RULES",
            {
                **RULES,
                "__test_duplicate__": notifications_module.NotificationRule(
                    resolve_recipients=lambda db, ctx: [user.id, user.id],
                    render_message=lambda ctx: "dup test",
                ),
            },
        )

        created = dispatch_event(sqlite_session, "__test_duplicate__", {}, None)

        assert len(created) == 1


def test_every_registered_rule_has_callable_resolver_and_renderer():
    for event_type, rule in RULES.items():
        assert callable(rule.resolve_recipients), event_type
        assert callable(rule.render_message), event_type


def test_expected_event_types_are_registered():
    # The set of events this phase was asked to cover -- submitted, returned, rejected,
    # approved, recomputed, plus the routing/negotiation events already in the system.
    expected = {
        "quotation_submitted_for_approval",
        "quotation_auto_approved",
        "quotation_routed_to_next_approver",
        "quotation_approved",
        "quotation_rejected",
        "quotation_returned_for_revision",
        "quotation_recomputed_reentered_approval",
        "negotiation_created",
        "quotation_reentered_approval_from_portal",
    }
    assert expected.issubset(RULES.keys())

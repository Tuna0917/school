"""보안·권한과 포인트 정합성 회귀 테스트.

여기 있는 테스트는 대부분 "예전 코드에서는 통과하지 못했던" 항목이다.
각 테스트 docstring에 원래 어떤 버그였는지 적어 두었다.
"""

import random

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from . import services
from .models import Log, Preset, Room, Seat, Student
from .services import DomainError

PW = "test-pw-12345"


def make_student(name, point=100, username=None, status=Student.ATTENDING):
    user = User.objects.create_user(username=username or name, password=PW)
    return Student.objects.create(user=user, name=name, point=point, status=status)


def make_teacher(username="teacher"):
    return User.objects.create_user(username=username, password=PW, is_staff=True)


# ---------------------------------------------------------------- 포인트 정합성


class PlaceBidTests(TestCase):
    def setUp(self):
        self.room = services.open_room(row=2, minimum=10, seat_count=4)
        self.seat = self.room.seat_set.first()
        self.student = make_student("김철수", point=100)

    def test_bid_deducts_point_and_creates_log(self):
        services.place_bid(self.student, self.seat, 30)

        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 70)
        self.assertEqual(services.active_bids([self.seat.id]).count(), 1)

    def test_bid_over_balance_is_rejected(self):
        """예전 `student.point -= int(post['point'])`는 잔액 검사가 없어서
        100포인트를 가진 학생이 500을 입찰하면 -400이 됐다."""
        with self.assertRaises(DomainError):
            services.place_bid(self.student, self.seat, 500)

        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 100)
        self.assertFalse(Log.objects.exists())

    def test_zero_or_negative_bid_is_rejected(self):
        """음수 입찰은 차감이 아니라 지급이 되는 포인트 증식 버그였다."""
        for amount in (-50, 0):
            with self.subTest(amount=amount):
                with self.assertRaises(DomainError):
                    services.place_bid(self.student, self.seat, amount)

        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 100)

    def test_bid_below_room_minimum_is_rejected(self):
        """Room.minimum이 모델에만 있고 아무도 검증하지 않았다."""
        with self.assertRaises(DomainError):
            services.place_bid(self.student, self.seat, 5)

    def test_duplicate_bid_on_same_seat_is_rejected(self):
        """같은 좌석에 두 번 입찰하면 포인트만 두 번 빠져나갔다."""
        services.place_bid(self.student, self.seat, 30)
        with self.assertRaises(DomainError):
            services.place_bid(self.student, self.seat, 30)

        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 70)

    def test_bid_on_closed_room_is_rejected(self):
        self.room.status = Room.CLOSED
        self.room.save(update_fields=["status"])

        with self.assertRaises(DomainError):
            services.place_bid(self.student, self.seat, 30)

    def test_non_attending_student_cannot_bid(self):
        dropout = make_student("자퇴생", username="dropout", status=Student.DROPOUT)
        with self.assertRaises(DomainError):
            services.place_bid(dropout, self.seat, 30)

    def test_point_cannot_go_negative_at_db_level(self):
        """서비스 계층을 우회해도 CheckConstraint가 막는다."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Student.objects.filter(pk=self.student.pk).update(point=-1)

    def test_duplicate_active_bid_blocked_at_db_level(self):
        """UniqueConstraint가 마지막 방어선으로 동작한다."""
        services.place_bid(self.student, self.seat, 30)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Log.objects.create(
                    status=Log.USE,
                    obj_name=services.SEAT,
                    obj_id=self.seat.id,
                    log_student=self.student,
                    point=30,
                )


class CancelBidTests(TestCase):
    def setUp(self):
        self.room = services.open_room(row=2, minimum=10, seat_count=4)
        self.seat = self.room.seat_set.first()
        self.student = make_student("김철수", point=100)

    def test_cancel_refunds_point(self):
        log = services.place_bid(self.student, self.seat, 30)
        services.cancel_bid(log)

        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 100)

    def test_cancel_twice_is_rejected(self):
        """예전 cancel은 canceled 플래그를 보지 않아 새로고침만으로 같은
        입찰을 여러 번 환불받을 수 있었다."""
        log = services.place_bid(self.student, self.seat, 30)
        services.cancel_bid(log)

        with self.assertRaises(DomainError):
            services.cancel_bid(log)

        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 100)

    def test_cancelled_bid_frees_the_seat_for_rebidding(self):
        log = services.place_bid(self.student, self.seat, 30)
        services.cancel_bid(log)

        services.place_bid(self.student, self.seat, 50)
        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 50)


class AdjustPointTests(TestCase):
    def setUp(self):
        self.student = make_student("김철수", point=100)

    def test_adjust_records_reason(self):
        services.adjust_point(self.student, 50, reason="숙제 보상")

        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 150)
        self.assertTrue(Log.objects.filter(reason="숙제 보상").exists())

    def test_adjust_cannot_push_balance_below_zero(self):
        with self.assertRaises(DomainError):
            services.adjust_point(self.student, -500, reason="차감")

        self.student.refresh_from_db()
        self.assertEqual(self.student.point, 100)


# ---------------------------------------------------------------- 배정 알고리즘


class AllocateTests(TestCase):
    """`allocate`는 DB를 건드리지 않는 순수 함수라 단독으로 검증할 수 있다."""

    def test_highest_bid_wins_and_the_rest_are_refunded(self):
        bids = [("b1", 1, 10), ("b2", 1, 20)]  # 우선순위 순으로 정렬된 상태
        won, refunded, _ = services.allocate(bids, [1], [10, 20])

        self.assertEqual(won, {1: (10, "b1")})
        self.assertEqual(refunded, ["b2"])

    def test_student_winning_two_seats_keeps_only_the_first(self):
        """예전 루프는 한 학생이 두 좌석을 동시에 낙찰할 수 있었다."""
        bids = [("b1", 1, 10), ("b2", 2, 10)]
        won, refunded, _ = services.allocate(bids, [1, 2], [10])

        self.assertEqual(won, {1: (10, "b1")})
        self.assertEqual(refunded, ["b2"])

    def test_leftover_seats_are_filled_without_duplicates(self):
        """예전 while/pop/continue 조합은 학생이 남았는데도 좌석이 비거나
        같은 학생이 두 번 배정되는 경우가 있었다."""
        bids = [("b1", 1, 10)]
        won, _, random_assigned = services.allocate(
            bids, [1, 2, 3], [10, 20, 30], rng=random.Random(0)
        )

        owners = list(won.keys()) + list(random_assigned.keys())
        self.assertCountEqual(owners, [1, 2, 3])

        students = [s for s, _ in won.values()] + list(random_assigned.values())
        self.assertCountEqual(students, [10, 20, 30])

    def test_more_students_than_seats_leaves_nobody_double_seated(self):
        won, _, random_assigned = services.allocate(
            [], [1, 2], [10, 20, 30, 40], rng=random.Random(0)
        )

        self.assertEqual(won, {})
        self.assertEqual(len(random_assigned), 2)
        self.assertEqual(len(set(random_assigned.values())), 2)

    def test_more_seats_than_students_leaves_seats_empty(self):
        _, _, random_assigned = services.allocate(
            [], [1, 2, 3], [10], rng=random.Random(0)
        )
        self.assertEqual(len(random_assigned), 1)


class CloseRoomTests(TestCase):
    def setUp(self):
        self.room = services.open_room(row=2, minimum=10, seat_count=2)

    def test_winner_keeps_point_and_loser_is_refunded(self):
        winner = make_student("최고", point=100, username="winner")
        loser = make_student("차순", point=100, username="loser")
        seat = self.room.seat_set.first()

        services.place_bid(winner, seat, 80)
        services.place_bid(loser, seat, 20)

        services.close_room(self.room, rng=random.Random(0))

        seat.refresh_from_db()
        winner.refresh_from_db()
        loser.refresh_from_db()

        self.assertEqual(seat.owner, winner)
        self.assertEqual(seat.status, Seat.TAKEN)
        self.assertEqual(winner.point, 20)  # 낙찰가는 돌려받지 않는다
        self.assertEqual(loser.point, 100)  # 유찰은 전액 환불

    def test_every_student_gets_exactly_one_seat(self):
        students = [
            make_student(f"학생{i}", point=100, username=f"s{i}") for i in range(2)
        ]
        services.place_bid(students[0], self.room.seat_set.first(), 50)

        services.close_room(self.room, rng=random.Random(0))

        owners = [s.owner_id for s in self.room.seat_set.all()]
        self.assertNotIn(None, owners)
        self.assertCountEqual(owners, [s.pk for s in students])

    def test_closing_twice_is_rejected(self):
        services.close_room(self.room)
        with self.assertRaises(DomainError):
            services.close_room(self.room)

    def test_only_one_room_can_be_open(self):
        """예전 room_now는 `Room.objects.get(status='a')`를 써서 열린 교실이
        둘이 되는 순간 MultipleObjectsReturned로 500이 났다."""
        with self.assertRaises(DomainError):
            services.open_room(row=2, minimum=10, seat_count=2)


class RoomGridTests(TestCase):
    def test_grid_pads_the_last_row(self):
        room = services.open_room(row=3, minimum=1, seat_count=5)
        rows = room.grid()

        self.assertEqual([len(r) for r in rows], [3, 3])
        self.assertIsNone(rows[-1][-1])


# ---------------------------------------------------------------- 권한


class PermissionTests(TestCase):
    """예전에는 아래 대부분이 비로그인 상태로도 통과했다."""

    def setUp(self):
        self.room = services.open_room(row=2, minimum=10, seat_count=4)
        self.seat = self.room.seat_set.first()
        self.me = make_student("나", point=100, username="me")
        self.other = make_student("남", point=100, username="other")

    def test_anonymous_is_redirected_to_login(self):
        for name, args in [
            ("student_list", []),
            ("room_list", []),
            ("preset_list", []),
            ("room_detail", [self.room.pk]),
            ("seat_detail", [self.seat.pk]),
        ]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response["Location"])

    def test_student_cannot_view_student_list(self):
        self.client.force_login(self.me.user)
        response = self.client.get(reverse("student_list"))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_view_another_students_detail(self):
        self.client.force_login(self.me.user)
        response = self.client.get(reverse("student_detail", args=[self.other.pk]))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_edit_another_student(self):
        """예전 StudentUpdateView는 소유자 검사가 없어 아무나 남의 pk로
        접근해 이름을 바꿀 수 있었다."""
        self.client.force_login(self.me.user)

        response = self.client.post(
            reverse("student_update", args=[self.other.pk]), {"name": "해킹됨"}
        )

        self.assertEqual(response.status_code, 403)
        self.other.refresh_from_db()
        self.assertEqual(self.other.name, "남")

    def test_student_cannot_change_own_status(self):
        """status 필드는 선생님에게만 노출돼야 한다. 예전 코드는 dispatch에서
        클래스 속성을 바꿔, 선생님이 한 번 접속하면 이후 학생 요청에도 status가
        남아 학생이 스스로 상태를 바꿀 수 있었다."""
        self.client.force_login(self.me.user)

        self.client.post(
            reverse("student_update", args=[self.me.pk]),
            {"name": "나", "status": Student.DROPOUT},
        )

        self.me.refresh_from_db()
        self.assertEqual(self.me.status, Student.ATTENDING)

    def test_student_cannot_change_points(self):
        """point_change에 권한 검사가 없어 학생이 자기 포인트를 직접 올릴 수 있었다."""
        self.client.force_login(self.me.user)

        response = self.client.post(
            reverse("point_change", args=[self.me.pk]),
            {"point": 9999, "reason": "셀프 지급"},
        )

        self.assertEqual(response.status_code, 403)
        self.me.refresh_from_db()
        self.assertEqual(self.me.point, 100)

    def test_student_cannot_create_or_delete_preset(self):
        preset = Preset.objects.create(name="기존", point=10)
        self.client.force_login(self.me.user)

        create = self.client.post(
            reverse("preset_create"), {"name": "몰래", "point": 1}
        )
        delete = self.client.post(reverse("preset_delete", args=[preset.pk]))

        self.assertEqual(create.status_code, 403)
        self.assertEqual(delete.status_code, 403)
        self.assertFalse(Preset.objects.filter(name="몰래").exists())
        self.assertTrue(Preset.objects.filter(pk=preset.pk).exists())

    def test_student_cannot_close_room(self):
        self.client.force_login(self.me.user)
        response = self.client.post(reverse("close_room"))

        self.assertEqual(response.status_code, 403)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.OPEN)

    def test_student_cannot_create_students(self):
        self.client.force_login(self.me.user)
        response = self.client.post(reverse("create_students"), {"number": 5})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Student.objects.count(), 2)

    def test_bid_is_always_charged_to_the_logged_in_student(self):
        """예전 auction은 POST의 student id를 그대로 믿어서 남의 포인트로
        입찰해 잔액을 소진시킬 수 있었다."""
        self.client.force_login(self.me.user)

        self.client.post(
            reverse("auction", args=[self.seat.pk]),
            {"point": 50, "student": self.other.pk},
        )

        self.me.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.me.point, 50)
        self.assertEqual(self.other.point, 100)

    def test_student_cannot_cancel_another_students_bid(self):
        log = services.place_bid(self.other, self.seat, 30)
        self.client.force_login(self.me.user)

        self.client.post(reverse("cancel", args=[log.pk]))

        self.other.refresh_from_db()
        self.assertEqual(self.other.point, 70)

    def test_student_can_cancel_own_bid(self):
        log = services.place_bid(self.me, self.seat, 30)
        self.client.force_login(self.me.user)

        self.client.post(reverse("cancel", args=[log.pk]))

        self.me.refresh_from_db()
        self.assertEqual(self.me.point, 100)


class UnsafeMethodTests(TestCase):
    """상태를 바꾸는 요청은 POST여야 한다. GET으로 열려 있으면 링크
    프리페치나 크롤러가 교실을 마감시킬 수 있다."""

    def setUp(self):
        self.room = services.open_room(row=2, minimum=10, seat_count=4)
        make_teacher()
        self.client.login(username="teacher", password=PW)

    def test_close_room_ignores_get(self):
        self.client.get(reverse("close_room"))

        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.OPEN)

    def test_teacher_can_close_room_with_post(self):
        response = self.client.post(reverse("close_room"))

        self.assertEqual(response.status_code, 302)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, Room.CLOSED)


class StudentAccountCreationTests(TestCase):
    def test_created_students_get_distinct_random_passwords(self):
        """예전 create_students는 `password = 123123`을 하드코딩해서
        학번만 알면 누구나 남의 계정으로 로그인할 수 있었다."""
        created = services.create_student_accounts(3)

        self.assertEqual(len(created), 3)
        passwords = [pw for _, pw in created]
        self.assertEqual(len(set(passwords)), 3)

        for student, password in created:
            self.assertNotEqual(password, "123123")
            self.assertTrue(
                self.client.login(username=student.user.username, password=password)
            )

    def test_passwords_are_hashed_not_stored_in_plain_text(self):
        created = services.create_student_accounts(1)
        student, password = created[0]

        self.assertNotEqual(student.user.password, password)
        self.assertTrue(student.user.password.startswith("pbkdf2_"))

    def test_teacher_sees_generated_passwords_once(self):
        make_teacher()
        self.client.login(username="teacher", password=PW)

        response = self.client.post(reverse("create_students"), {"number": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["passwords"]), 2)
        self.assertEqual(Student.objects.count(), 2)

        # 화면에 표시되는 아이디는 추측값이 아니라 실제 username이어야 한다.
        shown = {username for username, _, _ in response.context["passwords"]}
        self.assertEqual(shown, set(User.objects.filter(is_staff=False).values_list("username", flat=True)))

    def test_username_collision_does_not_reuse_an_existing_account(self):
        """`student1`이 이미 있으면 비어 있는 번호를 찾아야 한다.
        같은 username으로 create_user를 부르면 IntegrityError가 난다."""
        make_student("기존", username="student1")

        created = services.create_student_accounts(2)

        usernames = [s.user.username for s, _ in created]
        self.assertNotIn("student1", usernames)
        self.assertEqual(len(set(usernames)), 2)

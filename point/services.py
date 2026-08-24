"""
포인트/좌석 경매의 도메인 로직.

뷰에서 직접 `student.point -= n; student.save()` 하는 대신 이 모듈을 통해서만
포인트를 변경한다. 모든 함수는

  * `transaction.atomic()` 안에서 동작하고
  * 포인트를 건드리는 대상 행을 `select_for_update()`로 잠그며
  * 규칙 위반 시 `DomainError`를 던진다 (조용히 무시하지 않는다)

는 세 가지 규칙을 지킨다. 덕분에 동시에 들어온 두 요청이 같은 포인트를 두 번
쓰는 lost update가 발생하지 않는다.
"""

import random
import secrets

from django.contrib.auth.models import User
from django.db import transaction

from .models import Log, Room, Seat, Student

SEAT = "seat"
LOG = "log"


class DomainError(Exception):
    """사용자에게 그대로 보여줘도 되는 규칙 위반."""


def get_open_room():
    """열려 있는 교실. 없으면 None.

    예전 코드의 `Room.objects.get(status='a')`는 열린 교실이 2개가 되는 순간
    MultipleObjectsReturned로 500을 냈다. 가장 최근 것을 쓰도록 바꿔 방어한다.
    """
    return Room.objects.filter(status=Room.OPEN).order_by("-created_date").first()


def require_open_room():
    room = get_open_room()
    if room is None:
        raise DomainError("열려 있는 교실이 없습니다.")
    return room


def active_bids(seat_ids):
    """주어진 좌석들에 살아 있는(취소되지 않은) 입찰 로그."""
    return Log.objects.filter(
        obj_name=SEAT,
        obj_id__in=list(seat_ids),
        status=Log.USE,
        canceled=False,
    )


def bid_of(student, seat):
    """학생이 해당 좌석에 이미 걸어둔 입찰. 없으면 None."""
    return active_bids([seat.id]).filter(log_student=student).first()


@transaction.atomic
def place_bid(student, seat, amount, *, reason=None):
    """좌석에 입찰한다.

    검증 순서가 중요하다. 포인트를 차감하기 *전에* 잠근 행에서 다시 잔액을
    확인해야 동시 요청에서 잔액이 음수로 내려가지 않는다.
    """
    if amount is None or amount < 1:
        raise DomainError("입찰 포인트는 1 이상이어야 합니다.")

    # 좌석 -> 교실 순으로 잠가 교실 마감과 입찰이 경쟁하지 않게 한다.
    seat = Seat.objects.select_for_update().select_related("room").get(pk=seat.pk)
    room = seat.room

    if room.status != Room.OPEN:
        raise DomainError("이미 마감된 교실입니다.")
    if seat.status != Seat.OPEN or seat.owner_id is not None:
        raise DomainError("이미 배정이 끝난 좌석입니다.")
    if room.minimum and amount < room.minimum:
        raise DomainError(f"이 교실의 최소 입찰 포인트는 {room.minimum}입니다.")

    locked = Student.objects.select_for_update().get(pk=student.pk)
    if locked.status != Student.ATTENDING:
        raise DomainError("재학 중인 학생만 입찰할 수 있습니다.")
    if bid_of(locked, seat) is not None:
        raise DomainError("이 좌석에는 이미 입찰했습니다. 취소한 뒤 다시 입찰해 주세요.")
    if locked.point < amount:
        raise DomainError(f"포인트가 부족합니다. (보유 {locked.point}, 필요 {amount})")

    locked.point -= amount
    locked.save(update_fields=["point", "modified_date"])

    return Log.objects.create(
        status=Log.USE,
        obj_name=SEAT,
        obj_id=seat.id,
        log_student=locked,
        point=amount,
        reason=reason or f"{seat.num}번 좌석에 입찰함.",
    )


@transaction.atomic
def cancel_bid(log, *, refund_reason=None):
    """입찰을 취소하고 포인트를 되돌려준다.

    `canceled` 플래그를 잠긴 행에서 다시 읽어 확인하므로, 취소 링크를 두 번
    빠르게 눌러도 포인트가 두 번 환급되지 않는다.
    """
    log = Log.objects.select_for_update().get(pk=log.pk)

    if log.status != Log.USE:
        raise DomainError("입찰 기록만 취소할 수 있습니다.")
    if log.canceled:
        raise DomainError("이미 취소된 입찰입니다.")

    student = Student.objects.select_for_update().get(pk=log.log_student_id)

    log.canceled = True
    log.save(update_fields=["canceled", "modified_date"])

    student.point += log.point
    student.save(update_fields=["point", "modified_date"])

    return Log.objects.create(
        status=Log.TEACHER,
        obj_name=LOG,
        log_student=student,
        cancel_log=log,
        point=log.point,
        reason=refund_reason or "입찰 취소로 포인트를 돌려받음.",
    )


@transaction.atomic
def adjust_point(student, amount, *, reason="", obj_name="teacher", obj_id=0):
    """선생님이 포인트를 지급/차감한다. 결과 잔액이 음수면 거부한다."""
    if amount == 0:
        raise DomainError("0포인트는 지급할 수 없습니다.")

    locked = Student.objects.select_for_update().get(pk=student.pk)
    if locked.point + amount < 0:
        raise DomainError(
            f"차감할 포인트가 보유 포인트보다 많습니다. (보유 {locked.point})"
        )

    locked.point += amount
    locked.save(update_fields=["point", "modified_date"])

    return Log.objects.create(
        status=Log.TEACHER,
        obj_name=obj_name,
        obj_id=obj_id,
        log_student=locked,
        point=amount,
        reason=reason,
    )


def allocate(bids, seats, students, *, rng=random):
    """좌석 배정 결과를 계산하는 순수 함수.

    DB를 건드리지 않으므로 단독으로 테스트할 수 있다.

    인자:
        bids: (bid_id, seat_id, student_id) 리스트. 낙찰 우선순위대로 정렬돼 있어야 한다.
        seats: 전체 좌석 id 리스트.
        students: 배정 대상 학생 id 리스트.

    반환:
        (won, refunded, random_assigned)
        won             -- {seat_id: (student_id, bid_id)} 입찰로 낙찰된 좌석
        refunded        -- 환급할 bid_id 리스트
        random_assigned -- {seat_id: student_id} 무작위로 배정된 좌석
    """
    won = {}
    refunded = []
    seated_students = set()

    for bid_id, seat_id, student_id in bids:
        # 좌석이 이미 팔렸거나, 그 학생이 이미 다른 좌석을 낙찰했으면 환급.
        if seat_id in won or student_id in seated_students:
            refunded.append(bid_id)
            continue
        won[seat_id] = (student_id, bid_id)
        seated_students.add(student_id)

    # 남은 좌석을 섞어서, 아직 자리가 없는 학생에게 하나씩 배정한다.
    # 예전 while/pop/continue 구조는 낙찰자를 pop으로 소진해버려 학생이
    # 남았는데도 좌석이 비는 버그가 있었다.
    leftover_seats = [s for s in seats if s not in won]
    waiting = [s for s in students if s not in seated_students]
    rng.shuffle(leftover_seats)
    rng.shuffle(waiting)

    random_assigned = {}
    for seat_id, student_id in zip(leftover_seats, waiting):
        random_assigned[seat_id] = student_id

    return won, refunded, random_assigned


@transaction.atomic
def close_room(room, *, rng=random):
    """교실을 마감해 좌석 주인을 확정한다."""
    room = Room.objects.select_for_update().get(pk=room.pk)
    if room.status != Room.OPEN:
        raise DomainError("이미 마감된 교실입니다.")

    seat_ids = list(room.seat_set.values_list("id", flat=True))
    bids = list(
        active_bids(seat_ids)
        .order_by("-point", "created_date")
        .values_list("id", "obj_id", "log_student_id")
    )
    student_ids = list(
        Student.objects.filter(status=Student.ATTENDING).values_list("id", flat=True)
    )

    won, refunded, random_assigned = allocate(bids, seat_ids, student_ids, rng=rng)

    for bid_id in refunded:
        cancel_bid(
            Log.objects.get(pk=bid_id),
            refund_reason="다른 좌석에 낙찰되어 이 입찰은 자동 취소됨.",
        )

    owners = {seat_id: student for seat_id, (student, _) in won.items()}
    owners.update(random_assigned)

    for seat in Seat.objects.select_for_update().filter(id__in=list(owners)):
        seat.owner_id = owners[seat.id]
        seat.status = Seat.TAKEN
        seat.save(update_fields=["owner", "status", "modified_date"])

    room.status = Room.CLOSED
    room.save(update_fields=["status", "modified_date"])
    return room


@transaction.atomic
def open_room(*, row, minimum, seat_count, notice=""):
    """새 교실을 연다. 이미 열린 교실이 있으면 거부한다."""
    if get_open_room() is not None:
        raise DomainError("이미 열려 있는 교실이 있습니다. 먼저 마감해 주세요.")

    room = Room.objects.create(row=row, minimum=minimum, notice=notice)
    Seat.objects.bulk_create(
        [Seat(room=room, num=i + 1) for i in range(seat_count)]
    )
    return room


def bid_counts_by_student(room):
    """마감 확인 화면용. (학생, 살아 있는 입찰 수) 리스트를 한 번의 쿼리로 만든다."""
    seat_ids = list(room.seat_set.values_list("id", flat=True))
    counts = {}
    for student_id in active_bids(seat_ids).values_list("log_student_id", flat=True):
        counts[student_id] = counts.get(student_id, 0) + 1
    students = Student.objects.filter(status=Student.ATTENDING).order_by("name")
    return [(student, counts.get(student.id, 0)) for student in students]


def create_student_accounts(count, *, password_factory=None):
    """학생 계정을 일괄 생성하고 [(student, 평문 비밀번호)]를 돌려준다.

    비밀번호는 `secrets`로 만든 난수다. 예전 코드처럼 `123123`을 하드코딩하면
    학번만 알면 아무나 남의 계정으로 로그인할 수 있다.
    """
    if password_factory is None:
        password_factory = _random_password

    created = []
    with transaction.atomic():
        offset = User.objects.count()
        for i in range(count):
            username = _unique_username(User, offset + i + 1)
            password = password_factory()
            user = User.objects.create_user(
                username,
                email=f"{username}@school.com",
                password=password,
                first_name="Student",
            )
            student = Student.objects.create(user=user, name=username)
            created.append((student, password))
    return created


def _unique_username(user_model, seed):
    """student{n} 이 이미 있으면 비어 있는 번호를 찾는다.

    예전 코드는 `User.objects.count()`만 보고 이름을 만들어서, 계정을 하나
    지웠다가 다시 만들면 기존 username과 충돌해 IntegrityError가 났다.
    """
    n = seed
    while user_model.objects.filter(username=f"student{n}").exists():
        n += 1
    return f"student{n}"


def _random_password():
    """초기 비밀번호. `random`이 아니라 `secrets`를 써야 예측할 수 없다."""
    return f"{secrets.randbelow(10 ** 8):08d}"

import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.shortcuts import resolve_url


class TimeStamped(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Student(TimeStamped):
    ATTENDING = "a"  # 재학
    BREAK = "b"  # 휴학
    DROPOUT = "d"  # 자퇴
    KICKED = "k"  # 퇴학
    STATUS = (
        (ATTENDING, "재학"),
        (BREAK, "휴학"),
        (DROPOUT, "자퇴"),
        (KICKED, "퇴학"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=32)
    point = models.IntegerField(default=100)
    status = models.CharField(
        max_length=1, choices=STATUS, blank=True, default=ATTENDING
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            # 포인트가 음수로 내려가는 것을 DB에서 막는다. 애플리케이션 검증을
            # 빠뜨리더라도 잘못된 데이터가 저장되지 않게 하는 마지막 방어선.
            models.CheckConstraint(
                check=Q(point__gte=0), name="student_point_not_negative"
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        # template에서는 {%%}가 아니라 {{ }}로 호출해야 한다.
        return resolve_url("student_detail", self.id)


class Log(TimeStamped):
    USE = "u"  # 사용(입찰)
    CANCEL = "c"  # 취소
    TEACHER = "t"  # 선생님 지급/차감
    STATUS = (
        (USE, "사용"),
        (CANCEL, "취소"),
        (TEACHER, "선생님"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=1, choices=STATUS, default=TEACHER)
    obj_name = models.CharField(max_length=32)
    obj_id = models.IntegerField(null=True)
    log_student = models.ForeignKey(Student, on_delete=models.CASCADE)
    point = models.IntegerField()
    canceled = models.BooleanField(default=False)  # 'u'의 경우 True로 바뀔 수 있음
    cancel_log = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True
    )  # 'c'의 경우
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["created_date"]
        indexes = [
            # 좌석별 입찰 조회가 가장 잦은 쿼리다.
            models.Index(fields=["obj_name", "obj_id", "canceled"]),
            models.Index(fields=["log_student", "-created_date"]),
        ]
        constraints = [
            # 한 학생이 같은 좌석에 살아 있는 입찰을 두 개 가질 수 없다.
            models.UniqueConstraint(
                fields=["obj_name", "obj_id", "log_student"],
                condition=Q(canceled=False, status="u"),
                name="one_active_bid_per_seat_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.log_student} {self.point:+d}"

    @property
    def is_bid(self):
        return self.status == self.USE and self.obj_name == "seat"


class Room(TimeStamped):
    OPEN = "a"  # 가능
    CLOSED = "u"  # 불가능
    STATUS = ((OPEN, "가능"), (CLOSED, "불가능"))

    notice = models.TextField(blank=True)
    row = models.PositiveIntegerField()
    minimum = models.PositiveIntegerField(null=True, blank=True, default=1)
    status = models.CharField(max_length=1, choices=STATUS, blank=True, default=OPEN)

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return f"{self.created_date:%Y-%m-%d} 교실"

    def get_absolute_url(self):
        return resolve_url("room_detail", self.id)

    @property
    def is_open(self):
        return self.status == self.OPEN

    def grid(self):
        """좌석을 한 줄에 `row`개씩 끊어 담은 2차원 리스트.

        예전에는 이 계산이 RoomDetailView와 room_now에 그대로 복사돼 있었고,
        `False`/`'empty'` 같은 센티널 값을 한 리스트에 섞어 쓰고 있었다.
        템플릿에서 중첩 for로 순회하면 훨씬 읽기 쉽다.
        """
        seats = list(self.seat_set.order_by("num"))
        rows = [seats[i : i + self.row] for i in range(0, len(seats), self.row)]
        if rows:
            # 마지막 줄의 빈 칸을 None으로 채워 격자 모양을 유지한다.
            rows[-1] += [None] * (self.row - len(rows[-1]))
        return rows


class Seat(TimeStamped):
    OPEN = "a"  # 가능
    TAKEN = "u"  # 불가능
    STATUS = ((OPEN, "가능"), (TAKEN, "불가능"))

    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    num = models.PositiveIntegerField()
    status = models.CharField(max_length=1, choices=STATUS, blank=True, default=OPEN)
    owner = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["num"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "num"], name="unique_seat_num_per_room"
            ),
        ]

    def __str__(self):
        return f"{self.num}번 자리"

    def get_absolute_url(self):
        return resolve_url("seat_detail", self.id)

    @property
    def is_biddable(self):
        return self.status == self.OPEN and self.owner_id is None


class Preset(TimeStamped):
    name = models.CharField(max_length=32)
    point = models.IntegerField()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.point:+d})"


class Charge(TimeStamped):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    reason = models.TextField()
    submit = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_date"]

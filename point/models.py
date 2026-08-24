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


class Bid(TimeStamped):
    """좌석 입찰.

    예전에는 `Log(status='u', obj_name='seat', obj_id=<좌석 id>)`로 표현했다.
    `obj_id`는 그냥 IntegerField였기 때문에

      * 좌석을 지워도 로그가 존재하지 않는 좌석을 계속 가리켰고 (FK 제약 없음),
      * 조회할 때마다 `obj_name='seat'`을 문자열로 맞춰야 했고,
      * `seat.bids` 같은 역참조를 쓸 수 없어 N+1 쿼리가 나기 쉬웠다.

    실제 ForeignKey를 쓰면 이 세 문제가 모두 사라진다.
    """

    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name="bids")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="bids")
    point = models.PositiveIntegerField()
    canceled = models.BooleanField(default=False)
    won = models.BooleanField(default=False)  # 마감 시 낙찰됐는지

    class Meta:
        # 낙찰 우선순위: 높은 포인트 우선, 같으면 먼저 낸 쪽 우선.
        # 경매 규칙을 모델에 박아두면 정렬을 빠뜨린 쿼리가 조용히 틀리지 않는다.
        ordering = ["-point", "created_date"]
        indexes = [
            models.Index(fields=["seat", "canceled"]),
            models.Index(fields=["student", "-created_date"]),
        ]
        constraints = [
            # 한 학생이 같은 좌석에 살아 있는 입찰을 두 개 가질 수 없다.
            models.UniqueConstraint(
                fields=["seat", "student"],
                condition=Q(canceled=False),
                name="unique_active_bid_per_seat_student",
            ),
            models.CheckConstraint(check=Q(point__gte=1), name="bid_point_positive"),
        ]

    def __str__(self):
        return f"{self.student} → {self.seat} ({self.point}p)"


class PointLog(TimeStamped):
    """포인트 원장(ledger). 모든 포인트 이동을 부호 있는 금액으로 남긴다.

    예전 Log는 `point`가 항상 양수여서 지급인지 차감인지 알려면 `status`와
    `obj_name`을 조합해 추측해야 했다. `amount`에 부호를 넣으면 한 학생의
    이력을 그냥 더해서 잔액을 검산할 수 있다 — `sum(amount) == student.point`.
    이 항등식은 테스트로 검증한다.
    """

    INITIAL = "i"  # 최초 지급분
    BID = "b"  # 입찰로 차감
    REFUND = "r"  # 입찰 취소로 환급
    TEACHER = "t"  # 선생님 지급/차감
    KIND = (
        (INITIAL, "최초"),
        (BID, "입찰"),
        (REFUND, "환급"),
        (TEACHER, "선생님"),
    )

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="point_logs"
    )
    kind = models.CharField(max_length=1, choices=KIND, default=TEACHER)
    amount = models.IntegerField(help_text="지급은 양수, 차감은 음수")
    # 좌석이 지워져도 원장은 남아야 하므로 SET_NULL. 원장이 사라지면
    # 학생 잔액을 설명할 수 없게 된다.
    bid = models.ForeignKey(
        Bid, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger"
    )
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_date"]
        indexes = [
            models.Index(fields=["student", "-created_date"]),
        ]

    def __str__(self):
        return f"{self.student} {self.amount:+d}"

    @property
    def is_refundable_bid(self):
        """이 기록이 아직 취소할 수 있는 입찰인지."""
        return self.kind == self.BID and self.bid is not None and not self.bid.canceled


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

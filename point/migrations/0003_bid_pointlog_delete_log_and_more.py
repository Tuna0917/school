"""Log(수동 다형성) -> Bid + PointLog(실제 FK + 부호 있는 원장) 전환.

makemigrations가 만들어준 원본은 `DeleteModel('Log')`만 있어서 기존 입찰
이력이 전부 사라졌다. 아래 `forwards`가 그 데이터를 새 표로 옮긴 *뒤에*
Log를 지운다.

되돌리기(reverse)는 일부러 막아뒀다. Log는 obj_name/obj_id로 여러 종류의
기록을 한 표에 섞어두었기 때문에, 새 구조에서 예전 구조로 무손실 복원할 수
없다. 잘못 되돌려 이력을 잃는 대신 명시적으로 실패시킨다.
"""

import django.db.models.deletion
from django.db import migrations, models


def _restore_timestamps(model, stamps):
    """auto_now_add가 덮어쓴 created_date를 원래 값으로 되돌린다.

    `auto_now_add=True`는 INSERT 때 항상 현재 시각을 넣기 때문에 create()로는
    과거 시각을 보존할 수 없다. queryset.update()는 auto_now를 거치지 않는다.

    입찰 이력에서 시각은 장식이 아니다. Bid의 낙찰 우선순위가
    `-point, created_date`(동점이면 먼저 낸 쪽 우선)이므로, 전부 마이그레이션
    시각으로 뭉개지면 동점 입찰의 승자가 뒤바뀐다.
    """
    for pk, created in stamps:
        model.objects.filter(pk=pk).update(created_date=created)


def forwards(apps, schema_editor):
    Log = apps.get_model("point", "Log")
    Bid = apps.get_model("point", "Bid")
    PointLog = apps.get_model("point", "PointLog")
    Seat = apps.get_model("point", "Seat")
    Student = apps.get_model("point", "Student")

    seats = dict(Seat.objects.values_list("id", "owner_id"))
    bid_by_log = {}
    bid_stamps = []
    log_stamps = []

    # 1) 입찰 기록 -> Bid + 차감 원장.
    for log in Log.objects.filter(status="u", obj_name="seat").order_by("created_date"):
        bid = None
        # obj_id는 FK가 아니었으므로 이미 삭제된 좌석을 가리킬 수 있다.
        # 그런 입찰은 Bid로 만들 수 없지만, 포인트는 실제로 차감됐으므로
        # 원장에는 남겨야 잔액이 설명된다.
        if log.obj_id in seats and log.point >= 1:
            bid = Bid.objects.create(
                seat_id=log.obj_id,
                student_id=log.log_student_id,
                point=log.point,
                canceled=log.canceled,
                # 마감 후라면 그 좌석의 주인이 곧 낙찰자다.
                won=(not log.canceled and seats[log.obj_id] == log.log_student_id),
            )
            bid_by_log[log.id] = bid
            bid_stamps.append((bid.pk, log.created_date))

        entry = PointLog.objects.create(
            student_id=log.log_student_id,
            kind="b",
            amount=-log.point,  # 예전 Log.point는 차감액을 양수로 저장했다
            bid=bid,
            reason=log.reason
            or ("입찰함." if bid else "입찰함. (좌석이 삭제되어 연결 없음)"),
        )
        log_stamps.append((entry.pk, log.created_date))

    # 2) 환급 기록 -> 환급 원장. 예전에는 cancel_log로 원본 입찰을 가리켰다.
    for log in Log.objects.exclude(cancel_log=None).order_by("created_date"):
        entry = PointLog.objects.create(
            student_id=log.log_student_id,
            kind="r",
            amount=abs(log.point),  # 환급은 항상 양수
            bid=bid_by_log.get(log.cancel_log_id),
            reason=log.reason or "입찰 취소로 포인트를 돌려받음.",
        )
        log_stamps.append((entry.pk, log.created_date))

    # 3) 나머지(선생님 지급/차감) -> 선생님 원장. point가 이미 부호를 갖고 있다.
    others = Log.objects.exclude(status="u", obj_name="seat").filter(cancel_log=None)
    for log in others.order_by("created_date"):
        entry = PointLog.objects.create(
            student_id=log.log_student_id,
            kind="t",
            amount=log.point,
            reason=log.reason,
        )
        log_stamps.append((entry.pk, log.created_date))

    _restore_timestamps(Bid, bid_stamps)
    _restore_timestamps(PointLog, log_stamps)

    # 4) 원장 합계가 현재 잔액과 맞도록 '최초 지급' 항목을 채운다.
    #    Student.point는 기본값 100으로 시작했고 그에 대응하는 기록이 없었다.
    #    이 보정이 없으면 `sum(amount) == point` 항등식이 성립하지 않아
    #    원장을 검산에 쓸 수 없다.
    for student in Student.objects.all():
        total = sum(
            PointLog.objects.filter(student=student).values_list("amount", flat=True)
        )
        gap = student.point - total
        if gap:
            entry = PointLog.objects.create(
                student=student,
                kind="i",
                amount=gap,
                reason="최초 지급분 (이력 전환 시 잔액 보정).",
            )
            PointLog.objects.filter(pk=entry.pk).update(
                created_date=student.created_date
            )


def backwards(apps, schema_editor):
    raise RuntimeError(
        "이 마이그레이션은 되돌릴 수 없습니다. 예전 Log는 여러 종류의 기록을 "
        "obj_name/obj_id로 한 표에 섞어 저장했기 때문에 무손실 복원이 "
        "불가능합니다. 되돌려야 한다면 DB 백업에서 복구하세요."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("point", "0002_alter_charge_options_alter_preset_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Bid",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_date", models.DateTimeField(auto_now_add=True)),
                ("modified_date", models.DateTimeField(auto_now=True)),
                ("point", models.PositiveIntegerField()),
                ("canceled", models.BooleanField(default=False)),
                ("won", models.BooleanField(default=False)),
                (
                    "seat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bids",
                        to="point.seat",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bids",
                        to="point.student",
                    ),
                ),
            ],
            options={
                "ordering": ["-point", "created_date"],
            },
        ),
        migrations.CreateModel(
            name="PointLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_date", models.DateTimeField(auto_now_add=True)),
                ("modified_date", models.DateTimeField(auto_now=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("i", "최초"),
                            ("b", "입찰"),
                            ("r", "환급"),
                            ("t", "선생님"),
                        ],
                        default="t",
                        max_length=1,
                    ),
                ),
                ("amount", models.IntegerField(help_text="지급은 양수, 차감은 음수")),
                ("reason", models.TextField(blank=True)),
                (
                    "bid",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ledger",
                        to="point.bid",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="point_logs",
                        to="point.student",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_date"],
            },
        ),
        migrations.AddIndex(
            model_name="bid",
            index=models.Index(
                fields=["seat", "canceled"], name="point_bid_seat_id_942a7f_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="bid",
            index=models.Index(
                fields=["student", "-created_date"], name="point_bid_student_c1d193_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="bid",
            constraint=models.UniqueConstraint(
                condition=models.Q(("canceled", False)),
                fields=("seat", "student"),
                name="unique_active_bid_per_seat_student",
            ),
        ),
        migrations.AddConstraint(
            model_name="bid",
            constraint=models.CheckConstraint(
                condition=models.Q(("point__gte", 1)), name="bid_point_positive"
            ),
        ),
        migrations.AddIndex(
            model_name="pointlog",
            index=models.Index(
                fields=["student", "-created_date"],
                name="point_point_student_5deea7_idx",
            ),
        ),
        # 데이터를 옮긴 뒤에 Log를 지운다. 제약이 이미 걸린 상태에서 넣으므로
        # 옮기는 데이터가 규칙을 위반하면 조용히 넘어가지 않고 실패한다.
        migrations.RunPython(forwards, backwards),
        migrations.DeleteModel(
            name="Log",
        ),
    ]

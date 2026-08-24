from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from . import services
from .forms import (
    BidForm,
    PointChangeForm,
    RoomCreateForm,
    StudentBulkCreateForm,
    StudentForm,
)
from .mixins import (
    LoggedInMixin,
    OwnerOrStaffMixin,
    StaffRequiredMixin,
    handle_domain_error,
    is_staff,
    staff_required,
    student_of,
    student_required,
)
from .models import Log, Preset, Room, Seat, Student

# ---------------------------------------------------------------- 학생


class StudentListView(StaffRequiredMixin, ListView):
    model = Student
    paginate_by = 20

    def get_queryset(self):
        # select_related로 N+1 쿼리를 없앤다.
        return Student.objects.select_related("user")


class StudentDetailView(OwnerOrStaffMixin, DetailView):
    model = Student

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = context["object"]
        context["logs"] = Log.objects.filter(log_student=student).order_by(
            "-created_date"
        )[:100]
        context["presets"] = Preset.objects.all()
        context["point_form"] = PointChangeForm()
        return context


class StudentUpdateView(OwnerOrStaffMixin, UpdateView):
    model = Student
    form_class = StudentForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # 상태(재학/휴학/자퇴) 변경은 선생님만.
        kwargs["allow_status"] = is_staff(self.request.user)
        return kwargs

    def get_success_url(self):
        return reverse("student_detail", kwargs={"pk": self.object.id})


@staff_required
@handle_domain_error(lambda request, pk: resolve_url("student_detail", pk))
def point_change(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method != "POST":
        return redirect(student.get_absolute_url())

    form = PointChangeForm(request.POST)
    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, error.as_text())
        return redirect(student.get_absolute_url())

    services.adjust_point(
        student,
        form.cleaned_data["point"],
        reason=form.cleaned_data["reason"],
        obj_name="teacher",
    )
    messages.success(request, f"{student.name}의 포인트를 변경했습니다.")
    return redirect(student.get_absolute_url())


@staff_required
def create_students(request):
    if request.method == "POST":
        form = StudentBulkCreateForm(request.POST)
        if form.is_valid():
            created = services.create_student_accounts(form.cleaned_data["number"])
            # 아이디를 추측해서 보여주면 안 된다. 실제 username을 그대로 넘긴다.
            return render(
                request,
                "student_create_complete.html",
                {
                    "passwords": [
                        (s.user.username, pw, s.get_absolute_url())
                        for s, pw in created
                    ]
                },
            )
    else:
        form = StudentBulkCreateForm()
    return render(request, "student_create.html", {"form": form})


# ---------------------------------------------------------------- 교실 / 좌석


class RoomListView(StaffRequiredMixin, ListView):
    model = Room


class RoomDetailView(LoggedInMixin, DetailView):
    model = Room

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rows"] = context["object"].grid()
        return context


class RoomUpdateView(StaffRequiredMixin, UpdateView):
    model = Room
    fields = ["notice", "row", "minimum"]


class SeatDetailView(LoggedInMixin, DetailView):
    model = Seat

    def get_queryset(self):
        return Seat.objects.select_related("room", "owner")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        seat = context["object"]
        student = student_of(self.request.user)
        room_closed = not seat.room.is_open

        if is_staff(self.request.user) or room_closed:
            # 선생님은 항상, 학생은 마감 후에만 전체 입찰 내역을 본다.
            context["logs"] = services.active_bids([seat.id]).select_related(
                "log_student"
            )
        else:
            context["logs"] = []

        context["log"] = (
            services.bid_of(student, seat) if student is not None else None
        )
        if student is not None and context["log"] is None and seat.is_biddable:
            context["bid_form"] = BidForm(student=student, room=seat.room)
        return context


@student_required
@handle_domain_error(lambda request, pk: resolve_url("seat_detail", pk))
def auction(request, pk):
    seat = get_object_or_404(Seat.objects.select_related("room"), pk=pk)
    if request.method != "POST":
        return redirect(seat.get_absolute_url())

    student = student_of(request.user)
    form = BidForm(request.POST, student=student, room=seat.room)
    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, error.as_text())
        return redirect(seat.get_absolute_url())

    services.place_bid(student, seat, form.cleaned_data["point"])
    messages.success(request, f"{seat.num}번 좌석에 입찰했습니다.")
    return redirect("room_now")


@login_required
@handle_domain_error("room_now")
def cancel(request, pk):
    log = get_object_or_404(Log.objects.select_related("log_student"), pk=pk)
    student = student_of(request.user)

    # 선생님이거나 본인의 입찰일 때만 취소 가능.
    if not (is_staff(request.user) or log.log_student == student):
        messages.error(request, "본인의 입찰만 취소할 수 있습니다.")
        return redirect("room_now")
    if not log.is_bid:
        messages.error(request, "입찰 기록만 취소할 수 있습니다.")
        return redirect("room_now")

    services.cancel_bid(log)
    messages.success(request, "입찰을 취소하고 포인트를 돌려받았습니다.")
    return redirect(request.GET.get("next") or "room_now")


@staff_required
@handle_domain_error("room_now")
def create_room(request):
    if services.get_open_room() is not None:
        messages.error(request, "이미 열려 있는 교실이 있습니다. 먼저 마감해 주세요.")
        return redirect("room_now")

    if request.method == "POST":
        form = RoomCreateForm(request.POST)
        if form.is_valid():
            room = services.open_room(
                row=form.cleaned_data["row"],
                minimum=form.cleaned_data["minimum"],
                seat_count=form.cleaned_data["num"],
                notice=form.cleaned_data["notice"],
            )
            messages.success(request, "새 교실을 열었습니다.")
            return redirect("room_detail", pk=room.id)
    else:
        form = RoomCreateForm()
    return render(request, "room_create.html", {"form": form})


@staff_required
@handle_domain_error("room_now")
def close_confirm(request):
    room = services.require_open_room()
    return render(
        request,
        "close_confirm.html",
        {"object_list": services.bid_counts_by_student(room), "room": room},
    )


@staff_required
@handle_domain_error("room_now")
def close_room(request):
    # 마감은 상태를 바꾸는 동작이므로 GET으로 실행되면 안 된다.
    if request.method != "POST":
        return redirect("close_confirm")
    room = services.require_open_room()
    services.close_room(room)
    messages.success(request, "자리 배정을 마감했습니다.")
    return redirect("room_detail", pk=room.id)


@handle_domain_error("home")
def room_now(request):
    """가장 최근 교실 화면. 로그인한 사람만 볼 수 있다."""
    if not request.user.is_authenticated:
        return redirect("login")

    room = Room.objects.order_by("-created_date").first()
    if room is None:
        if is_staff(request.user):
            return redirect("create_room")
        messages.info(request, "아직 열린 교실이 없습니다.")
        return render(request, "home.html")

    return render(
        request,
        "point/room_detail.html",
        {"object": room, "rows": room.grid()},
    )


# ---------------------------------------------------------------- 프리셋 (선생님 전용)


class PresetListView(StaffRequiredMixin, ListView):
    model = Preset


class PresetDetailView(StaffRequiredMixin, DetailView):
    model = Preset


class PresetCreateView(StaffRequiredMixin, CreateView):
    model = Preset
    fields = ["name", "point"]

    def get_success_url(self):
        return resolve_url("preset_list")


class PresetUpdateView(StaffRequiredMixin, UpdateView):
    model = Preset
    fields = ["name", "point"]

    def get_success_url(self):
        return resolve_url("preset_list")


class PresetDeleteView(StaffRequiredMixin, DeleteView):
    model = Preset

    def get_success_url(self):
        return resolve_url("preset_list")

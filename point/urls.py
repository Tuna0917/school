from django import urls
from django.urls import path
from .views import *


urlpatterns = [
    path("", room_now, name="home"),
    # path('', HomeTemplateView.as_view(), name='home'),
    path("student/view", checkbox_test, name="test"),
    path("tptp", checkbox_point, name="tptp"),
    path("ccc", changer, name="ccc"),
]

# 학생 관련
urlpatterns += [
    path("students", login_required(StudentListView.as_view()), name="student_list"),
    path(
        "student/<int:pk>",
        login_required(StudentDetailView.as_view()),
        name="student_detail",
    ),
    path("student/<int:pk>/update", StudentUpdateView.as_view(), name="student_update"),
    path("student/<int:pk>/point", point_change, name="point_change"),
    path(
        "student/<int:student_id>/preset/<int:preset_id>",
        point_preset,
        name="point_preset",
    ),
    path("students/create", create_students, name="create_students"),
    path("log/<uuid:pk>/cancel", cancel, name="cancel"),
]

# 교실 관련
urlpatterns += [
    path("room", room_now, name="room_now"),
    path("rooms", RoomListView.as_view(), name="room_list"),
    path("room/<int:pk>", RoomDetailView.as_view(), name="room_detail"),
    # path('room/create', RoomCreateView.as_view(), name='room_create'),
    path("room/create", create_room, name="create_room"),
    path("room/confirm/close", close_room, name="close_room"),
    path("room/confirm", close_confirm, name="close_confirm"),
    path("room/<int:pk>/update", RoomUpdateView.as_view(), name="room_update"),
    path("seat/<int:pk>", SeatDetailView.as_view(), name="seat_detail"),
    path(
        "seat/<int:pk>/ban_update",
        SeatBanlistUpdateView.as_view(),
        name="seat_ban_update",
    ),
    path(
        "seat/<int:pk>/owner_update",
        SeatOwnerUpdateView.as_view(),
        name="seat_owner_update",
    ),
    path("seat/<int:pk>/status_update", change_status, name="seat_status_update"),
    path("seat/<int:pk>/auction", auction, name="auction"),
    path("seat/<int:pk>/owner_delete", owner_delete, name="seat_owner_delete"),
]

# 선생님 관련
urlpatterns += [
    path("presets", PresetListView.as_view(), name="preset_list"),
    path("preset/create", PresetCreateView.as_view(), name="preset_create"),
    path("preset/<int:pk>", PresetDetailView.as_view(), name="preset_detail"),
    path("preset/<int:pk>/update", PresetUpdateView.as_view(), name="preset_update"),
    path("preset/<int:pk>/delete", PresetDeleteView.as_view(), name="preset_delete"),
    # path('charges', ChargeListView.as_view(), name='charge_list'),
]

# Archive
urlpatterns += [
    path("archive/", LogArchiveView.as_view(), name="log_archive"),
    path("archive/<int:year>/", LogYearArchiveView.as_view(), name="log_year_archive"),
    path(
        "archive/<int:year>/<str:month>/",
        LogMonthArchiveView.as_view(),
        name="log_month_archive",
    ),
    path(
        "archive/<int:year>/<str:month>/<int:day>/",
        LogDayArchiveView.as_view(),
        name="log_day_archive",
    ),
    path("archive/today/", LogTodayArchiveView.as_view(), name="log_today_archive"),
]

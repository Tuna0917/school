from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
]

# 학생 관련
urlpatterns += [
    path("students", views.StudentListView.as_view(), name="student_list"),
    path("student/<int:pk>", views.StudentDetailView.as_view(), name="student_detail"),
    path(
        "student/<int:pk>/update",
        views.StudentUpdateView.as_view(),
        name="student_update",
    ),
    path("student/<int:pk>/point", views.point_change, name="point_change"),
    path("students/create", views.create_students, name="create_students"),
    # Bid의 PK는 정수다(예전 Log는 UUID였다).
    # 예전 'cancle' 오타 경로도 유지해 기존 링크가 깨지지 않게 한다.
    path("bid/<int:pk>/cancel", views.cancel, name="cancel"),
    path("bid/<int:pk>/cancle", views.cancel, name="cancel_legacy"),
]

# 교실 관련
urlpatterns += [
    path("room", views.room_now, name="room_now"),
    path("rooms", views.RoomListView.as_view(), name="room_list"),
    path("room/<int:pk>", views.RoomDetailView.as_view(), name="room_detail"),
    path("room/create", views.create_room, name="create_room"),
    path("room/confirm", views.close_confirm, name="close_confirm"),
    path("room/confirm/close", views.close_room, name="close_room"),
    path("room/<int:pk>/update", views.RoomUpdateView.as_view(), name="room_update"),
    path("seat/<int:pk>", views.SeatDetailView.as_view(), name="seat_detail"),
    path("seat/<int:pk>/auction", views.auction, name="auction"),
]

# 선생님 관련
urlpatterns += [
    path("presets", views.PresetListView.as_view(), name="preset_list"),
    path("preset/create", views.PresetCreateView.as_view(), name="preset_create"),
    path("preset/<int:pk>", views.PresetDetailView.as_view(), name="preset_detail"),
    path(
        "preset/<int:pk>/update",
        views.PresetUpdateView.as_view(),
        name="preset_update",
    ),
    path(
        "preset/<int:pk>/delete",
        views.PresetDeleteView.as_view(),
        name="preset_delete",
    ),
]

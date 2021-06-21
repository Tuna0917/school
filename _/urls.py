from django import urls
from django.urls import path
from .views import *

app_name= 'school'

urlpatterns = []

#학생 관련
urlpatterns += [
    path('students', StudentListView.as_view(), name='student_list'),
    path('student/<int:pk>', StudentDetailView.as_view(), name='student_detail'),
    path('student/<int:pk>/update', StudentUpdateView.as_view(), name='student_update'),
]

#교실 관련
urlpatterns += [
    path('rooms', RoomListView.as_view(), name='room_list'),
    path('room/<int:pk>', RoomDetailView.as_view(), name='room_detail'),
    path('room/create', RoomCreateView.as_view(), name='room_create'),
    path('room/<int:pk>/update', RoomUpdateView.as_view(), name='room_update'),
    path('seat/<int:pk>', SeatDetailView.as_view(), name='seat_detail'),
]

#선생님 관련
urlpatterns += [
    path('presets', PresetListView.as_view(), name='preset_list'),
    path('preset/<int:pk>', PresetCreateView.as_view(), name='preset_create'),
    path('preset/<int:pk>/update', PresetUpdateView.as_view(), name='preset_update'),
    path('preset/<int:pk>/delete', PresetDeleteView.as_view(), name='preset_delete'),

    path('charges', ChargeListView.as_view(), name='charge_list'),
]
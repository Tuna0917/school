from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('create/students', create_students, name='create_students'),
    path('create/room', create_room, name='create_room'),
    path('close', close_room, name='close_room'),
    path('auction/<int:pk>', auction, name='auction'),
    path('auction/<int:pk>/cancel', auction_cancel, name='auction_cancel'),
    path('seat/<int:pk>', SeatDetailView.as_view(), name='seat'),
    path('seat/<int:pk>/finished', FinshedSeatDetailView.as_view(), name='seat_end'),
    path('students/', StudentListView.as_view(), name='students'),
    path('student/<int:pk>', StudentDetailView.as_view(), name='student_detail'),
    path('student/<int:pk>/update/', StudentUpdateView.as_view(), name='student_update'),
    path('student/<int:pk>/change/', point_change, name='point_change')
]

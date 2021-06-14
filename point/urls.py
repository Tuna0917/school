from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('create/', student_signup, name='signup'),
    path('auction/<int:pk>', auction, name='auction'),
    path('seat/<int:pk>', SeatDetailView.as_view(), name='seat'),
    path('students/', StudentListView.as_view(), name='students'),
    path('student/<int:pk>', StudentDetailView.as_view(), name='student_detail'),
    path('student/<int:pk>/update/', StudentUpdateView.as_view(), name='student_update')
]

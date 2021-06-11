from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('create/', student_signup, name='signup'),
    path('auction/<int:pk>', auction, name='auction'),
]

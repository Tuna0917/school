from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.contrib.auth.models import User
# Create your models here.

class Student(models.Model):
    STATUS = (
        ('a', '재학'), #Attending
        ('b', '휴학'), #Break
        ('d', '자퇴'), #Dropout
        ('k', '퇴학') #Kicked
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=32) #이름
    point = models.IntegerField(default=0,validators=[MinValueValidator(0),])
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        blank=True,
        default='a'
    )

    def __str__(self):
        return self.name



class Seat(models.Model):
    pass

class SeatLog(models.Model):
    date = models.DateTimeField(auto_now_add=True) #언제
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING) #누가
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE) #어떤 좌석을
    points = models.IntegerField(validators=[MinValueValidator(0),]) #얼마에
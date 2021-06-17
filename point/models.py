from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.shortcuts import redirect
from django.shortcuts import resolve_url
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
    point = models.IntegerField(default=100,validators=[MinValueValidator(0),])
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        blank=True,
        default='a'
    )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        '''
        template에서 get_absolute_url을 쓸 때는 제발 {%%}말고 {{}}
        잊지말자...
        '''
        return resolve_url('student_detail', self.id)

class Room(models.Model):
    STATUS = (
        ('a', '가능'),
        ('u', '불가능')
    )
    row = models.IntegerField()
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        blank=True,
        default='a'
    )

class Seat(models.Model):
    STATUS = (
        ('a', '가능'),
        ('u', '불가능')
    )
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    num = models.IntegerField()
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        blank=True,
        default='a'
    )
    owner = models.IntegerField(null=True)
    def __str__(self):
        return f"좌석 (id: {self.id})"

class Log(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    log_concept_id = models.IntegerField(default=0) #0이면 선생님이 직접 올리고 내린거.
    log_student_id = models.IntegerField()
    point = models.IntegerField()  
    activated = models.BooleanField(default=True)
    reason = models.TextField(blank=True)


class Concept(models.Model): #이름이 직관성 바닥인데. 뭐로 바꾸지?
    concept_id = models.IntegerField(primary_key=True)
    concept_name = models.CharField(max_length = 32) #obj의 모델 명이랑 같게.
    obj_id = models.IntegerField() #obj의 pk
    #concept_name이랑 obj_id는 같으면서 concept_id가 다른 애는 생길 수 없음.

    def __str__(self) -> str:
        return f'{self.concept_name}'

class SeatResult(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    room_id = models.IntegerField()
    seat_num = models.IntegerField()
    student_id = models.IntegerField()

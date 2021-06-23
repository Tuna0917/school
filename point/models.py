from django.db import models
from django.db.models.fields.related import ForeignKey
from django.shortcuts import resolve_url
from django.contrib.auth.models import User
import uuid
# Create your models here.
class Student(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    STATUS = (
        ('a', '재학'), #Attending
        ('b', '휴학'), #Break
        ('d', '자퇴'), #Dropout
        ('k', '퇴학') #Kicked
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=32) #이름
    point = models.IntegerField(default=100,)
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        blank=True,
        default='a'
    )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        
        return resolve_url('student_detail', self.id)
        '''
        template에서 get_absolute_url을 쓸 때는 제발 {%%}말고 {{}} 쓰기
        잊지말자...
        '''
class Log(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    STATUS = (
        ('u', '사용'),
        ('c', '취소'),
        ('t', '선생님')
    )
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    status = models.CharField( 
        max_length=1,
        choices=STATUS,
        default='t'
    )
    obj_name = models.CharField(max_length=32)
    obj_id = models.IntegerField(null=True)
    log_student = models.ForeignKey(Student, on_delete=models.CASCADE)
    point = models.IntegerField()  
    canceled = models.BooleanField(default=False) #'u'의 경우 이게 T로 바뀔 수 있음.
    cancel_log = models.ForeignKey('self', on_delete=models.CASCADE, null=True) # 'c'의 경우
    reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['created_date']
    


class Room(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    STATUS = (
        ('a', '가능'),
        ('u', '불가능')
    )
    notice = models.TextField(blank=True)
    row = models.IntegerField()
    minimum = models.IntegerField(null=True)
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        blank=True,
        default='a'
    )
    def get_absolute_url(self):
        return resolve_url('room_detail', self.id)


class Seat(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
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
    owner = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.num}번 자리"

    def get_absolute_url(self):
        return resolve_url('seat_detail', self.id)


class Preset(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=32)
    point = models.IntegerField()


class Charge(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    reason = models.TextField()
    submit = models.BooleanField(default=False)
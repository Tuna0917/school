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
        return reverse('student_detail', args=[self.id])

class Room(models.Model):
    row = models.IntegerField()

class Seat(models.Model):
    
    def __str__(self):
        return f"좌석 (id: {self.id})"

#폐기할 예정
class SeatLog(models.Model):
    date = models.DateTimeField(auto_now_add=True) #언제
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING) #누가
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE) #어떤 좌석을
    points = models.IntegerField(validators=[MinValueValidator(0),]) #얼마에

    def __str__(self):
        return f"{self.date.date()}에 {self.student}(이)가 {self.points} 포인트에 입찰함."


class Log(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    log_concept_id = models.IntegerField()
    log_student_id = models.IntegerField()
    point = models.IntegerField()
    reason = models.TextField(blank=True)


class Concept(models.Model):
    concept_id = models.IntegerField(primary_key=True)
    concept_name = models.CharField(max_length = 32)

    def __str__(self) -> str:
        return f'{self.concept_name} (concept_id = {self.concept_id})'
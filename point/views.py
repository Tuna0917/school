from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse,HttpResponseRedirect
from django.urls.base import reverse_lazy
from django.views.generic import *
from .models import *
from django.contrib import auth
from django.contrib.auth.mixins import *
from django.contrib.auth.decorators import permission_required
from django.db.models import F, Sum, Count, Case, When
# Create your views here.
# concept = dict()
# q = Concept.objects.all()
# for conc in q:
#     concept[conc.concept_id] = conc.concept_name

def home(request):
    context = {}
    context['seats'] = Seat.objects.all()
    return render(request, 'home.html', context=context)

# util에 추가
def create_room(request):
    if request.method == 'POST':
        number = int(request.POST['number'])
        room = Room.objects.create(
            row = request.POST['row']
        )
        for i in range(number):
            Seat.objects.create(
                room=room
            )
    return render(request, 'create_room.html')
# util에 추가
def create_students(request):
    if request.method == 'POST':
        n = User.objects.count()
        for i in range(int(request.POST['number'])):

            username = f'student{i+n}'
            user = User.objects.create_user(
                username,
                email = username+'@school.com',
                password='123123',
                first_name = 'None',
                last_name = 'Student'
            )
            student = Student.objects.create(
                    user = user,
                    name = username,
                )
        return redirect('home')
    return render(request, 'create_students.html')

#'str' object has no attribute 'get'라는 메세지가 나온다면 HttpResponse를 생각하기.
def point_change(request, pk):
    if request.method == 'POST':
        point = int(request.POST['point'])
        student = Student.objects.get(id=pk)
        student.point += point
        student.save()
        log = Log.objects.create(
            log_student_id = pk,
            point = point,
            reason = request.POST['reason'],
        )
    return HttpResponseRedirect(student.get_absolute_url())




def auction(request, pk):
    seat = Seat.objects.get(id=pk)
    if request.method == 'POST':
        if int(request.POST['point']):
            if request.user.student:
                student = request.user.student
                student.point -= int(request.POST['point'])
                student.save()
                Log.objects.create(
                    log_concept_id=Concept.objects.filter(concept_name='seat',obj_id=pk),
                    log_student_id=pk, 
                    seat=seat,
                    points=int(request.POST['point'])
                    )

        return redirect('home')
        
    context=dict()
    context['pk']=pk
    context['user']=request.user
    context['student']=request.user.student
    return render(request, 'auction.html', context=context)

class SeatDetailView(DetailView):
    model = Seat
    # http://raccoonyy.github.io/django-annotate-and-aggregate-like-as-excel/
    def get_context_data(self, **kwargs):
        context=  super().get_context_data(**kwargs)
        seat = context['object']
        concept = Concept.objects.get(concept_name__icontains='seat',obj_id=seat.id)
        context['logs'] = Log.objects.filter(log_concept_id=concept.concept_id).all()
        return context


class StudentListView(ListView):
    model = Student

class StudentDetailView(DetailView):
    model = Student

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['logs'] = Log.objects.filter(log_student_id = context['object'].id).all()
        return context


class StudentUpdateView(UpdateView):
    model = Student
    fields = ['name', 'point', 'status', ]

    def get_success_url(self):
        return reverse('student_detail',kwargs={'pk': self.object.id })

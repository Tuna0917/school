from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.urls.base import reverse_lazy
from django.views.generic import *
from .models import *
from django.contrib import auth
from django.contrib.auth.mixins import *
from django.contrib.auth.decorators import permission_required
from django.db.models import F, Sum, Count, Case, When
# Create your views here.

def home(request):
    context = {}
    context['seats'] = Seat.objects.all()
    return render(request, 'home.html', context=context)


# def student_signup(request):
#     if request.method == 'POST':
#         if request.POST['password1'] == request.POST['password2']:
#             try: 
#                 user = User.objects.create_user(
#                     request.POST['username'], 
#                     email=request.POST['email'],
#                     password=request.POST['password1'],
#                     first_name=request.POST['first_name'],
#                     last_name=request.POST['last_name']
#                     )
                
#                 student = Student.objects.create(
#                     user = user,
#                     name = request.POST['last_name'] +' ' + request.POST['first_name'],
#                 )
            
#                 auth.login(request, user)
#                 return redirect('home')
#             except:
#                 return render(request, 'rejectedsignup.html')
#     return render(request, 'signup.html')

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
            



def auction(request, pk):
    seat = Seat.objects.get(id=pk)
    if request.method == 'POST':
        if int(request.POST['point']):
            student = request.user.student
            student.point -= int(request.POST['point'])
            student.save()
            SeatLog.objects.create(student=student, seat=seat,points=int(request.POST['point']))
            return redirect('home')
        else:
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
        q = context['object'].seatlog_set.values('student').order_by('student').annotate(total_point=Sum('points'))
        for x in q:
            x['student'] = Student.objects.get(id=x['student'])
        context['query'] = sorted(q, key=lambda x : -x['total_point'])
        return context


class StudentListView(ListView):
    model = Student

class StudentDetailView(DetailView):
    model = Student


class StudentUpdateView(UpdateView):
    model = Student
    fields = ['name', 'point', 'status', ]

    def get_success_url(self):
        return reverse('student_detail',kwargs={'pk': self.object.id })
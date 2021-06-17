from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse,HttpResponseRedirect
from django.shortcuts import get_object_or_404 # 'model' matching query does not exist.
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
    try:
        room = Room.objects.get(status='a')
        seats = Seat.objects.filter(room=room)

        for_context = []
        for i, seat in enumerate(seats):
            if i%(room.row) == 0:
                for_context.append(False)
            for_context.append(seat)

        context['seats'] = for_context
    except Exception as ex: #여기가 홈화면이 아니게하면 해결됨.
        print(ex)
        pass
    return render(request, 'home.html', context=context)

# util에 추가
def create_room(request):
    if Room.objects.filter(status='a'):
        return redirect('home')
    if request.method == 'POST':
        number = int(request.POST['number'])
        room = Room.objects.create(
            row = request.POST['row']
        )
        for i in range(number):
            seat = Seat.objects.create(
                num= i+1,
                room=room
            )
            concept = Concept.objects.create(
                concept_name='seat',
                obj_id=seat.id
            )
        return redirect('home')
    return render(request, 'create_room.html')

def close_room(request):
    pass

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

        if int(request.POST['point']): #0포인트 방지

            if not request.user.is_staff: #선생님은 안돼요...
                           
                student = request.user.student
                concept_id=Concept.objects.get(concept_name='seat',obj_id=pk).concept_id

                if Log.objects.filter(log_concept_id=concept_id, activated=True):
                    #이미 좌석을 가진게 있음.
                    return redirect('home')

                student.point -= int(request.POST['point'])
                student.save()

                Log.objects.create(
                    log_concept_id=concept_id,
                    log_student_id=student.id, 
                    point=int(request.POST['point']),
                    reason='좌석 예약'
                    )

    return redirect('home')


def cancel(request, pk):
    log = Log.objects.get(id=pk)
    if request.user.is_staff or (request.user.student.id == log.log_student_id): #선생님이거나, log의 주인이랑 요청한 사람이랑 같으면.
        pass
    
    return redirect('home')


class SeatDetailView(DetailView):
    model = Seat
    # http://raccoonyy.github.io/django-annotate-and-aggregate-like-as-excel/
    def get_context_data(self, **kwargs):
        context=  super().get_context_data(**kwargs)
        seat = context['object']
        concept = Concept.objects.get(concept_name__icontains='seat',obj_id=seat.id)
        if self.request.user.is_staff:
            context['logs'] = Log.objects.filter(log_concept_id=concept.concept_id).all()
        else:
            student = self.request.user.student
            
            if Log.objects.filter(log_concept_id=concept.concept_id, log_student_id=student.id,activated=True):
                context['log'] = Log.objects.get(log_concept_id=concept.concept_id, log_student_id=student.id,activated=True)
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
    fields = ['name', 'status', ]

    def get_success_url(self):
        return reverse('student_detail',kwargs={'pk': self.object.id })



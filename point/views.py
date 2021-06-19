from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse,HttpResponseRedirect
from django.shortcuts import get_object_or_404 # 'model' matching query does not exist.
from django.urls.base import reverse_lazy
from django.utils.translation import activate
from django.views.generic import *
from .models import *
from .non_view import *
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

    if Room.objects.all():
        room = list(Room.objects.order_by('-id').all())[0]
        if room.status == 'u':
            seats = SeatResult.objects.filter(room_id=room.id).order_by('seat_num').values()

            for dic in seats:
                dic['student'] = Student.objects.filter(id=dic['student_id']).get()

            for_context = []
            for i, seat in enumerate(seats):
                if i%(room.row) == 0:
                    for_context.append(False)
                for_context.append(seat)

            context['seats'] = for_context
            return render(request, 'extra_home.html', context=context)
        else:
            seats = Seat.objects.filter(room=room)

            for_context = []
            for i, seat in enumerate(seats):
                if i%(room.row) == 0:
                    for_context.append(False)
                for_context.append(seat)

            context['seats'] = for_context

            if request.user.is_active:
                if not request.user.is_staff:
                    student = request.user.student
                    context['my_seat']=find_seat(student)
    else:
        if request.user.is_staff:
            return redirect('create_room')
        


    return render(request, 'home.html', context=context)


# util에 추가
def create_room(request):
    if not request.user.is_staff:
        return redirect('home')
    if not Student.objects.all(): #학생이 없다면.
        return redirect('create_students')

    if Room.objects.filter(status='a'):
        return redirect('home')
    if request.method == 'POST':
        number = Student.objects.count()
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
    if not request.user.is_staff: #선생님이 아니면 안됨
        return redirect('home')
 
    if Room.objects.filter(status='a'): #룸이 열려있어야함.
        room = Room.objects.get(status='a') #이론상 하나밖에 없음.
        seats = Seat.objects.filter(room=room) #그 룸의 좌석들을 가져옴.

        for seat in seats: #좌석마다 
            concept_id  = Concept.objects.get(concept_name='seat',obj_id=seat.id).concept_id #좌석의 concept_id 가져오기
            if Log.objects.filter(log_concept_id=concept_id,log_name='seat',activated=True).order_by('-point', 'created_date').all(): #해당 좌석에 입찰한 애들이 있다면
                for log in Log.objects.filter(log_concept_id=concept_id,log_name='seat',activated=True).order_by('-point', 'created_date').all():
                    student = Student.objects.get(id=log.log_student_id)
                    log.activated = False
                    log.save()
                    if fix_seat(student=student,seat=seat): 
                        #입찰 실패한 나머지들은...
                        student.point += log.point
                        student.save()
                        Log.objects.create(
                        log_concept_id = log.log_concept_id,
                        log_student_id = student.id,
                        log_name='refund', 
                        point = log.point,
                        reason='입찰에 실패함'
                        )
        
        '''
        이제 랜덤배치
        '''

        exclude = list(SeatResult.objects.filter(room_id = room.id).values_list('student_id',flat=True))

        import random
        a = list(Student.objects.exclude(id__in=exclude))
        random.shuffle(a)

        b = list(Seat.objects.filter(room=room,status='a'))

        for STUDENT, SEAT in zip(a,b):
            fix_seat(STUDENT, SEAT)
        
        room.status = 'u'
        room.save()
    return redirect('home')








# util에 추가
def create_students(request):
    if not request.user.is_staff:
        return redirect('home')
    if Room.objects.filter(status='a'): #자리배치시즌페이즈일때는 새로운 학생을 추가할 수 없게.
        return redirect('home')
    if request.method == 'POST':
        n = max(User.objects.count(),1)
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

                if find_seat(student):
                    #이미 좌석을 가진게 있음.
                    return redirect('home')

                student.point -= int(request.POST['point'])
                student.save()

                Log.objects.create(
                    log_concept_id=concept_id,
                    log_student_id=student.id, 
                    log_name='seat',
                    point= int(request.POST['point']),
                    reason=f'{seat.num}번 좌석 예약'
                    )

    return redirect('home')

##################  log_concept_id = -log.log_concept_id, 를 그냥 +로 바꿈
def auction_cancel(request, pk):
    log = Log.objects.get(id=pk)
    if log.log_name != 'seat':
        return redirect('home')
    if request.user.is_staff or (request.user.student.id == log.log_student_id): #선생님이거나, log의 주인이랑 요청한 사람이랑 같으면.
        student = Student.objects.get(id=log.log_student_id)
        student.point += log.point
        student.save()
        log.activated = False
        log.save()
        Log.objects.create(
                    log_concept_id = log.log_concept_id,
                    log_student_id = student.id,
                    log_name='cancel', 
                    point = log.point,
                    reason='취소'
                    )
    return redirect('home')


class SeatDetailView(DetailView):
    model = Seat
    # http://raccoonyy.github.io/django-annotate-and-aggregate-like-as-excel/
    def get_context_data(self, **kwargs):
        context=  super().get_context_data(**kwargs)
        seat = context['object']
        concept = Concept.objects.get(concept_name='seat',obj_id=seat.id)
        if self.request.user.is_staff:
            context['logs'] = Log.objects.filter(log_concept_id=concept.concept_id).order_by('id').all()
        else:
            student = self.request.user.student
            context['seat'] = find_seat(student)
            if Log.objects.filter(log_name='seat', log_student_id=student.id,activated=True):
                context['log'] = Log.objects.get(log_name='seat', log_student_id=student.id,activated=True)
                
        return context

class FinshedSeatDetailView(DetailView):
    model = Seat
    template_name = 'end_seat_detail.html'
    # http://raccoonyy.github.io/django-annotate-and-aggregate-like-as-excel/
    def get_context_data(self, **kwargs):
        context=  super().get_context_data(**kwargs)
        seat = context['object']
        concept = Concept.objects.get(concept_name='seat',obj_id=seat.id)
        context['logs'] = Log.objects.filter(log_concept_id=concept.concept_id).order_by('id').all()
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


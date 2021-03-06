from django.shortcuts import render, redirect, resolve_url
from django.urls import reverse
from django.urls import reverse_lazy
from .models import *
from django.views.generic import *
from django.views.generic import edit
from django.http import HttpResponseRedirect, HttpResponseNotFound
from django.contrib import messages
# Create your views here.


class StudentListView(ListView):
    model = Student
    paginate_by = 8
class StudentDetailView(DetailView):
    model = Student

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['logs'] = Log.objects.filter(log_student = context['object']).order_by('-created_date').all()
        context['charges'] = Charge.objects.filter(student = context['object']).all()
        context['presets'] = Preset.objects.all()
        return context

class StudentUpdateView(UpdateView):
    model = Student
    fields = ['name', ] #학생은 'name'만 보이게 하기

    def get_success_url(self):
        return reverse('student_detail',kwargs={'pk': self.object.id })
    
    def dispatch(self, request, *args, **kwargs):
        # Check permissions for the request.user here
        if request.user.is_staff:
            self.fields = ['name','status']
        return super().dispatch(request, *args, **kwargs)

class ChargeListView(ListView):
    modle = Charge



class RoomListView(ListView):
    model = Room

class RoomDetailView(DetailView): #사실상 SeatListView죠?
    model = Room

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seats'] = []

        for i, seat in enumerate(context['object'].seat_set.all()):
                if i%(context['object'].row) == 0:
                    context['seats'].append(False)
                context['seats'].append(seat)
        room = context['object']
        seats = context['object'].seat_set.all()
        n = (room.row-seats.count()%room.row)
        context['seats'].extend(['empty']*(n if n != room.row else 0))
        return context

    # def get_template_names(self) -> List[str]:
    #     return super().get_template_names()

# class RoomCreateView(CreateView):
#     model = Room
#     fields = ['notice', 'row', 'minimum',]

#     def form_valid(self, form):
#         return super().form_valid(form)

class RoomUpdateView(UpdateView):
    model = Room
    fields = ['notice', 'row', 'minimum',]

class SeatDetailView(DetailView):
    model = Seat

    def get_context_data(self, **kwargs):
        context= super().get_context_data(**kwargs)
        seat = context['object']
        context['logs'] = Log.objects.filter(obj_name='seat', obj_id=seat.id, canceled=False)
        if not self.request.user.is_staff:
            try:
                context['log'] = Log.objects.get(obj_name='seat', obj_id=seat.id,canceled=False, log_student = self.request.user.student)
            except:
                context['log'] = None
        return context


class PresetListView(ListView):
    model = Preset

class PresetDetailView(DetailView):
    model = Preset

class PresetCreateView(CreateView):
    model = Preset
    fields = ['name', 'point']

    def get_success_url(self) -> str:
        return resolve_url('preset_list')

class PresetUpdateView(UpdateView):
    model = Preset
    fields = ['name', 'point']

    def get_success_url(self) -> str:
        return resolve_url('preset_list')

class PresetDeleteView(DeleteView):
    model = Preset

    def get_success_url(self) -> str:
        return resolve_url('preset_list')





def create_room(request):
    if (not Room.objects.filter(status='a'))and request.user.is_staff: #열려있는 교실이 없고 선생님이면.
        if request.method == 'POST':
            room = Room.objects.create(
                row = request.POST['row'],
                minimum = request.POST['minimum']
            )
            
            for i in range(int(request.POST['num'])):
                Seat.objects.create(
                    room = room,
                    num = i+1
                )

            return redirect('room_detail', pk=Room.objects.get(status='a').id)
        return render(request, 'room_create.html')
    return HttpResponseNotFound('<h1>Page not found</h1>')


def create_students(request):
    if not request.user.is_staff:
        return HttpResponseNotFound('<h1>Page not found</h1>')
    if request.method == 'POST':
        context = dict()
        context['passwords'] = []
        n = max(User.objects.count(),1) #1
        import random
        for i in range(int(request.POST['number'])): #구조상 여기서 렉걸림
            #password = int(random.random()*100000000)
            password = 123123
            username = f'student{i+n}'
            user = User.objects.create_user(
                username,
                email = username+'@school.com',
                password=f'{password}',
                first_name = 'Student',
                last_name = 'Student'
            )
            student = Student.objects.create(
                    user = user,
                    name = username,
                )
            context['passwords'].append((student.id, f'{password}'))
        return render(request, 'student_create_complete.html', context=context)
    return render(request, 'student_create.html')


def auction(request, pk):
    seat = Seat.objects.get(id=pk)
    if seat.room.status == 'u':
        return redirect('home')
    if request.method == 'POST':
        student = request.user.student
        #해당 좌석에 이미 입찰한 적이 있는가?
        if not Log.objects.filter(obj_name='seat', obj_id = seat.id, log_student=student, canceled=False):

            post = request.POST
 
            student.point -= int(post['point'])
            student.save()

            log = Log.objects.create(
                status = 'u',
                obj_name = 'seat',
                obj_id = pk,
                log_student = student,
                point = int(post['point']),
                reason = f'{seat.num}번 좌석에 입찰함.'
            )
    return redirect('room_now')

def point_change(request, pk):
    student = Student.objects.get(id=pk)
    if request.user.is_staff and request.method=='POST':
        post = request.POST

        student.point += int(post['point'])
        student.save()

        log = Log.objects.create(
            status = 't',
            obj_name = post.get('name', 'teacher'),
            obj_id = int(post.get('id', '0')),
            point = int(post['point']),
            log_student = student,
            reason = post.get('reason', '')
        )
        messages.success(request, 'Profile details updated.')
        return HttpResponseRedirect(student.get_absolute_url())
    return HttpResponseNotFound('<h1>Page not found</h1>')


def cancel(request, pk):
    log = Log.objects.get(id=pk)
    if request.user.is_staff or request.user.student == log.log_student:
        if log.status == 'u' and (not log.canceled):

            log.canceled = True
            log.save()

            student = log.log_student
            student.point += log.point
            student.save()

            Log.objects.create(
                obj_name='log',
                log_student = student,
                cancel_log = log,
                point = log.point,
            )
    return redirect('room_now')

def close_confirm(request):
    if request.user.is_staff:
        if Room.objects.filter(status='a'):
            room = Room.objects.get(status='a')
        else:
            return HttpResponseNotFound('<h1>열려있는 교실이 없어요</h1>')
        seats = Seat.objects.filter(room = room).values_list('id', flat=True)
        '''
        미달인 학생 - 입찰한 좌석 수. 
        '''
        context = dict()
        context['object_list'] = [(student, Log.objects.filter(obj_name='seat',obj_id__in=seats,log_student=student, canceled=False).count())  for student in Student.objects.all()]
        context['room'] = room
        return render(request, 'close_confirm.html', context=context)
    return HttpResponseNotFound('<h1>Page not found</h1>')

        


def close_room(request):
    if not request.user.is_staff:
        return HttpResponseNotFound('<h1>Page not found</h1>')
    room = Room.objects.get(status='a')
    seats = Seat.objects.filter(room = room).values_list('id', flat=True)
    logs = Log.objects.filter(obj_name='seat',obj_id__in=seats, canceled=False).order_by('-point', 'created_date')
    has = []
    for log in logs:
        seat = Seat.objects.get(id= log.obj_id)
        student = log.log_student
        if seat.status == 'u' or (seat in student.seat_set.all()):
            log.canceled = True
            log.save()

            student.point += log.point
            student.save()

            Log.objects.create(
                obj_name='log',
                log_student = student,
                cancel_log = log,
                point = log.point,
            )
        else:
            seat.status = 'u'
            seat.owner = student
            seat.save()
            has.append(student)

    import random
    students = list(Student.objects.filter(status='a').all())
    seats = list(Seat.objects.filter(room = room, status='a', owner__isnull=True))
    random.shuffle(seats)

    for seat in seats:
        if students:
            while seat.status == 'a':
                if students:
                    std = students.pop()
                else:
                    break
                if std in has:
                    continue
                seat.status = 'u'
                seat.owner = std
                seat.save()
        else:
            break
    room.status = 'u'
    room.save()
    return room_now(request)
        

def room_now(request):
    if Room.objects.count():
        context = dict()
        context['object']= Room.objects.order_by('-created_date').first()
        context['seats'] = []

        for i, seat in enumerate(context['object'].seat_set.all()):
                if i%(context['object'].row) == 0:
                    context['seats'].append(False)
                context['seats'].append(seat)
        room = context['object']
        seats = context['object'].seat_set.all()
        n = (room.row-seats.count()%room.row)
        context['seats'].extend(['empty']*(n if n != room.row else 0))
        
        return render(request,'point/room_detail.html',context=context)
    else:
        if request.user.is_staff:
            return redirect('create_room')
        else:
            return HttpResponseNotFound('<h1>Page not found</h1>')
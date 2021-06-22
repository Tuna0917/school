from django.shortcuts import render, redirect
from django.urls import reverse
from .models import *
from django.views.generic import *
from django.http import HttpResponseRedirect
# Create your views here.
password = 123123


class StudentListView(ListView):
    model = Student

class StudentDetailView(DetailView):
    model = Student

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['logs'] = Log.objects.filter(log_student = context['object']).all()
        context['charges'] = Charge.objects.filter(student = context['object']).all()
        context['presets'] = Preset.objects.all()
        return context

class StudentUpdateView(UpdateView):
    model = Student
    fields = ['name', 'status', ] #학생은 'name'만 보이게 하기

    def get_success_url(self):
        return reverse('school:student_detail',kwargs={'pk': self.object.id })

class ChargeListView(ListView):
    modle = Charge



class RoomListView(ListView):
    model = Room

class RoomDetailView(DetailView): #사실상 SeatListView죠?
    model = Room

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seats'] = context['object'].seat_set.all()
        return context

    # def get_template_names(self) -> List[str]:
    #     return super().get_template_names()

class RoomCreateView(CreateView):
    model = Room
    fields = ['notice', 'row', 'minimum',]

    def form_valid(self, form):
        return super().form_valid(form)

class RoomUpdateView(UpdateView):
    model = Room
    fields = ['notice', 'row', 'minimum',] #status는 건들이면 안됨. 정식으로 close를 해야함.

class SeatDetailView(DetailView):
    model = Seat



class PresetListView(ListView):
    model = Preset

class PresetCreateView(CreateView):
    model = Preset
    fields = ['name', 'point']

class PresetUpdateView(UpdateView):
    model = Preset
    fields = ['name', 'point']

class PresetDeleteView(DeleteView):
    model = Preset
    success_url = reverse('home')



def home(request):
    return render(request,'home.html')

def create_room(request):
    if not Room.objects.filter(status='a'):
        
        if request.user.is_staff:
            pass

    return redirect('room_detail', pk=Room.objects.get(status='a').id)

def close_room(request, pk):
    room = Room.objects.get(id=pk)

def create_students(request):
    if not request.user.is_staff:
        return redirect('home')
    if Room.objects.filter(status='a'): #자리배치시즌페이즈일때는 새로운 학생을 추가할 수 없게.
        return redirect('home')
    if request.method == 'POST':
        n = max(User.objects.count(),1) #1
        for i in range(int(request.POST['number'])):

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
        return redirect('home')

def auction(request, pk):
    seat = Seat.objects.get(id=pk)

    if request.method == 'POST':
        
        #room의 조건을 위배했는가?
        
        
        post = request.POST



        student = request.user.student
        student.point -= post['point']
        student.save()

        log = Log.objects.create(
            status = 'u',
            obj_name = 'seat',
            obj_id = pk,
            point = post['point'],
        )

def point_change(request, pk):
    student = Student.objects.get(id=pk)
    if request.user.is_staff and request.method=='POST':
        post = request.POST

        student.point += post['point']
        student.save()

        log = Log.objects.create(
            status = 't',
            obj_name = post.get('name', 'teacher'),
            obj_id = int(post.get('id', '0')),
            log_student = student,
            reason = post.get('reason', '')
        )

    return HttpResponseRedirect(student.get_absolute_url())


def cancel(request, pk):
    log = Log.object.get(id=pk)
    if request.user.is_staff or request.user.student == log.log_student:
        if log.status == 'u':

            log.status = 'c'
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
    "{% url 'cancle' log.uuid %}?next={{ request.path }}"


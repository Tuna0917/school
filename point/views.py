from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.urls.base import reverse_lazy
from django.views.generic import *
from .models import *
from django.contrib import auth
# Create your views here.

def home(request):
    context = {}
    context['seats'] = Seat.objects.all()
    return render(request, 'home.html', context=context)


def student_signup(request):
    if request.method == 'POST':
        if request.POST['password1'] == request.POST['password2']:
            try: 
                user = User.objects.create_user(
                    request.POST['username'], 
                    email=request.POST['email'],
                    password=request.POST['password1'],
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name']
                    )
                
                student = Student.objects.create(
                    user = user,
                    name = request.POST['last_name'] +' ' + request.POST['first_name'],
                )
            
                auth.login(request, user)
                return redirect('home')
            except:
                return render(request, 'rejectedsignup.html')
    return render(request, 'signup.html')


def auction(request, pk):
    print(request)
    print(pk)
    print(request.user)
    return redirect('home')

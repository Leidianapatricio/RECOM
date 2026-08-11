from django.shortcuts import render


def home(request):
    return render(request, 'home.html')


def login_view(request):
    return render(request, 'login.html')


def dashboard_admin(request):
    return render(request, 'dashboard_admin.html')


def dashboard_cidadao(request):
    return render(request, 'dashboard_cidadao.html')


def dashboard_profissional(request):
    return render(request, 'dashboard_profissional.html')
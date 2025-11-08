from django.http import HttpResponse

def home(request):
    return HttpResponse("CS 4750 Project")

"""app URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import include, path
from . import views
# from rest_framework import routers

# router = routers.DefaultRouter()
# router.register(r'users', views.UserViewSet)


urlpatterns = [
    path('', views.IndexView, name='index'),
    path('media/', views.media_view),
    path('datetime/',views.current_datetime),
    path('dashboard/',views.dashboard_view),
    path('dashboard/',views.export_picturae,name="export_picturae"),
    path('odk/',views.odk_list),
    path('odk/',views.import_odk,name="import_odk"),
    path('mass-digi/',views.list_picturae),
    path('mass-digi/',views.import_picturae,name="import_mass_digi")
    # path('airflow'),
    
    # path('', include(router.urls)),
    # path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]

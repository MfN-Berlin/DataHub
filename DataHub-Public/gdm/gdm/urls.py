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
from email.mime import base
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from rest_framework import serializers, viewsets, routers
from datahub import api_views
from rest_framework.schemas import get_schema_view
from rest_framework import renderers
from django.views.generic import TemplateView, RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage

# Automatically determining the API URL conf by Routers.
router = routers.DefaultRouter()
router.register(r'dataset', api_views.DatasetViewset)
router.register(r'report', api_views.ReportViewset)
router.register(r'origin', api_views.OriginViewset)
router.register(r'user', api_views.UserViewset)
# router.register(r'odkimport', api_views.ODKImportView, basename='dataset')
# router.register(r'sambaexport', api_views.SambaExportView, basename='datahub')

# common web URLs
urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('img/favicon.ico'))),
    path('admin/', admin.site.urls),
    path('', include('datahub.urls')),    
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# common API URLs
urlpatterns += [
    path('api/', include(router.urls)),
    path('api/odkimport/<str:params>/', api_views.ODKImportView.as_view()),
    path('api/sambaexport/<str:id>/', api_views.SambaExportView.as_view()),
    path('api/easydbexport/<str:id>/', api_views.EasydbExportView.as_view()),
    path('api/picturaeexport/<str:id>/', api_views.PicturaeExportView.as_view()),

    # path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('docs/', TemplateView.as_view(
        template_name='swagger-ui.html',
        extra_context={'schema_url':'openapi-schema-yaml'}
    ), name='swagger-ui'),
    path('openapi.yaml', get_schema_view(
            title="Best API Service",
            renderer_classes=[renderers.OpenAPIRenderer]
        ), name='openapi-schema-yaml'),
    path('openapi.json', get_schema_view(
            title="Best API Service",
            renderer_classes = [renderers.JSONOpenAPIRenderer], 
        ), name='openapi-schema-json'),
]
